from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VideoMetadata(BaseModel):
    duration: float = Field(gt=0)
    fps: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    format_name: str = ""


class VideoShot(BaseModel):
    index: int = Field(gt=0)
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    duration: float = Field(gt=0)
    keyframe_time: float = Field(default=0, ge=0)


class KeyframeEvidence(BaseModel):
    shot_index: int = Field(gt=0)
    keyframe_time: float = Field(ge=0)
    local_path: str = Field(min_length=1)
    public_url: str = Field(min_length=1)


class FrameEvidence(BaseModel):
    shot_index: int = Field(gt=0)
    frame_index: int = Field(gt=0)
    time: float = Field(ge=0)
    role: Literal["start", "middle", "safe_end", "end", "third", "two_thirds", "ocr_heavy"] = "middle"
    local_path: str = Field(min_length=1)
    public_url: str = Field(min_length=1)


class FrameOCRText(BaseModel):
    shot_index: int = Field(gt=0)
    frame_index: int = Field(gt=0)
    frame_time: float = Field(ge=0)
    text: str = ""
    position: str = ""
    confidence: float = Field(default=0, ge=0, le=1)


class TranscriptSegment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str = ""

    @model_validator(mode="after")
    def validate_timing(self) -> "TranscriptSegment":
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class ShotTextAlignment(BaseModel):
    shot_index: int = Field(gt=0)
    text: str = ""
    source_start: float = Field(ge=0)
    source_end: float = Field(ge=0)
    overlap_ratio: float = Field(default=0, ge=0, le=1)


class ShotVisualAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_index: int = Field(gt=0)
    visual_summary: str = Field(min_length=1)
    subject_type: str = ""
    scene_type: str = ""
    packaging_signals: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class ShotEvidence(BaseModel):
    shot_index: int = Field(gt=0)
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    duration: float = Field(gt=0)
    keyframe_public_url: str = ""
    transcript_text: str = ""
    visual_summary: str = ""
    packaging_signals: list[str] = Field(default_factory=list)


class RhythmMetrics(BaseModel):
    avg_shot_duration: float = 0
    cut_density: Literal["slow", "medium", "fast"] = "medium"
    fastest_window: str = ""
    slowest_window: str = ""


class VideoSignal(BaseModel):
    metadata: VideoMetadata
    shot_count: int = Field(default=0, ge=0)
    detection_method: Literal[
        "scene_detect",
        "pyscenedetect_adaptive",
        "pyscenedetect_content",
        "ffmpeg_scene_detect",
        "uniform_fallback",
    ] = "ffmpeg_scene_detect"
    shots: list[VideoShot] = Field(default_factory=list)
    rhythm_metrics: RhythmMetrics = Field(default_factory=RhythmMetrics)


class VideoStructureSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    type: str = Field(min_length=1)
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    shot_indices: list[int] = Field(default_factory=list, min_length=1)
    purpose: str = Field(min_length=1)
    method: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    rhythm: str = Field(min_length=1)
    packaging: str = Field(min_length=1)
    required_asset: str = ""
    transferable_rule: str = Field(min_length=1)
    non_transferable: str = Field(min_length=1)
    confidence: float = Field(default=0, ge=0, le=1)

    @model_validator(mode="after")
    def validate_timing_and_shots(self) -> "VideoStructureSegment":
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        if any(item <= 0 for item in self.shot_indices):
            raise ValueError("shot_indices must contain only positive integers")
        return self


class AIRhythmStructure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = ""
    peak_position: str = ""
    slowdown_position: str = ""


class AIPackagingStructure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caption_density: str = ""
    title_style: str = ""
    transition_style: str = ""
    cover_style: str = ""


class AIStructureAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["ai"] = "ai"
    headline: str = Field(min_length=1)
    segments: list[VideoStructureSegment] = Field(min_length=1)
    rhythm_structure: AIRhythmStructure = Field(default_factory=AIRhythmStructure)
    packaging_structure: AIPackagingStructure = Field(default_factory=AIPackagingStructure)
    confidence: float = Field(default=0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class ShotUnderstanding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_index: int = Field(gt=0)
    visual_summary: str = ""
    text_summary: str = ""
    subject: str = ""
    scene: str = ""
    action: str = ""
    packaging_signals: list[str] = Field(default_factory=list)
    creative_function_hint: str = ""
    confidence: float = Field(default=0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class AnalysisUnitUnderstanding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: str = Field(min_length=1)
    visual_summary: str = ""
    text_summary: str = ""
    subject: str = ""
    scene: str = ""
    action: str = ""
    packaging_signals: list[str] = Field(default_factory=list)
    creative_function_hint: str = ""
    confidence: float = Field(default=0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class ShotEvidenceNode(BaseModel):
    shot: VideoShot
    frames: list[FrameEvidence] = Field(default_factory=list)
    ocr_texts: list[FrameOCRText] = Field(default_factory=list)
    transcript_texts: list[ShotTextAlignment] = Field(default_factory=list)
    understanding: Optional[ShotUnderstanding] = None

    @model_validator(mode="after")
    def validate_understanding_index(self) -> "ShotEvidenceNode":
        if self.understanding is None:
            self.understanding = ShotUnderstanding(shot_index=self.shot.index)
        if self.understanding.shot_index != self.shot.index:
            raise ValueError("understanding.shot_index must match shot.index")
        return self


class AnalysisUnit(BaseModel):
    unit_id: str = Field(min_length=1)
    shot_indices: list[int] = Field(default_factory=list, min_length=1)
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    duration: float = Field(gt=0)
    representative_frames: list[FrameEvidence] = Field(default_factory=list)
    ocr_texts: list[FrameOCRText] = Field(default_factory=list)
    transcript_texts: list[ShotTextAlignment] = Field(default_factory=list)
    understanding: Optional[AnalysisUnitUnderstanding] = None

    @model_validator(mode="after")
    def validate_timing_and_understanding(self) -> "AnalysisUnit":
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        if any(shot_index <= 0 for shot_index in self.shot_indices):
            raise ValueError("shot_indices must contain only positive integers")
        if self.understanding is None:
            self.understanding = AnalysisUnitUnderstanding(unit_id=self.unit_id)
        if self.understanding.unit_id != self.unit_id:
            raise ValueError("understanding.unit_id must match unit_id")
        return self


class ShotRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_shot: int = Field(gt=0)
    to_shot: int = Field(gt=0)
    relation_type: str = Field(min_length=1)
    relation_summary: str = ""
    rhythm_change: str = ""
    semantic_shift: str = ""
    confidence: float = Field(default=0, ge=0, le=1)


class CreativeBeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    shot_indices: list[int] = Field(default_factory=list, min_length=1)
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    function: str = ""
    reason: str = ""
    confidence: float = Field(default=0, ge=0, le=1)


class EvidenceBackedSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    beat_ids: list[str] = Field(default_factory=list)
    shot_indices: list[int] = Field(default_factory=list, min_length=1)
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    purpose: str = ""
    method: str = ""
    evidence: list[str] = Field(default_factory=list)
    rhythm: str = ""
    packaging: str = ""
    transferable_rule: str = ""
    non_transferable: str = ""
    required_asset: str = ""
    confidence: float = Field(default=0, ge=0, le=1)


class RhythmCurvePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: float = Field(ge=0)
    end: float = Field(ge=0)
    shot_count: int = Field(default=0, ge=0)
    density: str = ""
    note: str = ""

    @model_validator(mode="after")
    def validate_timing(self) -> "RhythmCurvePoint":
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class SegmentRhythmNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str = ""
    note: str = ""


class GraphRhythmStructure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = ""
    avg_shot_duration: float = Field(default=0, ge=0)
    cut_density: str = ""
    fast_windows: list[str] = Field(default_factory=list)
    slow_windows: list[str] = Field(default_factory=list)
    peak_position: str = ""
    slowdown_position: str = ""
    rhythm_curve: list[RhythmCurvePoint] = Field(default_factory=list)
    segment_notes: list[SegmentRhythmNote] = Field(default_factory=list)


class PackagingTimelineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: float = Field(default=0, ge=0)
    end: float = Field(default=0, ge=0)
    type: str = ""
    evidence: str = ""

    @model_validator(mode="after")
    def validate_timing(self) -> "PackagingTimelineItem":
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class GraphPackagingStructure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caption_density: str = ""
    title_style: str = ""
    transition_style: str = ""
    cover_style: str = ""
    text_layout: str = ""
    title_cards: list[str] = Field(default_factory=list)
    sticker_signals: list[str] = Field(default_factory=list)
    packaging_timeline: list[PackagingTimelineItem] = Field(default_factory=list)


class ShotEvidenceGraph(BaseModel):
    shots: list[ShotEvidenceNode] = Field(default_factory=list)
    analysis_units: list[AnalysisUnit] = Field(default_factory=list)
    relations: list[ShotRelation] = Field(default_factory=list)
    beats: list[CreativeBeat] = Field(default_factory=list)
    segments: list[EvidenceBackedSegment] = Field(default_factory=list)
    rhythm_structure: GraphRhythmStructure = Field(default_factory=GraphRhythmStructure)
    packaging_structure: GraphPackagingStructure = Field(default_factory=GraphPackagingStructure)
    warnings: list[str] = Field(default_factory=list)


class GraphAggregationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relations: list[ShotRelation] = Field(default_factory=list)
    beats: list[CreativeBeat] = Field(default_factory=list)
    segments: list[EvidenceBackedSegment] = Field(default_factory=list)
    rhythm_structure: GraphRhythmStructure = Field(default_factory=GraphRhythmStructure)
    packaging_structure: GraphPackagingStructure = Field(default_factory=GraphPackagingStructure)
    warnings: list[str] = Field(default_factory=list)
