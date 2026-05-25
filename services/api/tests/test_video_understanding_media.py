from pathlib import Path
import logging
import subprocess
from subprocess import CompletedProcess
from unittest.mock import patch

from app.video_understanding.keyframe_service import (
    FFMPEG_TIMEOUT_SECONDS,
    extract_frame_evidence,
    extract_keyframes,
    frame_sample_times,
)
from app.video_understanding.media_probe import probe_video_metadata
from app.video_understanding.schemas import VideoMetadata, VideoShot
from app.video_understanding.shot_detector import (
    _detect_scene_cut_times,
    _parse_cut_times,
    detect_video_signal,
    normalize_shots,
)


def test_probe_video_metadata_returns_real_duration_resolution_and_fps():
    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "vid_001.mp4"

    metadata = probe_video_metadata(fixture_path)

    assert metadata.duration > 0
    assert metadata.fps > 0
    assert metadata.width > 0
    assert metadata.height > 0
    assert metadata.format_name


def test_detect_video_signal_returns_shots_and_rhythm_metrics():
    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "vid_001.mp4"

    signal = detect_video_signal(fixture_path)

    assert signal.metadata.duration > 0
    assert signal.shot_count == len(signal.shots)
    assert signal.shot_count >= 1
    assert signal.shots[0].start == 0
    assert signal.shots[-1].end <= signal.metadata.duration + 0.1
    assert signal.rhythm_metrics.avg_shot_duration > 0
    assert signal.rhythm_metrics.cut_density in {"slow", "medium", "fast"}
    assert signal.detection_method in {
        "scene_detect",
        "pyscenedetect_adaptive",
        "pyscenedetect_content",
        "ffmpeg_scene_detect",
        "uniform_fallback",
    }


def test_extract_keyframes_writes_real_image_files(tmp_path):
    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "vid_001.mp4"
    signal = detect_video_signal(fixture_path)

    keyframes = extract_keyframes(
        fixture_path,
        signal.shots[:2],
        output_dir=tmp_path / "keyframes",
        public_prefix="/keyframes",
    )

    assert len(keyframes) == min(2, len(signal.shots))
    for keyframe in keyframes:
        path = Path(keyframe.local_path)
        assert path.is_file()
        assert path.suffix == ".jpg"
        assert keyframe.public_url.startswith("/keyframes/")


def test_frame_sample_times_uses_one_middle_frame_for_very_short_shot():
    assert frame_sample_times(start=0.0, end=0.6) == [("middle", 0.3)]


def test_frame_sample_times_keeps_raw_duration_boundary_in_very_short_bucket():
    assert frame_sample_times(start=0.0, end=0.7996) == [("middle", 0.4)]


def test_frame_sample_times_uses_middle_and_safe_end_for_short_shot():
    assert frame_sample_times(start=0.0, end=1.5) == [
        ("middle", 0.75),
        ("safe_end", 1.35),
    ]


def test_frame_sample_times_uses_start_middle_end_for_medium_shot():
    assert frame_sample_times(start=2.0, end=5.0) == [
        ("start", 2.15),
        ("middle", 3.5),
        ("end", 4.85),
    ]


def test_frame_sample_times_uses_quarters_for_long_shot():
    assert frame_sample_times(start=10.0, end=18.0) == [
        ("start", 10.15),
        ("third", 12.667),
        ("two_thirds", 15.333),
        ("end", 17.85),
    ]


def test_extract_frame_evidence_writes_multiple_frames_with_roles_and_times(tmp_path):
    shots = [VideoShot(index=2, start=2, end=5, duration=3, keyframe_time=3.5)]

    def fake_run(args, **kwargs):
        Path(args[-1]).write_bytes(b"jpg")
        return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with patch("app.video_understanding.keyframe_service.subprocess.run", side_effect=fake_run):
        frames = extract_frame_evidence(
            Path("sample.mp4"),
            shots,
            output_dir=tmp_path / "frames",
            public_prefix="/frames/",
        )

    assert [(frame.frame_index, frame.role, frame.time) for frame in frames] == [
        (1, "start", 2.15),
        (2, "middle", 3.5),
        (3, "end", 4.85),
    ]
    assert all(frame.shot_index == 2 for frame in frames)
    assert [Path(frame.local_path).name for frame in frames] == [
        "shot_0002_01_start_00002150.jpg",
        "shot_0002_02_middle_00003500.jpg",
        "shot_0002_03_end_00004850.jpg",
    ]
    assert [frame.public_url for frame in frames] == [
        "/frames/shot_0002_01_start_00002150.jpg",
        "/frames/shot_0002_02_middle_00003500.jpg",
        "/frames/shot_0002_03_end_00004850.jpg",
    ]


