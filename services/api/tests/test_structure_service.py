import pytest

from app import structure_service
from app.models import (
    CompositionSpec,
    MaterialGap,
    MaterialRequestTask,
    NewContentInput,
    SampleAnalysisBeat,
    SampleAnalysisMetric,
    SampleAnalysisSummary,
    SampleVideoInput,
    SlotFillDecision,
    StructureSlot,
    SupplementSelection,
    TemplateStructure,
    TransferPlan,
    TransferMappingOverride,
    UserSlotAsset,
)
from app.structure_service import build_structure_preview
from app.material_rag_service import index_material_asset, reset_material_vector_store_for_tests
from app.material_vector_store import MaterialVectorSearchResult
from app.video_understanding.schemas import (
    AIPackagingStructure,
    AIRhythmStructure,
    AnalysisUnit,
    AnalysisUnitUnderstanding,
    AIStructureAnalysis,
    EvidenceBackedSegment,
    GraphPackagingStructure,
    GraphRhythmStructure,
    PackagingTimelineItem,
    RhythmCurvePoint,
    SegmentRhythmNote,
    FrameOCRText,
    ShotEvidenceGraph,
    ShotEvidenceNode,
    ShotUnderstanding,
    VideoShot,
    VideoStructureSegment,
)
from app.video_understanding.template_adapter import (
    adapt_ai_structure_to_template,
    adapt_graph_segments_to_template,
)


@pytest.fixture(autouse=True)
def reset_material_rag_index():
    reset_material_vector_store_for_tests()
    yield
    reset_material_vector_store_for_tests()


def test_structure_service_delegates_transfer_planning_to_domain_module(monkeypatch):
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
            )
        ],
        rhythm_summary="快开场",
        packaging_notes=[],
        analysis_summary=SampleAnalysisSummary(headline="分析"),
    )
    expected_content = NewContentInput(
        topic="咖啡店开业短视频",
        product_name="巷口手作咖啡",
        available_assets=["开头吸引镜头"],
    )
    expected_gaps = [
        MaterialGap(
            slot_id="hook",
            missing_asset="开头吸引镜头",
            impact="缺少开头镜头",
            fill_strategy="补一个强钩子镜头",
        )
    ]
    mapping_overrides = [TransferMappingOverride(slot_id="hook", target_message="先说结果")]
    request_sheet = [MaterialRequestTask(slot_id="hook", status="已拍")]
    supplement_selections = [SupplementSelection(slot_id="hook", method="包装补全")]
    expected_plan = TransferPlan(
        title="巷口手作咖啡 高点击版结构迁移方案",
        target_topic=expected_content.topic,
        variant="high_click",
        mappings=[],
        gaps=expected_gaps,
        material_request_sheet=request_sheet,
    )
    captured: dict[str, object] = {}

    assert structure_service.build_transfer_plan.__module__ == "app.domain.structure.transfer_planner"

    monkeypatch.setattr(structure_service, "extract_template_structure", lambda sample: template)
    monkeypatch.setattr(structure_service, "apply_variant_to_template", lambda current, variant: current)
    monkeypatch.setattr(structure_service, "apply_slot_level_overrides", lambda current, overrides: current)
    monkeypatch.setattr(
        structure_service,
        "apply_delivered_material_tasks_to_content",
        lambda current_template, current_content, current_sheet: expected_content,
    )
    monkeypatch.setattr(
        structure_service,
        "apply_uploaded_slot_assets_to_content",
        lambda current_template, current_content: current_content,
    )
    monkeypatch.setattr(
        structure_service,
        "detect_material_gaps",
        lambda current_template, current_content: expected_gaps,
    )

    def fake_build_transfer_plan(
        current_template,
        current_content,
        current_gaps,
        *,
        variant="standard",
        mapping_overrides=None,
        material_request_sheet=None,
        supplement_selections=None,
    ):
        captured.update(
            template=current_template,
            content=current_content,
            gaps=current_gaps,
            variant=variant,
            mapping_overrides=mapping_overrides,
            material_request_sheet=material_request_sheet,
            supplement_selections=supplement_selections,
        )
        return expected_plan

    monkeypatch.setattr(structure_service, "build_transfer_plan", fake_build_transfer_plan)
    monkeypatch.setattr(
        structure_service,
        "build_composition_spec",
        lambda current_template, current_plan, current_content: CompositionSpec(duration=12, tracks=[]),
    )

    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=12, shot_count=4),
        content=NewContentInput(topic="原始输入"),
        mapping_overrides=mapping_overrides,
        material_request_sheet=request_sheet,
        supplement_selections=supplement_selections,
        variant="high_click",
    )

    assert captured == {
        "template": template,
        "content": expected_content,
        "gaps": expected_gaps,
        "variant": "high_click",
        "mapping_overrides": mapping_overrides,
        "material_request_sheet": request_sheet,
        "supplement_selections": supplement_selections,
    }
    assert response.transfer_plan == expected_plan


def test_build_structure_preview_marks_missing_assets_and_tracks():
    response = build_structure_preview(
        sample=SampleVideoInput(
            title="爆款护肤样例",
            duration=30,
            shot_count=9,
            transcript_summary="先讲痛点，再展示使用效果。",
        ),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头", "使用过程镜头"],
        ),
    )

    assert response.template.script_pattern[0].id == "hook"
    assert response.transfer_plan.title == "清透保湿精华 结构迁移方案"
    assert {gap.slot_id for gap in response.transfer_plan.gaps} == {"selling_points", "cta"}
    gap_lookup = {gap.slot_id: gap for gap in response.transfer_plan.gaps}
    assert gap_lookup["selling_points"].suggested_asset_type == "商品卖点特写"
    assert any("产品特写" in item for item in gap_lookup["selling_points"].suggested_shots)
    assert any("字幕" in item for item in gap_lookup["cta"].pickup_checklist)
    assert any(track.type == "card" for track in response.composition.tracks)
    assert response.composition.duration == 30


def test_material_gap_serializes_empty_slot_fill_decision():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            selling_points=["手作咖啡"],
            available_assets=["开头吸引镜头"],
        ),
    )

    gap_payload = response.transfer_plan.gaps[0].model_dump()

    assert "slot_fill_decision" in gap_payload
    assert gap_payload["slot_fill_decision"]["slot_id"]
    assert gap_payload["slot_fill_decision"]["actions"]


def test_material_gap_serializes_rag_v4_completion_fields():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花", "开业优惠"],
            available_assets=["开头吸引镜头"],
        ),
    )

    gap_payload = response.transfer_plan.gaps[0].model_dump()

    assert "slot_query_profile" in gap_payload
    assert "graph_search_results" in gap_payload
    assert "timeline_patches" in gap_payload
    assert "evidence_path" in gap_payload["slot_fill_decision"]
    assert "timeline_patch_id" in gap_payload["slot_fill_decision"]


def test_structure_preview_exposes_segment_unit_shot_hierarchy():
    response = build_structure_preview(
        sample=SampleVideoInput(
            title="结构样例",
            duration=24,
            shot_count=6,
            transcript_summary="开头吸引，中段卖点，结尾行动号召。",
        ),
        content=NewContentInput(topic="新品推广"),
    )

    graph = response.template.shot_evidence_graph

    assert graph is not None
    assert len(graph.shots) == 6
    assert graph.analysis_units
    assert graph.segments
    assert all(unit.shot_indices for unit in graph.analysis_units)
    assert all(segment.start < segment.end for segment in graph.segments)
    assert response.template.analysis_summary.graph_presentation is not None
    assert any(node.node_type == "segment" for node in response.template.analysis_summary.graph_presentation.nodes)
    assert any(node.node_type == "unit" for node in response.template.analysis_summary.graph_presentation.nodes)
    assert any(node.node_type == "shot" for node in response.template.analysis_summary.graph_presentation.nodes)


def test_build_slot_query_profile_extracts_visual_text_and_packaging_terms():
    from app.slot_profile_service import build_slot_query_profile

    slot = StructureSlot(
        id="selling_points",
        label="卖点展开",
        start=3,
        duration=8,
        purpose="连续推进核心卖点，保持信息密度。",
        required_asset="商品特写镜头",
        sample_evidence="样例用产品细节特写推进卖点。",
        role="建立兴趣",
        method="利益点连续推进",
        intent="让观众快速知道核心价值",
        packaging_intent="用卖点卡片、关键词高亮和短字幕提高信息密度。",
    )
    content = NewContentInput(
        topic="新品保湿精华短视频",
        product_name="清透保湿精华",
        selling_points=["快速补水", "清爽不黏"],
    )

    profile = build_slot_query_profile(slot, content)

    assert profile.slot_id == "selling_points"
    assert profile.slot_label == "卖点展开"
    assert profile.target_duration == 8
    assert profile.min_usable_duration >= 1
    assert "商品特写镜头" in profile.required_asset
    assert {"产品", "特写"}.issubset(set(profile.visual_terms))
    assert {"快速补水", "清爽不黏"}.issubset(set(profile.text_terms))
    assert "卖点卡片" in profile.packaging_terms
    assert "reuse_with_packaging" in profile.replacement_modes


