import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.video_understanding.schemas import TranscriptSegment


ASR_ENABLED_ENV = "REELSTRUCT_ASR_ENABLED"
ASR_MODEL_NAME_ENV = "REELSTRUCT_ASR_MODEL_NAME"
ASR_LANGUAGE_ENV = "REELSTRUCT_ASR_LANGUAGE"
ASR_DEVICE_ENV = "REELSTRUCT_ASR_DEVICE"
ASR_COMPUTE_TYPE_ENV = "REELSTRUCT_ASR_COMPUTE_TYPE"
FFMPEG_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class ASRConfig:
    enabled: bool = False
    model_name: str = "small"
    language: str = "zh"
    device: str = "cpu"
    compute_type: str = "int8"


@dataclass
class ASRResult:
    segments: list[TranscriptSegment] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def asr_is_enabled() -> bool:
    return load_asr_config().enabled


def load_asr_config() -> ASRConfig:
    return ASRConfig(
        enabled=_read_bool_env(ASR_ENABLED_ENV, default=False),
        model_name=os.getenv(ASR_MODEL_NAME_ENV, "small").strip() or "small",
        language=os.getenv(ASR_LANGUAGE_ENV, "zh").strip() or "zh",
        device=os.getenv(ASR_DEVICE_ENV, "cpu").strip() or "cpu",
        compute_type=os.getenv(ASR_COMPUTE_TYPE_ENV, "int8").strip() or "int8",
    )


def transcribe_video_with_asr(
    video_path: Path,
    *,
    work_dir: Path,
    clip_start: Optional[float] = None,
    clip_end: Optional[float] = None,
) -> ASRResult:
    config = load_asr_config()
    if not config.enabled:
        return ASRResult()

    work_dir.mkdir(parents=True, exist_ok=True)
    audio_path = _audio_output_path(work_dir, clip_start=clip_start, clip_end=clip_end)
    warnings = _extract_audio(video_path, audio_path, clip_start=clip_start, clip_end=clip_end)
    if warnings:
        return ASRResult(warnings=warnings)

    try:
        WhisperModel = _load_whisper_model()
        model = WhisperModel(config.model_name, device=config.device, compute_type=config.compute_type)
        raw_segments, _info = model.transcribe(
            str(audio_path),
            language=config.language,
            task="transcribe",
            vad_filter=True,
        )
    except Exception as exc:
        return ASRResult(warnings=[f"faster-whisper transcription failed: {exc}"])

    segments, normalization_warnings = _normalize_segments(raw_segments, time_offset=clip_start or 0)
    return ASRResult(segments=segments, warnings=normalization_warnings)


def _audio_output_path(work_dir: Path, *, clip_start: Optional[float], clip_end: Optional[float]) -> Path:
    if clip_start is None or clip_end is None:
        return work_dir / "asr_audio.wav"
    return work_dir / f"asr_audio_{clip_start:.3f}_{clip_end:.3f}.wav"


def _extract_audio(
    video_path: Path,
    audio_path: Path,
    *,
    clip_start: Optional[float] = None,
    clip_end: Optional[float] = None,
) -> list[str]:
    clip_args = []
    if clip_start is not None and clip_end is not None:
        clip_args = ["-ss", f"{clip_start:.3f}", "-t", f"{max(0, clip_end - clip_start):.3f}"]

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                *clip_args,
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
                str(audio_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        return [f"ffmpeg executable not found: {exc}"]
    except subprocess.TimeoutExpired as exc:
        return [f"ffmpeg audio extraction timed out after {exc.timeout}s"]

    if result.returncode == 0:
        return []

    warning = f"ffmpeg audio extraction failed with returncode={result.returncode}"
    stderr = (result.stderr or "").strip()
    if stderr:
        warning = f"{warning}; stderr={stderr}"
    return [warning]


def _load_whisper_model() -> Any:
    from faster_whisper import WhisperModel

    return WhisperModel


def _normalize_segments(raw_segments: Any, *, time_offset: float = 0) -> tuple[list[TranscriptSegment], list[str]]:
    segments: list[TranscriptSegment] = []
    warnings: list[str] = []
    for item in raw_segments:
        text = str(getattr(item, "text", "")).strip()
        try:
            segment = TranscriptSegment(
                start=round(float(getattr(item, "start")) + time_offset, 3),
                end=round(float(getattr(item, "end")) + time_offset, 3),
                text=text,
            )
        except Exception as exc:
            warnings.append(f"skipped invalid ASR segment: {exc}")
            continue
        segments.append(segment)
    return segments, warnings


def _read_bool_env(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}