def test_extract_frame_evidence_retries_slot_with_keyframe_fallback_after_primary_failure(tmp_path):
    shots = [VideoShot(index=4, start=0.0, end=0.6, duration=0.6, keyframe_time=0.4)]
    attempted_ss_times: list[str] = []

    def fake_run(args, **kwargs):
        attempted_ss_times.append(args[args.index("-ss") + 1])
        if len(attempted_ss_times) == 2:
            Path(args[-1]).write_bytes(b"jpg")
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        return CompletedProcess(args=args, returncode=1, stdout="", stderr="first attempt failed")

    with patch("app.video_understanding.keyframe_service.subprocess.run", side_effect=fake_run):
        frames = extract_frame_evidence(
            Path("sample.mp4"),
            shots,
            output_dir=tmp_path / "frames",
            public_prefix="/frames",
        )

    assert attempted_ss_times == ["0.300", "0.400"]
    assert [(frame.frame_index, frame.role, frame.time) for frame in frames] == [(1, "middle", 0.4)]
    assert [Path(frame.local_path).name for frame in frames] == ["shot_0004_01_middle_00000400.jpg"]


def test_extract_keyframes_skips_when_ffmpeg_is_missing(tmp_path):
    shots = [VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)]

    with patch("app.video_understanding.keyframe_service.subprocess.run", side_effect=FileNotFoundError):
        keyframes = extract_keyframes(
            Path("sample.mp4"),
            shots,
            output_dir=tmp_path / "keyframes",
            public_prefix="/keyframes",
        )

    assert keyframes == []


def test_extract_keyframes_skips_when_ffmpeg_times_out(tmp_path):
    shots = [VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)]

    with patch(
        "app.video_understanding.keyframe_service.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=20),
    ):
        keyframes = extract_keyframes(
            Path("sample.mp4"),
            shots,
            output_dir=tmp_path / "keyframes",
            public_prefix="/keyframes",
        )

    assert keyframes == []


def test_extract_keyframes_skips_when_ffmpeg_fails(tmp_path):
    shots = [VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)]

    with patch(
        "app.video_understanding.keyframe_service.subprocess.run",
        return_value=CompletedProcess(args=["ffmpeg"], returncode=1, stdout="", stderr="bad input"),
    ):
        keyframes = extract_keyframes(
            Path("sample.mp4"),
            shots,
            output_dir=tmp_path / "keyframes",
            public_prefix="/keyframes",
        )

    assert keyframes == []


def test_extract_keyframes_passes_expected_ffmpeg_command_and_timeout(tmp_path):
    shots = [VideoShot(index=3, start=2, end=4, duration=2, keyframe_time=3.25)]

    def fake_run(args, **kwargs):
        Path(args[-1]).write_bytes(b"jpg")
        return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with patch("app.video_understanding.keyframe_service.subprocess.run", side_effect=fake_run) as run:
        keyframes = extract_keyframes(
            Path("sample.mp4"),
            shots,
            output_dir=tmp_path / "keyframes",
            public_prefix="/keyframes/",
        )

    assert len(keyframes) == 1
    assert "//" not in keyframes[0].public_url.removeprefix("/")
    command = run.call_args.args[0]
    assert "-ss" in command
    assert "3.250" in command
    assert "-frames:v" in command
    assert "1" in command
    assert "-q:v" in command
    assert "2" in command
    assert "-y" in command
    assert run.call_args.kwargs["timeout"] == FFMPEG_TIMEOUT_SECONDS


