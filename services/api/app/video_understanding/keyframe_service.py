from pathlib import Path
import logging
import subprocess
from typing import Optional

from app.video_understanding.schemas import FrameEvidence, KeyframeEvidence, VideoShot

FFMPEG_TIMEOUT_SECONDS = 20
logger = logging.getLogger(__name__)


def frame_sample_times(*, start: float, end: float) -> list[tuple[str, float]]:
    duration = end - start
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
            last_failure_reason = None
            for frame_time in _frame_attempt_times(shot, primary_time):
                filename = f"shot_{shot.index:04d}_{frame_index:02d}_{role}_{int(frame_time * 1000):08d}.jpg"
                local_path = output_dir / filename
                extracted, failure_reason = _extract_one_frame(
                    video_path,
                    shot,
                    frame_time,
                    local_path,
                    log_warning=False,
                    warning_subject="frame",
                )
                if extracted:
                    extracted_time = frame_time
                    break
                last_failure_reason = failure_reason or f"frame_time={frame_time:.3f}"

            if extracted_time is None or local_path is None:
                _log_frame_warning(
                    video_path,
                    shot,
                    local_path or output_dir / f"shot_{shot.index:04d}_{frame_index:02d}_{role}.jpg",
                    "all fallback attempts failed" + (f"; last_attempt={last_failure_reason}" if last_failure_reason else ""),
                )
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

        extracted, _ = _extract_one_frame(
            video_path,
            shot,
            shot.keyframe_time,
            local_path,
            warning_subject="keyframe",
        )
        if not extracted:
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


def _extract_one_frame(
    video_path: Path,
    shot: VideoShot,
    frame_time: float,
    local_path: Path,
    *,
    log_warning: bool = True,
    warning_subject: str = "frame",
) -> tuple[bool, Optional[str]]:
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
        reason = f"ffmpeg executable not found: {exc}"
        if log_warning:
            _log_frame_warning(video_path, shot, local_path, reason, warning_subject=warning_subject)
        return False, reason
    except subprocess.TimeoutExpired as exc:
        reason = f"ffmpeg timed out after {exc.timeout}s"
        if log_warning:
            _log_frame_warning(video_path, shot, local_path, reason, warning_subject=warning_subject)
        _cleanup_failed_frame(local_path)
        return False, reason

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        reason = f"ffmpeg exited with returncode={result.returncode}"
        if stderr:
            reason = f"{reason}; stderr={stderr}"
        if log_warning:
            _log_frame_warning(video_path, shot, local_path, reason, warning_subject=warning_subject)
        _cleanup_failed_frame(local_path)
        return False, reason

    if not local_path.is_file():
        reason = "target file was not created"
        if log_warning:
            _log_frame_warning(video_path, shot, local_path, reason, warning_subject=warning_subject)
        return False, reason

    return True, None


def _cleanup_failed_frame(local_path: Path) -> None:
    try:
        local_path.unlink(missing_ok=True)
    except OSError:
        logger.debug("failed to clean up extracted frame target_path=%s", local_path, exc_info=True)


def _log_frame_warning(
    video_path: Path,
    shot: VideoShot,
    target_path: Path,
    reason: str,
    *,
    warning_subject: str = "frame",
) -> None:
    logger.warning(
        "failed to extract %s shot_index=%s video_path=%s target_path=%s reason=%s",
        warning_subject,
        shot.index,
        video_path,
        target_path,
        reason,
    )
