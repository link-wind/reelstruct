from app.models import MaterialGraphSearchResult, SlotQueryProfile
from app.structure_coverage_service import score_structure_slot_coverage


def test_score_structure_slot_coverage_returns_gap_level_and_fillability():
    profile = SlotQueryProfile(
        slot_id="selling_points",
        slot_label="卖点展开",
        required_asset="商品特写镜头",
        visual_terms=["产品", "特写"],
        text_terms=["补水"],
        target_duration=3.0,
    )
    result = MaterialGraphSearchResult(
        slot_id="selling_points",
        asset_id="detail.mp4",
        chunk_id="chunk_a",
        start=1.0,
        end=3.6,
        matched_nodes=[],
        evidence_path=["命中产品特写"],
        missing=["缺少 OCR/ASR 文本证据"],
        score_breakdown={"visual": 20, "duration_fit": 14},
        confidence=0.54,
    )

    coverage = score_structure_slot_coverage(profile, [result])

    assert coverage.slot_id == "selling_points"
    assert 0 <= coverage.coverage_score <= 1
    assert coverage.gap_level in {"low", "medium", "high"}
    assert coverage.fillability in {"direct", "packaging", "reorder", "missing"}
    assert coverage.summary