def test_extract_keyframes_extracts_only_representative_frame_for_compatibility(tmp_path):
    shots = [VideoShot(index=1, start=10, end=18, duration=8, keyframe_time=14)]

    def fake_run(args, **kwargs):
        Path(args[-1]).write_bytes(b"jpg")
        return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with patch("app.video_understanding.keyframe_service.subprocess.run", side_effect=fake_run) as run:
        keyframes = extract_keyframes(
            Path("sample.mp4"),
            shots,
            output_dir=tmp_path / "keyframes",
            public_prefix="/keyframes",
        )

    assert len(keyframes) == 1
    assert keyframes[0].keyframe_time == 14
    assert run.call_count == 1
    assert "14.000" in run.call_args.args[0]


def test_extract_keyframes_returns_successes_and_logs_partial_failures(tmp_path, caplog):
    shots = [
        VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
        VideoShot(index=2, start=2, end=4, duration=2, keyframe_time=3),
    ]

    def fake_run(args, **kwargs):
        if "0001" in args[-1]:
            Path(args[-1]).write_bytes(b"jpg")
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        return CompletedProcess(args=args, returncode=1, stdout="", stderr="bad input")

    with (
        caplog.at_level(logging.WARNING, logger="app.video_understanding.keyframe_service"),
        patch("app.video_understanding.keyframe_service.subprocess.run", side_effect=fake_run),
    ):
        keyframes = extract_keyframes(
            Path("sample.mp4"),
            shots,
            output_dir=tmp_path / "keyframes",
            public_prefix="/keyframes",
        )

    assert [keyframe.shot_index for keyframe in keyframes] == [1]
    assert "shot_index=2" in caplog.text
    assert "sample.mp4" in caplog.text
    assert "bad input" in caplog.text


def test_extract_keyframes_logs_warning_when_output_file_is_missing(tmp_path, caplog):
    shots = [VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)]

    with (
        caplog.at_level(logging.WARNING, logger="app.video_understanding.keyframe_service"),
        patch(
            "app.video_understanding.keyframe_service.subprocess.run",
            return_value=CompletedProcess(args=["ffmpeg"], returncode=0, stdout="", stderr=""),
        ),
    ):
        keyframes = extract_keyframes(
            Path("sample.mp4"),
            shots,
            output_dir=tmp_path / "keyframes",
            public_prefix="/keyframes",
        )

    assert keyframes == []
    assert "target file was not created" in caplog.text
    assert "shot_index=1" in caplog.text


def test_extract_keyframes_returns_empty_and_logs_when_all_fail(tmp_path, caplog):
    shots = [VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)]

    with (
        caplog.at_level(logging.WARNING, logger="app.video_understanding.keyframe_service"),
        patch(
            "app.video_understanding.keyframe_service.subprocess.run",
            return_value=CompletedProcess(args=["ffmpeg"], returncode=1, stdout="", stderr="bad input"),
        ),
    ):
        keyframes = extract_keyframes(
            Path("sample.mp4"),
            shots,
            output_dir=tmp_path / "keyframes",
            public_prefix="/keyframes",
        )

    assert keyframes == []
    assert "shot_index=1" in caplog.text
    assert "bad input" in caplog.text


def test_scenes_to_video_shots_preserves_scene_boundaries_and_midpoint_keyframes():
    from app.video_understanding.pyscenedetect_detector import scenes_to_video_shots

    shots = scenes_to_video_shots([(0, 1.25), (1.25, 3.5), (3.5, 5)], duration=5)

    assert [shot.index for shot in shots] == [1, 2, 3]
    assert [(shot.start, shot.end) for shot in shots] == [(0, 1.25), (1.25, 3.5), (3.5, 5)]
    assert [shot.keyframe_time for shot in shots] == [0.625, 2.375, 4.25]


def test_scenes_to_video_shots_filters_invalid_and_too_short_scenes():
    from app.video_understanding.pyscenedetect_detector import scenes_to_video_shots

    shots = scenes_to_video_shots([(0, 0.02), (0.1, 1.0), (2.0, 1.5), (1.0, 3.0)], duration=3)

    assert [(shot.index, shot.start, shot.end, shot.duration) for shot in shots] == [
        (1, 0.1, 1.0, 0.9),
        (2, 1.0, 3.0, 2.0),
    ]
    assert [shot.keyframe_time for shot in shots] == [0.55, 2.0]


