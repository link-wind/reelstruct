from typing import Optional

from app.models import (
    CompositionSpec,
    CompositionTrack,
    MaterialGap,
    MaterialRequestTask,
    NewContentInput,
    SampleAnalysisBeat,
    SampleAnalysisMetric,
    SampleAnalysisSummary,
    SampleVideoInput,
    StructurePreviewResponse,
    StructureSlot,
    TemplateStructure,
    TransferMapping,
    TransferMappingOverride,
    TransferPlan,
)


def build_structure_preview(
    sample: SampleVideoInput,
    content: NewContentInput,
    template_override: Optional[TemplateStructure] = None,
    mapping_overrides: Optional[list[TransferMappingOverride]] = None,
    material_request_sheet: Optional[list[MaterialRequestTask]] = None,
    variant: str = "standard",
) -> StructurePreviewResponse:
    template = template_override.model_copy(deep=True) if template_override is not None else extract_template_structure(sample)
    template = apply_variant_to_template(template, variant)
    template = apply_slot_level_overrides(template, mapping_overrides)
    effective_content = apply_delivered_material_tasks_to_content(template, content, material_request_sheet)
    gaps = detect_material_gaps(template, effective_content)
    transfer_plan = build_transfer_plan(
        template,
        effective_content,
        gaps,
        variant=variant,
        mapping_overrides=mapping_overrides,
        material_request_sheet=material_request_sheet,
    )
    composition = build_composition_spec(template, transfer_plan)
    return StructurePreviewResponse(
        template=template,
        transfer_plan=transfer_plan,
        composition=composition,
    )


def extract_template_structure(sample: SampleVideoInput) -> TemplateStructure:
    duration = max(sample.duration, 12)
    hook_duration = min(3, duration * 0.15)
    cta_duration = min(4, duration * 0.16)
    middle_duration = max(duration - hook_duration - cta_duration, 6)
    selling_duration = round(middle_duration * 0.58, 1)
    usage_duration = round(middle_duration - selling_duration, 1)
    transcript_beats = split_transcript_beats(sample.transcript_summary)

    slots = [
        StructureSlot(
            id="hook",
            label="Hook",
            start=0,
            duration=round(hook_duration, 1),
            purpose="开头制造注意力，快速给出痛点或结果承诺。",
            required_asset="开头吸引镜头",
            sample_evidence=transcript_beats["hook"] or f"{sample.title} 在开头约 {round(hook_duration, 1)} 秒建立注意力。",
        ),
        StructureSlot(
            id="selling_points",
            label="卖点展开",
            start=round(hook_duration, 1),
            duration=selling_duration,
            purpose="连续推进核心卖点，保持信息密度。",
            required_asset="商品特写镜头",
            sample_evidence=f"样例中段通过 {sample.shot_count} 个镜头维持节奏。",
        ),
        StructureSlot(
            id="usage",
            label="使用过程",
            start=round(hook_duration + selling_duration, 1),
            duration=usage_duration,
            purpose="展示真实使用语境，降低理解成本。",
            required_asset="使用过程镜头",
            sample_evidence=transcript_beats["usage"] or sample.transcript_summary or "样例在中后段补充场景说明。",
        ),
        StructureSlot(
            id="cta",
            label="CTA",
            start=round(duration - cta_duration, 1),
            duration=round(cta_duration, 1),
            purpose="收束行动号召，强化记忆点。",
            required_asset="结尾 CTA 镜头",
            sample_evidence=transcript_beats["cta"] or "样例结尾保留明确收束段落。",
        ),
    ]

    return TemplateStructure(
        title=f"{sample.title} 的可迁移结构",
        script_pattern=slots,
        rhythm_summary=f"约 {sample.shot_count} 个镜头 / {round(duration, 1)} 秒，开头快、中段密集、结尾收束。",
        packaging_notes=build_packaging_notes(sample.transcript_summary),
        analysis_summary=build_analysis_summary(sample, slots),
    )


