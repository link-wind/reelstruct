from typing import Optional

from app.domain.shared.domain_models import (
    GraphPresentationEdge,
    GraphPresentationNode,
    GraphPresentationSummary,
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
    rhythm_metric = _graph_rhythm_metric(graph)
    packaging_metric = _graph_packaging_metric(graph)

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
                *([rhythm_metric] if rhythm_metric else []),
                *([packaging_metric] if packaging_metric else []),
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
            graph_presentation=_graph_presentation_summary(sample_title, graph),
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


def _graph_presentation_summary(sample_title: str, graph: ShotEvidenceGraph) -> GraphPresentationSummary:
    segment_nodes = [
        GraphPresentationNode(
            id=segment.segment_id,
            label=segment.label,
            node_type="segment",
            summary=_short_text(segment.purpose or segment.method or segment.label),
            shot_indices=segment.shot_indices,
            confidence=segment.confidence,
        )
        for segment in graph.segments
    ]
    unit_nodes = [
        GraphPresentationNode(
            id=unit.unit_id,
            label=unit.unit_id.replace("unit_", "分析单元 "),
            node_type="unit",
            summary=_short_text(unit.understanding.visual_summary if unit.understanding else ""),
            shot_indices=unit.shot_indices,
            confidence=unit.understanding.confidence if unit.understanding else 0,
        )
        for unit in graph.analysis_units
    ]
    shot_nodes = [
        GraphPresentationNode(
            id=f"shot_{shot_index}",
            label=f"镜头 {shot_index}",
            node_type="shot",
            summary=_shot_presentation_summary(graph, shot_index),
            shot_indices=[shot_index],
            confidence=_shot_presentation_confidence(graph, shot_index),
        )
        for shot_index in _graph_presentation_shot_indices(graph)
    ]
    segment_unit_edges = [
        GraphPresentationEdge(source=segment.segment_id, target=unit.unit_id, relation="覆盖")
        for segment in graph.segments
        for unit in graph.analysis_units
        if set(segment.shot_indices).intersection(unit.shot_indices)
    ]
    unit_shot_edges = [
        GraphPresentationEdge(source=unit.unit_id, target=f"shot_{shot_index}", relation="包含")
        for unit in graph.analysis_units
        for shot_index in unit.shot_indices
    ]
    return GraphPresentationSummary(
        headline=f"{sample_title} 图谱概要",
        summary_points=_graph_summary_points(graph),
        nodes=[*segment_nodes, *unit_nodes, *shot_nodes],
        edges=[*segment_unit_edges, *unit_shot_edges],
    )


def _graph_presentation_shot_indices(graph: ShotEvidenceGraph) -> list[int]:
    shot_indices = {node.shot.index for node in graph.shots}
    for segment in graph.segments:
        shot_indices.update(segment.shot_indices)
    for unit in graph.analysis_units:
        shot_indices.update(unit.shot_indices)
    return sorted(shot_indices)


def _shot_presentation_summary(graph: ShotEvidenceGraph, shot_index: int) -> str:
    node = next((item for item in graph.shots if item.shot.index == shot_index), None)
    if node is None:
        return ""
    understanding = node.understanding
    if understanding and understanding.visual_summary:
        return _short_text(understanding.visual_summary)
    if node.ocr_texts:
        text = " / ".join(item.text for item in node.ocr_texts[:2] if item.text)
        return _short_text(f"OCR：{text}")
    if node.transcript_texts:
        text = " / ".join(item.text for item in node.transcript_texts[:2] if item.text)
        return _short_text(f"ASR：{text}")
    return f"{node.shot.start:g}-{node.shot.end:g}s"


def _shot_presentation_confidence(graph: ShotEvidenceGraph, shot_index: int) -> float:
    node = next((item for item in graph.shots if item.shot.index == shot_index), None)
    if node is None or node.understanding is None:
        return 0
    return node.understanding.confidence


def _graph_summary_points(graph: ShotEvidenceGraph) -> list[str]:
    points: list[str] = []
    if graph.segments:
        segment_labels = " / ".join(segment.label for segment in graph.segments[:4] if segment.label)
        if segment_labels:
            points.append(f"结构段落：{segment_labels}")
        first_purpose = graph.segments[0].purpose.strip()
        if first_purpose:
            points.append(_short_text(first_purpose))
    rhythm = _graph_rhythm_summary(graph).strip()
    if rhythm:
        points.append(_short_text(rhythm))
    packaging_notes = _graph_packaging_notes(graph)[:2]
    if packaging_notes:
        points.append(_short_text("；".join(packaging_notes)))
    if graph.warnings:
        points.append(_short_text(f"注意：{graph.warnings[0]}"))
    return _dedupe_texts(points)[:5]


def _short_text(value: str, *, max_length: int = 72) -> str:
    text = value.replace("analysis_units.", "分析单元 ").replace("understanding.", "")
    text = " ".join(text.split())
    if len(text) <= max_length:
        return text
    return f"{text[:max_length - 1]}…"


def _dedupe_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _graph_packaging_notes(graph: ShotEvidenceGraph) -> list[str]:
    structured_notes = _graph_structured_packaging_notes(graph)
    if structured_notes:
        return structured_notes
    derived_notes = _graph_derived_packaging_notes(graph)
    if derived_notes:
        return derived_notes

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
    if graph.rhythm_structure.summary:
        return graph.rhythm_structure.summary
    derived_summary = _graph_derived_rhythm_summary(graph)
    if derived_summary:
        return derived_summary
    if not graph.segments:
        return "图谱来源，未生成 segment"
    return "图谱来源，节奏由 segment 节点聚合生成"


def _graph_rhythm_metric(graph: ShotEvidenceGraph) -> Optional[SampleAnalysisMetric]:
    rhythm = graph.rhythm_structure
    parts = [
        f"平均镜头 {rhythm.avg_shot_duration:g}s" if rhythm.avg_shot_duration else "",
        f"高峰 {rhythm.peak_position}" if rhythm.peak_position else "",
        f"快节奏 {' / '.join(rhythm.fast_windows)}" if rhythm.fast_windows else "",
        f"慢节奏 {' / '.join(rhythm.slow_windows)}" if rhythm.slow_windows else "",
    ]
    detail = "；".join(part for part in parts if part)
    if not rhythm.cut_density and not detail:
        return _graph_derived_rhythm_metric(graph)
    return SampleAnalysisMetric(
        label="节奏结构",
        value=rhythm.cut_density or "-",
        detail=detail or rhythm.summary,
    )


def _graph_packaging_metric(graph: ShotEvidenceGraph) -> Optional[SampleAnalysisMetric]:
    packaging = graph.packaging_structure
    parts = [
        f"标题 {packaging.title_style}" if packaging.title_style else "",
        f"转场 {packaging.transition_style}" if packaging.transition_style else "",
        f"封面 {packaging.cover_style}" if packaging.cover_style else "",
        f"布局 {packaging.text_layout}" if packaging.text_layout else "",
    ]
    detail = "；".join(part for part in parts if part)
    if not packaging.caption_density and not detail:
        return _graph_derived_packaging_metric(graph)
    return SampleAnalysisMetric(
        label="包装结构",
        value=packaging.caption_density or "-",
        detail=detail,
    )


def _graph_derived_rhythm_summary(graph: ShotEvidenceGraph) -> str:
    if not graph.shots:
        return ""
    durations = [node.shot.duration for node in graph.shots if node.shot.duration > 0]
    if not durations:
        return ""
    avg_duration = round(sum(durations) / len(durations), 1)
    fastest = min(graph.shots, key=lambda node: node.shot.duration).shot
    slowest = max(graph.shots, key=lambda node: node.shot.duration).shot
    density = _density_label(_cut_density(avg_duration))
    return (
        f"平均镜头 {avg_duration:g}s，整体{density}；"
        f"最快 {fastest.start:.3f}-{fastest.end:.3f}；"
        f"最慢 {slowest.start:.3f}-{slowest.end:.3f}。"
    )


def _graph_derived_rhythm_metric(graph: ShotEvidenceGraph) -> Optional[SampleAnalysisMetric]:
    if not graph.shots:
        return None
    durations = [node.shot.duration for node in graph.shots if node.shot.duration > 0]
    if not durations:
        return None
    avg_duration = round(sum(durations) / len(durations), 1)
    fastest = min(graph.shots, key=lambda node: node.shot.duration).shot
    slowest = max(graph.shots, key=lambda node: node.shot.duration).shot
    return SampleAnalysisMetric(
        label="节奏结构",
        value=_cut_density(avg_duration),
        detail=(
            f"平均镜头 {avg_duration:g}s；"
            f"最快 {fastest.start:.3f}-{fastest.end:.3f}；"
            f"最慢 {slowest.start:.3f}-{slowest.end:.3f}"
        ),
    )


def _cut_density(avg_duration: float) -> str:
    if avg_duration >= 6:
        return "slow"
    if avg_duration >= 2:
        return "medium"
    return "fast"


def _density_label(value: str) -> str:
    labels = {"fast": "快节奏", "medium": "中等节奏", "slow": "慢节奏"}
    return labels.get(value, value)


def _graph_derived_packaging_notes(graph: ShotEvidenceGraph) -> list[str]:
    caption_density = _derived_caption_density(graph)
    signals = _graph_packaging_signal_set(graph)
    notes = [
        f"字幕密度：{caption_density}" if caption_density else "",
        "标题风格：大标题" if any("大标题" in signal or "标题" in signal for signal in signals) else "",
        "转场：硬切" if any("硬切" in signal or "转场" in signal for signal in signals) else "",
        "文字布局：底部字幕" if _has_bottom_text(graph) else "",
        f"贴纸/标签：{' / '.join(sorted(signal for signal in signals if '贴纸' in signal or '标签' in signal))}",
    ]
    return [item for item in notes if item and not item.endswith("：")]


def _graph_derived_packaging_metric(graph: ShotEvidenceGraph) -> Optional[SampleAnalysisMetric]:
    caption_density = _derived_caption_density(graph)
    signals = _graph_packaging_signal_set(graph)
    parts = [
        "标题 大标题" if any("大标题" in signal or "标题" in signal for signal in signals) else "",
        "转场 硬切" if any("硬切" in signal or "转场" in signal for signal in signals) else "",
        "布局 底部字幕" if _has_bottom_text(graph) else "",
    ]
    detail = "；".join(part for part in parts if part)
    if not caption_density and not detail:
        return None
    return SampleAnalysisMetric(
        label="包装结构",
        value=caption_density or "-",
        detail=detail,
    )


def _derived_caption_density(graph: ShotEvidenceGraph) -> str:
    shot_count = len(graph.shots)
    if not shot_count:
        return ""
    text_count = sum(len(node.ocr_texts) for node in graph.shots)
    ratio = text_count / shot_count
    if ratio >= 1:
        return "高"
    if ratio > 0:
        return "中"
    return ""


def _graph_packaging_signal_set(graph: ShotEvidenceGraph) -> set[str]:
    signals: set[str] = set()
    for node in graph.shots:
        for signal in node.understanding.packaging_signals if node.understanding else []:
            if signal:
                signals.add(signal)
    return signals


def _has_bottom_text(graph: ShotEvidenceGraph) -> bool:
    return any("bottom" in item.position.lower() or "底" in item.position for node in graph.shots for item in node.ocr_texts)


def _graph_structured_packaging_notes(graph: ShotEvidenceGraph) -> list[str]:
    packaging = graph.packaging_structure
    notes = [
        f"字幕密度：{packaging.caption_density}" if packaging.caption_density else "",
        f"标题风格：{packaging.title_style}" if packaging.title_style else "",
        f"转场：{packaging.transition_style}" if packaging.transition_style else "",
        f"封面：{packaging.cover_style}" if packaging.cover_style else "",
        f"文字布局：{packaging.text_layout}" if packaging.text_layout else "",
        f"标题卡：{' / '.join(packaging.title_cards)}" if packaging.title_cards else "",
        f"贴纸/标签：{' / '.join(packaging.sticker_signals)}" if packaging.sticker_signals else "",
    ]
    return [item for item in notes if item]