def test_detect_video_signal_passes_threshold_to_scene_detection():
    metadata = VideoMetadata(duration=9, fps=30, width=1920, height=1080, format_name="mp4")

    with (
        patch("app.video_understanding.shot_detector.probe_video_metadata", return_value=metadata),
        patch("app.video_understanding.shot_detector._detect_scene_cut_times", return_value=[3]) as detect_cuts,
    ):
        detect_video_signal(Path("sample.mp4"), threshold=0.77)

    detect_cuts.assert_called_once_with(Path("sample.mp4"), 9.0, 0.77)


def test_detect_video_signal_keeps_short_no_cut_video_as_scene_detect():
    metadata = VideoMetadata(duration=5, fps=30, width=1920, height=1080, format_name="mp4")

    with (
        patch("app.video_understanding.shot_detector.probe_video_metadata", return_value=metadata),
        patch("app.video_understanding.shot_detector._detect_scene_cut_times", return_value=[]),
    ):
        signal = detect_video_signal(Path("short.mp4"), fallback_seconds=3)

    assert signal.detection_method == "ffmpeg_scene_detect"
    assert signal.shot_count == 1
    assert signal.shots[0].start == 0
    assert signal.shots[0].end == 5


def test_detect_video_signal_uses_uniform_fallback_for_long_no_cut_video():
    metadata = VideoMetadata(duration=10, fps=30, width=1920, height=1080, format_name="mp4")

    with (
        patch("app.video_understanding.shot_detector.probe_video_metadata", return_value=metadata),
        patch("app.video_understanding.shot_detector._detect_scene_cut_times", return_value=[]),
    ):
        signal = detect_video_signal(Path("long.mp4"), fallback_seconds=3)

    assert signal.detection_method == "uniform_fallback"
    assert signal.shot_count > 1
    assert [shot.start for shot in signal.shots] == [0, 3, 6, 9]
    assert signal.shots[-1].end == 10


def test_detect_video_signal_uses_uniform_fallback_when_pyscenedetect_and_ffmpeg_find_no_shots():
    metadata = VideoMetadata(duration=15, fps=30, width=1920, height=1080, format_name="mp4")

    with (
        patch("app.video_understanding.shot_detector.probe_video_metadata", return_value=metadata),
        patch("app.video_understanding.shot_detector.detect_shots_with_pyscenedetect", return_value=[]),
        patch("app.video_understanding.shot_detector._detect_scene_cut_times", return_value=[]),
    ):
        signal = detect_video_signal(Path("long.mp4"), fallback_seconds=3)

    assert signal.detection_method == "uniform_fallback"
    assert signal.shot_count == 5
    assert [shot.start for shot in signal.shots] == [0, 3, 6, 9, 12]
    assert signal.shots[-1].end == 15


def test_detect_video_signal_uses_pyscenedetect_adaptive_when_it_returns_usable_shots():
    metadata = VideoMetadata(duration=15, fps=30, width=1920, height=1080, format_name="mp4")
    detected_shots = [
        VideoShot(index=1, start=0, end=5, duration=5, keyframe_time=2.5),
        VideoShot(index=2, start=5, end=10, duration=5, keyframe_time=7.5),
        VideoShot(index=3, start=10, end=15, duration=5, keyframe_time=12.5),
    ]

    with (
        patch("app.video_understanding.shot_detector.probe_video_metadata", return_value=metadata),
        patch("app.video_understanding.shot_detector.detect_shots_with_pyscenedetect", return_value=detected_shots) as detect,
        patch("app.video_understanding.shot_detector._detect_scene_cut_times") as detect_cuts,
    ):
        signal = detect_video_signal(Path("sample.mp4"))

    assert signal.detection_method == "pyscenedetect_adaptive"
    assert [(shot.start, shot.end) for shot in signal.shots] == [(0, 5), (5, 10), (10, 15)]
    detect.assert_called_once_with(Path("sample.mp4"), detector="adaptive")
    detect_cuts.assert_not_called()