def test_build_slot_query_profile_adds_cta_defaults():
    from app.slot_profile_service import build_slot_query_profile

    slot = StructureSlot(
        id="cta",
        label="CTA",
        start=16,
        duration=4,
        purpose="收束行动号召，强化记忆点。",
        required_asset="结尾 CTA 镜头",
        sample_evidence="结尾引导到店。",
        role="推动转化",
        method="利益收束 + 行动指令",
        intent="",
        packaging_intent="用结尾标题卡片、行动按钮感字幕和停留画面强化 CTA。",
    )
    content = NewContentInput(topic="咖啡店开业", product_name="巷口手作咖啡", selling_points=["开业优惠"])

    profile = build_slot_query_profile(slot, content)

    assert "行动" in profile.action_terms
    assert "入口" in profile.text_terms
    assert "结尾标题卡片" in profile.packaging_terms
    assert profile.replacement_modes[-1] == "shoot_or_aigc"


def test_slot_fill_decision_reuses_candidate_with_packaging_actions():
    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    filename="detail-shot.mp4",
                    public_url="/materials/detail-shot.mp4",
                    analysis={
                        "evidence_chunks": [
                            {
                                "asset_id": "detail-shot.mp4",
                                "chunk_id": "chunk_detail",
                                "start": 1.2,
                                "end": 3.8,
                                "duration": 2.6,
                                "visual_summary": "清透保湿精华瓶身细节特写。",
                                "ocr_texts": ["快速补水"],
                                "packaging_signals": ["卖点字幕"],
                                "subject_tags": ["产品", "瓶身"],
                                "action_tags": ["特写"],
                                "slot_hints": ["卖点展开"],
                                "modalities": ["visual", "ocr", "packaging"],
                                "embedding_text": "清透保湿精华 快速补水 产品 瓶身 特写 卖点展开",
                            }
                        ],
                    },
                )
            ],
        ),
    )

    decision = {gap.slot_id: gap for gap in response.transfer_plan.gaps}["selling_points"].slot_fill_decision

    assert decision.decision_type in {"reuse_direct", "reuse_with_packaging"}
    assert decision.selected_asset_id == "detail-shot.mp4"
    assert decision.selected_chunk_id == "chunk_detail"
    assert decision.actions
    assert "卖点" in " ".join(decision.actions) or "裁切" in " ".join(decision.actions)
    assert decision.timeline_hint


def test_slot_fill_decision_uses_graph_evidence_path_for_uploaded_chunk():
    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    filename="detail-shot.mp4",
                    public_url="/materials/detail-shot.mp4",
                    analysis={
                        "evidence_chunks": [
                            {
                                "asset_id": "detail-shot.mp4",
                                "chunk_id": "chunk_detail",
                                "start": 1.2,
                                "end": 3.8,
                                "duration": 2.6,
                                "visual_summary": "清透保湿精华瓶身细节特写。",
                                "ocr_texts": ["快速补水"],
                                "packaging_signals": ["卖点字幕"],
                                "subject_tags": ["产品", "瓶身"],
                                "action_tags": ["特写"],
                                "slot_hints": ["卖点展开"],
                                "modalities": ["visual", "ocr", "packaging"],
                                "embedding_text": "清透保湿精华 快速补水 产品 瓶身 特写 卖点展开",
                            }
                        ],
                    },
                )
            ],
        ),
    )

    gap = {item.slot_id: item for item in response.transfer_plan.gaps}["selling_points"]
    mapping = {item.slot_id: item for item in response.transfer_plan.mappings}["selling_points"]
    decision = gap.slot_fill_decision

    assert gap.graph_search_results
    assert decision.selected_asset_id == "detail-shot.mp4"
    assert decision.selected_chunk_id == "chunk_detail"
    assert decision.evidence_path
    assert any("OCR=快速补水" in item for item in decision.evidence_path)
    assert decision.timeline_patch_id
    assert gap.timeline_patches[0].patch_id == decision.timeline_patch_id
    assert decision.actions[0] in mapping.asset_strategy


def test_timeline_patch_inserts_caption_card_for_missing_material():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花", "开业优惠"],
            available_assets=["开头吸引镜头"],
        ),
    )

    gap = {item.slot_id: item for item in response.transfer_plan.gaps}["selling_points"]
    patch = gap.timeline_patches[0]
    patch_card_text = patch.track_updates[0].text

    assert patch.operation == "insert_caption_card"
    assert patch.execution_summary
    assert any(update.type == "card" for update in patch.track_updates)
    assert any(
        track.type == "card" and track.slot_id == "selling_points" and track.text == patch_card_text
        for track in response.composition.tracks
    )


def test_timeline_patch_replaces_slot_media_for_graph_candidate():
    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    filename="detail-shot.mp4",
                    public_url="/materials/detail-shot.mp4",
                    analysis={
                        "evidence_chunks": [
                            {
                                "asset_id": "detail-shot.mp4",
                                "chunk_id": "chunk_detail",
                                "start": 1.2,
                                "end": 3.8,
                                "duration": 2.6,
                                "visual_summary": "清透保湿精华瓶身细节特写。",
                                "ocr_texts": ["快速补水"],
                                "packaging_signals": ["卖点字幕"],
                                "subject_tags": ["产品", "瓶身"],
                                "action_tags": ["特写"],
                                "slot_hints": ["卖点展开"],
                                "modalities": ["visual", "ocr", "packaging"],
                                "embedding_text": "清透保湿精华 快速补水 产品 瓶身 特写 卖点展开",
                            }
                        ],
                    },
                )
            ],
        ),
    )

    gap = {item.slot_id: item for item in response.transfer_plan.gaps}["selling_points"]
    patch = gap.timeline_patches[0]

    assert patch.operation == "replace_slot_media"
    assert patch.execution_summary
    assert patch.source_asset_id == "detail-shot.mp4"
    assert any(
        track.type == "video"
        and track.slot_id == "selling_points"
        and track.asset_public_url == "/materials/detail-shot.mp4"
        for track in response.composition.tracks
    )


def test_timeline_patch_matches_uploaded_asset_by_public_url_basename():
    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    public_url="/materials/detail-shot.mp4",
                    analysis={
                        "evidence_chunks": [
                            {
                                "chunk_id": "chunk_detail",
                                "start": 1.2,
                                "end": 3.8,
                                "duration": 2.6,
                                "visual_summary": "清透保湿精华瓶身细节特写。",
                                "ocr_texts": ["快速补水"],
                                "packaging_signals": ["卖点字幕"],
                                "subject_tags": ["产品", "瓶身"],
                                "action_tags": ["特写"],
                                "slot_hints": ["卖点展开"],
                                "modalities": ["visual", "ocr", "packaging"],
                                "embedding_text": "清透保湿精华 快速补水 产品 瓶身 特写 卖点展开",
                            }
                        ],
                    },
                )
            ],
        ),
    )

    assert any(
        track.type == "video"
        and track.slot_id == "selling_points"
        and track.asset_public_url == "/materials/detail-shot.mp4"
        for track in response.composition.tracks
    )


def test_timeline_patch_normalizes_invalid_durations():
    from app.timeline_patch_service import build_timeline_patch

    slot = StructureSlot(
        id="selling_points",
        label="卖点展开",
        start=5,
        duration=-2,
        purpose="连续推进卖点。",
        required_asset="商品特写镜头",
        sample_evidence="样例用产品细节承载卖点。",
    )
    decision = SlotFillDecision(
        slot_id="selling_points",
        selected_asset_id="detail-shot.mp4",
        selected_chunk_id="chunk_detail",
        start=4,
        end=2,
        actions=["裁切素材补位。"],
    )

    patch = build_timeline_patch(slot, decision)

    assert patch.target_end > patch.target_start
    assert patch.track_updates[0].duration > 0
    assert patch.source_end >= patch.source_start


