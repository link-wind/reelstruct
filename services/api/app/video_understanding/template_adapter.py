from app.models import (
    SampleAnalysisBeat,
    SampleAnalysisMetric,
    SampleAnalysisSummary,
    StructureSlot,
    TemplateStructure,
)
from app.video_understanding.schemas import AIStructureAnalysis, ShotEvidenceGraph


def adapt_ai_structure_to_template(sample_title: str, analysis: AIStructureAnalysis) -> TemplateStructure:
    slots = [
        StructureSlot(
            id=segment.id,
            label=segment.label,
            start=round(segment.start, 1),
            duration=round(segment.end - segment.start, 1),
            purpose=segment.purpose,
            required_asset=segment.required_asset,
            sample_evidence=segment.evidence,
            role=segment.type,
            method=segment.method,
            intent=segment.purpose,
            rhythm=segment.rhythm,
            transferable_rule=segment.transferable_rule,
            non_transferable=segment.non_transferable,
            packaging_intent=segment.packaging,
            evidence_shot_indices=segment.shot_indices,
            confidence=segment.confidence,
        )
        for segment in analysis.segments
    ]

    return TemplateStructure(
        title=f"{sample_title} 的 AI 可迁移结构",
        script_pattern=slots,
        rhythm_summary=analysis.rhythm_structure.summary,
        packaging_notes=_packaging_notes(analysis),
        analysis_summary=SampleAnalysisSummary(
            headline=analysis.headline,
            metrics=[
                SampleAnalysisMetric(label="来源", value="AI 拆解", detail="基于镜头证据、关键帧理解和字幕摘要生成"),
                SampleAnalysisMetric(label="置信度", value=f"{analysis.confidence:.2f}", detail="AI 对整体结构拆解的自评置信度"),
                SampleAnalysisMetric(label="段落数", value=str(len(analysis.segments)), detail="由证据决定，不套固定四段模板"),
            ],
            narrative_beats=[
                SampleAnalysisBeat(slot_id=segment.id, label=segment.label, evidence=segment.evidence)
                for segment in analysis.segments
            ],
            packaging_signals=_packaging_notes(analysis),
            source="ai",
            confidence=analysis.confidence,
            warnings=analysis.warnings,
        ),
    )


def adapt_graph_segments_to_template(sample_title: str, graph: ShotEvidenceGraph) -> TemplateStructure:
    slots = [
        StructureSlot(
            id=segment.segment_id,
            label=segment.label,
            start=round(segment.start, 1),
            duration=round(segment.end - segment.start, 1),
            purpose=segment.purpose,
            required_asset=segment.required_asset,
            sample_evidence="；".join(segment.evidence),
            method=segment.method,
            intent=segment.purpose,
            rhythm=segment.rhythm,
            transferable_rule=segment.transferable_rule,
            non_transferable=segment.non_transferable,
            packaging_intent=segment.packaging,
            evidence_shot_indices=segment.shot_indices,
            confidence=segment.confidence,
        )
        for segment in graph.segments
    ]
    packaging_signals = _graph_packaging_notes(graph)
    average_confidence = _graph_average_confidence(graph)

    return TemplateStructure(
        title=f"{sample_title} 的 图谱可迁移结构",
        script_pattern=slots,
        rhythm_summary=_graph_rhythm_summary(graph),
        packaging_notes=packaging_signals,
        shot_evidence_graph=graph,
        analysis_summary=SampleAnalysisSummary(
            headline=f"{sample_title} 图谱拆解",
            metrics=[
                SampleAnalysisMetric(
                    label="来源",
                    value="图谱拆解",
                    detail="基于 ShotEvidenceGraph 的 segments、beats 和 relations 聚合",
                ),
                SampleAnalysisMetric(
                    label="平均置信度",
                    value=f"{average_confidence:.2f}",
                    detail="segment 置信度的平均值",
                ),
                SampleAnalysisMetric(
                    label="段落数",
                    value=str(len(graph.segments)),
                    detail="由图谱 segment 节点生成",
                ),
                SampleAnalysisMetric(
                    label="镜头数",
                    value=str(_graph_shot_count(graph, slots)),
                    detail="由图谱 shot 节点和 segment 证据汇总",
                ),
            ],
            narrative_beats=[
                SampleAnalysisBeat(
                    slot_id=segment.segment_id,
                    label=segment.label,
                    evidence="；".join(segment.evidence),
                )
                for segment in graph.segments
            ],
            packaging_signals=packaging_signals,
            source="ai",
            confidence=average_confidence,
            warnings=graph.warnings,
        ),
    )


def _packaging_notes(analysis: AIStructureAnalysis) -> list[str]:
    packaging = analysis.packaging_structure
    return [
        item
        for item in [
            f"字幕密度：{packaging.caption_density}" if packaging.caption_density else "",
            f"标题风格：{packaging.title_style}" if packaging.title_style else "",
            f"转场：{packaging.transition_style}" if packaging.transition_style else "",
            f"封面：{packaging.cover_style}" if packaging.cover_style else "",
        ]
        if item
    ]


def _graph_packaging_notes(graph: ShotEvidenceGraph) -> list[str]:
    notes: list[str] = []
    seen: set[str] = set()
    for segment in graph.segments:
        packaging = segment.packaging.strip()
        if packaging and packaging not in seen:
            seen.add(packaging)
            notes.append(packaging)
    return notes


def _graph_average_confidence(graph: ShotEvidenceGraph) -> float:
    if not graph.segments:
        return 0.0
    return round(sum(segment.confidence for segment in graph.segments) / len(graph.segments), 2)


def _graph_shot_count(graph: ShotEvidenceGraph, slots: list[StructureSlot]) -> int:
    shot_ids = {node.shot.index for node in graph.shots}
    if shot_ids:
        return len(shot_ids)
    return len({shot_index for slot in slots for shot_index in slot.evidence_shot_indices})


def _graph_rhythm_summary(graph: ShotEvidenceGraph) -> str:
    if not graph.segments:
        return "图谱来源，未生成 segment"
    return "图谱来源，节奏由 segment 节点聚合生成"
