import subprocess
import sys
import types
from pathlib import Path

from app.video_understanding.schemas import TranscriptSegment


def _clear_asr_env(monkeypatch):
    for name in (
        "REELSTRUCT_ASR_ENABLED",
        "REELSTRUCT_ASR_MODEL_NAME",
        "REELSTRUCT_ASR_LANGUAGE",
        "REELSTRUCT_ASR_DEVICE",
        "REELSTRUCT_ASR_COMPUTE_TYPE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_asr_is_disabled_by_default(monkeypatch):
    _clear_asr_env(monkeypatch)

    from app.video_understanding.asr_service import asr_is_enabled

    assert asr_is_enabled() is False


def test_load_asr_config_uses_default_local_values(monkeypatch):
    _clear_asr_env(monkeypatch)

    from app.video_understanding.asr_service import load_asr_config

    config = load_asr_config()

    assert config.enabled is False
    assert config.model_name == "small"
    assert config.language == "zh"
    assert config.device == "cpu"
    assert config.compute_type == "int8"


def test_transcribe_video_with_asr_returns_empty_result_when_disabled(monkeypatch, tmp_path):
    _clear_asr_env(monkeypatch)
    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"video")

    from app.video_understanding.asr_service import transcribe_video_with_asr

    result = transcribe_video_with_asr(video_path, work_dir=tmp_path)

    assert result.segments == []
    assert result.warnings == []


def test_enabled_asr_extracts_audio_with_expected_ffmpeg_command(monkeypatch, tmp_path):
    _clear_asr_env(monkeypatch)
    monkeypatch.setenv("REELSTRUCT_ASR_ENABLED", "true")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        output_path = Path(cmd[-1])
        output_path.write_bytes(b"wav")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, audio_path, **kwargs):
            return [], object()

    monkeypatch.setattr("app.video_understanding.asr_service.subprocess.run", fake_run)
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        types.SimpleNamespace(WhisperModel=FakeWhisperModel),
    )

    from app.video_understanding.asr_service import transcribe_video_with_asr

    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"video")
    transcribe_video_with_asr(video_path, work_dir=tmp_path)

    assert calls == [
        (
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(video_path),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-y",
                str(tmp_path / "asr_audio.wav"),
            ],
            {
                "check": False,
                "capture_output": True,
                "text": True,
                "timeout": 120,
            },
        )
    ]


def test_enabled_asr_extracts_requested_clip_and_offsets_segment_times(monkeypatch, tmp_path):
    _clear_asr_env(monkeypatch)
    monkeypatch.setenv("REELSTRUCT_ASR_ENABLED", "true")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        Path(cmd[-1]).write_bytes(b"wav")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    class FakeSegment:
        def __init__(self, start, end, text):
            self.start = start
            self.end = end
            self.text = text

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, audio_path, **kwargs):
            return [FakeSegment(0.1, 1.2, "片段口播")], object()

    monkeypatch.setattr("app.video_understanding.asr_service.subprocess.run", fake_run)
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        types.SimpleNamespace(WhisperModel=FakeWhisperModel),
    )

    from app.video_understanding.asr_service import transcribe_video_with_asr

    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"video")
    result = transcribe_video_with_asr(video_path, work_dir=tmp_path, clip_start=2.0, clip_end=4.0)

    assert calls[0][0] == [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        "2.000",
        "-t",
        "2.000",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-y",
        str(tmp_path / "asr_audio_2.000_4.000.wav"),
    ]
    assert result.segments == [TranscriptSegment(start=2.1, end=3.2, text="片段口播")]


def test_enabled_asr_normalizes_faster_whisper_segments(monkeypatch, tmp_path):
    _clear_asr_env(monkeypatch)
    monkeypatch.setenv("REELSTRUCT_ASR_ENABLED", "true")
    model_calls = []
    transcribe_calls = []

    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"wav")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    class FakeSegment:
        def __init__(self, start, end, text):
            self.start = start
            self.end = end
            self.text = text

    class FakeWhisperModel:
        def __init__(self, model_name, *, device, compute_type):
            model_calls.append((model_name, device, compute_type))

        def transcribe(self, audio_path, *, language, task, vad_filter):
            transcribe_calls.append((audio_path, language, task, vad_filter))
            return [
                FakeSegment(0.0, 1.25, " 第一段 "),
                FakeSegment(1.25, 2.5, "第二段"),
            ], object()

    monkeypatch.setattr("app.video_understanding.asr_service.subprocess.run", fake_run)
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        types.SimpleNamespace(WhisperModel=FakeWhisperModel),
    )

    from app.video_understanding.asr_service import transcribe_video_with_asr

    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"video")
    result = transcribe_video_with_asr(video_path, work_dir=tmp_path)

    assert model_calls == [("small", "cpu", "int8")]
    assert transcribe_calls == [(str(tmp_path / "asr_audio.wav"), "zh", "transcribe", True)]
    assert result.segments == [
        TranscriptSegment(start=0.0, end=1.25, text="第一段"),
        TranscriptSegment(start=1.25, end=2.5, text="第二段"),
    ]
    assert result.warnings == []


def test_enabled_asr_returns_warning_when_ffmpeg_audio_extraction_fails(monkeypatch, tmp_path):
    _clear_asr_env(monkeypatch)
    monkeypatch.setenv("REELSTRUCT_ASR_ENABLED", "true")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="bad input")

    monkeypatch.setattr("app.video_understanding.asr_service.subprocess.run", fake_run)

    from app.video_understanding.asr_service import transcribe_video_with_asr

    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"video")
    result = transcribe_video_with_asr(video_path, work_dir=tmp_path)

    assert result.segments == []
    assert result.warnings == ["ffmpeg audio extraction failed with returncode=1; stderr=bad input"]


def test_enabled_asr_skips_invalid_transcript_segments(monkeypatch, tmp_path):
    _clear_asr_env(monkeypatch)
    monkeypatch.setenv("REELSTRUCT_ASR_ENABLED", "true")

    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"wav")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    class FakeSegment:
        def __init__(self, start, end, text):
            self.start = start
            self.end = end
            self.text = text

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, audio_path, *, language, task, vad_filter):
            return [
                FakeSegment(0.0, 1.0, "第一段"),
                FakeSegment(1.0, 1.0, "坏段"),
                FakeSegment(1.0, 2.0, "第二段"),
            ], object()

    monkeypatch.setattr("app.video_understanding.asr_service.subprocess.run", fake_run)
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        types.SimpleNamespace(WhisperModel=FakeWhisperModel),
    )

    from app.video_understanding.asr_service import transcribe_video_with_asr

    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"video")
    result = transcribe_video_with_asr(video_path, work_dir=tmp_path)

    assert result.segments == [
        TranscriptSegment(start=0.0, end=1.0, text="第一段"),
        TranscriptSegment(start=1.0, end=2.0, text="第二段"),
    ]
    assert result.warnings[0].startswith("skipped invalid ASR segment: 1 validation error for TranscriptSegment")
