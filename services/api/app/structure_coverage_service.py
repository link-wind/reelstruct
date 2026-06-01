from __future__ import annotations

from app.domain.shared.domain_models import MaterialGraphSearchResult, SlotQueryProfile, StructureCoverageResult


def score_structure_slot_coverage(
    profile: SlotQueryProfile,
    results: list[MaterialGraphSearchResult],
) -> StructureCoverageResult:
    if not results:
        return StructureCoverageResult(
            slot_id=profile.slot_id,
            coverage_score=0,
            gap_level="high",
            fillability="missing",
            summary=f"{profile.slot_label or profile.slot_id} 当前没有可直接支撑的素材证据。",
        )

    best = results[0]
    coverage = round(best.confidence, 2)
    if coverage >= 0.75:
        gap_level = "low"
        fillability = "direct"
    elif coverage >= 0.45:
        gap_level = "medium"
        fillability = "packaging"
    elif best.evidence_path:
        gap_level = "high"
        fillability = "reorder"
    else:
        gap_level = "high"
        fillability = "missing"

    return StructureCoverageResult(
        slot_id=profile.slot_id,
        coverage_score=coverage,
        gap_level=gap_level,
        fillability=fillability,
        summary=f"{profile.slot_label or profile.slot_id} 覆盖率 {round(coverage * 100)}%，缺口等级 {gap_level}。",
    )
