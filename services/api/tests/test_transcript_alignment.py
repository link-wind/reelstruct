import pytest

from app.video_understanding.schemas import TranscriptSegment, VideoShot
from app.video_understanding.transcript_alignment import align_transcript_to_shots, parse_srt_segments


def test_parse_srt_segments_extracts_timestamps_and_text():
    raw = """1
00:00:01,000 --> 00:00:03,500
早上来不及吃饭？

2
00:00:03,500 --> 00:00:06,000
三分钟搞定早餐
"""

    segments = parse_srt_segments(raw)

    assert segments == [
        TranscriptSegment(start=1.0, end=3.5, text="早上来不及吃饭？"),
        TranscriptSegment(start=3.5, end=6.0, text="三分钟搞定早餐"),
    ]


def test_parse_srt_segments_joins_multiline_text():
    raw = """1
00:00:00,000 --> 00:00:02,000
第一行
第二行
"""

    segments = parse_srt_segments(raw)

    assert segments == [TranscriptSegment(start=0.0, end=2.0, text="第一行 第二行")]


def test_parse_srt_segments_returns_empty_for_blank_text():
    assert parse_srt_segments("") == []


def test_transcript_segment_requires_end_after_start():
    with pytest.raises(ValueError, match="end must be greater than start"):
        TranscriptSegment(start=2.0, end=2.0, text="无效字幕")


def test_align_transcript_to_shots_uses_time_overlap():
    shots = [
        VideoShot(index=1, start=0.0, end=2.0, duration=2.0, keyframe_time=1.0),
        VideoShot(index=2, start=2.0, end=5.0, duration=3.0, keyframe_time=3.5),
    ]
    segments = [
        TranscriptSegment(start=1.0, end=3.0, text="早上来不及吃饭？"),
        TranscriptSegment(start=3.2, end=4.8, text="三分钟搞定早餐"),
    ]

    aligned = align_transcript_to_shots(shots, segments)

    assert [item.shot_index for item in aligned] == [1, 2, 2]
    assert aligned[0].overlap_ratio == 0.5
    assert aligned[1].overlap_ratio == 0.333
    assert aligned[2].text == "三分钟搞定早餐"


def test_align_transcript_to_shots_skips_segments_without_overlap():
    shots = [VideoShot(index=1, start=0.0, end=1.0, duration=1.0, keyframe_time=0.5)]
    segments = [TranscriptSegment(start=2.0, end=3.0, text="不重叠")]

    assert align_transcript_to_shots(shots, segments) == []
