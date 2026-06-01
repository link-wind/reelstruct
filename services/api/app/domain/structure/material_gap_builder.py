from typing import Optional

from app import material_rag_service
from app.domain.shared.domain_models import (
    MaterialGap,
    MaterialGraphSearchResult,
    MaterialRetrievalCandidate,
    MaterialSupplementOption,
    NewContentInput,
    SlotFillDecision,
    SlotQueryProfile,
    SlotRetrievalPlan,
    StructureSlot,
    TemplateStructure,
)
from app.material_graph_service import build_material_graph, search_material_graph_for_slot
from app.material_rerank_service import rerank_material_graph_results
from app.slot_profile_service import build_slot_query_profile
from app.structure_coverage_service import score_structure_slot_coverage
from app.timeline_patch_service import build_timeline_patch


def detect_material_gaps(
    template: TemplateStructure,
    content: NewContentInput,
) -> list[MaterialGap]:
    assets = {asset.strip() for asset in content.available_assets if asset.strip()}
    gaps: list[MaterialGap] = []
    material_graph = build_material_graph(content.uploaded_assets)

    for slot in template.script_pattern:
        if slot.required_asset in assets:
            continue
        profile = build_slot_query_profile(slot, content)
        graph_results = rerank_material_graph_results(
            profile,
            search_material_graph_for_slot(material_graph, profile),
        )
        candidates = material_rag_service.retrieve_material_candidates_for_slot(slot, content)
        gaps.append(
            build_material_gap(
                slot,
                candidates,
                content=content,
                slot_query_profile=profile,
                graph_search_results=graph_results,
            )
        )
    return gaps


def build_material_gap(
    slot: StructureSlot,
    candidates: list[MaterialRetrievalCandidate],
    *,
    content: Optional[NewContentInput] = None,
    slot_query_profile: Optional[SlotQueryProfile] = None,
    graph_search_results: Optional[list[MaterialGraphSearchResult]] = None,
) -> MaterialGap:
    effective_content = content or NewContentInput(topic="")
    profile = slot_query_profile or build_slot_query_profile(slot, effective_content)
    graph_results = graph_search_results or []
    coverage_result = score_structure_slot_coverage(profile, graph_results)
    best = candidates[0] if candidates else None
    retrieval_status = _retrieval_status(best.match_score if best else 0)
    base_strategy = _fill_strategy_for_slot(slot.id)
    fill_strategy = base_strategy
    retrieval_reason = "素材库没有检索到可支撑该槽位的候选素材。"
    if best and retrieval_status == "可复用":
        fill_strategy = f"RAG 检索建议复用 {best.filename or best.asset_id}：{best.reuse_strategy}"
        retrieval_reason = best.match_reason
    elif best and retrieval_status == "可包装后使用":
        fill_strategy = f"RAG 检索到可包装补位素材 {best.filename or best.asset_id}，建议结合{base_strategy}"
        retrieval_reason = best.match_reason
    supplement_options = _material_supplement_options(slot, candidates, base_strategy)
    retrieval_plan = build_slot_retrieval_plan(slot, candidates, supplement_options)
    slot_fill_decision = build_slot_fill_decision(slot, candidates, supplement_options, graph_results)
    uses_graph_decision = bool(graph_results and slot_fill_decision.selected_asset_id and slot_fill_decision.evidence_path)
    if uses_graph_decision:
        fill_strategy = slot_fill_decision.actions[0] if slot_fill_decision.actions else fill_strategy
        retrieval_reason = slot_fill_decision.why or retrieval_reason
        retrieval_status = "可复用" if slot_fill_decision.decision_type == "reuse_direct" else "可包装后使用"
    timeline_patch = build_timeline_patch(slot, slot_fill_decision)
    if slot_fill_decision.timeline_patch_id != timeline_patch.patch_id:
        slot_fill_decision = slot_fill_decision.model_copy(update={"timeline_patch_id": timeline_patch.patch_id})

    return MaterialGap(
        slot_id=slot.id,
        missing_asset=slot.required_asset,
        impact=f"{slot.label} 缺少直接画面支撑，表达会变弱。",
        fill_strategy=fill_strategy,
        suggested_asset_type=_suggested_asset_type_for_slot(slot.id),
        suggested_shots=_suggested_shots_for_slot(slot.id),
        pickup_checklist=_pickup_checklist_for_slot(slot.id),
        retrieval_status=retrieval_status,
        candidates=candidates,
        retrieval_reason=retrieval_reason,
        primary_supplement=slot_fill_decision.actions[0]
        if uses_graph_decision and slot_fill_decision.actions
        else supplement_options[0].action
        if supplement_options
        else fill_strategy,
        supplement_options=supplement_options,
        retrieval_plan=retrieval_plan,
        slot_fill_decision=slot_fill_decision,
        slot_query_profile=profile,
        coverage_result=coverage_result,
        graph_search_results=graph_results,
        timeline_patches=[timeline_patch],
    )


