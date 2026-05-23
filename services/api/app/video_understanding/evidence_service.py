import re

from app.video_understanding.schemas import KeyframeEvidence, ShotEvidence, ShotVisualAnalysis, VideoShot

_TRANSCRIPT_SPLIT_RE = re.compile(r"[。！？!?]+")


def build_shot_evidence(
    shots: list[VideoShot],
    keyframes: list[KeyframeEvidence],
    visual_analyses: list[ShotVisualAnalysis],
    transcript_summary: str,
) -> list[ShotEvidence]:
    keyframe_lookup = {item.shot_index: item for item in keyframes}
    visual_lookup = {item.shot_index: item for item in visual_analyses}
    transcript_parts = _split_transcript(transcript_summary, len(shots))
    evidence: list[ShotEvidence] = []

    for index, shot in enumerate(shots):
        keyframe = keyframe_lookup.get(shot.index)
        visual = visual_lookup.get(shot.index)
        evidence.append(
            ShotEvidence(
                shot_index=shot.index,
                start=shot.start,
                end=shot.end,
                duration=shot.duration,
                keyframe_public_url=keyframe.public_url if keyframe else "",
                transcript_text=transcript_parts[index] if index < len(transcript_parts) else "",
                visual_summary=visual.visual_summary if visual else "",
                packaging_signals=list(visual.packaging_signals) if visual else [],
            )
        )

    return evidence


def _split_transcript(transcript_summary: str, count: int) -> list[str]:
    if count <= 0:
        return []

    parts = [item.strip() for item in _TRANSCRIPT_SPLIT_RE.split(transcript_summary) if item.strip()]
    if not parts:
        return ["" for _ in range(count)]
    if len(parts) > count:
        return [*parts[: count - 1], "。".join(parts[count - 1 :])]
    if len(parts) == count:
        return parts
    return [*parts, *["" for _ in range(count - len(parts))]]
