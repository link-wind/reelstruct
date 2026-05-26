from app.models import SampleVideoInput
from app.video_understanding.pipeline import (
    DEFAULT_KEYFRAMES_DIR,
    build_ai_or_fallback_structure_template,
    build_ai_structure_template,
    build_fallback_structure_template,
)
from app.video_understanding.schemas import (
    CreativeBeat,
    EvidenceBackedSegment,
    FrameEvidence,
    FrameOCRText,
    RhythmMetrics,
    ShotTextAlignment,
    ShotEvidenceGraph,
    ShotEvidenceNode,
    ShotUnderstanding,
    TranscriptSegment,
    VideoMetadata,
    VideoShot,
    VideoSignal,
)


def test_build_ai_structure_template_uses_graph_pipeline(monkeypatch, tmp_path):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"not a real video because dependencies are patched")
    signal = VideoSignal(
        metadata=VideoMetadata(duration=5, fps=30, width=720, height=1280, format_name="mov"),
        shot_count=2,
        detection_method="scene_detect",
        rhythm_metrics=RhythmMetrics(avg_shot_duration=5, cut_density="slow"),
        shots=[
            VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
            VideoShot(index=2, start=2, end=5, duration=3, keyframe_time=3.5),
        ],
    )
    frames = [
        FrameEvidence(
            shot_index=1,
            frame_index=1,
            time=1,
            role="middle",
            local_path=str(tmp_path / "shot_1.jpg"),
            public_url="/keyframes/test/shot_1.jpg",
        ),
        FrameEvidence(
            shot_index=2,
            frame_index=1,
            time=3.5,
            role="middle",
            local_path=str(tmp_path / "shot_2.jpg"),
            public_url="/keyframes/test/shot_2.jpg",
        ),
    ]
    graph = ShotEvidenceGraph(
        beats=[
            CreativeBeat(
                beat_id="beat_1",
                label="开场",
                shot_indices=[1, 2],
                start=0,
                end=5,
                function="hook",
                reason="连续开场",
            )
        ],
        segments=[
            EvidenceBackedSegment(
                segment_id="seg_1",
                label="痛点 Hook",
                beat_ids=["beat_1"],
                shot_indices=[1, 2],
                start=0,
                end=5,
                purpose="快速吸引注意",
                method="痛点开场",
                evidence=["Shot 1-2 开场"],
                rhythm="快",
                packaging="大标题",
                transferable_rule="先痛点",
                non_transferable="原商品",
                required_asset="痛点场景",
                confidence=0.8,
            )
        ],
    )
    calls: list[str] = []

    def fake_detect(path):
        calls.append(f"detect:{path.name}")
        return signal

    def fake_extract_frames(path, shots, *, output_dir, public_prefix):
        calls.append(f"frames:{len(shots)}:{public_prefix}")
        return frames

    def fake_build_graph_with_ai(*, signal, frames, sample, transcript_texts, ocr_texts, warnings):
        calls.append(
            f"graph:{signal.shot_count}:{len(frames)}:{len(transcript_texts)}:{len(ocr_texts)}:{len(warnings)}:{sample.title}"
        )
        return graph

    monkeypatch.setattr("app.video_understanding.pipeline.detect_video_signal", fake_detect)
    monkeypatch.setattr("app.video_understanding.pipeline.extract_frame_evidence", fake_extract_frames)
    monkeypatch.setattr(
        "app.video_understanding.pipeline.recognize_frames_with_ocr",
        lambda frames: calls.append(f"ocr:{len(frames)}") or type(
            "OCRResult",
            (),
            {"texts": [], "warnings": []},
        )(),
    )
    monkeypatch.setattr(
        "app.video_understanding.pipeline.transcribe_video_with_asr",
        lambda path, *, work_dir: calls.append(f"asr:{path.name}:{work_dir.name}") or type(
            "ASRResult",
            (),
            {"segments": [], "warnings": []},
        )(),
    )
    monkeypatch.setattr("app.video_understanding.pipeline.build_graph_with_ai", fake_build_graph_with_ai)

    template = build_ai_structure_template(
        sample=SampleVideoInput(title="样例", transcript_summary="字幕摘要"),
        sample_local_path=str(video_path),
        keyframes_dir=tmp_path / "keyframes",
        public_prefix="/keyframes/test",
    )

    assert calls == [
        "detect:sample.mp4",
        "frames:2:/keyframes/test",
        "graph:2:2:0:0:0:样例",
    ]
    assert template.analysis_summary.source == "ai"
    assert template.script_pattern[0].id == "seg_1"
    assert template.script_pattern[0].evidence_shot_indices == [1, 2]


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


