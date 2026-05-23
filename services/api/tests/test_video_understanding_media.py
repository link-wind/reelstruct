from pathlib import Path
import subprocess
from subprocess import CompletedProcess
from unittest.mock import patch

from app.video_understanding.media_probe import probe_video_metadata


def test_probe_video_metadata_returns_real_duration_resolution_and_fps():
    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "vid_001.mp4"

    metadata = probe_video_metadata(fixture_path)

    assert metadata.duration > 0
    assert metadata.fps > 0
    assert metadata.width > 0
    assert metadata.height > 0
    assert metadata.format_name


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
