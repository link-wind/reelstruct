from typing import Optional

from app.models import (
    CompositionSpec,
    CompositionTrack,
    MaterialGap,
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
) -> StructurePreviewResponse:
    template = extract_template_structure(sample)
    gaps = detect_material_gaps(template, content)
    transfer_plan = build_transfer_plan(template, content, gaps, mapping_overrides=mapping_overrides)
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
            )
        )
    return gaps


def build_transfer_plan(
    template: TemplateStructure,
    content: NewContentInput,
    gaps: list[MaterialGap],
    mapping_overrides: Optional[list[TransferMappingOverride]] = None,
) -> TransferPlan:
    gap_lookup = {gap.slot_id: gap for gap in gaps}
    override_lookup = {
        item.slot_id: item.target_message.strip()
        for item in (mapping_overrides or [])
        if item.target_message.strip()
    }
    mappings = []

    for slot in template.script_pattern:
        target_message = override_lookup.get(slot.id) or _target_message_for_slot(slot.id, content)
        asset_strategy = (
            gap_lookup[slot.id].fill_strategy
            if slot.id in gap_lookup
            else f"使用已有素材：{slot.required_asset}"
        )
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
    )


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