def detect_material_gaps(
    template: TemplateStructure,
    content: NewContentInput,
) -> list[MaterialGap]:
    assets = {asset.strip() for asset in content.available_assets if asset.strip()}
    gaps: list[MaterialGap] = []

    for slot in template.script_pattern:
        if slot.required_asset in assets:
            continue
        gaps.append(
            MaterialGap(
                slot_id=slot.id,
                missing_asset=slot.required_asset,
                impact=f"{slot.label} 缺少直接画面支撑，表达会变弱。",
                fill_strategy=_fill_strategy_for_slot(slot.id),
                suggested_asset_type=_suggested_asset_type_for_slot(slot.id),
                suggested_shots=_suggested_shots_for_slot(slot.id),
                pickup_checklist=_pickup_checklist_for_slot(slot.id),
            )
        )
    return gaps


def apply_delivered_material_tasks_to_content(
    template: TemplateStructure,
    content: NewContentInput,
    request_sheet: Optional[list[MaterialRequestTask]] = None,
) -> NewContentInput:
    if not request_sheet:
        return content

    delivered_slot_ids = {
        item.slot_id
        for item in request_sheet
        if item.status in {"已拍", "已交付"}
    }
    if not delivered_slot_ids:
        return content

    delivered_assets = [
        slot.required_asset
        for slot in template.script_pattern
        if slot.id in delivered_slot_ids
    ]
    return content.model_copy(
        update={
            "available_assets": _dedupe([*content.available_assets, *delivered_assets]),
        }
    )


def build_transfer_plan(
    template: TemplateStructure,
    content: NewContentInput,
    gaps: list[MaterialGap],
    variant: str = "standard",
    mapping_overrides: Optional[list[TransferMappingOverride]] = None,
    material_request_sheet: Optional[list[MaterialRequestTask]] = None,
) -> TransferPlan:
    gap_lookup = {gap.slot_id: gap for gap in gaps}
    override_lookup = {item.slot_id: item for item in (mapping_overrides or [])}
    mappings = []

    for slot in template.script_pattern:
        override = override_lookup.get(slot.id)
        target_message = (
            override.target_message.strip()
            if override and override.target_message.strip()
            else _target_message_for_slot(slot.id, content, variant)
        )
        asset_strategy = build_asset_strategy(slot, gap_lookup.get(slot.id), override)
        mappings.append(
            TransferMapping(
                slot_id=slot.id,
                source_label=slot.label,
                target_message=target_message,
                asset_strategy=asset_strategy,
            )
        )

    title = content.product_name or content.topic
    variant_label = _variant_label(variant)
    return TransferPlan(
        title=f"{title} {variant_label}结构迁移方案",
        target_topic=content.topic,
        variant=variant,
        mappings=mappings,
        gaps=gaps,
        material_request_sheet=build_material_request_sheet(template, material_request_sheet),
    )


def build_material_request_sheet(
    template: TemplateStructure,
    request_sheet: Optional[list[MaterialRequestTask]] = None,
) -> list[MaterialRequestTask]:
    if not request_sheet:
        return []

    request_lookup = {item.slot_id: item for item in request_sheet}
    return [
        MaterialRequestTask(slot_id=slot.id, status=request_lookup[slot.id].status)
        for slot in template.script_pattern
        if slot.id in request_lookup
    ]


def build_composition_spec(
    template: TemplateStructure,
    transfer_plan: TransferPlan,
) -> CompositionSpec:
    mapping_lookup = {mapping.slot_id: mapping for mapping in transfer_plan.mappings}
    tracks: list[CompositionTrack] = []

    for slot in template.script_pattern:
        mapping = mapping_lookup[slot.id]
        tracks.append(
            CompositionTrack(
                type="video",
                start=slot.start,
                duration=slot.duration,
                source=" ".join(
                    [
                        slot.label,
                        slot.required_asset,
                        slot.purpose,
                        mapping.target_message,
                        transfer_plan.target_topic,
                    ]
                ),
                slot_id=slot.id,
            )
        )
        tracks.append(
            CompositionTrack(
                type="caption",
                start=slot.start + min(0.5, slot.duration / 3),
                duration=max(slot.duration - 0.5, 1),
                text=mapping.target_message,
                slot_id=slot.id,
            )
        )
        if "卡片" in mapping.asset_strategy:
            tracks.append(
                CompositionTrack(
                    type="card",
                    start=slot.start + 0.8,
                    duration=max(slot.duration - 1, 1),
                    text=mapping.asset_strategy,
                    slot_id=slot.id,
                )
            )

    total_duration = max(slot.start + slot.duration for slot in template.script_pattern)
    return CompositionSpec(duration=round(total_duration, 1), tracks=tracks)