def test_slot_fill_decision_falls_back_to_caption_when_no_candidate():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            selling_points=["手作咖啡"],
            available_assets=["开头吸引镜头"],
        ),
    )

    decision = {gap.slot_id: gap for gap in response.transfer_plan.gaps}["selling_points"].slot_fill_decision

    assert decision.selected_asset_id == ""
    assert decision.decision_type in {"caption_only", "shoot_or_aigc"}
    assert decision.missing
    assert decision.actions
    assert decision.confidence <= 0.35


def test_build_structure_preview_retrieves_uploaded_material_candidates_for_gaps():
    response = build_structure_preview(
        sample=SampleVideoInput(
            title="爆款护肤样例",
            duration=30,
            shot_count=9,
            transcript_summary="先讲痛点，再展示使用效果。",
        ),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    filename="detail-shot.mp4",
                    public_url="/materials/detail-shot.mp4",
                    analysis={
                        "duration": 6,
                        "shot_count": 3,
                        "recommended_slot_id": "selling_points",
                        "recommended_slot_label": "卖点展开",
                        "recommendation_reason": "素材包含产品细节，适合承载卖点展开。",
                        "slot_fit_scores": {
                            "hook": 45,
                            "selling_points": 91,
                            "usage": 58,
                            "cta": 30,
                        },
                    },
                )
            ],
        ),
    )

    gap_lookup = {gap.slot_id: gap for gap in response.transfer_plan.gaps}

    assert "selling_points" in gap_lookup
    selling_gap = gap_lookup["selling_points"]
    assert selling_gap.retrieval_status == "可复用"
    assert selling_gap.candidates[0].asset_id == "detail-shot.mp4"
    assert selling_gap.candidates[0].match_score == 91
    assert "RAG" in selling_gap.fill_strategy
    assert "detail-shot.mp4" in selling_gap.fill_strategy
    assert response.transfer_plan.mappings[1].asset_strategy == selling_gap.fill_strategy


def test_material_rag_uses_text_semantics_when_slot_scores_are_weak():
    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    filename="product-detail-closeup.mp4",
                    public_url="/materials/product-detail-closeup.mp4",
                    analysis={
                        "duration": 5,
                        "shot_count": 1,
                        "recommended_slot_id": "hook",
                        "recommended_slot_label": "Hook",
                        "recommendation_reason": "清透保湿精华瓶身细节和质地近景。",
                        "slot_fit_scores": {
                            "hook": 40,
                            "selling_points": 35,
                            "usage": 20,
                            "cta": 15,
                        },
                    },
                )
            ],
        ),
    )

    selling_gap = {gap.slot_id: gap for gap in response.transfer_plan.gaps}["selling_points"]

    assert selling_gap.candidates
    assert selling_gap.candidates[0].asset_id == "product-detail-closeup.mp4"
    assert selling_gap.candidates[0].match_score >= 55
    assert selling_gap.retrieval_status == "可包装后使用"


def test_material_rag_uses_material_understanding_card_for_semantic_match():
    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    filename="clip-001.mp4",
                    public_url="/materials/clip-001.mp4",
                    analysis={
                        "duration": 5,
                        "shot_count": 1,
                        "recommended_slot_id": "hook",
                        "recommended_slot_label": "Hook",
                        "recommendation_reason": "普通素材。",
                        "slot_fit_scores": {
                            "hook": 40,
                            "selling_points": 35,
                            "usage": 20,
                            "cta": 15,
                        },
                        "visual_summary": "清透保湿精华的瓶身细节与质地近景。",
                        "tags": ["产品特写", "瓶身", "质地"],
                        "usable_for": ["卖点展开"],
                        "embedding_text": "清透保湿精华 产品 特写 细节 瓶身 质地 卖点展开",
                    },
                )
            ],
        ),
    )

    selling_gap = {gap.slot_id: gap for gap in response.transfer_plan.gaps}["selling_points"]

    assert selling_gap.candidates
    assert selling_gap.candidates[0].asset_id == "clip-001.mp4"
    assert selling_gap.candidates[0].match_score >= 55
    assert selling_gap.retrieval_status == "可包装后使用"


def test_material_rag_returns_chunk_level_candidate_evidence():
    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    filename="clip-001.mp4",
                    public_url="/materials/clip-001.mp4",
                    analysis={
                        "duration": 5,
                        "shot_count": 1,
                        "recommended_slot_id": "hook",
                        "recommended_slot_label": "Hook",
                        "recommendation_reason": "普通素材。",
                        "slot_fit_scores": {
                            "hook": 40,
                            "selling_points": 35,
                            "usage": 20,
                            "cta": 15,
                        },
                        "evidence_chunks": [
                            {
                                "asset_id": "clip-001.mp4",
                                "chunk_id": "chunk_detail",
                                "start": 1.2,
                                "end": 3.8,
                                "duration": 2.6,
                                "visual_summary": "清透保湿精华瓶身细节特写。",
                                "ocr_texts": ["快速补水"],
                                "asr_texts": [],
                                "packaging_signals": ["卖点字幕"],
                                "subject_tags": ["产品", "瓶身"],
                                "action_tags": ["特写"],
                                "slot_hints": ["卖点展开"],
                                "modalities": ["visual", "ocr", "packaging"],
                                "embedding_text": "清透保湿精华 快速补水 产品 瓶身 特写 卖点展开",
                            }
                        ],
                    },
                )
            ],
        ),
    )

    selling_gap = {gap.slot_id: gap for gap in response.transfer_plan.gaps}["selling_points"]
    candidate = selling_gap.candidates[0]

    assert candidate.asset_id == "clip-001.mp4"
    assert candidate.chunk_id == "chunk_detail"
    assert candidate.start == 1.2
    assert candidate.end == 3.8
    assert {"visual", "ocr", "packaging"}.issubset(set(candidate.matched_modalities))
    assert any("快速补水" in item for item in candidate.evidence)
    assert candidate.score_breakdown["semantic"] > 0
    assert candidate.score_breakdown["ocr_asr"] > 0
    assert candidate.score_breakdown["packaging"] > 0
    assert "1.2s-3.8s" in candidate.reuse_strategy


def test_material_gap_outputs_structured_supplement_options():
    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头"],
        ),
    )

    selling_gap = {gap.slot_id: gap for gap in response.transfer_plan.gaps}["selling_points"]

    assert selling_gap.primary_supplement
    assert selling_gap.supplement_options
    methods = {option.method for option in selling_gap.supplement_options}
    assert {"文案/字幕补全", "包装补全", "结构重排"}.issubset(methods)
    assert all(option.action for option in selling_gap.supplement_options)


def test_selected_supplement_option_changes_transfer_mapping_strategy():
    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头"],
        ),
        supplement_selections=[
            SupplementSelection(slot_id="selling_points", method="包装补全"),
        ],
    )

    mapping = {item.slot_id: item for item in response.transfer_plan.mappings}["selling_points"]

    assert "采用“包装补全”" in mapping.asset_strategy
    assert mapping.explanation.gap_handling
    assert mapping.explanation.gap_handling in mapping.asset_strategy
    assert mapping.fallback_strategy == mapping.explanation.gap_handling


def test_slot_fill_decision_updates_mapping_gap_handling():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            selling_points=["手作咖啡"],
            available_assets=["开头吸引镜头"],
        ),
    )

    gap = {item.slot_id: item for item in response.transfer_plan.gaps}["selling_points"]
    mapping = {item.slot_id: item for item in response.transfer_plan.mappings}["selling_points"]

    assert mapping.asset_strategy == gap.fill_strategy
    assert gap.slot_fill_decision.actions[0] in mapping.explanation.gap_handling


def test_material_gap_includes_slot_retrieval_plan_for_reusable_candidate():
    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    filename="detail-shot.mp4",
                    public_url="/materials/detail-shot.mp4",
                    analysis={
                        "duration": 5,
                        "shot_count": 1,
                        "evidence_chunks": [
                            {
                                "asset_id": "detail-shot.mp4",
                                "chunk_id": "chunk_detail",
                                "start": 1.2,
                                "end": 3.8,
                                "duration": 2.6,
                                "visual_summary": "清透保湿精华瓶身细节特写。",
                                "ocr_texts": ["快速补水"],
                                "packaging_signals": ["卖点字幕"],
                                "subject_tags": ["产品", "瓶身"],
                                "action_tags": ["特写"],
                                "slot_hints": ["卖点展开"],
                                "modalities": ["visual", "ocr", "packaging"],
                                "embedding_text": "清透保湿精华 快速补水 产品 瓶身 特写 卖点展开",
                            }
                        ],
                    },
                )
            ],
        ),
    )

    gap = {item.slot_id: item for item in response.transfer_plan.gaps}["selling_points"]
    plan = gap.retrieval_plan

    assert plan.slot_id == "selling_points"
    assert plan.required_expression
    assert "商品特写镜头" in plan.required_asset
    assert plan.best_candidate_id == "detail-shot.mp4::chunk_detail"
    assert plan.matched_evidence
    assert any("快速补水" in item for item in plan.matched_evidence)
    assert "裁切" in plan.generation_action
    assert plan.confidence >= 0.8


