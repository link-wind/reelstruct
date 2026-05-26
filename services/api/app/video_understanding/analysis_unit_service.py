from typing import Optional

from app.video_understanding.schemas import AnalysisUnit, FrameEvidence, ShotEvidenceNode

DEFAULT_TARGET_DURATION_SECONDS = 4.0
DEFAULT_MAX_SHOTS_PER_UNIT = 8
LONG_SHOT_RATIO = 1.5
MAX_REPRESENTATIVE_FRAMES = 5


def build_analysis_units(
    nodes: list[ShotEvidenceNode],
    *,
    target_duration: float = DEFAULT_TARGET_DURATION_SECONDS,
    max_shots_per_unit: int = DEFAULT_MAX_SHOTS_PER_UNIT,
) -> list[AnalysisUnit]:
    if target_duration <= 0:
        raise ValueError(f"target_duration must be greater than 0, got {target_duration}")
    if max_shots_per_unit <= 0:
        raise ValueError(f"max_shots_per_unit must be greater than 0, got {max_shots_per_unit}")

    units: list[AnalysisUnit] = []
    bucket: list[ShotEvidenceNode] = []

    for node in nodes:
        if _is_long_shot(node, target_duration):
            if bucket:
                units.append(_build_unit(bucket, len(units) + 1))
                bucket = []
            units.append(_build_unit([node], len(units) + 1))
            continue

        if bucket and _would_exceed_bucket(bucket, node, target_duration, max_shots_per_unit):
            units.append(_build_unit(bucket, len(units) + 1))
            bucket = []
        bucket.append(node)

    if bucket:
        units.append(_build_unit(bucket, len(units) + 1))

    return units


def _is_long_shot(node: ShotEvidenceNode, target_duration: float) -> bool:
    return node.shot.duration >= target_duration * LONG_SHOT_RATIO


def _would_exceed_bucket(
    bucket: list[ShotEvidenceNode],
    node: ShotEvidenceNode,
    target_duration: float,
    max_shots_per_unit: int,
) -> bool:
    next_duration = round(node.shot.end - bucket[0].shot.start, 3)
    return len(bucket) >= max_shots_per_unit or next_duration > target_duration


def _build_unit(nodes: list[ShotEvidenceNode], unit_index: int) -> AnalysisUnit:
    start = nodes[0].shot.start
    end = nodes[-1].shot.end
    return AnalysisUnit(
        unit_id=f"unit_{unit_index}",
        shot_indices=[node.shot.index for node in nodes],
        start=start,
        end=end,
        duration=round(end - start, 3),
        representative_frames=_select_representative_frames(nodes),
        ocr_texts=[item for node in nodes for item in node.ocr_texts],
        transcript_texts=[item for node in nodes for item in node.transcript_texts],
    )


def _select_representative_frames(nodes: list[ShotEvidenceNode]) -> list[FrameEvidence]:
    frames = [frame for node in nodes for frame in node.frames]
    if not frames:
        return []

    selected: list[FrameEvidence] = []
    _append_unique(selected, _first_frame(frames))
    _append_unique(selected, _middle_frame(frames))
    _append_unique(selected, _last_frame(frames))
    _append_unique(selected, _ocr_heavy_frame(nodes))

    return selected[:MAX_REPRESENTATIVE_FRAMES]


def _first_frame(frames: list[FrameEvidence]) -> FrameEvidence:
    return min(frames, key=lambda frame: frame.time)


def _middle_frame(frames: list[FrameEvidence]) -> FrameEvidence:
    midpoint = (frames[0].time + frames[-1].time) / 2
    return min(frames, key=lambda frame: abs(frame.time - midpoint))


def _last_frame(frames: list[FrameEvidence]) -> FrameEvidence:
    return max(frames, key=lambda frame: frame.time)


def _ocr_heavy_frame(nodes: list[ShotEvidenceNode]) -> Optional[FrameEvidence]:
    frames_by_key = {
        (frame.shot_index, frame.frame_index): frame
        for node in nodes
        for frame in node.frames
    }
    text_by_key: dict[tuple[int, int], int] = {}
    for node in nodes:
        for item in node.ocr_texts:
            key = (item.shot_index, item.frame_index)
            text_by_key[key] = text_by_key.get(key, 0) + len(item.text.strip())

    if not text_by_key:
        return None

    best_key = max(text_by_key, key=lambda key: text_by_key[key])
    frame = frames_by_key.get(best_key)
    if frame is None:
        return None
    return frame.model_copy(update={"role": "ocr_heavy"})


def _append_unique(selected: list[FrameEvidence], frame: Optional[FrameEvidence]) -> None:
    if frame is None:
        return
    identity = (frame.shot_index, frame.frame_index, frame.time, frame.role)
    if any((item.shot_index, item.frame_index, item.time, item.role) == identity for item in selected):
        return
    selected.append(frame)