def build_slot_retrieval_plan(
    slot: StructureSlot,
    candidates: list[MaterialRetrievalCandidate],
    supplement_options: list[MaterialSupplementOption],
) -> SlotRetrievalPlan:
    best = candidates[0] if candidates else None
    recommended = supplement_options[0] if supplement_options else None
    candidate_id = ""
    candidate_label = ""
    evidence: list[str] = []
    confidence = 0.2
    if best is not None:
        candidate_id = f"{best.asset_id}::{best.chunk_id}" if best.chunk_id else best.asset_id
        candidate_label = best.filename or best.asset_id
        evidence = best.evidence[:4] or [best.match_reason]
        confidence = min(0.95, max(0.35, best.match_score / 100))
    return SlotRetrievalPlan(
        slot_id=slot.id,
        slot_label=slot.label,
        required_asset=slot.required_asset,
        required_expression=_slot_required_expression(slot),
        query_summary=_slot_query_summary(slot),
        best_candidate_id=candidate_id,
        best_candidate_label=candidate_label,
        matched_evidence=evidence,
        missing_evidence=_slot_missing_evidence(slot, best),
        recommended_method=recommended.method if recommended else "补拍/AIGC",
        generation_action=recommended.action if recommended else f"补拍一段能直接支撑“{slot.required_asset}”的镜头。",
        confidence=round(confidence, 2),
    )


def build_slot_fill_decision(
    slot: StructureSlot,
    candidates: list[MaterialRetrievalCandidate],
    supplement_options: list[MaterialSupplementOption],
    graph_search_results: Optional[list[MaterialGraphSearchResult]] = None,
) -> SlotFillDecision:
    graph_best = graph_search_results[0] if graph_search_results else None
    if graph_best is not None and graph_best.confidence >= 0.45:
        action = f"裁切 {graph_best.asset_id} 的 {graph_best.start}s-{graph_best.end}s 放入“{slot.label}”段。"
        if graph_best.score_breakdown.get("packaging", 0) > 0:
            action = f"{action} 保留或叠加其包装信息。"
        decision_type = "reuse_direct" if graph_best.confidence >= 0.82 and not graph_best.missing else "reuse_with_packaging"
        return SlotFillDecision(
            slot_id=slot.id,
            decision_type=decision_type,
            selected_asset_id=graph_best.asset_id,
            selected_chunk_id=graph_best.chunk_id,
            start=graph_best.start,
            end=graph_best.end,
            confidence=graph_best.confidence,
            why="；".join(graph_best.evidence_path[:3]),
            missing=graph_best.missing,
            actions=[action],
            timeline_hint=f"放在“{slot.label}”段，优先使用 {graph_best.start}s-{graph_best.end}s。",
            evidence_path=graph_best.evidence_path,
            timeline_patch_id=f"patch_{slot.id}_1",
        )

    best = candidates[0] if candidates else None
    recommended = supplement_options[0] if supplement_options else None
    if best is None:
        action = recommended.action if recommended else f"用字幕补足“{slot.required_asset}”的信息表达。"
        return SlotFillDecision(
            slot_id=slot.id,
            decision_type="caption_only" if recommended and recommended.method == "文案/字幕补全" else "shoot_or_aigc",
            confidence=0.2,
            why=f"素材库没有可直接支撑“{slot.required_asset}”的候选素材。",
            missing=[f"缺少“{slot.required_asset}”", "缺少可追溯的素材证据"],
            actions=[action],
            timeline_hint=f"在“{slot.label}”段使用字幕或补拍素材占位。",
        )
    action = recommended.action if recommended else best.reuse_strategy
    decision_type = "reuse_direct" if best.match_score >= 82 else "reuse_with_packaging"
    return SlotFillDecision(
        slot_id=slot.id,
        decision_type=decision_type,
        selected_asset_id=best.asset_id,
        selected_chunk_id=best.chunk_id,
        start=best.start,
        end=best.end,
        confidence=round(min(0.95, max(0.35, best.match_score / 100)), 2),
        why=best.match_reason,
        missing=_slot_missing_evidence(slot, best),
        actions=[action],
        timeline_hint=_slot_timeline_hint(slot, best),
    )


