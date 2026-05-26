from pathlib import Path
from typing import Any

from app.video_understanding.schemas import VideoShot

try:
    from scenedetect import detect
    from scenedetect.detectors import AdaptiveDetector, ContentDetector
except ImportError:  # pragma: no cover - exercised through detect_shots_with_pyscenedetect
    detect = None
    AdaptiveDetector = None
    ContentDetector = None

MIN_SCENE_DURATION_SECONDS = 0.05


def detect_shots_with_pyscenedetect(path: Path, detector: str = "adaptive") -> list[VideoShot]:
    if detect is None or AdaptiveDetector is None or ContentDetector is None:
        raise RuntimeError("PySceneDetect is not installed")

    scene_detector = AdaptiveDetector() if detector == "adaptive" else ContentDetector()
    scenes = detect(str(path), scene_detector)
    scene_ranges = [(_frame_time_to_seconds(start), _frame_time_to_seconds(end)) for start, end in scenes]
    duration = max((end for _, end in scene_ranges), default=0)
    return scenes_to_video_shots(scene_ranges, duration=duration)


def scenes_to_video_shots(scenes: list[tuple[float, float]], duration: float) -> list[VideoShot]:
    shots: list[VideoShot] = []
    video_duration = round(max(duration, 0), 3)

    for raw_start, raw_end in scenes:
        start = round(min(max(float(raw_start), 0), video_duration), 3)
        end = round(min(max(float(raw_end), 0), video_duration), 3)
        shot_duration = round(end - start, 3)
        if shot_duration < MIN_SCENE_DURATION_SECONDS:
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


def _frame_time_to_seconds(frame_time: Any) -> float:
    if hasattr(frame_time, "get_seconds"):
        return float(frame_time.get_seconds())
    return float(frame_time)
