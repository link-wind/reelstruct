from pathlib import Path
import logging
import subprocess

from app.video_understanding.schemas import KeyframeEvidence, VideoShot

FFMPEG_TIMEOUT_SECONDS = 20
logger = logging.getLogger(__name__)


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

        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{shot.keyframe_time:.3f}",
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
            _log_keyframe_warning(video_path, shot, local_path, f"ffmpeg executable not found: {exc}")
            continue
        except subprocess.TimeoutExpired as exc:
            _log_keyframe_warning(
                video_path,
                shot,
                local_path,
                f"ffmpeg timed out after {exc.timeout}s",
            )
            continue

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            reason = f"ffmpeg exited with returncode={result.returncode}"
            if stderr:
                reason = f"{reason}; stderr={stderr}"
            _log_keyframe_warning(video_path, shot, local_path, reason)
            continue

        if not local_path.is_file():
            _log_keyframe_warning(video_path, shot, local_path, "target file was not created")
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


def _log_keyframe_warning(video_path: Path, shot: VideoShot, target_path: Path, reason: str) -> None:
    logger.warning(
        "failed to extract keyframe shot_index=%s video_path=%s target_path=%s reason=%s",
        shot.index,
        video_path,
        target_path,
        reason,
    )
