from app.models import (
    SampleAnalysisBeat,
    SampleAnalysisMetric,
    SampleAnalysisSummary,
    StructureSlot,
    TemplateStructure,
)
from app.video_understanding.schemas import AIStructureAnalysis


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
