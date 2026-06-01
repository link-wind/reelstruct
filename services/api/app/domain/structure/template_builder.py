from typing import Optional

from app.domain.shared.domain_models import (
    SampleAnalysisBeat,
    SampleAnalysisMetric,
    SampleAnalysisSummary,
    SampleVideoInput,
    StructureSlot,
    TemplateStructure,
    TransferMappingOverride,
)
from app.video_understanding.analysis_unit_service import build_analysis_units
from app.video_understanding.schemas import (
    EvidenceBackedSegment,
    GraphPackagingStructure,
    GraphRhythmStructure,
    ShotEvidenceGraph,
    ShotEvidenceNode,
    ShotUnderstanding,
    VideoShot,
)
from app.video_understanding.template_adapter import adapt_graph_segments_to_template


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
            **_slot_method_profile("hook"),
        ),
        StructureSlot(
            id="selling_points",
            label="卖点展开",
            start=round(hook_duration, 1),
            duration=selling_duration,
            purpose="连续推进核心卖点，保持信息密度。",
            required_asset="商品特写镜头",
            sample_evidence=f"样例中段通过 {sample.shot_count} 个镜头维持节奏。",
            **_slot_method_profile("selling_points"),
        ),
        StructureSlot(
            id="usage",
            label="使用过程",
            start=round(hook_duration + selling_duration, 1),
            duration=usage_duration,
            purpose="展示真实使用语境，降低理解成本。",
            required_asset="使用过程镜头",
            sample_evidence=transcript_beats["usage"] or sample.transcript_summary or "样例在中后段补充场景说明。",
            **_slot_method_profile("usage"),
        ),
        StructureSlot(
            id="cta",
            label="CTA",
            start=round(duration - cta_duration, 1),
            duration=round(cta_duration, 1),
            purpose="收束行动号召，强化记忆点。",
            required_asset="结尾 CTA 镜头",
            sample_evidence=transcript_beats["cta"] or "样例结尾保留明确收束段落。",
            **_slot_method_profile("cta"),
        ),
    ]

    template = TemplateStructure(
        title=f"{sample.title} 的可迁移结构",
        script_pattern=slots,
        rhythm_summary=f"约 {sample.shot_count} 个镜头 / {round(duration, 1)} 秒，开头快、中段密集、结尾收束。",
        packaging_notes=build_packaging_notes(sample.transcript_summary),
        analysis_summary=build_analysis_summary(sample, slots),
    )
    graph = _build_fallback_shot_evidence_graph(sample=sample, slots=slots)
    return template.model_copy(
        update={
            "shot_evidence_graph": graph,
            "analysis_summary": build_analysis_summary(sample, slots, graph=graph),
        }
    )


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


def build_analysis_summary(
    sample: SampleVideoInput,
    slots: list[StructureSlot],
    *,
    graph: Optional[ShotEvidenceGraph] = None,
) -> SampleAnalysisSummary:
    graph_presentation = None
    if graph is not None:
        graph_presentation = adapt_graph_segments_to_template(sample.title, graph).analysis_summary.graph_presentation
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
        graph_presentation=graph_presentation,
    )


