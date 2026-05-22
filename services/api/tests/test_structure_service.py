from app.models import NewContentInput, SampleVideoInput
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