def test_material_gap_retrieval_plan_explains_missing_evidence_without_candidates():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            selling_points=["手作咖啡"],
            available_assets=["开头吸引镜头"],
        ),
    )

    gap = {item.slot_id: item for item in response.transfer_plan.gaps}["selling_points"]
    plan = gap.retrieval_plan

    assert plan.slot_id == "selling_points"
    assert plan.best_candidate_id == ""
    assert plan.matched_evidence == []
    assert any("缺少" in item for item in plan.missing_evidence)
    assert plan.recommended_method in {"文案/字幕补全", "包装补全", "结构重排", "补拍/AIGC"}
    assert plan.generation_action
    assert plan.confidence <= 0.35


def test_material_gap_promotes_retrieved_candidate_as_supplement_option():
    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    filename="clip-001.mp4",
                    public_url="/materials/clip-001.mp4",
                    analysis={
                        "duration": 5,
                        "shot_count": 1,
                        "evidence_chunks": [
                            {
                                "asset_id": "clip-001.mp4",
                                "chunk_id": "chunk_detail",
                                "start": 1.2,
                                "end": 3.8,
                                "duration": 2.6,
                                "visual_summary": "清透保湿精华瓶身细节特写。",
                                "ocr_texts": ["快速补水"],
                                "packaging_signals": ["卖点字幕"],
                                "subject_tags": ["产品", "瓶身"],
                                "action_tags": ["特写"],
                                "slot_hints": ["卖点展开"],
                                "modalities": ["visual", "ocr", "packaging"],
                                "embedding_text": "清透保湿精华 快速补水 产品 瓶身 特写 卖点展开",
                            }
                        ],
                    },
                )
            ],
        ),
    )

    selling_gap = {gap.slot_id: gap for gap in response.transfer_plan.gaps}["selling_points"]

    assert selling_gap.supplement_options[0].method == "现有素材复用"
    assert "clip-001.mp4" in selling_gap.supplement_options[0].action
    assert selling_gap.supplement_options[0].evidence


def test_material_rag_uses_vector_store_when_rule_scores_are_weak(monkeypatch):
    class FakeVectorStore:
        def __init__(self):
            self.queries = []

        def upsert(self, documents):
            pass

        def search(self, query, *, top_k=5, filters=None, query_embedding=None):
            self.queries.append(query)
            return [
                MaterialVectorSearchResult(
                    id="clip-001.mp4::shot_1",
                    score=0.92,
                    text="向量命中：清透保湿精华瓶身质地近景",
                    metadata={
                        "asset_id": "clip-001.mp4",
                        "filename": "clip-001.mp4",
                        "chunk_id": "shot_1",
                        "source_slot_id": "material_pool",
                        "public_url": "/materials/clip-001.mp4",
                    },
                )
            ]

    fake_store = FakeVectorStore()
    monkeypatch.setattr("app.material_rag_service.create_material_vector_store", lambda: fake_store)
    index_material_asset(
        UserSlotAsset(
            slot_id="material_pool",
            filename="clip-001.mp4",
            public_url="/materials/clip-001.mp4",
            analysis={
                "duration": 5,
                "shot_count": 1,
                "evidence_chunks": [
                    {
                        "asset_id": "clip-001.mp4",
                        "chunk_id": "shot_1",
                        "start": 1.2,
                        "end": 3.8,
                        "duration": 2.6,
                        "visual_summary": "抽象画面。",
                        "slot_hints": [],
                        "modalities": ["visual"],
                        "embedding_text": "清透保湿精华 瓶身 质地 近景",
                    }
                ],
            },
        )
    )

    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    filename="clip-001.mp4",
                    public_url="/materials/clip-001.mp4",
                    analysis={
                        "duration": 5,
                        "shot_count": 1,
                        "recommended_slot_id": "hook",
                        "recommended_slot_label": "Hook",
                        "recommendation_reason": "普通素材。",
                        "slot_fit_scores": {
                            "hook": 40,
                            "selling_points": 10,
                            "usage": 10,
                            "cta": 10,
                        },
                        "evidence_chunks": [
                            {
                                "asset_id": "clip-001.mp4",
                                "chunk_id": "shot_1",
                                "start": 1.2,
                                "end": 3.8,
                                "duration": 2.6,
                                "visual_summary": "抽象画面。",
                                "slot_hints": [],
                                "modalities": ["visual"],
                                "embedding_text": "清透保湿精华 瓶身 质地 近景",
                            }
                        ],
                    },
                )
            ],
        ),
    )

    selling_gap = {gap.slot_id: gap for gap in response.transfer_plan.gaps}["selling_points"]
    candidate = selling_gap.candidates[0]

    assert any("清透保湿精华" in query for query in fake_store.queries)
    assert candidate.chunk_id == "shot_1"
    assert candidate.match_score >= 80
    assert "向量检索" in candidate.match_reason
    assert "vector" in candidate.matched_modalities
    assert candidate.score_breakdown["vector"] >= 80


def test_material_rag_uses_default_in_memory_vector_store_for_chunk_search():
    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="清透保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["瓶身质地", "快速补水"],
            available_assets=["开头吸引镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    filename="neutral-name.mp4",
                    public_url="/materials/neutral-name.mp4",
                    analysis={
                        "duration": 5,
                        "shot_count": 1,
                        "recommended_slot_id": "hook",
                        "recommended_slot_label": "Hook",
                        "recommendation_reason": "普通素材。",
                        "slot_fit_scores": {
                            "hook": 40,
                            "selling_points": 10,
                            "usage": 10,
                            "cta": 10,
                        },
                        "evidence_chunks": [
                            {
                                "asset_id": "neutral-name.mp4",
                                "chunk_id": "shot_1",
                                "start": 0.5,
                                "end": 2.5,
                                "duration": 2,
                                "visual_summary": "抽象质感画面。",
                                "slot_hints": [],
                                "modalities": ["visual"],
                                "embedding_text": "瓶身质地 快速补水 清透保湿精华",
                            }
                        ],
                    },
                )
            ],
        ),
    )

    selling_gap = {gap.slot_id: gap for gap in response.transfer_plan.gaps}["selling_points"]

    assert selling_gap.candidates
    assert selling_gap.candidates[0].chunk_id == "shot_1"
    assert "vector" in selling_gap.candidates[0].matched_modalities


def test_material_rag_can_retrieve_preindexed_material_asset():
    index_material_asset(
        UserSlotAsset(
            slot_id="material_pool",
            filename="indexed-detail.mp4",
            public_url="/materials/indexed-detail.mp4",
            analysis={
                "duration": 4,
                "shot_count": 1,
                "evidence_chunks": [
                    {
                        "asset_id": "indexed-detail.mp4",
                        "chunk_id": "shot_product",
                        "start": 0.4,
                        "end": 2.8,
                        "duration": 2.4,
                        "visual_summary": "清透保湿精华瓶身细节特写。",
                        "ocr_texts": ["快速补水"],
                        "modalities": ["visual", "ocr"],
                        "embedding_text": "清透保湿精华 快速补水 产品 瓶身 特写 卖点展开",
                    }
                ],
            },
        )
    )

    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="清透保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水"],
            available_assets=["开头吸引镜头"],
        ),
    )

    selling_gap = {gap.slot_id: gap for gap in response.transfer_plan.gaps}["selling_points"]

    assert selling_gap.candidates
    assert selling_gap.candidates[0].asset_id == "indexed-detail.mp4"
    assert selling_gap.candidates[0].chunk_id == "shot_product"
    assert "vector" in selling_gap.candidates[0].matched_modalities


