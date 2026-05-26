import re

from app.video_understanding.schemas import ShotTextAlignment, TranscriptSegment, VideoShot

_SRT_BLOCK_RE = re.compile(
    r"(?:\d+\s+)?(?P<start>\d\d:\d\d:\d\d,\d\d\d)\s+-->\s+"
    r"(?P<end>\d\d:\d\d:\d\d,\d\d\d)\s+(?P<text>.*?)(?=\n\s*\n|\Z)",
    re.DOTALL,
)


def parse_srt_segments(raw: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    for match in _SRT_BLOCK_RE.finditer(raw.strip()):
        text = " ".join(line.strip() for line in match.group("text").splitlines() if line.strip())
        segments.append(
            TranscriptSegment(
                start=_parse_srt_time(match.group("start")),
                end=_parse_srt_time(match.group("end")),
                text=text,
            )
        )
    return segments


def align_transcript_to_shots(
    shots: list[VideoShot],
    segments: list[TranscriptSegment],
) -> list[ShotTextAlignment]:
    aligned: list[ShotTextAlignment] = []
    for shot in shots:
        for segment in segments:
            overlap = max(0.0, min(shot.end, segment.end) - max(shot.start, segment.start))
            if overlap <= 0:
                continue
            aligned.append(
                ShotTextAlignment(
                    shot_index=shot.index,
                    text=segment.text,
                    source_start=segment.start,
                    source_end=segment.end,
                    overlap_ratio=round(overlap / shot.duration, 3),
                )
            )
    return aligned


def _parse_srt_time(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return round(int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000, 3)
