from app.domain.structure.input_normalizer import (
    apply_delivered_material_tasks_to_content,
    apply_uploaded_slot_assets_to_content,
    build_material_request_sheet,
)
from app.models import MaterialRequestTask, NewContentInput, StructureSlot, TemplateStructure, UserSlotAsset


def test_apply_delivered_material_tasks_to_content_marks_delivered_slot_assets_available():
    template = TemplateStructure(
        title="模板",
        script_pattern=[
            StructureSlot(
                id="selling_points",
                label="卖点展开",
                start=0,
                duration=5,
                purpose="推进卖点",
                required_asset="商品特写镜头",
                sample_evidence="样例卖点段",
            ),
            StructureSlot(
                id="cta",
                label="CTA",
                start=5,
                duration=3,
                purpose="收束转化",
                required_asset="结尾 CTA 镜头",
                sample_evidence="样例结尾段",
            ),
        ],
        rhythm_summary="前快后收",
        packaging_notes=[],
        analysis_summary={"headline": "分析"},
    )
    content = NewContentInput(topic="新品短视频", available_assets=["开头吸引镜头"])

    updated = apply_delivered_material_tasks_to_content(
        template,
        content,
        request_sheet=[
            MaterialRequestTask(slot_id="selling_points", status="已拍"),
            MaterialRequestTask(slot_id="cta", status="待补拍"),
        ],
    )

    assert updated.available_assets == ["开头吸引镜头", "商品特写镜头"]


def test_uploaded_slot_assets_and_request_sheet_follow_template_slot_order():
    template = TemplateStructure(
        title="模板",
        script_pattern=[
            StructureSlot(
                id="hook",
                label="Hook",
                start=0,
                duration=2,
                purpose="开头吸引",
                required_asset="开头吸引镜头",
                sample_evidence="样例开头",
            ),
            StructureSlot(
                id="selling_points",
                label="卖点展开",
                start=2,
                duration=5,
                purpose="推进卖点",
                required_asset="商品特写镜头",
                sample_evidence="样例卖点段",
            ),
        ],
        rhythm_summary="前快后稳",
        packaging_notes=[],
        analysis_summary={"headline": "分析"},
    )
    content = NewContentInput(
        topic="新品短视频",
        uploaded_assets=[
            UserSlotAsset(slot_id="selling_points", filename="selling.mp4", public_url="/materials/selling.mp4"),
            UserSlotAsset(slot_id="hook", filename="hook.mp4"),
        ],
    )

    updated = apply_uploaded_slot_assets_to_content(template, content)
    request_sheet = build_material_request_sheet(
        template,
        request_sheet=[
            MaterialRequestTask(slot_id="selling_points", status="待补拍"),
            MaterialRequestTask(slot_id="hook", status="已交付"),
        ],
    )

    assert updated.available_assets == ["商品特写镜头"]
    assert [item.slot_id for item in request_sheet] == ["hook", "selling_points"]