def test_detect_video_signal_falls_back_when_pyscenedetect_detector_fails():
    metadata = VideoMetadata(duration=5, fps=30, width=1920, height=1080, format_name="mp4")

    with (
        patch("app.video_understanding.shot_detector.probe_video_metadata", return_value=metadata),
        patch("app.video_understanding.shot_detector.detect_shots_with_pyscenedetect", side_effect=ValueError("bad video")),
        patch("app.video_understanding.shot_detector._detect_scene_cut_times", return_value=[2.0]),
    ):
        signal = detect_video_signal(Path("sample.mp4"))

    assert signal.detection_method == "ffmpeg_scene_detect"
    assert [(shot.start, shot.end) for shot in signal.shots] == [(0.0, 2.0), (2.0, 5.0)]


def test_normalize_shots_merges_too_short_shots_to_preserve_coverage():
    shots = normalize_shots(
        [
            VideoShot(index=1, start=0, end=1.0, duration=1.0, keyframe_time=0.5),
            VideoShot(index=2, start=1.0, end=1.1, duration=0.1, keyframe_time=1.05),
            VideoShot(index=3, start=1.1, end=3.0, duration=1.9, keyframe_time=2.05),
        ],
        duration=3.0,
    )

    assert [(shot.index, shot.start, shot.end, shot.duration) for shot in shots] == [
        (1, 0.0, 1.1, 1.1),
        (2, 1.1, 3.0, 1.9),
    ]
    assert [shot.keyframe_time for shot in shots] == [0.55, 2.05]


def test_detect_video_signal_rejects_non_positive_fallback_seconds():
    metadata = VideoMetadata(duration=10, fps=30, width=1920, height=1080, format_name="mp4")

    with (
        patch("app.video_understanding.shot_detector.probe_video_metadata", return_value=metadata),
        patch("app.video_understanding.shot_detector._detect_scene_cut_times", return_value=[]),
    ):
        try:
            detect_video_signal(Path("sample.mp4"), fallback_seconds=0)
        except ValueError as exc:
            assert "fallback_seconds" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_detect_scene_cut_times_returns_empty_when_ffmpeg_is_missing():
    with patch("app.video_understanding.shot_detector.subprocess.run", side_effect=FileNotFoundError):
        assert _detect_scene_cut_times(Path("sample.mp4"), 10, 0.3) == []


def test_detect_scene_cut_times_returns_empty_when_ffmpeg_times_out():
    with patch(
        "app.video_understanding.shot_detector.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=20),
    ):
        assert _detect_scene_cut_times(Path("sample.mp4"), 10, 0.3) == []


def test_detect_scene_cut_times_returns_empty_when_ffmpeg_fails():
    with patch(
        "app.video_understanding.shot_detector.subprocess.run",
        return_value=CompletedProcess(args=["ffmpeg"], returncode=1, stdout="", stderr="bad input"),
    ):
        assert _detect_scene_cut_times(Path("sample.mp4"), 10, 0.3) == []


def test_parse_cut_times_deduplicates_sorts_and_filters_edge_cuts():
    output = """
    [Parsed_showinfo_1] pts_time:9.99
    [Parsed_showinfo_1] pts_time:3
    [Parsed_showinfo_1] pts_time:0.02
    [Parsed_showinfo_1] pts_time:7
    [Parsed_showinfo_1] pts_time:3.000
    """

    assert _parse_cut_times(output, duration=10) == [3.0, 7.0]


def test_probe_video_metadata_falls_back_to_r_frame_rate_when_avg_is_zero():
    stdout = """
    {
      "streams": [
        {
          "codec_type": "video",
          "width": 1920,
          "height": 1080,
          "avg_frame_rate": "0/0",
          "r_frame_rate": "30000/1001"
        }
      ],
      "format": {
        "duration": "12.5",
        "format_name": "mov,mp4,m4a,3gp,3g2,mj2"
      }
    }
    """
    with patch(
        "app.video_understanding.media_probe.subprocess.run",
        return_value=CompletedProcess(args=["ffprobe"], returncode=0, stdout=stdout, stderr=""),
    ):
        metadata = probe_video_metadata(Path("sample.mp4"))

    assert metadata.fps == 29.97