def test_material_rag_can_render_vector_result_from_metadata_only(monkeypatch):
    class FakeVectorStore:
        def upsert(self, documents):
            pass

        def search(self, query, *, top_k=5, filters=None, query_embedding=None):
            return [
                MaterialVectorSearchResult(
                    id="persisted-detail.mp4::shot_product",
                    score=0.88,
                    text="清透保湿精华 快速补水 产品特写",
                    metadata={
                        "asset_id": "persisted-detail.mp4",
                        "filename": "persisted-detail.mp4",
                        "chunk_id": "shot_product",
                        "source_slot_id": "material_pool",
                        "public_url": "/materials/persisted-detail.mp4",
                        "start": 0.4,
                        "end": 2.8,
                        "modalities": "visual,ocr,vector",
                        "evidence": "OCR：快速补水；主体：产品",
                    },
                )
            ]

    monkeypatch.setattr("app.material_rag_service.create_material_vector_store", lambda: FakeVectorStore())

    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="清透保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水"],
            available_assets=["开头吸引镜头"],
        ),
    )

    selling_gap = {gap.slot_id: gap for gap in response.transfer_plan.gaps}["selling_points"]
    candidate = selling_gap.candidates[0]

    assert candidate.asset_id == "persisted-detail.mp4"
    assert candidate.chunk_id == "shot_product"
    assert candidate.start == 0.4
    assert candidate.end == 2.8
    assert "OCR：快速补水" in candidate.evidence


def test_material_rag_does_not_leak_uploaded_assets_between_requests():
    first_response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="清透保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水"],
            available_assets=["开头吸引镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    filename="leak-source.mp4",
                    public_url="/materials/leak-source.mp4",
                    analysis={
                        "duration": 4,
                        "shot_count": 1,
                        "evidence_chunks": [
                            {
                                "asset_id": "leak-source.mp4",
                                "chunk_id": "shot_product",
                                "start": 0,
                                "end": 2,
                                "duration": 2,
                                "visual_summary": "清透保湿精华快速补水特写。",
                                "modalities": ["visual"],
                                "embedding_text": "清透保湿精华 快速补水 产品特写 卖点展开",
                            }
                        ],
                    },
                )
            ],
        ),
    )
    second_response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="清透保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水"],
            available_assets=["开头吸引镜头"],
        ),
    )

    first_selling_gap = {gap.slot_id: gap for gap in first_response.transfer_plan.gaps}["selling_points"]
    second_selling_gap = {gap.slot_id: gap for gap in second_response.transfer_plan.gaps}["selling_points"]

    assert any(candidate.asset_id == "leak-source.mp4" for candidate in first_selling_gap.candidates)
    assert all(candidate.asset_id != "leak-source.mp4" for candidate in second_selling_gap.candidates)


def test_material_rag_matches_cta_assets_by_filename_and_reason():
    response = build_structure_preview(
        sample=SampleVideoInput(title="门店样例", duration=24, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业短视频",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花", "开业优惠"],
            available_assets=["开头吸引镜头", "商品特写镜头", "使用过程镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    filename="ending-cta-store-card.mp4",
                    public_url="/materials/ending-cta-store-card.mp4",
                    analysis={
                        "duration": 3,
                        "shot_count": 1,
                        "recommended_slot_id": "hook",
                        "recommended_slot_label": "Hook",
                        "recommendation_reason": "结尾门店信息卡，包含到店行动号召和优惠提示。",
                        "slot_fit_scores": {
                            "hook": 45,
                            "selling_points": 20,
                            "usage": 20,
                            "cta": 35,
                        },
                    },
                )
            ],
        ),
    )

    cta_gap = {gap.slot_id: gap for gap in response.transfer_plan.gaps}["cta"]

    assert cta_gap.retrieval_status in {"可复用", "可包装后使用"}
    assert cta_gap.candidates[0].asset_id == "ending-cta-store-card.mp4"
    assert cta_gap.candidates[0].match_score >= 55
    assert "CTA" in cta_gap.fill_strategy or "行动" in cta_gap.fill_strategy


def test_build_structure_preview_adds_rule_fallback_transfer_explanations():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业短视频",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花", "新店开业优惠"],
            available_assets=["开头吸引镜头", "使用过程镜头"],
        ),
        use_ai_transfer_explanation=False,
    )

    mapping = response.transfer_plan.mappings[0]

    assert mapping.explanation.slot_id == mapping.slot_id
    assert mapping.explanation.source_observation == mapping.source_method
    assert mapping.explanation.target_expression == mapping.target_message
    assert mapping.explanation.asset_plan == mapping.asset_strategy
    assert mapping.explanation.transferable_principle


def test_build_structure_preview_can_enrich_transfer_explanations_with_ai(monkeypatch):
    from app.models import TransferExplanation

    captured = {}

    def fake_explainer(*, template, content, transfer_plan, graph, variant):
        captured["topic"] = content.topic
        captured["graph"] = graph
        captured["variant"] = variant
        return transfer_plan.model_copy(
            update={
                "mappings": [
                    mapping.model_copy(
                        update={
                            "explanation": TransferExplanation(
                                slot_id=mapping.slot_id,
                                source_observation=f"AI 观察 {mapping.source_label}",
                                transferable_principle="AI 判断先迁移表达功能，再替换商品内容",
                                target_expression=f"AI 新表达：{content.product_name or content.topic}",
                                asset_plan="AI 建议用现有镜头和标题卡共同支撑",
                                gap_handling="AI 判断缺镜头时用卖点卡片补足",
                                reasoning="AI 基于样例证据、目标卖点和素材缺口生成",
                                confidence=0.82,
                                warnings=[],
                            )
                        }
                    )
                    for mapping in transfer_plan.mappings
                ]
            }
        )

    monkeypatch.setattr("app.structure_service.explain_transfer_with_ai", fake_explainer)

    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业短视频",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花", "新店开业优惠"],
            available_assets=["开头吸引镜头", "使用过程镜头"],
        ),
        use_ai_transfer_explanation=True,
        variant="high_click",
    )

    assert captured["topic"] == "咖啡店开业短视频"
    assert captured["variant"] == "high_click"
    assert response.transfer_plan.mappings[0].explanation.target_expression == "AI 新表达：巷口手作咖啡"
    assert response.transfer_plan.mappings[0].explanation.confidence == 0.82


def test_build_structure_preview_prefers_ai_template_when_provided():
    ai_template = TemplateStructure(
        title="AI 样例模板",
        script_pattern=[
            StructureSlot(
                id="ai_hook",
                label="AI 识别钩子",
                start=0,
                duration=3.2,
                purpose="AI 识别出的开场目的",
                required_asset="结果吸引镜头",
                sample_evidence="AI 引用第 1 镜证据",
                evidence_shot_indices=[1],
                confidence=0.9,
            )
        ],
        rhythm_summary="AI 识别的节奏",
        packaging_notes=["AI 包装"],
        analysis_summary=SampleAnalysisSummary(
            headline="AI 拆解",
            source="ai",
            confidence=0.88,
            narrative_beats=[SampleAnalysisBeat(slot_id="ai_hook", label="AI 识别钩子", evidence="AI 引用第 1 镜证据")],
        ),
    )

    response = build_structure_preview(
        sample=SampleVideoInput(title="规则样例", duration=20, shot_count=6),
        content=NewContentInput(topic="新品短视频", available_assets=["结果吸引镜头"]),
        ai_template=ai_template,
    )

    assert response.template.title == "AI 样例模板"
    assert response.template.analysis_summary.source == "ai"
    assert response.template.script_pattern[0].id == "ai_hook"
    assert response.transfer_plan.gaps == []


