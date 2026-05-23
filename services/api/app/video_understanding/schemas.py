from typing import Literal

from pydantic import BaseModel, Field


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
    shot_index: int = Field(gt=0)
    visual_summary: str = Field(min_length=1)
    subject_type: str = ""
    scene_type: str = ""
    packaging_signals: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


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
