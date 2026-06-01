from app.domain.structure.material_gap_builder import build_material_gap, detect_material_gaps
from app.models import (
    MaterialGap,
    MaterialGraphSearchResult,
    MaterialRetrievalCandidate,
    NewContentInput,
    SlotQueryProfile,
    StructureSlot,
    TemplateStructure,
)


def test_build_material_gap_prefers_graph_decision_and_syncs_timeline_patch():
    slot = StructureSlot(
        id="selling_points",
        label="卖点展开",
        start=3,
        duration=8,
        purpose="连续推进核心卖点，保持信息密度。",
        required_asset="商品特写镜头",
        sample_evidence="样例中段通过产品细节推进卖点。",
        packaging_intent="用卖点卡片和字幕强化信息密度。",
    )
    candidate = MaterialRetrievalCandidate(
        asset_id="detail-shot.mp4",
        filename="detail-shot.mp4",
        chunk_id="chunk_detail",
        start=1.2,
        end=3.8,
        matched_modalities=["visual", "ocr", "packaging"],
        evidence=["OCR=快速补水", "visual=瓶身细节特写"],
        match_score=76,
        match_reason="候选素材能承接卖点表达，但需要包装补强。",
        reuse_strategy="裁切产品细节镜头承接卖点。",
    )
    profile = SlotQueryProfile(
        slot_id="selling_points",
        slot_label="卖点展开",
        required_asset="商品特写镜头",
        required_expression="连续推进核心卖点",
        packaging_terms=["卖点卡片"],
    )
    graph_result = MaterialGraphSearchResult(
        slot_id="selling_points",
        asset_id="detail-shot.mp4",
        chunk_id="chunk_detail",
        start=1.2,
        end=3.8,
        evidence_path=["chunk_detail", "OCR=快速补水"],
        score_breakdown={"packaging": 10},
        confidence=0.74,
    )

    gap = build_material_gap(
        slot,
        [candidate],
        slot_query_profile=profile,
        graph_search_results=[graph_result],
    )

    assert gap.retrieval_status == "可包装后使用"
    assert gap.retrieval_reason == "chunk_detail；OCR=快速补水"
    assert gap.fill_strategy == gap.slot_fill_decision.actions[0]
    assert gap.primary_supplement == gap.slot_fill_decision.actions[0]
    assert gap.slot_fill_decision.selected_asset_id == "detail-shot.mp4"
    assert gap.slot_fill_decision.selected_chunk_id == "chunk_detail"
    assert gap.slot_fill_decision.evidence_path == ["chunk_detail", "OCR=快速补水"]
    assert gap.timeline_patches[0].patch_id == gap.slot_fill_decision.timeline_patch_id


def test_detect_material_gaps_skips_available_assets_and_builds_missing_slots(monkeypatch):
    template = TemplateStructure(
        title="样例结构",
        script_pattern=[
            StructureSlot(
                id="hook",
                label="Hook",
                start=0,
                duration=3,
                purpose="开头吸引注意",
                required_asset="开头吸引镜头",
                sample_evidence="样例开头",
            ),
            StructureSlot(
                id="selling_points",
                label="卖点展开",
                start=3,
                duration=8,
                purpose="连续推进卖点",
                required_asset="商品特写镜头",
                sample_evidence="样例中段",
            ),
        ],
        rhythm_summary="快开场",
        packaging_notes=[],
        analysis_summary={"headline": "分析"},
    )
    content = NewContentInput(
        topic="咖啡店开业短视频",
        available_assets=["开头吸引镜头"],
    )
    expected_gap = MaterialGap(
        slot_id="selling_points",
        missing_asset="商品特写镜头",
        impact="缺少商品特写",
        fill_strategy="补一个商品特写",
    )
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        "app.domain.structure.material_gap_builder.build_material_graph",
        lambda uploaded_assets: "graph",
    )
    monkeypatch.setattr(
        "app.domain.structure.material_gap_builder.build_slot_query_profile",
        lambda slot, current_content: {"slot_id": slot.id},
    )
    monkeypatch.setattr(
        "app.domain.structure.material_gap_builder.search_material_graph_for_slot",
        lambda graph, profile: ["raw-result", graph, profile],
    )
    monkeypatch.setattr(
        "app.domain.structure.material_gap_builder.rerank_material_graph_results",
        lambda profile, results: ["reranked", profile, results],
    )
    monkeypatch.setattr(
        "app.domain.structure.material_gap_builder.material_rag_service.retrieve_material_candidates_for_slot",
        lambda slot, current_content: ["candidate", slot.id, current_content.topic],
    )

    def fake_build_material_gap(
        slot,
        candidates,
        *,
        content=None,
        slot_query_profile=None,
        graph_search_results=None,
    ):
        calls.update(
            slot_id=slot.id,
            candidates=candidates,
            content=content,
            slot_query_profile=slot_query_profile,
            graph_search_results=graph_search_results,
        )
        return expected_gap

    monkeypatch.setattr("app.domain.structure.material_gap_builder.build_material_gap", fake_build_material_gap)

    gaps = detect_material_gaps(template, content)

    assert gaps == [expected_gap]
    assert calls == {
        "slot_id": "selling_points",
        "candidates": ["candidate", "selling_points", "咖啡店开业短视频"],
        "content": content,
        "slot_query_profile": {"slot_id": "selling_points"},
        "graph_search_results": ["reranked", {"slot_id": "selling_points"}, ["raw-result", "graph", {"slot_id": "selling_points"}]],
    }