def _target_message_for_slot(slot_id: str, content: NewContentInput, variant: str = "standard") -> str:
    product = content.product_name or content.topic
    first_point = content.selling_points[0] if content.selling_points else "核心卖点"
    second_point = content.selling_points[1] if len(content.selling_points) > 1 else first_point

    if variant == "high_click":
        if slot_id == "hook":
            return f"前 2 秒抛出反差问题：为什么 {product} 会让人停下来"
        if slot_id == "selling_points":
            return f"先给最强利益点 {first_point}，再用 {second_point} 放大好奇心"
        if slot_id == "usage":
            return f"用一个真实瞬间证明 {product} 不是普通选择"
        return f"用一句强 CTA 收束：现在就记住 {product}"
    if variant == "high_conversion":
        if slot_id == "hook":
            return f"先明确 {product} 解决的具体需求"
        if slot_id == "selling_points":
            return f"把 {first_point} 和 {second_point} 转成可感知的购买理由"
        if slot_id == "usage":
            return f"展示 {product} 的使用场景，并补足信任细节"
        return f"给出行动理由，引导用户立即完成咨询、到店或下单"
    if variant == "fast_rhythm":
        if slot_id == "hook":
            return f"快速点题：{product} 的最大亮点"
        if slot_id == "selling_points":
            return f"{first_point} / {second_point} 连续快切"
        if slot_id == "usage":
            return f"用短镜头展示 {product} 的关键使用过程"
        return f"用短 CTA 记住 {product}"
    if slot_id == "hook":
        return f"用 3 秒说明：为什么现在需要 {product}"
    if slot_id == "selling_points":
        return f"突出 {first_point}，再补充 {second_point}"
    if slot_id == "usage":
        return f"展示 {product} 在真实场景里的使用过程"
    return f"引导用户记住 {product} 并完成下一步行动"


def apply_variant_to_template(template: TemplateStructure, variant: str) -> TemplateStructure:
    if variant == "standard":
        return template

    notes = [*template.packaging_notes, *_variant_packaging_notes(variant)]
    slots = template.script_pattern
    rhythm_summary = f"{template.rhythm_summary} / {_variant_label(variant)}输出。"

    if variant == "fast_rhythm":
        slots = _compress_slots_for_fast_rhythm(slots)
        rhythm_summary = f"高节奏快切版，整体压缩到 {round(slots[-1].start + slots[-1].duration, 1)} 秒，前段更快进入卖点。"

    analysis = template.analysis_summary.model_copy(
        update={"packaging_signals": [*template.analysis_summary.packaging_signals, *_variant_packaging_notes(variant)]}
    )
    return template.model_copy(
        update={
            "script_pattern": slots,
            "rhythm_summary": rhythm_summary,
            "packaging_notes": _dedupe(notes),
            "analysis_summary": analysis,
        }
    )


def _compress_slots_for_fast_rhythm(slots: list[StructureSlot]) -> list[StructureSlot]:
    duration_by_slot = {
        "hook": 2.0,
        "selling_points": 5.0,
        "usage": 4.0,
        "cta": 2.0,
    }
    next_start = 0.0
    compressed: list[StructureSlot] = []
    for slot in slots:
        duration = min(slot.duration, duration_by_slot.get(slot.id, max(round(slot.duration * 0.72, 1), 1.5)))
        compressed.append(
            slot.model_copy(
                update={
                    "start": round(next_start, 1),
                    "duration": round(duration, 1),
                }
            )
        )
        next_start += duration
    return compressed


