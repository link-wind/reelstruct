import json
from pathlib import Path
import subprocess

from app.video_understanding.schemas import VideoMetadata

FFPROBE_TIMEOUT_SECONDS = 10


def probe_video_metadata(path: Path) -> VideoMetadata:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise ValueError(f"ffprobe executable not found while probing {path}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"ffprobe timed out after {FFPROBE_TIMEOUT_SECONDS}s for {path}") from exc

    if result.returncode != 0:
        raise ValueError(f"ffprobe failed for {path}: {(result.stderr or '').strip()}")

    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"invalid ffprobe output for {path}: stdout is not JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"invalid ffprobe output for {path}: expected object")

    streams = payload.get("streams", [])
    if not isinstance(streams, list):
        raise ValueError(f"invalid ffprobe output for {path}: streams is not a list")

    video_stream = next(
        (
            stream
            for stream in streams
            if isinstance(stream, dict) and stream.get("codec_type") == "video"
        ),
        None,
    )
    if not video_stream:
        raise ValueError(f"no video stream found for {path}")

    format_payload = payload.get("format", {})
    if not isinstance(format_payload, dict):
        raise ValueError(f"invalid ffprobe output for {path}: format is not an object")

    try:
        duration = _parse_float(format_payload.get("duration") or video_stream.get("duration") or 0)
        width = _parse_int(video_stream.get("width") or 0)
        height = _parse_int(video_stream.get("height") or 0)
        fps = _first_positive_fps(
            video_stream.get("avg_frame_rate"),
            video_stream.get("r_frame_rate"),
        )
        format_name = str(format_payload.get("format_name") or "")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid ffprobe output for {path}: {exc}") from exc

    if duration <= 0 or width <= 0 or height <= 0 or fps <= 0:
        raise ValueError(f"incomplete video metadata for {path}")

    return VideoMetadata(
        duration=round(duration, 3),
        fps=round(fps, 3),
        width=width,
        height=height,
        format_name=format_name,
    )


def _parse_fps(value: str) -> float:
    if value == "N/A":
        return 0
    if "/" not in value:
        return _parse_float(value or 0)
    numerator, denominator = value.split("/", 1)
    denominator_float = _parse_float(denominator or 1)
    if denominator_float == 0:
        return 0
    return _parse_float(numerator or 0) / denominator_float


def _first_positive_fps(*values: object) -> float:
    for value in values:
        fps = _parse_fps(str(value or "0/1"))
        if fps > 0:
            return fps
    return 0


def _parse_float(value: object) -> float:
    if value == "N/A":
        raise ValueError("numeric field is N/A")
    return float(value)


def _parse_int(value: object) -> int:
    if value == "N/A":
        raise ValueError("integer field is N/A")
    return int(value)