def test_probe_video_metadata_raises_value_error_when_ffprobe_fails():
    with patch(
        "app.video_understanding.media_probe.subprocess.run",
        return_value=CompletedProcess(args=["ffprobe"], returncode=1, stdout="", stderr="bad input"),
    ):
        try:
            probe_video_metadata(Path("missing.mp4"))
        except ValueError as exc:
            assert "ffprobe failed for missing.mp4" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_probe_video_metadata_raises_value_error_for_non_json_stdout():
    with patch(
        "app.video_understanding.media_probe.subprocess.run",
        return_value=CompletedProcess(args=["ffprobe"], returncode=0, stdout="not json", stderr=""),
    ):
        try:
            probe_video_metadata(Path("sample.mp4"))
        except ValueError as exc:
            assert "invalid ffprobe output" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_probe_video_metadata_raises_value_error_without_video_stream():
    stdout = """
    {
      "streams": [
        {"codec_type": "audio"}
      ],
      "format": {
        "duration": "12.5",
        "format_name": "mp4"
      }
    }
    """
    with patch(
        "app.video_understanding.media_probe.subprocess.run",
        return_value=CompletedProcess(args=["ffprobe"], returncode=0, stdout=stdout, stderr=""),
    ):
        try:
            probe_video_metadata(Path("audio.mp4"))
        except ValueError as exc:
            assert "no video stream found for audio.mp4" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_probe_video_metadata_raises_value_error_when_ffprobe_is_missing():
    with patch(
        "app.video_understanding.media_probe.subprocess.run",
        side_effect=FileNotFoundError,
    ):
        try:
            probe_video_metadata(Path("sample.mp4"))
        except ValueError as exc:
            assert "ffprobe executable not found" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_probe_video_metadata_raises_value_error_when_ffprobe_times_out():
    with patch(
        "app.video_understanding.media_probe.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=10),
    ):
        try:
            probe_video_metadata(Path("sample.mp4"))
        except ValueError as exc:
            assert "ffprobe timed out after 10s" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_probe_video_metadata_raises_value_error_when_streams_is_not_a_list():
    with patch(
        "app.video_understanding.media_probe.subprocess.run",
        return_value=CompletedProcess(
            args=["ffprobe"],
            returncode=0,
            stdout='{"streams": {}, "format": {}}',
            stderr="",
        ),
    ):
        try:
            probe_video_metadata(Path("sample.mp4"))
        except ValueError as exc:
            assert "streams is not a list" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_probe_video_metadata_raises_value_error_when_format_is_not_an_object():
    stdout = """
    {
      "streams": [
        {
          "codec_type": "video",
          "width": 1920,
          "height": 1080,
          "avg_frame_rate": "25/1"
        }
      ],
      "format": []
    }
    """
    with patch(
        "app.video_understanding.media_probe.subprocess.run",
        return_value=CompletedProcess(args=["ffprobe"], returncode=0, stdout=stdout, stderr=""),
    ):
        try:
            probe_video_metadata(Path("sample.mp4"))
        except ValueError as exc:
            assert "format is not an object" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_probe_video_metadata_raises_value_error_when_numeric_field_is_na():
    stdout = """
    {
      "streams": [
        {
          "codec_type": "video",
          "width": "N/A",
          "height": 1080,
          "avg_frame_rate": "25/1"
        }
      ],
      "format": {
        "duration": "12.5",
        "format_name": "mp4"
      }
    }
    """
    with patch(
        "app.video_understanding.media_probe.subprocess.run",
        return_value=CompletedProcess(args=["ffprobe"], returncode=0, stdout=stdout, stderr=""),
    ):
        try:
            probe_video_metadata(Path("sample.mp4"))
        except ValueError as exc:
            assert "invalid ffprobe output" in str(exc)
        else:
            raise AssertionError("expected ValueError")
