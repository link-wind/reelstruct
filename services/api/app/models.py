# Phase 2 compatibility layer. Do not add new model definitions here.
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
    visual_summary: str = ""
    tags: list[str] = Field(default_factory=list)
    usable_for: list[str] = Field(default_factory=list)
    embedding_text: str = ""
    evidence_chunks: list["MaterialEvidenceChunk"] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MaterialEvidenceChunk(BaseModel):
    asset_id: str = ""
    chunk_id: str
    start: float = 0
    end: float = 0
    duration: float = 0
    frame_urls: list[str] = Field(default_factory=list)
    ocr_texts: list[str] = Field(default_factory=list)
    asr_texts: list[str] = Field(default_factory=list)
    visual_summary: str = ""
    packaging_signals: list[str] = Field(default_factory=list)
    subject_tags: list[str] = Field(default_factory=list)
    action_tags: list[str] = Field(default_factory=list)
    slot_hints: list[str] = Field(default_factory=list)
    modalities: list[str] = Field(default_factory=list)
    embedding_text: str = ""


class MaterialGraphNode(BaseModel):
    node_id: str
    node_type: Literal["asset", "chunk", "frame", "ocr_text", "asr_text", "packaging_signal", "tag", "slot_hint"]
    label: str = ""
    source_asset_id: str = ""
    chunk_id: str = ""
    start: float = 0
    end: float = 0
    text: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class MaterialGraphEdge(BaseModel):
    source: str
    target: str
    relation: Literal["contains", "has_evidence", "supports_slot", "needs_packaging"]
    weight: float = Field(default=1, ge=0, le=1)


class MaterialGraph(BaseModel):
    material_id: str = ""
    nodes: list[MaterialGraphNode] = Field(default_factory=list)
    edges: list[MaterialGraphEdge] = Field(default_factory=list)


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


class GraphPresentationNode(BaseModel):
    id: str
    label: str
    node_type: Literal["segment", "unit", "shot", "text", "gap"]
    summary: str = ""
    shot_indices: list[int] = Field(default_factory=list)
    confidence: float = 0


class GraphPresentationEdge(BaseModel):
    source: str
    target: str
    relation: str = ""


class GraphPresentationSummary(BaseModel):
    headline: str = ""
    summary_points: list[str] = Field(default_factory=list)
    nodes: list[GraphPresentationNode] = Field(default_factory=list)
    edges: list[GraphPresentationEdge] = Field(default_factory=list)


class SampleAnalysisSummary(BaseModel):
    headline: str
    metrics: list[SampleAnalysisMetric] = Field(default_factory=list)
    narrative_beats: list[SampleAnalysisBeat] = Field(default_factory=list)
    packaging_signals: list[str] = Field(default_factory=list)
    source: Literal["rule", "ai", "fallback"] = "rule"
    confidence: float = 0
    warnings: list[str] = Field(default_factory=list)
    graph_presentation: Optional[GraphPresentationSummary] = None


class TemplateStructure(BaseModel):
    title: str
    script_pattern: list[StructureSlot]
    rhythm_summary: str
    packaging_notes: list[str] = Field(default_factory=list)
    analysis_summary: SampleAnalysisSummary
    shot_evidence_graph: Optional[ShotEvidenceGraph] = None


class MaterialSupplementOption(BaseModel):
    method: Literal["现有素材复用", "文案/字幕补全", "包装补全", "结构重排", "补拍/AIGC"] = "文案/字幕补全"
    title: str = ""
    action: str = ""
    evidence: list[str] = Field(default_factory=list)
    priority: int = 0


class SlotRetrievalPlan(BaseModel):
    slot_id: str = ""
    slot_label: str = ""
    required_asset: str = ""
    required_expression: str = ""
    query_summary: str = ""
    best_candidate_id: str = ""
    best_candidate_label: str = ""
    matched_evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommended_method: str = ""
    generation_action: str = ""
    confidence: float = Field(default=0, ge=0, le=1)


class SlotQueryProfile(BaseModel):
    slot_id: str = ""
    slot_label: str = ""
    required_asset: str = ""
    required_expression: str = ""
    semantic_terms: list[str] = Field(default_factory=list)
    visual_terms: list[str] = Field(default_factory=list)
    action_terms: list[str] = Field(default_factory=list)
    text_terms: list[str] = Field(default_factory=list)
    packaging_terms: list[str] = Field(default_factory=list)
    target_duration: float = 0
    min_usable_duration: float = 0
    replacement_modes: list[
        Literal["reuse_direct", "reuse_with_packaging", "caption_only", "structure_reorder", "shoot_or_aigc"]
    ] = Field(default_factory=list)


class MaterialGraphMatchedNode(BaseModel):
    node_id: str = ""
    node_type: str = ""
    label: str = ""
    text: str = ""
    source_asset_id: str = ""
    chunk_id: str = ""


class MaterialGraphSearchResult(BaseModel):
    slot_id: str = ""
    asset_id: str = ""
    chunk_id: str = ""
    start: float = 0
    end: float = 0
    matched_nodes: list[MaterialGraphMatchedNode] = Field(default_factory=list)
    evidence_path: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, int] = Field(default_factory=dict)
    confidence: float = Field(default=0, ge=0, le=1)


class StructureCoverageResult(BaseModel):
    slot_id: str = ""
    coverage_score: float = Field(default=0, ge=0, le=1)
    gap_level: Literal["low", "medium", "high"] = "high"
    fillability: Literal["direct", "packaging", "reorder", "missing"] = "missing"
    summary: str = ""


class TimelineTrackUpdate(BaseModel):
    type: Literal["video", "caption", "card"]
    action: Literal["replace", "insert", "request"]
    text: str = ""
    duration: float = 0
    style_hint: str = ""


class TimelinePatch(BaseModel):
    patch_id: str = ""
    slot_id: str = ""
    operation: Literal["replace_slot_media", "insert_caption_card", "request_asset"] = "insert_caption_card"
    target_start: float = 0
    target_end: float = 0
    execution_summary: str = ""
    source_asset_id: str = ""
    source_chunk_id: str = ""
    source_start: float = 0
    source_end: float = 0
    track_updates: list[TimelineTrackUpdate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SlotFillDecision(BaseModel):
    slot_id: str = ""
    decision_type: Literal["reuse_direct", "reuse_with_packaging", "caption_only", "structure_reorder", "shoot_or_aigc"] = "caption_only"
    selected_asset_id: str = ""
    selected_chunk_id: str = ""
    start: float = 0
    end: float = 0
    confidence: float = Field(default=0, ge=0, le=1)
    why: str = ""
    missing: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    timeline_hint: str = ""
    evidence_path: list[str] = Field(default_factory=list)
    timeline_patch_id: str = ""


class MaterialGap(BaseModel):
    slot_id: str
    missing_asset: str
    impact: str
    fill_strategy: str
    suggested_asset_type: str = ""
    suggested_shots: list[str] = Field(default_factory=list)
    pickup_checklist: list[str] = Field(default_factory=list)
    retrieval_status: Literal["缺失", "可复用", "可包装后使用"] = "缺失"
    candidates: list["MaterialRetrievalCandidate"] = Field(default_factory=list)
    retrieval_reason: str = ""
    primary_supplement: str = ""
    supplement_options: list[MaterialSupplementOption] = Field(default_factory=list)
    retrieval_plan: SlotRetrievalPlan = Field(default_factory=SlotRetrievalPlan)
    slot_fill_decision: SlotFillDecision = Field(default_factory=SlotFillDecision)
    slot_query_profile: SlotQueryProfile = Field(default_factory=SlotQueryProfile)
    coverage_result: StructureCoverageResult = Field(default_factory=StructureCoverageResult)
    graph_search_results: list[MaterialGraphSearchResult] = Field(default_factory=list)
    timeline_patches: list[TimelinePatch] = Field(default_factory=list)


class MaterialRetrievalCandidate(BaseModel):
    asset_id: str
    filename: str = ""
    source_slot_id: str = ""
    public_url: str = ""
    chunk_id: str = ""
    start: float = 0
    end: float = 0
    matched_modalities: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    match_score: int = 0
    score_breakdown: dict[str, int] = Field(default_factory=dict)
    match_reason: str = ""
    reuse_strategy: str = ""


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


class SupplementSelection(BaseModel):
    slot_id: str
    method: Literal["现有素材复用", "文案/字幕补全", "包装补全", "结构重排", "补拍/AIGC"]


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


class EvaluationSummary(BaseModel):
    headline: str = ""
    highlights: list[str] = Field(default_factory=list)
    structure_quality: Literal["low", "medium", "high"] = "low"
    retrieval_quality: Literal["low", "medium", "high"] = "low"
    completion_quality: Literal["low", "medium", "high"] = "low"
    result_quality: Literal["low", "medium", "high"] = "low"


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
    evaluation_summary: EvaluationSummary = Field(default_factory=EvaluationSummary)
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
    supplement_selections: list[SupplementSelection] = Field(default_factory=list)


class StructurePreviewResponse(BaseModel):
    template: TemplateStructure
    transfer_plan: TransferPlan
    composition: CompositionSpec
    shot_evidence_graph: Optional[ShotEvidenceGraph] = None
    evaluation_summary: EvaluationSummary = Field(default_factory=EvaluationSummary)


class PreviewRunRequest(BaseModel):
    preview: StructurePreviewResponse
    template_id: str = ""
    template_title: str = ""
    template_tags: list[str] = Field(default_factory=list)
    variant: Literal["standard", "high_click", "high_conversion", "fast_rhythm"] = "standard"
    mapping_overrides: list[TransferMappingOverride] = Field(default_factory=list)


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


# Phase 2 keeps the legacy module path intact here; split modules re-export
# these names without moving the underlying definitions yet.
