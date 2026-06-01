from __future__ import annotations

from app.workflow.workflow_models import EvaluationSummary


def build_evaluation_summary(
    *,
    structure_quality: str,
    retrieval_quality: str,
    completion_quality: str,
    result_quality: str,
) -> EvaluationSummary:
    highlights = [
        f"结构质量：{_quality_label(structure_quality)}",
        f"检索质量：{_quality_label(retrieval_quality)}",
        f"补全质量：{_quality_label(completion_quality)}",
        f"结果质量：{_quality_label(result_quality)}",
    ]
    return EvaluationSummary(
        headline="本次迁移质量评估",
        highlights=highlights[:4],
        structure_quality=_normalize_quality(structure_quality),
        retrieval_quality=_normalize_quality(retrieval_quality),
        completion_quality=_normalize_quality(completion_quality),
        result_quality=_normalize_quality(result_quality),
    )


def build_preview_evaluation_summary(*, gap_count: int, graph_available: bool, can_reuse_count: int) -> EvaluationSummary:
    structure_quality = "high" if graph_available else "medium"
    retrieval_quality = "high" if can_reuse_count >= max(1, gap_count) else "medium" if can_reuse_count > 0 else "low"
    completion_quality = "high" if gap_count == 0 else "medium" if can_reuse_count > 0 else "low"
    result_quality = "medium" if graph_available else "low"
    return build_evaluation_summary(
        structure_quality=structure_quality,
        retrieval_quality=retrieval_quality,
        completion_quality=completion_quality,
        result_quality=result_quality,
    )


def _normalize_quality(value: str) -> str:
    if value in {"low", "medium", "high"}:
        return value
    return "low"


def _quality_label(value: str) -> str:
    labels = {
        "low": "偏弱",
        "medium": "中等",
        "high": "较强",
    }
    return labels.get(value, "偏弱")
