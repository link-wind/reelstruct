from __future__ import annotations

from app.domain.shared.domain_models import MaterialGraphSearchResult, SlotQueryProfile


def rerank_material_graph_results(
    profile: SlotQueryProfile,
    results: list[MaterialGraphSearchResult],
) -> list[MaterialGraphSearchResult]:
    ranked = [_with_rule_bonus(profile, result) for result in results]
    return sorted(ranked, key=_ranking_key, reverse=True)


def _with_rule_bonus(
    profile: SlotQueryProfile,
    result: MaterialGraphSearchResult,
) -> MaterialGraphSearchResult:
    bonus = 0.0
    breakdown = result.score_breakdown
    if breakdown.get("visual", 0) > 0 and breakdown.get("ocr_asr", 0) > 0:
        bonus += 0.12
    if breakdown.get("slot_hint", 0) > 0:
        bonus += 0.08
    if breakdown.get("packaging", 0) > 0 and "reuse_with_packaging" in profile.replacement_modes:
        bonus += 0.05
    if breakdown.get("visual", 0) == 0 and breakdown.get("ocr_asr", 0) > 0:
        bonus -= 0.05

    next_confidence = round(min(0.95, max(0, result.confidence + bonus)), 2)
    return result.model_copy(update={"confidence": next_confidence})


def _ranking_key(result: MaterialGraphSearchResult) -> tuple[float, int, int, int, int, str, str]:
    breakdown = result.score_breakdown
    evidence_quality = 0
    if breakdown.get("visual", 0) > 0:
        evidence_quality += 1
    if breakdown.get("ocr_asr", 0) > 0:
        evidence_quality += 1
    if breakdown.get("packaging", 0) > 0:
        evidence_quality += 1
    if breakdown.get("slot_hint", 0) > 0:
        evidence_quality += 1
    return (
        result.confidence,
        evidence_quality,
        breakdown.get("slot_hint", 0),
        breakdown.get("packaging", 0),
        sum(breakdown.values()),
        result.asset_id,
        result.chunk_id,
    )
