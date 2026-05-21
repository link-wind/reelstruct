from typing import Literal

from pydantic import BaseModel, Field


class SampleVideoInput(BaseModel):
    title: str = "样例视频"
    duration: float = 30.0
    shot_count: int = Field(default=8, ge=1)
    transcript_summary: str = ""


class NewContentInput(BaseModel):
    topic: str
    product_name: str = ""
    selling_points: list[str] = Field(default_factory=list)
    available_assets: list[str] = Field(default_factory=list)


class StructureSlot(BaseModel):
    id: str
    label: str
    start: float
    duration: float
    purpose: str
    required_asset: str
    sample_evidence: str


class TemplateStructure(BaseModel):
    title: str
    script_pattern: list[StructureSlot]
    rhythm_summary: str
    packaging_notes: list[str] = Field(default_factory=list)


class MaterialGap(BaseModel):
    slot_id: str
    missing_asset: str
    impact: str
    fill_strategy: str


class TransferMapping(BaseModel):
    slot_id: str
    source_label: str
    target_message: str
    asset_strategy: str


class TransferPlan(BaseModel):
    title: str
    target_topic: str
    mappings: list[TransferMapping]
    gaps: list[MaterialGap] = Field(default_factory=list)


class CompositionTrack(BaseModel):
    type: Literal["video", "caption", "card"]
    start: float
    duration: float
    text: str = ""
    source: str = ""
    slot_id: str


class CompositionSpec(BaseModel):
    width: int = 720
    height: int = 1280
    fps: int = 30
    duration: float
    tracks: list[CompositionTrack]


class StructurePreviewRequest(BaseModel):
    sample: SampleVideoInput
    content: NewContentInput


class StructurePreviewResponse(BaseModel):
    template: TemplateStructure
    transfer_plan: TransferPlan
    composition: CompositionSpec