def test_build_ai_or_fallback_structure_template_falls_back_when_graph_has_no_segments(monkeypatch, tmp_path):
    video_path = tmp_path / "empty-graph.mp4"
    video_path.write_bytes(b"empty graph")

    monkeypatch.setattr(
        "app.video_understanding.pipeline.build_ai_structure_template",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("AI graph aggregation returned no segments")),
    )

    template = build_ai_or_fallback_structure_template(
        sample=SampleVideoInput(title="空图谱样例", duration=18, shot_count=5),
        sample_local_path=str(video_path),
    )

    assert template.analysis_summary.source == "fallback"
    assert template.script_pattern
    assert template.analysis_summary.warnings == ["AI 结构拆解未完成：AI graph aggregation returned no segments"]


def test_default_keyframes_dir_points_to_api_storage_keyframes():
    assert DEFAULT_KEYFRAMES_DIR.parts[-4:] == ("services", "api", "storage", "keyframes")
    assert "services/services" not in str(DEFAULT_KEYFRAMES_DIR)


def test_build_graph_with_ai_understands_shots_before_aggregation(monkeypatch):
    from app.video_understanding.pipeline import build_graph_with_ai

    signal = VideoSignal(
        metadata=VideoMetadata(duration=2, fps=30, width=720, height=1280, format_name="mov"),
        shot_count=1,
        detection_method="scene_detect",
        rhythm_metrics=RhythmMetrics(avg_shot_duration=2, cut_density="slow"),
        shots=[VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)],
    )
    calls: list[str] = []

    def fake_understand(graph):
        calls.append(f"understand:{len(graph.analysis_units)}:{graph.shots[0].understanding.confidence}")
        return graph.model_copy(
            update={
                "shots": [
                    graph.shots[0].model_copy(
                        update={
                            "understanding": ShotUnderstanding(
                                shot_index=1,
                                visual_summary="人物口播展示产品",
                                subject="人物和产品",
                                confidence=0.9,
                            )
                        }
                    )
                ]
            }
        )

    def fake_aggregate(graph):
        calls.append(f"aggregate:{graph.shots[0].understanding.visual_summary}")
        return graph.model_construct(
            relations=[],
            beats=[],
            segments=[
                EvidenceBackedSegment(
                    segment_id="seg_1",
                    label="产品介绍",
                    shot_indices=[1],
                    start=0,
                    end=2,
                    evidence=[graph.shots[0].understanding.visual_summary],
                )
            ],
            warnings=[],
        )

    monkeypatch.setattr("app.video_understanding.pipeline.understand_shots_with_ai", fake_understand)
    monkeypatch.setattr("app.video_understanding.pipeline.aggregate_graph_structure_with_ai", fake_aggregate)

    graph = build_graph_with_ai(
        signal=signal,
        frames=[],
        sample=SampleVideoInput(title="样例"),
        transcript_texts=[],
        ocr_texts=[],
        warnings=[],
    )

    assert calls == ["understand:1:0", "aggregate:人物口播展示产品"]
    assert graph.segments[0].evidence == ["人物口播展示产品"]