def _fill_strategy_for_slot(slot_id: str) -> str:
    strategies = {
        "hook": "使用标题卡片 + 快速字幕补足开头吸引力",
        "selling_points": "使用卖点卡片 + 局部放大补足商品特写",
        "usage": "使用字幕说明 + 通用场景素材补足使用过程",
        "cta": "使用结尾标题卡片 + 行动号召字幕补足 CTA",
    }
    return strategies.get(slot_id, "使用字幕和包装元素补足表达")


def _retrieval_status(score: int) -> str:
    if score >= 80:
        return "可复用"
    if score >= 55:
        return "可包装后使用"
    return "缺失"


def _material_supplement_options(
    slot: StructureSlot,
    candidates: list[MaterialRetrievalCandidate],
    base_strategy: str,
) -> list[MaterialSupplementOption]:
    options: list[MaterialSupplementOption] = []
    best = candidates[0] if candidates else None
    if best is not None:
        source = best.filename or best.asset_id
        time_range = f"{best.start}s-{best.end}s" if best.chunk_id and best.end > best.start else "整段素材"
        options.append(
            MaterialSupplementOption(
                method="现有素材复用",
                title=f"复用 {source}",
                action=f"裁切 {source} 的 {time_range}，作为“{slot.label}”画面基础，再按目标节奏微调。",
                evidence=best.evidence[:4] or [best.match_reason],
                priority=1,
            )
        )
        if best.match_score < 80:
            options.append(
                MaterialSupplementOption(
                    method="包装补全",
                    title="用包装强化候选素材",
                    action=f"候选素材只能部分支撑“{slot.label}”，叠加标题条、卖点贴纸或转场卡补足“{slot.required_asset}”。",
                    evidence=[best.match_reason],
                    priority=2,
                )
            )
    options.extend(_fallback_supplement_options(slot, base_strategy, start_priority=len(options) + 1))
    return options[:4]


def _fallback_supplement_options(
    slot: StructureSlot,
    base_strategy: str,
    *,
    start_priority: int = 1,
) -> list[MaterialSupplementOption]:
    slot_copy = {
        "hook": {
            "caption": "把开头核心利益点压成 1 句强标题，先用文字完成停留理由。",
            "packaging": "用封面式标题卡、关键词贴纸和快切转场补出开头吸引力。",
            "reorder": "把已有最强画面提前到开头，后续段落再展开细节。",
            "shoot": "补拍 1 个 2-3 秒结果画面或人物反应镜头。",
        },
        "selling_points": {
            "caption": "把卖点拆成 2-3 条短字幕，一条字幕只讲一个利益点。",
            "packaging": "用卖点卡片、局部放大框和箭头贴纸替代缺失的商品特写。",
            "reorder": "缩短卖点段，把证明压力转移给使用过程或 CTA 优惠信息。",
            "shoot": "补拍 1-2 个产品细节、质地或包装近景。",
        },
        "usage": {
            "caption": "用步骤字幕解释使用过程，弱化对连续实拍动作的依赖。",
            "packaging": "用步骤编号卡、手势提示贴纸和前后对比标题补足过程感。",
            "reorder": "把使用段压缩为说明卡，让卖点段承担主要说服。",
            "shoot": "补拍一段 3-5 秒手部动作或真实场景使用镜头。",
        },
        "cta": {
            "caption": "用结尾字幕明确下一步行动、优惠或入口信息。",
            "packaging": "用账号导流卡、门店信息条或优惠贴纸完成收束。",
            "reorder": "把 CTA 合并到最后一个卖点画面，减少独立结尾镜头需求。",
            "shoot": "补拍 1 个停留 1-2 秒的门店、二维码或购买入口画面。",
        },
    }.get(
        slot.id,
        {
            "caption": f"用字幕直接补足“{slot.required_asset}”的信息表达。",
            "packaging": base_strategy,
            "reorder": "调整段落顺序，降低当前缺失画面的表达权重。",
            "shoot": f"补拍一段能直接支撑“{slot.required_asset}”的镜头。",
        },
    )
    return [
        MaterialSupplementOption(
            method="文案/字幕补全",
            title="字幕替代画面信息",
            action=slot_copy["caption"],
            evidence=[slot.required_asset, slot.purpose],
            priority=start_priority,
        ),
        MaterialSupplementOption(
            method="包装补全",
            title="包装元素补表达",
            action=slot_copy["packaging"],
            evidence=[base_strategy],
            priority=start_priority + 1,
        ),
        MaterialSupplementOption(
            method="结构重排",
            title="降低缺口依赖",
            action=slot_copy["reorder"],
            evidence=[slot.transferable_rule or slot.method or slot.sample_evidence],
            priority=start_priority + 2,
        ),
        MaterialSupplementOption(
            method="补拍/AIGC",
            title="补一条最低成本素材",
            action=slot_copy["shoot"],
            evidence=_pickup_checklist_for_slot(slot.id)[:2],
            priority=start_priority + 3,
        ),
    ]