def _variant_label(variant: str) -> str:
    labels = {
        "standard": "",
        "high_click": "高点击版",
        "high_conversion": "高转化版",
        "fast_rhythm": "高节奏版",
    }
    return labels.get(variant, "")


def _variant_packaging_notes(variant: str) -> list[str]:
    notes = {
        "high_click": ["强钩子", "反差标题", "高停留字幕"],
        "high_conversion": ["信任背书", "转化 CTA", "行动理由"],
        "fast_rhythm": ["快切节奏", "短字幕", "高密度镜头"],
    }
    return notes.get(variant, [])


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _fill_strategy_for_slot(slot_id: str) -> str:
    strategies = {
        "hook": "使用标题卡片 + 快速字幕补足开头吸引力",
        "selling_points": "使用卖点卡片 + 局部放大补足商品特写",
        "usage": "使用字幕说明 + 通用场景素材补足使用过程",
        "cta": "使用结尾标题卡片 + 行动号召字幕补足 CTA",
    }
    return strategies.get(slot_id, "使用字幕和包装元素补足表达")


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


def apply_slot_level_overrides(
    template: TemplateStructure,
    mapping_overrides: Optional[list[TransferMappingOverride]] = None,
) -> TemplateStructure:
    if not mapping_overrides:
        return template

    override_lookup = {
        item.slot_id: item.sample_evidence.strip()
        for item in mapping_overrides
        if item.sample_evidence.strip()
    }
    if not override_lookup:
        return template

    slots = [
        slot.model_copy(
            update={
                "sample_evidence": override_lookup.get(slot.id, slot.sample_evidence),
            }
        )
        for slot in template.script_pattern
    ]
    analysis = template.analysis_summary.model_copy(
        update={
            "narrative_beats": [
                SampleAnalysisBeat(
                    slot_id=slot.id,
                    label=slot.label,
                    evidence=slot.sample_evidence,
                )
                for slot in slots
            ]
        }
    )
    return template.model_copy(
        update={
            "script_pattern": slots,
            "analysis_summary": analysis,
        }
    )


def build_asset_strategy(
    slot: StructureSlot,
    gap: Optional[MaterialGap],
    override: Optional[TransferMappingOverride],
) -> str:
    if override and override.asset_strategy.strip():
        return override.asset_strategy.strip()
    if gap:
        return gap.fill_strategy
    return f"使用已有素材：{slot.required_asset}"


def split_transcript_beats(transcript_summary: str) -> dict[str, str]:
    parts = [
        item.strip()
        for item in transcript_summary.replace("!", "。").replace("？", "。").split("。")
        if item.strip()
    ]
    if not parts:
        return {"hook": "", "usage": "", "cta": ""}
    return {
        "hook": parts[0],
        "usage": "。".join(parts[1:-1]) if len(parts) > 2 else transcript_summary,
        "cta": parts[-1] if len(parts) > 1 else "",
    }


def build_packaging_notes(transcript_summary: str) -> list[str]:
    notes = ["高密度字幕", "卖点标题卡片", "结尾行动号召"]
    if transcript_summary.strip():
        notes.append("口播驱动结构")
    return notes


def build_analysis_summary(sample: SampleVideoInput, slots: list[StructureSlot]) -> SampleAnalysisSummary:
    return SampleAnalysisSummary(
        headline=f"{sample.title} 样例拆解",
        metrics=[
            SampleAnalysisMetric(label="时长", value=f"{round(sample.duration, 1)}s", detail="样例总时长"),
            SampleAnalysisMetric(label="镜头数", value=str(sample.shot_count), detail="scene detect / 节奏估算"),
            SampleAnalysisMetric(
                label="转写",
                value="已提供" if sample.transcript_summary.strip() else "未提供",
                detail="用于提取 hook / usage / CTA 依据",
            ),
        ],
        narrative_beats=[
            SampleAnalysisBeat(slot_id=slot.id, label=slot.label, evidence=slot.sample_evidence)
            for slot in slots
        ],
        packaging_signals=build_packaging_notes(sample.transcript_summary),
    )