def test_adapt_ai_structure_to_template_preserves_segments_evidence_and_source():
    analysis = AIStructureAnalysis(
        headline="样例用强结果开场，再用过程证明完成转化",
        segments=[
            VideoStructureSegment(
                id="hook_result",
                label="结果钩子",
                type="hook",
                start=0,
                end=2.8,
                shot_indices=[1],
                purpose="用结果画面快速建立停留理由",
                method="结果先行 + 大字幕压强",
                evidence="第 1 镜出现产品完成效果和醒目标题。",
                rhythm="快进入，单镜头停留 2.8 秒。",
                packaging="大标题条 + 高密度字幕",
                required_asset="结果吸引镜头",
                transferable_rule="迁移先给结果再解释价值的方法。",
                non_transferable="不复制原视频的具体产品结果和文案。",
                confidence=0.91,
            ),
            VideoStructureSegment(
                id="proof_process",
                label="过程证明",
                type="proof",
                start=2.8,
                end=9.5,
                shot_indices=[2, 3],
                purpose="展示使用过程支撑卖点",
                method="动作过程 + 细节补充",
                evidence="第 2-3 镜展示手部动作和产品特写。",
                rhythm="中段镜头切换变密。",
                packaging="关键词贴纸",
                required_asset="使用过程镜头",
                transferable_rule="迁移用过程证明卖点的组织方式。",
                non_transferable="不复制人物动作和场景。",
                confidence=0.82,
            ),
        ],
        rhythm_structure=AIRhythmStructure(
            summary="前 3 秒快进入，中段用两段证明镜头加密。",
            peak_position="0-2.8s",
            slowdown_position="无明显降速",
        ),
        packaging_structure=AIPackagingStructure(
            caption_density="高密度",
            title_style="开场大标题",
            transition_style="硬切",
            cover_style="结果画面 + 强标题",
        ),
        confidence=0.87,
        warnings=["样例没有结尾 CTA 证据"],
    )

    template = adapt_ai_structure_to_template("护肤样例", analysis)

    assert template.title == "护肤样例 的 AI 可迁移结构"
    assert template.rhythm_summary == "前 3 秒快进入，中段用两段证明镜头加密。"
    assert template.packaging_notes == ["字幕密度：高密度", "标题风格：开场大标题", "转场：硬切", "封面：结果画面 + 强标题"]
    assert template.analysis_summary.source == "ai"
    assert template.analysis_summary.confidence == 0.87
    assert template.analysis_summary.warnings == ["样例没有结尾 CTA 证据"]

    first = template.script_pattern[0]
    assert first.id == "hook_result"
    assert first.start == 0
    assert first.duration == 2.8
    assert first.required_asset == "结果吸引镜头"
    assert first.sample_evidence == "第 1 镜出现产品完成效果和醒目标题。"
    assert first.method == "结果先行 + 大字幕压强"
    assert first.evidence_shot_indices == [1]
    assert first.confidence == 0.91

    beat_lookup = {item.slot_id: item.evidence for item in template.analysis_summary.narrative_beats}
    assert beat_lookup["proof_process"] == "第 2-3 镜展示手部动作和产品特写。"


def test_adapt_graph_segments_to_template_preserves_evidence():
    graph = ShotEvidenceGraph(
        segments=[
            EvidenceBackedSegment(
                segment_id="segment_1",
                label="开场钩子",
                shot_indices=[1, 2],
                start=0.24,
                end=2.64,
                purpose="快速建立停留理由",
                required_asset="结果吸引镜头",
                method="先抛结果再解释",
                rhythm="前 3 秒加速进入",
                transferable_rule="先给结果再讲原因",
                non_transferable="不复制原品牌名和具体文案",
                packaging="大标题 + 强对比字幕",
                evidence=["第 1 镜出现结果画面", "第 2 镜补充字幕信息"],
                confidence=0.84,
            ),
            EvidenceBackedSegment(
                segment_id="segment_2",
                label="使用证明",
                shot_indices=[3],
                start=2.64,
                end=7.06,
                purpose="展示过程支撑卖点",
                required_asset="使用过程镜头",
                method="动作展示 + 细节补充",
                rhythm="中段稳定推进",
                transferable_rule="保留过程证明的组织方式",
                non_transferable="不复制原视频人物动作",
                packaging="关键词贴纸",
                evidence=["第 3 镜展示使用过程"],
                confidence=0.66,
            ),
        ],
        analysis_units=[
            AnalysisUnit(
                unit_id="unit_1",
                shot_indices=[1, 2],
                start=0.24,
                end=2.64,
                duration=2.4,
                understanding=AnalysisUnitUnderstanding(
                    unit_id="unit_1",
                    visual_summary="开场用结果画面和字幕快速建立停留理由",
                    confidence=0.78,
                ),
            )
        ],
        rhythm_structure=GraphRhythmStructure(
            summary="前 3 秒快切建立注意力，2.6 秒后放慢展示过程。",
            avg_shot_duration=1.4,
            cut_density="fast",
            fast_windows=["0.0-2.6"],
            slow_windows=["2.6-7.1"],
            peak_position="0.0-2.6",
            rhythm_curve=[
                RhythmCurvePoint(start=0.0, end=2.6, shot_count=2, density="fast", note="开场快切")
            ],
            segment_notes=[
                SegmentRhythmNote(segment_id="segment_1", note="Hook 段快切"),
                SegmentRhythmNote(segment_id="segment_2", note="证明段放慢"),
            ],
        ),
        packaging_structure=GraphPackagingStructure(
            caption_density="高",
            title_style="开场大标题",
            transition_style="硬切",
            cover_style="结果画面 + 强标题",
            text_layout="中部标题 + 底部字幕",
            title_cards=["0.2-1.5 大标题"],
            sticker_signals=["关键词贴纸"],
            packaging_timeline=[
                PackagingTimelineItem(start=0.2, end=1.5, type="title_card", evidence="第 1 镜大标题")
            ],
        ),
        warnings=["graph 里缺少结尾 CTA 证据"],
    )

    template = adapt_graph_segments_to_template("咖啡样例", graph)

    assert template.title == "咖啡样例 的 图谱可迁移结构"
    assert template.script_pattern[0].id == "segment_1"
    assert template.script_pattern[0].start == 0.2
    assert template.script_pattern[0].duration == 2.4
    assert template.script_pattern[0].sample_evidence == "第 1 镜出现结果画面；第 2 镜补充字幕信息"
    assert template.script_pattern[0].evidence_shot_indices == [1, 2]
    assert template.script_pattern[0].confidence == 0.84
    assert template.script_pattern[0].required_asset == "结果吸引镜头"
    assert template.script_pattern[0].method == "先抛结果再解释"
    assert template.script_pattern[0].rhythm == "前 3 秒加速进入"
    assert template.script_pattern[0].transferable_rule == "先给结果再讲原因"
    assert template.script_pattern[0].non_transferable == "不复制原品牌名和具体文案"
    assert template.script_pattern[0].packaging_intent == "大标题 + 强对比字幕"

    analysis = template.analysis_summary
    assert analysis.source == "ai"
    assert analysis.warnings == ["graph 里缺少结尾 CTA 证据"]
    assert analysis.metrics[0].label == "来源"
    assert analysis.metrics[0].value == "图谱拆解"
    assert analysis.metrics[1].label == "平均置信度"
    assert analysis.metrics[1].value == "0.75"
    assert analysis.metrics[2].label == "段落数"
    assert analysis.metrics[2].value == "2"
    assert analysis.metrics[3].label == "镜头数"
    assert analysis.metrics[3].value == "3"
    assert analysis.narrative_beats[0].evidence == "第 1 镜出现结果画面；第 2 镜补充字幕信息"
    assert analysis.narrative_beats[1].evidence == "第 3 镜展示使用过程"
    assert analysis.packaging_signals == [
        "字幕密度：高",
        "标题风格：开场大标题",
        "转场：硬切",
        "封面：结果画面 + 强标题",
        "文字布局：中部标题 + 底部字幕",
        "标题卡：0.2-1.5 大标题",
        "贴纸/标签：关键词贴纸",
    ]
    assert template.rhythm_summary == "前 3 秒快切建立注意力，2.6 秒后放慢展示过程。"
    assert template.packaging_notes == [
        "字幕密度：高",
        "标题风格：开场大标题",
        "转场：硬切",
        "封面：结果画面 + 强标题",
        "文字布局：中部标题 + 底部字幕",
        "标题卡：0.2-1.5 大标题",
        "贴纸/标签：关键词贴纸",
    ]
    rhythm_metric = next(item for item in analysis.metrics if item.label == "节奏结构")
    assert rhythm_metric.value == "fast"
    assert rhythm_metric.detail == "平均镜头 1.4s；高峰 0.0-2.6；快节奏 0.0-2.6；慢节奏 2.6-7.1"
    packaging_metric = next(item for item in analysis.metrics if item.label == "包装结构")
    assert packaging_metric.value == "高"
    assert packaging_metric.detail == "标题 开场大标题；转场 硬切；封面 结果画面 + 强标题；布局 中部标题 + 底部字幕"
    assert analysis.graph_presentation is not None
    assert analysis.graph_presentation.headline == "咖啡样例 图谱概要"
    assert 1 <= len(analysis.graph_presentation.summary_points) <= 5
    assert "快速建立停留理由" in analysis.graph_presentation.summary_points
    assert "analysis_units." not in " ".join(analysis.graph_presentation.summary_points)
    assert any(node.node_type == "segment" and node.id == "segment_1" for node in analysis.graph_presentation.nodes)
    assert any(node.node_type == "unit" for node in analysis.graph_presentation.nodes)
    assert any(node.node_type == "shot" and node.id == "shot_1" for node in analysis.graph_presentation.nodes)
    assert any(edge.source == "segment_1" and edge.relation == "覆盖" for edge in analysis.graph_presentation.edges)
    assert any(edge.source == "unit_1" and edge.target == "shot_1" and edge.relation == "包含" for edge in analysis.graph_presentation.edges)