def _build_fallback_shot_evidence_graph(
    *,
    sample: SampleVideoInput,
    slots: list[StructureSlot],
) -> ShotEvidenceGraph:
    shot_count = max(sample.shot_count, 1)
    duration = max(sample.duration, float(shot_count))
    shot_duration = round(duration / shot_count, 3)
    shots = [
        ShotEvidenceNode(
            shot=VideoShot(
                index=index,
                start=round((index - 1) * shot_duration, 3),
                end=round(duration if index == shot_count else index * shot_duration, 3),
                duration=round(
                    (duration if index == shot_count else index * shot_duration) - ((index - 1) * shot_duration),
                    3,
                ),
                keyframe_time=round(((index - 1) * shot_duration) + (shot_duration / 2), 3),
            ),
            understanding=ShotUnderstanding(
                shot_index=index,
                visual_summary=f"镜头 {index} 作为 {sample.title} 的结构占位镜头。",
                creative_function_hint=_slot_id_for_shot(index=index, shots=shot_count, slots=slots),
                confidence=0,
                warnings=["fallback graph generated from sample duration and shot count"],
            ),
        )
        for index in range(1, shot_count + 1)
    ]
    analysis_units = build_analysis_units(shots)
    segments = [
        EvidenceBackedSegment(
            segment_id=slot.id,
            label=slot.label,
            shot_indices=_segment_shot_indices(slot, shots),
            start=round(slot.start, 3),
            end=round(slot.start + slot.duration, 3),
            purpose=slot.purpose,
            method=slot.method,
            evidence=[slot.sample_evidence],
            rhythm=slot.rhythm,
            packaging=slot.packaging_intent,
            transferable_rule=slot.transferable_rule,
            non_transferable=slot.non_transferable,
            required_asset=slot.required_asset,
            confidence=slot.confidence,
        )
        for slot in slots
        if _segment_shot_indices(slot, shots)
    ]
    return ShotEvidenceGraph(
        shots=shots,
        analysis_units=analysis_units,
        segments=segments,
        rhythm_structure=GraphRhythmStructure(summary=f"约 {shot_count} 个镜头均匀覆盖 {round(duration, 1)} 秒。"),
        packaging_structure=GraphPackagingStructure(
            caption_density="标准",
            title_style="默认结构占位",
            transition_style="按时序硬切推断",
            cover_style="基于样例结构生成的默认占位",
        ),
        warnings=["当前为 fallback 结构图谱，基于样例时长、镜头数和默认结构槽位生成。"],
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


def _slot_method_profile(slot_id: str) -> dict[str, str]:
    profiles = {
        "hook": {
            "role": "吸引注意",
            "method": "结果先行 + 视觉记忆点",
            "intent": "让观众在前几秒理解为什么值得继续看",
            "rhythm": "前段快进入，字幕和画面同时给出主信息",
            "transferable_rule": "保留先给结果或反差画面、再补一句利益承诺的创作方法。",
            "non_transferable": "不复制样例中的具体商品、门店名、画面内容和原始文案。",
            "packaging_intent": "用大标题、强字幕或开场卡片强化停留。",
        },
        "selling_points": {
            "role": "建立兴趣",
            "method": "利益点连续推进",
            "intent": "让观众快速知道新内容的核心价值",
            "rhythm": "信息密集，一镜一卖点，避免长停顿",
            "transferable_rule": "保留按优先级连续展开卖点的结构，不照搬原样例卖点。",
            "non_transferable": "不复制样例的具体优惠、价格、品牌描述。",
            "packaging_intent": "用卖点卡片、关键词高亮和短字幕提高信息密度。",
        },
        "usage": {
            "role": "场景证明",
            "method": "真实场景证明",
            "intent": "降低理解成本，让卖点落到可感知场景里",
            "rhythm": "中段放慢半拍，给观众看清使用过程",
            "transferable_rule": "保留用真实动作或场景证明卖点的结构。",
            "non_transferable": "不复制样例的具体动作、人物和场景，只迁移证明方式。",
            "packaging_intent": "用说明字幕补足动作含义，必要时加过程标签。",
        },
        "cta": {
            "role": "推动转化",
            "method": "利益收束 + 行动指令",
            "intent": "让观众知道下一步该做什么",
            "rhythm": "结尾短暂停留，保证行动信息可读",
            "transferable_rule": "保留明确行动词和最后记忆点，但替换成新内容的转化目标。",
            "non_transferable": "不复制样例的具体口令、地址或优惠细节。",
            "packaging_intent": "用结尾标题卡片、行动按钮感字幕和停留画面强化 CTA。",
        },
    }
    return profiles.get(
        slot_id,
        {
            "role": "结构承接",
            "method": "信息承接",
            "intent": "让内容保持连贯",
            "rhythm": "跟随上下文节奏",
            "transferable_rule": "保留结构目的，替换具体内容。",
            "non_transferable": "不复制样例具体表达。",
            "packaging_intent": "用字幕和卡片辅助理解。",
        },
    )


def _variant_packaging_notes(variant: str) -> list[str]:
    notes = {
        "high_click": ["强钩子", "反差标题", "高停留字幕"],
        "high_conversion": ["信任背书", "转化 CTA", "行动理由"],
        "fast_rhythm": ["快切节奏", "短字幕", "高密度镜头"],
    }
    return notes.get(variant, [])


def _segment_shot_indices(slot: StructureSlot, shots: list[ShotEvidenceNode]) -> list[int]:
    indices = [
        node.shot.index
        for node in shots
        if node.shot.end > slot.start and node.shot.start < slot.start + slot.duration
    ]
    if indices:
        return indices
    nearest = min(shots, key=lambda node: abs(node.shot.start - slot.start))
    return [nearest.shot.index]


def _slot_id_for_shot(*, index: int, shots: int, slots: list[StructureSlot]) -> str:
    current_time = (index - 0.5) * (max(slots[-1].start + slots[-1].duration if slots else shots, 1) / shots)
    for slot in slots:
        if slot.start <= current_time < slot.start + slot.duration:
            return slot.id
    return slots[-1].id if slots else ""


def _variant_label(variant: str) -> str:
    labels = {
        "standard": "",
        "high_click": "高点击版",
        "high_conversion": "高转化版",
        "fast_rhythm": "高节奏版",
    }
    return labels.get(variant, "")


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped
