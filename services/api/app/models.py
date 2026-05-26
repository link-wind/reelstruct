from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.video_understanding.schemas import KeyframeEvidence, ShotEvidenceGraph, VideoSignal


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
    video_signal: Optional[VideoSignal] = None
    keyframes: list[KeyframeEvidence] = Field(default_factory=list)


class TranscriptUploadResponse(BaseModel):
    filename: str
    transcript_summary: str


class SampleEvidenceRequest(BaseModel):
    sample_id: str
    sample_local_path: str
    video_signal: VideoSignal
    shot_indices: list[int] = Field(default_factory=list)


class MaterialFitAnalysis(BaseModel):
    duration: float = 0
    shot_count: int = 0
    recommended_slot_id: str = ""
    recommended_slot_label: str = ""
    recommendation_reason: str = ""
    slot_fit_scores: dict[str, int] = Field(default_factory=dict)


class UserSlotAsset(BaseModel):
    slot_id: str
    filename: str = ""
    local_path: str = ""
    public_url: str = ""
    analysis: MaterialFitAnalysis = Field(default_factory=MaterialFitAnalysis)


class NewContentInput(BaseModel):
    topic: str
    product_name: str = ""
    selling_points: list[str] = Field(default_factory=list)
    available_assets: list[str] = Field(default_factory=list)
    uploaded_assets: list[UserSlotAsset] = Field(default_factory=list)


class StructureSlot(BaseModel):
    id: str
    label: str
    start: float
    duration: float
    purpose: str
    required_asset: str
    sample_evidence: str
    role: str = ""
    method: str = ""
    intent: str = ""
    rhythm: str = ""
    transferable_rule: str = ""
    non_transferable: str = ""
    packaging_intent: str = ""
    evidence_shot_indices: list[int] = Field(default_factory=list)
    confidence: float = 0


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
    source: Literal["rule", "ai", "fallback"] = "rule"
    confidence: float = 0
    warnings: list[str] = Field(default_factory=list)


class TemplateStructure(BaseModel):
    title: str
    script_pattern: list[StructureSlot]
    rhythm_summary: str
    packaging_notes: list[str] = Field(default_factory=list)
    analysis_summary: SampleAnalysisSummary
    shot_evidence_graph: Optional[ShotEvidenceGraph] = None


class MaterialGap(BaseModel):
    slot_id: str
    missing_asset: str
    impact: str
    fill_strategy: str
    suggested_asset_type: str = ""
    suggested_shots: list[str] = Field(default_factory=list)
    pickup_checklist: list[str] = Field(default_factory=list)


class PackagingPlan(BaseModel):
    caption_density: str = "标准"
    title_card: str = ""
    card_text: str = ""
    emphasis_words: list[str] = Field(default_factory=list)
    transition_hint: str = ""
    cover_hint: str = ""