def _slot_timeline_hint(slot: StructureSlot, candidate: MaterialRetrievalCandidate) -> str:
    if candidate.chunk_id and candidate.end > candidate.start:
        return f"放在“{slot.label}”段，优先使用 {candidate.start}s-{candidate.end}s。"
    return f"放在“{slot.label}”段，按 {round(slot.duration, 1)} 秒节奏重新裁切。"


def _slot_required_expression(slot: StructureSlot) -> str:
    parts = _dedupe([slot.purpose, slot.intent, slot.method, slot.transferable_rule])
    return "；".join(parts[:3]) or f"完成“{slot.label}”段落表达。"


def _slot_query_summary(slot: StructureSlot) -> str:
    parts = _dedupe([slot.label, slot.required_asset, slot.role, slot.packaging_intent])
    return " / ".join(parts[:4])


def _slot_missing_evidence(
    slot: StructureSlot,
    best: Optional[MaterialRetrievalCandidate],
) -> list[str]:
    if best is None:
        return [f"缺少可直接支撑“{slot.required_asset}”的素材节点", "没有可追溯的 OCR、ASR 或视觉摘要命中"]
    missing: list[str] = []
    modalities = set(best.matched_modalities)
    if "visual" not in modalities:
        missing.append("缺少明确视觉摘要支撑")
    if "ocr" not in modalities and "asr" not in modalities:
        missing.append("缺少文字或语音卖点证据")
    if best.match_score < 80:
        missing.append("候选素材只能部分支撑，需要包装或字幕补足")
    return missing


def _suggested_asset_type_for_slot(slot_id: str) -> str:
    asset_types = {
        "hook": "情绪开场镜头",
        "selling_points": "商品卖点特写",
        "usage": "使用场景过程镜头",
        "cta": "结尾行动号召镜头",
    }
    return asset_types.get(slot_id, "补位素材镜头")


def _suggested_shots_for_slot(slot_id: str) -> list[str]:
    shot_map = {
        "hook": [
            "3 秒内完成结果或福利信息出场",
            "手持推进或快切镜头强化注意力",
            "人物表情 / 商品亮点做第一落点",
        ],
        "selling_points": [
            "产品特写交代核心卖点",
            "局部细节镜头补充质感或功能点",
            "一镜一卖点，避免多个信息挤在同一画面",
        ],
        "usage": [
            "真实场景里拍一段连续使用过程",
            "补一个手部动作或前后对比镜头",
            "环境音或字幕能直接说明使用语境",
        ],
        "cta": [
            "结尾停留 1-2 秒给行动信息",
            "门店位置 / 购买入口 / 优惠信息单独给镜头",
            "人物口播或字幕明确下一步动作",
        ],
    }
    return shot_map.get(slot_id, ["补一段能直接支撑当前文案的镜头"])


def _pickup_checklist_for_slot(slot_id: str) -> list[str]:
    checklist_map = {
        "hook": [
            "主信息是否在前 3 秒出现",
            "画面主体是否足够大",
            "字幕是否能脱离声音单独成立",
        ],
        "selling_points": [
            "每个卖点是否对应单独镜头",
            "产品特写是否清楚交代细节",
            "字幕和镜头是否在讲同一个卖点",
        ],
        "usage": [
            "过程镜头是否完整且连贯",
            "是否能看出真实使用场景",
            "字幕是否补足了动作含义",
        ],
        "cta": [
            "字幕里是否有明确行动词",
            "优惠或入口信息是否单独出现",
            "结尾停留时间是否足够读完",
        ],
    }
    return checklist_map.get(slot_id, ["确认这段镜头能直接支撑当前结构段"])


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped
