from typing import Literal

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
    detection_method: Literal["scene_detect", "uniform_fallback"] = "scene_detect"
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
