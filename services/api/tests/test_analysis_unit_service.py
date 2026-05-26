from app.video_understanding.analysis_unit_service import build_analysis_units
from app.video_understanding.schemas import (
    FrameEvidence,
    FrameOCRText,
    ShotEvidenceNode,
    ShotTextAlignment,
    VideoShot,
)


def _shot(index: int, start: float, end: float) -> VideoShot:
    return VideoShot(
        index=index,
        start=start,
        end=end,
        duration=round(end - start, 3),
        keyframe_time=round(start + (end - start) / 2, 3),
    )


def _frame(shot_index: int, frame_index: int, time: float, role: str = "middle") -> FrameEvidence:
    return FrameEvidence(
        shot_index=shot_index,
        frame_index=frame_index,
        time=time,
        role=role,
        local_path=f"/tmp/shot_{shot_index}_{frame_index}.jpg",
        public_url=f"/keyframes/shot_{shot_index}_{frame_index}.jpg",
    )


def test_build_analysis_units_compresses_many_short_shots_into_fewer_units():
    nodes = [
        ShotEvidenceNode(
            shot=_shot(index, (index - 1) * 0.5, index * 0.5),
            frames=[_frame(index, 1, (index - 0.5) * 0.5)],
        )
        for index in range(1, 21)
    ]

    units = build_analysis_units(nodes, target_duration=3.0, max_shots_per_unit=6)

    assert len(units) == 4
    assert units[0].unit_id == "unit_1"
    assert units[0].shot_indices == [1, 2, 3, 4, 5, 6]
    assert units[0].start == 0
    assert units[0].end == 3.0
    assert units[-1].shot_indices == [19, 20]
    assert units[-1].duration == 1.0


def test_build_analysis_units_keeps_long_shots_as_their_own_units():
    nodes = [
        ShotEvidenceNode(shot=_shot(1, 0, 1), frames=[_frame(1, 1, 0.5)]),
        ShotEvidenceNode(shot=_shot(2, 1, 9), frames=[_frame(2, 1, 5)]),
        ShotEvidenceNode(shot=_shot(3, 9, 10), frames=[_frame(3, 1, 9.5)]),
    ]

    units = build_analysis_units(nodes, target_duration=3.0, max_shots_per_unit=6)

    assert [unit.shot_indices for unit in units] == [[1], [2], [3]]
    assert units[1].duration == 8


def test_build_analysis_units_selects_representative_frames_and_text_evidence():
    nodes = [
        ShotEvidenceNode(
            shot=_shot(1, 0, 1),
            frames=[_frame(1, 1, 0.1, "start"), _frame(1, 2, 0.5, "middle")],
            ocr_texts=[
                FrameOCRText(shot_index=1, frame_index=1, frame_time=0.1, text="短", confidence=0.8),
                FrameOCRText(shot_index=1, frame_index=2, frame_time=0.5, text="限时优惠 今日下单", confidence=0.9),
            ],
            transcript_texts=[
                ShotTextAlignment(
                    shot_index=1,
                    text="开头先问痛点",
                    source_start=0,
                    source_end=1,
                    overlap_ratio=1,
                )
            ],
        ),
        ShotEvidenceNode(
            shot=_shot(2, 1, 2),
            frames=[_frame(2, 1, 1.5, "middle")],
            ocr_texts=[FrameOCRText(shot_index=2, frame_index=1, frame_time=1.5, text="马上抢", confidence=0.8)],
            transcript_texts=[
                ShotTextAlignment(
                    shot_index=2,
                    text="然后展示产品",
                    source_start=1,
                    source_end=2,
                    overlap_ratio=1,
                )
            ],
        ),
    ]

    units = build_analysis_units(nodes, target_duration=3.0, max_shots_per_unit=6)

    assert len(units) == 1
    assert [frame.role for frame in units[0].representative_frames] == ["start", "middle", "middle", "ocr_heavy"]
    assert units[0].representative_frames[-1].shot_index == 1
    assert units[0].ocr_texts[0].text == "短"
    assert [item.text for item in units[0].transcript_texts] == ["开头先问痛点", "然后展示产品"]
