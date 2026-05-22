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
    mapping_overrides: Optional[list[TransferMappingOverride]] = None,
    material_request_sheet: Optional[list[MaterialRequestTask]] = None,
) -> StructurePreviewResponse:
    template = extract_template_structure(sample)
    template = apply_slot_level_overrides(template, mapping_overrides)
    gaps = detect_material_gaps(template, content)
    transfer_plan = build_transfer_plan(
        template,
        content,
        gaps,
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


def build_transfer_plan(
    template: TemplateStructure,
    content: NewContentInput,
    gaps: list[MaterialGap],
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
            else _target_message_for_slot(slot.id, content)
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
    return TransferPlan(
        title=f"{title} 结构迁移方案",
        target_topic=content.topic,
        mappings=mappings,
        gaps=gaps,
        material_request_sheet=build_material_request_sheet(template, gaps, material_request_sheet),
    )


def build_material_request_sheet(
    template: TemplateStructure,
    gaps: list[MaterialGap],
    request_sheet: Optional[list[MaterialRequestTask]] = None,
) -> list[MaterialRequestTask]:
    if not request_sheet:
        return []

    request_lookup = {item.slot_id: item for item in request_sheet}
    gap_slots = {gap.slot_id for gap in gaps}
    return [
        MaterialRequestTask(slot_id=slot.id, status=request_lookup[slot.id].status)
        for slot in template.script_pattern
        if slot.id in gap_slots and slot.id in request_lookup
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


def _target_message_for_slot(slot_id: str, content: NewContentInput) -> str:
    product = content.product_name or content.topic
    first_point = content.selling_points[0] if content.selling_points else "核心卖点"
    second_point = content.selling_points[1] if len(content.selling_points) > 1 else first_point

    if slot_id == "hook":
        return f"用 3 秒说明：为什么现在需要 {product}"
    if slot_id == "selling_points":
        return f"突出 {first_point}，再补充 {second_point}"
    if slot_id == "usage":
        return f"展示 {product} 在真实场景里的使用过程"
    return f"引导用户记住 {product} 并完成下一步行动"


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