def test_adapt_graph_segments_to_template_derives_rhythm_and_packaging_when_ai_fields_missing():
    graph = ShotEvidenceGraph(
        shots=[
            ShotEvidenceNode(
                shot=VideoShot(index=1, start=0, end=0.8, duration=0.8, keyframe_time=0.4),
                ocr_texts=[
                    FrameOCRText(shot_index=1, frame_index=1, frame_time=0.4, text="超级大标题", position="top", confidence=0.95)
                ],
                understanding=ShotUnderstanding(
                    shot_index=1,
                    packaging_signals=["大标题", "硬切"],
                    creative_function_hint="hook",
                    confidence=0.8,
                ),
            ),
            ShotEvidenceNode(
                shot=VideoShot(index=2, start=0.8, end=3.8, duration=3.0, keyframe_time=2.3),
                ocr_texts=[
                    FrameOCRText(shot_index=2, frame_index=1, frame_time=2.3, text="底部字幕", position="bottom", confidence=0.9)
                ],
                understanding=ShotUnderstanding(
                    shot_index=2,
                    packaging_signals=["底部字幕"],
                    creative_function_hint="product_demo",
                    confidence=0.7,
                ),
            ),
        ],
        segments=[
            EvidenceBackedSegment(
                segment_id="seg_1",
                label="开场",
                shot_indices=[1],
                start=0,
                end=0.8,
                purpose="吸引注意",
                method="大标题快速切入",
                rhythm="",
                packaging="",
                evidence=["shot 1 OCR: 超级大标题"],
                confidence=0.7,
            ),
            EvidenceBackedSegment(
                segment_id="seg_2",
                label="展开",
                shot_indices=[2],
                start=0.8,
                end=3.8,
                purpose="展示产品",
                method="慢镜头说明",
                rhythm="",
                packaging="",
                evidence=["shot 2 OCR: 底部字幕"],
                confidence=0.7,
            ),
        ],
    )

    template = adapt_graph_segments_to_template("规则补足样例", graph)

    assert template.rhythm_summary == "平均镜头 1.9s，整体快节奏；最快 0.000-0.800；最慢 0.800-3.800。"
    assert "字幕密度：高" in template.packaging_notes
    assert "标题风格：大标题" in template.packaging_notes
    assert "转场：硬切" in template.packaging_notes
    rhythm_metric = next(item for item in template.analysis_summary.metrics if item.label == "节奏结构")
    assert rhythm_metric.value == "fast"
    packaging_metric = next(item for item in template.analysis_summary.metrics if item.label == "包装结构")
    assert packaging_metric.value == "高"


def test_build_structure_preview_uses_existing_assets_when_available():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            selling_points=["手作咖啡"],
            available_assets=["开头吸引镜头", "商品特写镜头", "使用过程镜头", "结尾 CTA 镜头"],
        ),
    )

    assert response.transfer_plan.gaps == []
    assert all("使用已有素材" in mapping.asset_strategy for mapping in response.transfer_plan.mappings)


def test_build_structure_preview_treats_delivered_material_tasks_as_available_assets():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花"],
            available_assets=["开头吸引镜头", "使用过程镜头"],
        ),
        material_request_sheet=[
            MaterialRequestTask(slot_id="selling_points", status="已拍"),
            MaterialRequestTask(slot_id="cta", status="待补拍"),
        ],
    )

    gap_lookup = {gap.slot_id: gap for gap in response.transfer_plan.gaps}
    mapping_lookup = {mapping.slot_id: mapping for mapping in response.transfer_plan.mappings}

    assert set(gap_lookup) == {"cta"}
    assert mapping_lookup["selling_points"].asset_strategy == "使用已有素材：商品特写镜头"
    assert "卡片" not in mapping_lookup["selling_points"].asset_strategy
    assert response.transfer_plan.material_request_sheet == [
        MaterialRequestTask(slot_id="selling_points", status="已拍"),
        MaterialRequestTask(slot_id="cta", status="待补拍"),
    ]


def test_build_structure_preview_binds_uploaded_slot_assets_to_composition_tracks():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花"],
            available_assets=["开头吸引镜头", "使用过程镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="selling_points",
                    filename="selling-points.mp4",
                    local_path="/tmp/selling-points.mp4",
                    public_url="/materials/selling-points.mp4",
                )
            ],
        ),
    )

    video_track_lookup = {
        track.slot_id: track
        for track in response.composition.tracks
        if track.type == "video"
    }
    mapping_lookup = {mapping.slot_id: mapping for mapping in response.transfer_plan.mappings}

    assert {gap.slot_id for gap in response.transfer_plan.gaps} == {"cta"}
    assert mapping_lookup["selling_points"].asset_strategy == "使用已有素材：商品特写镜头"
    assert video_track_lookup["selling_points"].asset_local_path == "/tmp/selling-points.mp4"
    assert video_track_lookup["selling_points"].asset_public_url == "/materials/selling-points.mp4"


def test_build_structure_preview_uses_transcript_summary_for_hook_and_cta_evidence():
    response = build_structure_preview(
        sample=SampleVideoInput(
            title="护肤样例",
            duration=18,
            shot_count=5,
            transcript_summary="先讲熬夜脸很垮。再展示精华上脸效果。最后引导现在下单。",
        ),
        content=NewContentInput(
            topic="新品精华短视频",
            selling_points=["修护透亮"],
            available_assets=["开头吸引镜头", "商品特写镜头", "使用过程镜头", "结尾 CTA 镜头"],
        ),
    )

    evidence_lookup = {slot.id: slot.sample_evidence for slot in response.template.script_pattern}
    assert "先讲熬夜脸很垮" in evidence_lookup["hook"]
    assert "最后引导现在下单" in evidence_lookup["cta"]


def test_build_structure_preview_returns_sample_analysis_summary():
    response = build_structure_preview(
        sample=SampleVideoInput(
            title="护肤样例",
            duration=18,
            shot_count=5,
            transcript_summary="先讲熬夜脸很垮。再展示精华上脸效果。最后引导现在下单。",
        ),
        content=NewContentInput(
            topic="新品精华短视频",
            selling_points=["修护透亮"],
            available_assets=["开头吸引镜头", "商品特写镜头", "使用过程镜头", "结尾 CTA 镜头"],
        ),
    )

    analysis = response.template.analysis_summary
    assert analysis.headline == "护肤样例 样例拆解"
    metric_lookup = {item.label: item.value for item in analysis.metrics}
    assert metric_lookup["时长"] == "18.0s"
    assert metric_lookup["镜头数"] == "5"
    assert metric_lookup["转写"] == "已提供"
    beat_lookup = {item.slot_id: item.evidence for item in analysis.narrative_beats}
    assert beat_lookup["hook"] == "先讲熬夜脸很垮"
    assert beat_lookup["cta"] == "最后引导现在下单"


def test_build_structure_preview_explains_transferable_slot_methods():
    response = build_structure_preview(
        sample=SampleVideoInput(
            title="咖啡拉花样例",
            duration=20,
            shot_count=6,
            transcript_summary="先用拉花特写吸引注意。再展示手作过程和门店氛围。最后引导到店打卡。",
        ),
        content=NewContentInput(
            topic="精品咖啡店开业短视频",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花", "新店开业优惠"],
            available_assets=["开头吸引镜头", "使用过程镜头"],
        ),
    )

    hook = response.template.script_pattern[0]

    assert hook.role == "吸引注意"
    assert hook.method == "结果先行 + 视觉记忆点"
    assert hook.intent == "让观众在前几秒理解为什么值得继续看"
    assert hook.rhythm == "前段快进入，字幕和画面同时给出主信息"
    assert "保留" in hook.transferable_rule
    assert "不复制" in hook.non_transferable
    assert "标题" in hook.packaging_intent


