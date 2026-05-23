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
from app.video_understanding.schemas import (
    AIPackagingStructure,
    AIRhythmStructure,
    AIStructureAnalysis,
    KeyframeEvidence,
    RhythmMetrics,
    ShotVisualAnalysis,
    VideoMetadata,
    VideoShot,
    VideoSignal,
    VideoStructureSegment,
)
from app.video_understanding.pipeline import build_ai_structure_template, build_fallback_structure_template
from app.video_understanding.template_adapter import adapt_ai_structure_to_template


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


def test_build_ai_structure_template_runs_video_understanding_pipeline(monkeypatch, tmp_path):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"not a real video because dependencies are patched")
    signal = VideoSignal(
        metadata=VideoMetadata(duration=5, fps=30, width=720, height=1280, format_name="mov"),
        shot_count=1,
        detection_method="scene_detect",
        rhythm_metrics=RhythmMetrics(avg_shot_duration=5, cut_density="slow"),
        shots=[VideoShot(index=1, start=0, end=5, duration=5, keyframe_time=2.5)],
    )
    keyframes = [
        KeyframeEvidence(
            shot_index=1,
            keyframe_time=2.5,
            local_path=str(tmp_path / "shot.jpg"),
            public_url="/keyframes/test/shot.jpg",
        )
    ]
    visual = [ShotVisualAnalysis(shot_index=1, visual_summary="结果画面", confidence=0.8)]
    analysis = AIStructureAnalysis(
        headline="AI 识别出结果开场",
        segments=[
            VideoStructureSegment(
                id="result_hook",
                label="结果开场",
                type="hook",
                start=0,
                end=5,
                shot_indices=[1],
                purpose="快速吸引注意",
                method="结果先行",
                evidence="第 1 镜是结果画面",
                rhythm="单镜头停留",
                packaging="大标题",
                required_asset="结果吸引镜头",
                transferable_rule="迁移结果先行方法。",
                non_transferable="不复制具体结果。",
                confidence=0.86,
            )
        ],
        confidence=0.84,
    )
    calls: list[str] = []

    def fake_detect(path):
        calls.append(f"detect:{path.name}")
        return signal

    def fake_extract(path, shots, *, output_dir, public_prefix):
        calls.append(f"extract:{len(shots)}:{public_prefix}")
        return keyframes

    def fake_visuals(items):
        calls.append(f"visuals:{len(items)}")
        return visual

    def fake_decompose(*, title, signal, evidence, transcript_summary):
        calls.append(f"decompose:{title}:{len(evidence)}:{transcript_summary}")
        return analysis

    monkeypatch.setattr("app.video_understanding.pipeline.detect_video_signal", fake_detect)
    monkeypatch.setattr("app.video_understanding.pipeline.extract_keyframes", fake_extract)
    monkeypatch.setattr("app.video_understanding.pipeline.analyze_keyframe_visuals", fake_visuals)
    monkeypatch.setattr("app.video_understanding.pipeline.decompose_video_structure_with_ai", fake_decompose)

    template = build_ai_structure_template(
        sample=SampleVideoInput(title="样例", transcript_summary="字幕摘要"),
        sample_local_path=str(video_path),
        keyframes_dir=tmp_path / "keyframes",
        public_prefix="/keyframes/test",
    )

    assert calls == [
        "detect:sample.mp4",
        "extract:1:/keyframes/test",
        "visuals:1",
        "decompose:样例:1:字幕摘要",
    ]
    assert template.analysis_summary.source == "ai"
    assert template.script_pattern[0].evidence_shot_indices == [1]


def test_build_fallback_structure_template_marks_source_and_warning():
    template = build_fallback_structure_template(
        sample=SampleVideoInput(title="样例", duration=20, shot_count=6),
        reason="OPENAI_API_KEY is required",
    )

    assert template.analysis_summary.source == "fallback"
    assert template.analysis_summary.warnings == ["AI 结构拆解未完成：OPENAI_API_KEY is required"]


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
