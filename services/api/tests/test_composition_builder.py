from app.domain.structure.composition_builder import build_composition_spec
from app.models import (
    MaterialGap,
    NewContentInput,
    PackagingPlan,
    SampleVideoInput,
    SlotFillDecision,
    SlotQueryProfile,
    SlotRetrievalPlan,
    StructureCoverageResult,
    StructureSlot,
    TemplateStructure,
    TimelinePatch,
    TimelineTrackUpdate,
    TransferMapping,
    TransferPlan,
    UserSlotAsset,
)


def test_build_composition_spec_prefers_patch_asset_and_inserts_patch_cards():
    template = TemplateStructure(
        title="咖啡模板",
        script_pattern=[
            StructureSlot(
                id="selling_points",
                label="卖点展开",
                start=0,
                duration=4,
                purpose="连续推进核心卖点",
                required_asset="商品特写镜头",
                sample_evidence="样例中段给卖点特写",
            )
        ],
        rhythm_summary="中段密集推进",
        packaging_notes=[],
        analysis_summary={"headline": "模板分析"},
    )
    transfer_plan = TransferPlan(
        title="巷口手作咖啡 结构迁移方案",
        target_topic="咖啡店开业",
        mappings=[
            TransferMapping(
                slot_id="selling_points",
                source_label="卖点展开",
                target_message="突出手作拉花和新店开业优惠",
                asset_strategy="优先复用现有成品特写",
                packaging=PackagingPlan(card_text="卖点卡片：手作拉花 / 开业优惠"),
            )
        ],
        gaps=[
            MaterialGap(
                slot_id="selling_points",
                missing_asset="商品特写镜头",
                impact="缺少特写支撑",
                fill_strategy="先复用，再补字幕",
                retrieval_plan=SlotRetrievalPlan(),
                slot_fill_decision=SlotFillDecision(
                    slot_id="selling_points",
                    decision_type="reuse_with_packaging",
                    selected_asset_id="detail-shot.mp4",
                    actions=["补一张优惠卡片"],
                ),
                slot_query_profile=SlotQueryProfile(),
                coverage_result=StructureCoverageResult(),
                timeline_patches=[
                    TimelinePatch(
                        patch_id="patch-selling",
                        slot_id="selling_points",
                        operation="replace_slot_media",
                        target_start=0,
                        target_end=4,
                        source_asset_id="detail-shot.mp4",
                        track_updates=[
                            TimelineTrackUpdate(
                                type="card",
                                action="insert",
                                text="限时开业优惠",
                                duration=1.8,
                            )
                        ],
                    )
                ],
            )
        ],
    )
    content = NewContentInput(
        topic="咖啡店开业",
        product_name="巷口手作咖啡",
        uploaded_assets=[
            UserSlotAsset(
                slot_id="selling_points",
                filename="slot-default.mp4",
                local_path="/tmp/slot-default.mp4",
                public_url="/materials/slot-default.mp4",
            ),
            UserSlotAsset(
                slot_id="material_pool",
                filename="detail-shot.mp4",
                local_path="/tmp/detail-shot.mp4",
                public_url="/materials/detail-shot.mp4",
                analysis={
                    "evidence_chunks": [
                        {
                            "asset_id": "detail-shot.mp4",
                            "chunk_id": "chunk-1",
                        }
                    ]
                },
            ),
        ],
    )

    composition = build_composition_spec(template, transfer_plan, content)

    video_tracks = [track for track in composition.tracks if track.type == "video"]
    card_tracks = [track for track in composition.tracks if track.type == "card"]

    assert len(video_tracks) == 1
    assert video_tracks[0].asset_local_path == "/tmp/detail-shot.mp4"
    assert video_tracks[0].asset_public_url == "/materials/detail-shot.mp4"
    assert any(track.text == "卖点卡片：手作拉花 / 开业优惠" for track in card_tracks)
    assert any(track.text == "限时开业优惠" for track in card_tracks)
