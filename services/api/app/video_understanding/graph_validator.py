from app.video_understanding.schemas import ShotEvidenceGraph


def validate_graph_segments(graph: ShotEvidenceGraph) -> list[str]:
    warnings: list[str] = []
    shot_ids = {node.shot.index for node in graph.shots}
    beat_ids = {beat.beat_id for beat in graph.beats}

    for segment in graph.segments:
        for shot_id in segment.shot_indices:
            if shot_id not in shot_ids:
                warnings.append(f"segment {segment.segment_id} references missing shot {shot_id}")
        for beat_id in segment.beat_ids:
            if beat_id not in beat_ids:
                warnings.append(f"segment {segment.segment_id} references missing beat {beat_id}")
        if segment.end <= segment.start:
            warnings.append(f"segment {segment.segment_id} has invalid time range")

    sorted_segments = sorted(
        [segment for segment in graph.segments if segment.end > segment.start],
        key=lambda item: item.start,
    )
    for previous, current in zip(sorted_segments, sorted_segments[1:]):
        if current.start < previous.end:
            warnings.append(f"segment {previous.segment_id} overlaps {current.segment_id}")

    return warnings