class TransferExplanation(BaseModel):
    slot_id: str = ""
    source_observation: str = ""
    transferable_principle: str = ""
    target_expression: str = ""
    asset_plan: str = ""
    gap_handling: str = ""
    reasoning: str = ""
    confidence: float = Field(default=0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class TransferMapping(BaseModel):
    slot_id: str
    source_label: str
    target_message: str
    asset_strategy: str
    source_method: str = ""
    target_adaptation: str = ""
    reasoning: str = ""
    asset_requirement: str = ""
    packaging_plan: str = ""
    packaging: PackagingPlan = Field(default_factory=PackagingPlan)
    fallback_strategy: str = ""
    explanation: TransferExplanation = Field(default_factory=TransferExplanation)


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
    variant: Literal["standard", "high_click", "high_conversion", "fast_rhythm"] = "standard"
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
    asset_local_path: str = ""
    asset_public_url: str = ""
    material_analysis: MaterialFitAnalysis = Field(default_factory=MaterialFitAnalysis)


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
    source_type: str = ""
    source_label: str = ""
    material_analysis: MaterialFitAnalysis = Field(default_factory=MaterialFitAnalysis)


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
    batch_id: str = ""
    created_at: str = ""
    status: Literal["succeeded", "failed"]
    pinned: bool = False
    preferred: bool = False
    template_id: str = ""
    template_title: str = ""
    template_tags: list[str] = Field(default_factory=list)
    variant: Literal["standard", "high_click", "high_conversion", "fast_rhythm"] = "standard"
    title: str
    target_topic: str = ""
    duration: float = 0
    hook: str = ""
    cta: str = ""
    gap_count: int = 0
    material_request_count: int = 0
    video_url: str = ""
    note: str = ""


class RunBatchResponse(BaseModel):
    batch_id: str
    preferred_run_id: str = ""
    runs: list[RunRecordSummary] = Field(default_factory=list)


class DemoRunResponse(BaseModel):
    run_id: str
    batch_id: str = ""
    created_at: str = ""
    status: Literal["succeeded", "failed"]
    pinned: bool = False
    preferred: bool = False
    template_id: str = ""
    template_title: str = ""
    template_tags: list[str] = Field(default_factory=list)
    variant: Literal["standard", "high_click", "high_conversion", "fast_rhythm"] = "standard"
    note: str = ""
    preview: "StructurePreviewResponse"
    prepared_assets: list[RenderClipPreview] = Field(default_factory=list)
    rendered_video: RenderDemoResponse
    trace: list[RunTraceEvent] = Field(default_factory=list)


class DemoVariantRunsResponse(BaseModel):
    runs: list[DemoRunResponse]


class RunNoteUpdateRequest(BaseModel):
    note: str = ""


class RunPinUpdateRequest(BaseModel):
    pinned: bool = False


class RunPreferredUpdateRequest(BaseModel):
    preferred: bool = False


class StructureTemplateSummary(BaseModel):
    template_id: str
    created_at: str = ""
    source_run_id: str = ""
    title: str
    tags: list[str] = Field(default_factory=list)
    slot_count: int = 0
    rhythm_summary: str = ""


class StructureTemplateVersion(BaseModel):
    version_id: str
    created_at: str = ""
    template: TemplateStructure


class StructureTemplateRecord(BaseModel):
    template_id: str
    created_at: str = ""
    source_run_id: str = ""
    tags: list[str] = Field(default_factory=list)
    template: TemplateStructure
    versions: list[StructureTemplateVersion] = Field(default_factory=list)


class CreateTemplateFromRunRequest(BaseModel):
    title: str = ""
    tags: list[str] = Field(default_factory=list)


class UpdateStructureTemplateSlotRequest(BaseModel):
    slot_id: str
    duration: float = Field(default=0, gt=0)
    required_asset: str = ""


class UpdateStructureTemplateRequest(BaseModel):
    title: str = ""
    rhythm_summary: str = ""
    tags: list[str] = Field(default_factory=list)
    slots: list[UpdateStructureTemplateSlotRequest] = Field(default_factory=list)


class StructurePreviewRequest(BaseModel):
    sample: SampleVideoInput
    content: NewContentInput
    sample_local_path: str = ""
    use_ai_structure: bool = True
    shot_evidence_graph: Optional[ShotEvidenceGraph] = None
    template_id: str = ""
    variant: Literal["standard", "high_click", "high_conversion", "fast_rhythm"] = "standard"
    use_ai_transfer_explanation: bool = False
    mapping_overrides: list[TransferMappingOverride] = Field(default_factory=list)
    material_request_sheet: list[MaterialRequestTask] = Field(default_factory=list)


class StructurePreviewResponse(BaseModel):
    template: TemplateStructure
    transfer_plan: TransferPlan
    composition: CompositionSpec
    shot_evidence_graph: Optional[ShotEvidenceGraph] = None


class StructureVariantSummary(BaseModel):
    variant: Literal["standard", "high_click", "high_conversion", "fast_rhythm"]
    title: str
    duration: float
    hook: str
    cta: str
    gap_count: int = 0
    rhythm_summary: str = ""


class StructureVariantsResponse(BaseModel):
    variants: list[StructureVariantSummary]
