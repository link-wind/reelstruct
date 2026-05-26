from pathlib import Path
import re
import subprocess

from app.video_understanding.media_probe import probe_video_metadata
from app.video_understanding.pyscenedetect_detector import detect_shots_with_pyscenedetect
from app.video_understanding.schemas import RhythmMetrics, VideoShot, VideoSignal

FFMPEG_TIMEOUT_SECONDS = 20
DEFAULT_SCENE_THRESHOLD = 0.3
DEFAULT_FALLBACK_SECONDS = 3.0
MIN_SHOT_DURATION_SECONDS = 0.05
_PTS_TIME_RE = re.compile(r"pts_time:(?P<time>\d+(?:\.\d+)?)")


def detect_video_signal(
    path: Path,
    *,
    threshold: float = DEFAULT_SCENE_THRESHOLD,
    fallback_seconds: float = DEFAULT_FALLBACK_SECONDS,
) -> VideoSignal:
    if fallback_seconds <= 0:
        raise ValueError(f"fallback_seconds must be greater than 0, got {fallback_seconds}")

    metadata = probe_video_metadata(path)
    shots = _try_pyscenedetect(path, "adaptive", metadata.duration)
    detection_method = "pyscenedetect_adaptive"

    if not _is_usable_shot_list(shots, metadata.duration):
        shots = _try_pyscenedetect(path, "content", metadata.duration)
        detection_method = "pyscenedetect_content"

    if not _is_usable_shot_list(shots, metadata.duration):
        cuts = _detect_scene_cut_times(path, metadata.duration, threshold)
        shots = normalize_shots(_shots_from_cuts(metadata.duration, cuts), metadata.duration)
        detection_method = "ffmpeg_scene_detect"

    if not _is_usable_shot_list(shots, metadata.duration) and metadata.duration > fallback_seconds * 2:
        shots = _build_uniform_shots(metadata.duration, fallback_seconds)
        detection_method = "uniform_fallback"

    return VideoSignal(
        metadata=metadata,
        shot_count=len(shots),
        detection_method=detection_method,
        shots=shots,
        rhythm_metrics=_build_rhythm_metrics(shots),
    )


def _try_pyscenedetect(path: Path, detector: str, duration: float) -> list[VideoShot]:
    try:
        return normalize_shots(detect_shots_with_pyscenedetect(path, detector=detector), duration)
    except Exception:
        return []


def _detect_scene_cut_times(path: Path, duration: float, threshold: float) -> list[float]:
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                str(path),
                "-vf",
                f"select='gt(scene,{threshold})',showinfo",
                "-an",
                "-f",
                "null",
                "-",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    return _parse_cut_times(result.stderr, duration)


def _parse_cut_times(output: str, duration: float) -> list[float]:
    cut_times: list[float] = []
    for match in _PTS_TIME_RE.finditer(output or ""):
        cut_time = round(float(match.group("time")), 3)
        if MIN_SHOT_DURATION_SECONDS <= cut_time <= duration - MIN_SHOT_DURATION_SECONDS:
            cut_times.append(cut_time)
    return sorted(set(cut_times))


def _shots_from_cuts(duration: float, cuts: list[float]) -> list[VideoShot]:
    boundaries = [0.0, *cuts, duration]
    return _shots_from_boundaries(boundaries)


def _build_uniform_shots(duration: float, fallback_seconds: float) -> list[VideoShot]:
    if fallback_seconds <= 0:
        raise ValueError(f"fallback_seconds must be greater than 0, got {fallback_seconds}")

    if duration <= fallback_seconds * 2:
        return _shots_from_boundaries([0.0, duration])

    cuts: list[float] = []
    next_cut = fallback_seconds
    while next_cut < duration - MIN_SHOT_DURATION_SECONDS:
        cuts.append(round(next_cut, 3))
        next_cut += fallback_seconds
    return _shots_from_boundaries([0.0, *cuts, duration])


def _shots_from_boundaries(boundaries: list[float]) -> list[VideoShot]:
    shots: list[VideoShot] = []
    for start, end in zip(boundaries, boundaries[1:]):
        start = round(start, 3)
        end = round(end, 3)
        shot_duration = round(end - start, 3)
        if shot_duration <= 0:
            continue
        shots.append(
            VideoShot(
                index=len(shots) + 1,
                start=start,
                end=end,
                duration=shot_duration,
                keyframe_time=round(start + shot_duration / 2, 3),
            )
        )
    return shots


def normalize_shots(shots: list[VideoShot], duration: float, min_duration: float = 0.3) -> list[VideoShot]:
    intervals: list[tuple[float, float]] = []
    video_duration = round(max(duration, 0), 3)

    for shot in shots:
        start = round(min(max(shot.start, 0), video_duration), 3)
        end = round(min(max(shot.end, 0), video_duration), 3)
        shot_duration = round(end - start, 3)
        if shot_duration <= 0:
            continue
        if intervals and shot_duration < min_duration:
            prev_start, _prev_end = intervals[-1]
            intervals[-1] = (prev_start, end)
            continue
        intervals.append((start, end))

    return _shots_from_boundaries([intervals[0][0], *[end for _start, end in intervals]]) if intervals else []


def _is_usable_shot_list(shots: list[VideoShot], duration: float) -> bool:
    if not shots:
        return False
    if any(shot.duration < MIN_SHOT_DURATION_SECONDS for shot in shots):
        return False
    if duration > DEFAULT_FALLBACK_SECONDS * 2 and len(shots) < 2:
        return False
    max_reasonable_count = max(1, int(duration / MIN_SHOT_DURATION_SECONDS))
    return len(shots) <= max_reasonable_count


def _build_rhythm_metrics(shots: list[VideoShot]) -> RhythmMetrics:
    if not shots:
        return RhythmMetrics()

    durations = [shot.duration for shot in shots]
    avg_duration = round(sum(durations) / len(durations), 3)
    fastest = min(shots, key=lambda shot: shot.duration)
    slowest = max(shots, key=lambda shot: shot.duration)

    if avg_duration >= 6:
        cut_density = "slow"
    elif avg_duration >= 2:
        cut_density = "medium"
    else:
        cut_density = "fast"

    return RhythmMetrics(
        avg_shot_duration=avg_duration,
        cut_density=cut_density,
        fastest_window=_format_window(fastest),
        slowest_window=_format_window(slowest),
    )


def _format_window(shot: VideoShot) -> str:
    return f"{shot.start:.3f}-{shot.end:.3f}"
