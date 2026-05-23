from app.models import (
    MaterialRequestTask,
    NewContentInput,
    SampleAnalysisBeat,
    SampleAnalysisMetric,
    SampleAnalysisSummary,
    SampleVideoInput,
    StructureSlot,
    TemplateStructure,
    TransferMappingOverride,
    UserSlotAsset,
)
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
    gap_lookup = {gap.slot_id: gap for gap in response.transfer_plan.gaps}
    assert gap_lookup["selling_points"].suggested_asset_type == "商品卖点特写"
    assert any("产品特写" in item for item in gap_lookup["selling_points"].suggested_shots)
    assert any("字幕" in item for item in gap_lookup["cta"].pickup_checklist)
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