def test_build_graph_with_ai_builds_analysis_units_before_understanding(monkeypatch):
    from app.video_understanding.pipeline import build_graph_with_ai

    signal = VideoSignal(
        metadata=VideoMetadata(duration=10, fps=30, width=720, height=1280, format_name="mov"),
        shot_count=20,
        detection_method="pyscenedetect_adaptive",
        rhythm_metrics=RhythmMetrics(avg_shot_duration=0.5, cut_density="fast"),
        shots=[
            VideoShot(
                index=index,
                start=round((index - 1) * 0.5, 3),
                end=round(index * 0.5, 3),
                duration=0.5,
                keyframe_time=round((index - 0.5) * 0.5, 3),
            )
            for index in range(1, 21)
        ],
    )
    captured = {}

    def fake_understand(graph):
        captured["unit_count"] = len(graph.analysis_units)
        captured["first_unit_shots"] = graph.analysis_units[0].shot_indices
        return graph

    def fake_aggregate(graph):
        return graph.model_construct(
            relations=[],
            beats=[],
            segments=[
                EvidenceBackedSegment(
                    segment_id="seg_1",
                    label="快速开场",
                    shot_indices=graph.analysis_units[0].shot_indices,
                    start=graph.analysis_units[0].start,
                    end=graph.analysis_units[0].end,
                    evidence=["unit grouped evidence"],
                )
            ],
            warnings=[],
        )

    monkeypatch.setattr("app.video_understanding.pipeline.understand_shots_with_ai", fake_understand)
    monkeypatch.setattr("app.video_understanding.pipeline.aggregate_graph_structure_with_ai", fake_aggregate)

    graph = build_graph_with_ai(
        signal=signal,
        frames=[],
        sample=SampleVideoInput(title="长视频样例"),
        transcript_texts=[],
        ocr_texts=[],
        warnings=[],
    )

    assert captured["unit_count"] < signal.shot_count
    assert captured["first_unit_shots"] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert graph.analysis_units[0].unit_id == "unit_1"
    assert graph.segments[0].shot_indices == [1, 2, 3, 4, 5, 6, 7, 8]


def test_build_ai_structure_template_aligns_text_evidence_before_graph(monkeypatch, tmp_path):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"video")
    signal = VideoSignal(
        metadata=VideoMetadata(duration=5, fps=30, width=720, height=1280, format_name="mov"),
        shot_count=2,
        detection_method="scene_detect",
        rhythm_metrics=RhythmMetrics(avg_shot_duration=2.5, cut_density="medium"),
        shots=[
            VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
            VideoShot(index=2, start=2, end=5, duration=3, keyframe_time=3.5),
        ],
    )
    captured = {}
    graph = ShotEvidenceGraph(
        segments=[
            EvidenceBackedSegment(
                segment_id="seg_1",
                label="Hook",
                shot_indices=[1],
                start=0,
                end=2,
                evidence=["ASR"],
            )
        ]
    )

    class FakeASRResult:
        segments = [TranscriptSegment(start=1, end=3, text="早上来不及吃饭？")]
        warnings = ["ASR warning"]

    class FakeOCRResult:
        texts = [
            FrameOCRText(
                shot_index=1,
                frame_index=1,
                frame_time=1.0,
                text="限时优惠",
                position="top",
                confidence=0.91,
            )
        ]
        warnings = ["OCR warning"]

    monkeypatch.setattr("app.video_understanding.pipeline.detect_video_signal", lambda path: signal)
    monkeypatch.setattr("app.video_understanding.pipeline.extract_frame_evidence", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.video_understanding.pipeline.recognize_frames_with_ocr", lambda frames: FakeOCRResult())
    monkeypatch.setattr("app.video_understanding.pipeline.transcribe_video_with_asr", lambda path, *, work_dir: FakeASRResult())

    def fake_build_graph_with_ai(*, signal, frames, sample, transcript_texts, ocr_texts, warnings):
        captured["transcript_texts"] = transcript_texts
        captured["ocr_texts"] = ocr_texts
        captured["warnings"] = warnings
        return graph

    monkeypatch.setattr("app.video_understanding.pipeline.build_graph_with_ai", fake_build_graph_with_ai)

    build_ai_structure_template(
        sample=SampleVideoInput(title="样例"),
        sample_local_path=str(video_path),
        keyframes_dir=tmp_path / "keyframes",
        enable_text_evidence=True,
    )

    assert [item.shot_index for item in captured["transcript_texts"]] == [1, 2]
    assert captured["transcript_texts"][0].text == "早上来不及吃饭？"
    assert captured["ocr_texts"][0].text == "限时优惠"
    assert captured["warnings"] == ["OCR warning", "ASR warning"]


def test_build_ai_structure_template_does_not_run_ocr_or_asr_by_default(monkeypatch, tmp_path):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"video")
    signal = VideoSignal(
        metadata=VideoMetadata(duration=2, fps=30, width=720, height=1280, format_name="mov"),
        shot_count=1,
        detection_method="pyscenedetect_adaptive",
        rhythm_metrics=RhythmMetrics(avg_shot_duration=2, cut_density="slow"),
        shots=[VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)],
    )
    captured = {}
    graph = ShotEvidenceGraph(
        segments=[
            EvidenceBackedSegment(
                segment_id="seg_1",
                label="Hook",
                shot_indices=[1],
                start=0,
                end=2,
                evidence=["visual only"],
            )
        ]
    )

    monkeypatch.setattr("app.video_understanding.pipeline.detect_video_signal", lambda path: signal)
    monkeypatch.setattr("app.video_understanding.pipeline.extract_frame_evidence", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "app.video_understanding.pipeline.recognize_frames_with_ocr",
        lambda frames: (_ for _ in ()).throw(AssertionError("OCR should be manual")),
    )
    monkeypatch.setattr(
        "app.video_understanding.pipeline.transcribe_video_with_asr",
        lambda path, *, work_dir: (_ for _ in ()).throw(AssertionError("ASR should be manual")),
    )

    def fake_build_graph_with_ai(*, signal, frames, sample, transcript_texts, ocr_texts, warnings):
        captured["transcript_texts"] = transcript_texts
        captured["ocr_texts"] = ocr_texts
        captured["warnings"] = warnings
        return graph

    monkeypatch.setattr("app.video_understanding.pipeline.build_graph_with_ai", fake_build_graph_with_ai)

    build_ai_structure_template(
        sample=SampleVideoInput(title="样例"),
        sample_local_path=str(video_path),
        keyframes_dir=tmp_path / "keyframes",
    )

    assert captured == {"transcript_texts": [], "ocr_texts": [], "warnings": []}


