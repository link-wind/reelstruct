from app.models import NewContentInput, SampleVideoInput, TransferMappingOverride
from app.structure_service import build_structure_preview


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
    assert any(track.type == "card" for track in response.composition.tracks)
    assert response.composition.duration == 30


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
