from pathlib import Path
import subprocess
from subprocess import CompletedProcess
from unittest.mock import patch

from app.video_understanding.media_probe import probe_video_metadata
from app.video_understanding.schemas import VideoMetadata
from app.video_understanding.shot_detector import (
    _detect_scene_cut_times,
    _parse_cut_times,
    detect_video_signal,
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
    assert signal.detection_method in {"scene_detect", "uniform_fallback"}


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

    assert signal.detection_method == "scene_detect"
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
