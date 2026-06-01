from app.evaluation_service import build_evaluation_summary


def test_build_evaluation_summary_returns_compact_sections():
    summary = build_evaluation_summary(
        structure_quality="medium",
        retrieval_quality="low",
        completion_quality="medium",
        result_quality="low",
    )

    assert summary.headline
    assert len(summary.highlights) >= 3
