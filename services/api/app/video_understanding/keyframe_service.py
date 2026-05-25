from pathlib import Path
import logging
import subprocess

from app.video_understanding.schemas import FrameEvidence, KeyframeEvidence, VideoShot

FFMPEG_TIMEOUT_SECONDS = 20
logger = logging.getLogger(__name__)


def frame_sample_times(*, start: float, end: float) -> list[tuple[str, float]]:
    duration = round(end - start, 3)
    if duration < 0.8:
        return [("middle", round(start + duration / 2, 3))]
    if duration < 2.0:
        return [
            ("middle", round(start + duration / 2, 3)),
            ("safe_end", round(end - 0.15, 3)),
        ]
    if duration < 4.0:
        return [
            ("start", round(start + 0.15, 3)),
            ("middle", round(start + duration / 2, 3)),
            ("end", round(end - 0.15, 3)),
        ]
    return [
        ("start", round(start + 0.15, 3)),
        ("third", round(start + duration / 3, 3)),
        ("two_thirds", round(start + duration * 2 / 3, 3)),
        ("end", round(end - 0.15, 3)),
    ]


def extract_frame_evidence(
    video_path: Path,
    shots: list[VideoShot],
    *,
    output_dir: Path,
    public_prefix: str,
) -> list[FrameEvidence]:
    output_dir.mkdir(parents=True, exist_ok=True)
    frames: list[FrameEvidence] = []
    prefix = public_prefix.rstrip("/")

    for shot in shots:
        for frame_index, (role, primary_time) in enumerate(
            frame_sample_times(start=shot.start, end=shot.end),
            start=1,
        ):
            extracted_time = None
            local_path = None
            for frame_time in _frame_attempt_times(shot, primary_time):
                filename = f"shot_{shot.index:04d}_{frame_index:02d}_{role}_{int(frame_time * 1000):08d}.jpg"
                local_path = output_dir / filename
                if _extract_one_frame(video_path, shot, frame_time, local_path):
                    extracted_time = frame_time
                    break

            if extracted_time is None or local_path is None:
                continue

            frames.append(
                FrameEvidence(
                    shot_index=shot.index,
                    frame_index=frame_index,
                    time=extracted_time,
                    role=role,
                    local_path=str(local_path),
                    public_url=f"{prefix}/{filename}" if prefix else f"/{filename}",
                )
            )

    return frames


def extract_keyframes(
    video_path: Path,
    shots: list[VideoShot],
    *,
    output_dir: Path,
    public_prefix: str,
) -> list[KeyframeEvidence]:
    output_dir.mkdir(parents=True, exist_ok=True)
    keyframes: list[KeyframeEvidence] = []
    prefix = public_prefix.rstrip("/")

    for shot in shots:
        filename = f"shot_{shot.index:04d}_{int(shot.keyframe_time * 1000):08d}.jpg"
        local_path = output_dir / filename

        if not _extract_one_frame(video_path, shot, shot.keyframe_time, local_path):
            continue

        keyframes.append(
            KeyframeEvidence(
                shot_index=shot.index,
                keyframe_time=shot.keyframe_time,
                local_path=str(local_path),
                public_url=f"{prefix}/{filename}" if prefix else f"/{filename}",
            )
        )

    return keyframes


def _frame_attempt_times(shot: VideoShot, primary_time: float) -> list[float]:
    attempts: list[float] = []
    seen: set[float] = set()

    for candidate in (primary_time, shot.keyframe_time, shot.start + 0.05, shot.end - 0.05):
        bounded = round(min(max(candidate, shot.start), shot.end), 3)
        if bounded in seen:
            continue
        seen.add(bounded)
        attempts.append(bounded)

    return attempts


def _extract_one_frame(video_path: Path, shot: VideoShot, frame_time: float, local_path: Path) -> bool:
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{frame_time:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                "-y",
                str(local_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        _log_frame_warning(video_path, shot, local_path, f"ffmpeg executable not found: {exc}")
        return False
    except subprocess.TimeoutExpired as exc:
        _log_frame_warning(video_path, shot, local_path, f"ffmpeg timed out after {exc.timeout}s")
        return False

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        reason = f"ffmpeg exited with returncode={result.returncode}"
        if stderr:
            reason = f"{reason}; stderr={stderr}"
        _log_frame_warning(video_path, shot, local_path, reason)
        return False

    if not local_path.is_file():
        _log_frame_warning(video_path, shot, local_path, "target file was not created")
        return False

    return True


def _log_frame_warning(video_path: Path, shot: VideoShot, target_path: Path, reason: str) -> None:
    logger.warning(
        "failed to extract frame shot_index=%s video_path=%s target_path=%s reason=%s",
        shot.index,
        video_path,
        target_path,
        reason,
    )
