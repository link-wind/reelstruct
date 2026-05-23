from app.models import SampleVideoInput
from app.video_understanding.pipeline import (
    build_ai_or_fallback_structure_template,
    build_ai_structure_template,
    build_fallback_structure_template,
)
from app.video_understanding.schemas import (
    AIStructureAnalysis,
    KeyframeEvidence,
    RhythmMetrics,
    ShotVisualAnalysis,
    VideoMetadata,
    VideoShot,
    VideoSignal,
    VideoStructureSegment,
)


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


def test_build_ai_or_fallback_structure_template_does_not_fake_ai_on_failure(monkeypatch, tmp_path):
    video_path = tmp_path / "broken.mp4"
    video_path.write_bytes(b"broken")

    def fail_ai_template(**_kwargs):
        raise RuntimeError("OPENAI_API_KEY is required")

    monkeypatch.setattr("app.video_understanding.pipeline.build_ai_structure_template", fail_ai_template)

    template = build_ai_or_fallback_structure_template(
        sample=SampleVideoInput(title="失败样例", duration=18, shot_count=5),
        sample_local_path=str(video_path),
    )

    assert template.analysis_summary.source == "fallback"
    assert template.analysis_summary.confidence == 0
    assert template.script_pattern[0].evidence_shot_indices == []
    assert template.analysis_summary.warnings == ["AI 结构拆解未完成：OPENAI_API_KEY is required"]
