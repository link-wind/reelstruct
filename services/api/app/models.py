from typing import Literal

from pydantic import BaseModel, Field


class SampleVideoInput(BaseModel):
    title: str = "样例视频"
    duration: float = 30.0
    shot_count: int = Field(default=8, ge=1)
    transcript_summary: str = ""


class SampleUploadResponse(BaseModel):
    sample_id: str
    filename: str
    local_path: str
    public_url: str
    sample: SampleVideoInput


class TranscriptUploadResponse(BaseModel):
    filename: str
    transcript_summary: str


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


class SampleAnalysisMetric(BaseModel):
    label: str
    value: str
    detail: str = ""


class SampleAnalysisBeat(BaseModel):
    slot_id: str
    label: str
    evidence: str


class SampleAnalysisSummary(BaseModel):
    headline: str
    metrics: list[SampleAnalysisMetric] = Field(default_factory=list)
    narrative_beats: list[SampleAnalysisBeat] = Field(default_factory=list)
    packaging_signals: list[str] = Field(default_factory=list)


class TemplateStructure(BaseModel):
    title: str
    script_pattern: list[StructureSlot]
    rhythm_summary: str
    packaging_notes: list[str] = Field(default_factory=list)
    analysis_summary: SampleAnalysisSummary


class MaterialGap(BaseModel):
    slot_id: str
    missing_asset: str
    impact: str
    fill_strategy: str
    suggested_asset_type: str = ""
    suggested_shots: list[str] = Field(default_factory=list)
    pickup_checklist: list[str] = Field(default_factory=list)


class TransferMapping(BaseModel):
    slot_id: str
    source_label: str
    target_message: str
    asset_strategy: str


class TransferMappingOverride(BaseModel):
    slot_id: str
    target_message: str = ""
    sample_evidence: str = ""
    asset_strategy: str = ""


class MaterialRequestTask(BaseModel):
    slot_id: str
    status: Literal["待补拍", "已拍", "已交付"] = "待补拍"


class TransferPlan(BaseModel):
    title: str
    target_topic: str
    mappings: list[TransferMapping]
    gaps: list[MaterialGap] = Field(default_factory=list)
    material_request_sheet: list[MaterialRequestTask] = Field(default_factory=list)


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


class RenderClipPreview(BaseModel):
    scene_id: str
    local_path: str
    public_url: str
    caption: str = ""
    start_time: float = 0
    duration: float = 0


class PrepareDemoAssetsResponse(BaseModel):
    clips: list[RenderClipPreview]


class RenderDemoResponse(BaseModel):
    video_url: str
    local_path: str


class RunTraceEvent(BaseModel):
    step: str
    title: str
    message: str
    progress: int


class RunRecordSummary(BaseModel):
    run_id: str
    created_at: str = ""
    status: Literal["succeeded", "failed"]
    pinned: bool = False
    template_id: str = ""
    template_title: str = ""
    title: str
    target_topic: str = ""
    gap_count: int = 0
    material_request_count: int = 0
    video_url: str = ""
    note: str = ""


class DemoRunResponse(BaseModel):
    run_id: str
    created_at: str = ""
    status: Literal["succeeded", "failed"]
    pinned: bool = False
    template_id: str = ""
    template_title: str = ""
    note: str = ""
    preview: "StructurePreviewResponse"
    prepared_assets: list[RenderClipPreview] = Field(default_factory=list)
    rendered_video: RenderDemoResponse
    trace: list[RunTraceEvent] = Field(default_factory=list)


class RunNoteUpdateRequest(BaseModel):
    note: str = ""


class RunPinUpdateRequest(BaseModel):
    pinned: bool = False


class StructureTemplateSummary(BaseModel):
    template_id: str
    created_at: str = ""
    source_run_id: str = ""
    title: str
    slot_count: int = 0
    rhythm_summary: str = ""


class StructureTemplateRecord(BaseModel):
    template_id: str
    created_at: str = ""
    source_run_id: str = ""
    template: TemplateStructure


class CreateTemplateFromRunRequest(BaseModel):
    title: str = ""


class StructurePreviewRequest(BaseModel):
    sample: SampleVideoInput
    content: NewContentInput
    template_id: str = ""
    mapping_overrides: list[TransferMappingOverride] = Field(default_factory=list)
    material_request_sheet: list[MaterialRequestTask] = Field(default_factory=list)


class StructurePreviewResponse(BaseModel):
    template: TemplateStructure
    transfer_plan: TransferPlan
    composition: CompositionSpec