def test_build_ai_structure_template_uses_provided_text_evidence_graph(monkeypatch, tmp_path):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"video")
    signal = VideoSignal(
        metadata=VideoMetadata(duration=2, fps=30, width=720, height=1280, format_name="mov"),
        shot_count=1,
        detection_method="pyscenedetect_adaptive",
        rhythm_metrics=RhythmMetrics(avg_shot_duration=2, cut_density="slow"),
        shots=[VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)],
    )
    provided_graph = ShotEvidenceGraph(
        warnings=["manual evidence warning"],
        shots=[
            ShotEvidenceNode(
                shot=signal.shots[0],
                ocr_texts=[
                    FrameOCRText(
                        shot_index=1,
                        frame_index=1,
                        frame_time=1,
                        text="手动 OCR 字幕",
                        confidence=0.9,
                    )
                ],
                transcript_texts=[
                    ShotTextAlignment(
                        shot_index=1,
                        text="手动 ASR 口播",
                        source_start=0.2,
                        source_end=1.5,
                        overlap_ratio=0.65,
                    )
                ],
            )
        ],
    )
    captured = {}
    graph = ShotEvidenceGraph(
        segments=[
            EvidenceBackedSegment(
                segment_id="seg_1",
                label="Hook",
                shot_indices=[1],
                start=0,
                end=2,
                evidence=["manual text evidence"],
            )
        ]
    )

    monkeypatch.setattr("app.video_understanding.pipeline.detect_video_signal", lambda path: signal)
    monkeypatch.setattr("app.video_understanding.pipeline.extract_frame_evidence", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "app.video_understanding.pipeline.recognize_frames_with_ocr",
        lambda frames: (_ for _ in ()).throw(AssertionError("manual OCR should be reused")),
    )
    monkeypatch.setattr(
        "app.video_understanding.pipeline.transcribe_video_with_asr",
        lambda path, *, work_dir: (_ for _ in ()).throw(AssertionError("manual ASR should be reused")),
    )

    def fake_build_graph_with_ai(*, signal, frames, sample, transcript_texts, ocr_texts, warnings):
        captured["transcript_texts"] = transcript_texts
        captured["ocr_texts"] = ocr_texts
        captured["warnings"] = warnings
        return graph

    monkeypatch.setattr("app.video_understanding.pipeline.build_graph_with_ai", fake_build_graph_with_ai)

    build_ai_structure_template(
        sample=SampleVideoInput(title="样例"),
        sample_local_path=str(video_path),
        keyframes_dir=tmp_path / "keyframes",
        text_evidence_graph=provided_graph,
    )

    assert captured["ocr_texts"][0].text == "手动 OCR 字幕"
    assert captured["transcript_texts"][0].text == "手动 ASR 口播"
    assert captured["warnings"] == ["manual evidence warning"]