def test_build_structure_preview_explains_mapping_reasoning_and_support():
    response = build_structure_preview(
        sample=SampleVideoInput(
            title="咖啡拉花样例",
            duration=20,
            shot_count=6,
            transcript_summary="先用拉花特写吸引注意。再展示手作过程和门店氛围。最后引导到店打卡。",
        ),
        content=NewContentInput(
            topic="精品咖啡店开业短视频",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花", "新店开业优惠"],
            available_assets=["开头吸引镜头", "使用过程镜头"],
        ),
    )

    mapping_lookup = {item.slot_id: item for item in response.transfer_plan.mappings}
    hook_mapping = mapping_lookup["hook"]
    selling_mapping = mapping_lookup["selling_points"]

    assert hook_mapping.source_method == "结果先行 + 视觉记忆点"
    assert "巷口手作咖啡" in hook_mapping.target_adaptation
    assert "只迁移方法" in hook_mapping.reasoning
    assert hook_mapping.asset_requirement == "开头吸引镜头"
    assert "标题" in hook_mapping.packaging_plan
    assert "卡片" in selling_mapping.fallback_strategy


def test_build_structure_preview_returns_structured_packaging_tracks():
    response = build_structure_preview(
        sample=SampleVideoInput(
            title="咖啡拉花样例",
            duration=20,
            shot_count=6,
            transcript_summary="先用拉花特写吸引注意。再展示手作过程和门店氛围。最后引导到店打卡。",
        ),
        content=NewContentInput(
            topic="精品咖啡店开业短视频",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花", "新店开业优惠"],
            available_assets=["开头吸引镜头", "使用过程镜头"],
        ),
        variant="high_click",
    )

    mapping_lookup = {item.slot_id: item for item in response.transfer_plan.mappings}
    hook_packaging = mapping_lookup["hook"].packaging
    selling_packaging = mapping_lookup["selling_points"].packaging
    cta_packaging = mapping_lookup["cta"].packaging

    assert hook_packaging.title_card == "标题卡片：巷口手作咖啡 为什么值得停下来"
    assert hook_packaging.caption_density == "高密度"
    assert "巷口手作咖啡" in hook_packaging.emphasis_words
    assert "反差" in hook_packaging.transition_hint
    assert "封面候选" in hook_packaging.cover_hint
    assert selling_packaging.card_text.startswith("卖点卡片：")
    assert cta_packaging.card_text.startswith("行动号召：")

    card_tracks = [track for track in response.composition.tracks if track.type == "card"]
    card_texts = [track.text for track in card_tracks]
    assert hook_packaging.card_text in card_texts
    assert selling_packaging.card_text in card_texts
    assert cta_packaging.card_text in card_texts


def test_build_structure_preview_applies_slot_level_overrides():
    response = build_structure_preview(
        sample=SampleVideoInput(
            title="咖啡样例",
            duration=20,
            shot_count=6,
            transcript_summary="先用拉花特写吸引注意。再展示手作过程和门店氛围。最后引导到店打卡。",
        ),
        content=NewContentInput(
            topic="咖啡店开业短视频",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花", "新店开业优惠"],
            available_assets=["开头吸引镜头", "使用过程镜头"],
        ),
        mapping_overrides=[
            TransferMappingOverride(
                slot_id="hook",
                target_message="先讲开业前三天限时买一送一",
                sample_evidence="样例开头用拉花特写 + 开业字幕抢注意力",
            ),
            TransferMappingOverride(
                slot_id="selling_points",
                asset_strategy="缺商品特写时，先上优惠卡片，再补环境镜头",
            ),
        ],
    )

    slot_lookup = {slot.id: slot for slot in response.template.script_pattern}
    assert slot_lookup["hook"].sample_evidence == "样例开头用拉花特写 + 开业字幕抢注意力"

    beat_lookup = {item.slot_id: item.evidence for item in response.template.analysis_summary.narrative_beats}
    assert beat_lookup["hook"] == "样例开头用拉花特写 + 开业字幕抢注意力"

    mapping_lookup = {item.slot_id: item for item in response.transfer_plan.mappings}
    assert mapping_lookup["hook"].target_message == "先讲开业前三天限时买一送一"
    assert mapping_lookup["selling_points"].asset_strategy == "缺商品特写时，先上优惠卡片，再补环境镜头"

    card_texts = [track.text for track in response.composition.tracks if track.type == "card"]
    assert "缺商品特写时，先上优惠卡片，再补环境镜头" in card_texts


def test_build_structure_preview_can_use_saved_template_structure():
    saved_template = TemplateStructure(
        title="已保存的咖啡模板",
        script_pattern=[
            StructureSlot(
                id="hook",
                label="Hook",
                start=0,
                duration=4.0,
                purpose="开头制造注意力",
                required_asset="开头吸引镜头",
                sample_evidence="模板里的开头依据",
            ),
            StructureSlot(
                id="selling_points",
                label="卖点展开",
                start=4.0,
                duration=8.0,
                purpose="连续推进核心卖点",
                required_asset="商品特写镜头",
                sample_evidence="模板里的卖点依据",
            ),
            StructureSlot(
                id="usage",
                label="使用过程",
                start=12.0,
                duration=5.0,
                purpose="展示真实使用语境",
                required_asset="使用过程镜头",
                sample_evidence="模板里的使用依据",
            ),
            StructureSlot(
                id="cta",
                label="CTA",
                start=17.0,
                duration=3.0,
                purpose="收束行动号召",
                required_asset="结尾 CTA 镜头",
                sample_evidence="模板里的 CTA 依据",
            ),
        ],
        rhythm_summary="4-8-5-3 的固定节奏",
        packaging_notes=["模板包装点"],
        analysis_summary=SampleAnalysisSummary(
            headline="模板分析",
            metrics=[SampleAnalysisMetric(label="时长", value="20.0s", detail="模板节奏")],
            narrative_beats=[
                SampleAnalysisBeat(slot_id="hook", label="Hook", evidence="模板里的开头依据"),
                SampleAnalysisBeat(slot_id="selling_points", label="卖点展开", evidence="模板里的卖点依据"),
                SampleAnalysisBeat(slot_id="usage", label="使用过程", evidence="模板里的使用依据"),
                SampleAnalysisBeat(slot_id="cta", label="CTA", evidence="模板里的 CTA 依据"),
            ],
            packaging_signals=["模板包装点"],
        ),
    )

    response = build_structure_preview(
        sample=SampleVideoInput(
            title="完全不同的样例",
            duration=36,
            shot_count=10,
            transcript_summary="这段样例不该决定最终结构。",
        ),
        content=NewContentInput(
            topic="咖啡店开业短视频",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花", "新店开业优惠"],
            available_assets=["开头吸引镜头", "使用过程镜头"],
        ),
        template_override=saved_template,
    )

    slot_lookup = {slot.id: slot for slot in response.template.script_pattern}
    assert response.template.title == "已保存的咖啡模板"
    assert response.template.rhythm_summary == "4-8-5-3 的固定节奏"
    assert slot_lookup["hook"].duration == 4.0
    assert slot_lookup["cta"].start == 17.0
    assert response.composition.duration == 20.0


def test_build_structure_preview_applies_output_variant_styles():
    click_response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花", "新店开业优惠"],
            available_assets=["开头吸引镜头", "使用过程镜头"],
        ),
        variant="high_click",
    )
    conversion_response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花", "新店开业优惠"],
            available_assets=["开头吸引镜头", "使用过程镜头"],
        ),
        variant="high_conversion",
    )
    rhythm_response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花", "新店开业优惠"],
            available_assets=["开头吸引镜头", "使用过程镜头"],
        ),
        variant="fast_rhythm",
    )

    click_mapping_lookup = {item.slot_id: item for item in click_response.transfer_plan.mappings}
    conversion_mapping_lookup = {item.slot_id: item for item in conversion_response.transfer_plan.mappings}
    rhythm_slot_lookup = {item.id: item for item in rhythm_response.template.script_pattern}

    assert click_response.transfer_plan.variant == "high_click"
    assert "高点击版" in click_response.transfer_plan.title
    assert "前 2 秒" in click_mapping_lookup["hook"].target_message
    assert "强钩子" in click_response.template.packaging_notes

    assert conversion_response.transfer_plan.variant == "high_conversion"
    assert "高转化版" in conversion_response.transfer_plan.title
    assert "行动理由" in conversion_mapping_lookup["cta"].target_message
    assert "转化 CTA" in conversion_response.template.packaging_notes

    assert rhythm_response.transfer_plan.variant == "fast_rhythm"
    assert "高节奏版" in rhythm_response.transfer_plan.title
    assert rhythm_slot_lookup["hook"].duration < 3
    assert rhythm_response.composition.duration < 20
