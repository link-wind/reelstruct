'use client'

import { useEffect, useMemo, useState } from 'react'
import type { WorkspaceRuntimeState } from '../agent/types'

export type StructureSlot = {
  id: string
  label: string
  start: number
  duration: number
  purpose: string
  required_asset: string
  sample_evidence: string
  role: string
  method: string
  intent: string
  rhythm: string
  transferable_rule: string
  non_transferable: string
  packaging_intent: string
  evidence_shot_indices: number[]
  confidence: number
}

type SlotFillDecision = {
  slot_id: string
  decision_type: 'reuse_direct' | 'reuse_with_packaging' | 'caption_only' | 'structure_reorder' | 'shoot_or_aigc'
  selected_asset_id: string
  selected_chunk_id: string
  start: number
  end: number
  confidence: number
  why: string
  missing: string[]
  actions: string[]
  timeline_hint: string
  evidence_path: string[]
  timeline_patch_id: string
}

type SlotQueryProfile = {
  slot_id: string
  slot_label: string
  required_asset: string
  required_expression: string
  semantic_terms: string[]
  visual_terms: string[]
  action_terms: string[]
  text_terms: string[]
  packaging_terms: string[]
  target_duration: number
  min_usable_duration: number
  replacement_modes: Array<'reuse_direct' | 'reuse_with_packaging' | 'caption_only' | 'structure_reorder' | 'shoot_or_aigc'>
}

type MaterialGraphMatchedNode = {
  node_id: string
  node_type: string
  label: string
  text: string
  source_asset_id: string
  chunk_id: string
}

type MaterialGraphSearchResult = {
  slot_id: string
  asset_id: string
  chunk_id: string
  start: number
  end: number
  matched_nodes: MaterialGraphMatchedNode[]
  evidence_path: string[]
  missing: string[]
  score_breakdown: Record<string, number>
  confidence: number
}

type StructureCoverageResult = {
  slot_id: string
  coverage_score: number
  gap_level: 'low' | 'medium' | 'high'
  fillability: 'direct' | 'packaging' | 'reorder' | 'missing'
  summary: string
}

type TimelineTrackUpdate = {
  type: 'video' | 'caption' | 'card'
  action: 'replace' | 'insert' | 'request'
  text: string
  duration: number
  style_hint: string
}

type TimelinePatch = {
  patch_id: string
  slot_id: string
  operation: 'replace_slot_media' | 'insert_caption_card' | 'request_asset'
  target_start: number
  target_end: number
  execution_summary: string
  source_asset_id: string
  source_chunk_id: string
  source_start: number
  source_end: number
  track_updates: TimelineTrackUpdate[]
  warnings: string[]
}

export type MaterialGap = {
  slot_id: string
  missing_asset: string
  impact: string
  fill_strategy: string
  suggested_asset_type: string
  suggested_shots: string[]
  pickup_checklist: string[]
  retrieval_status: '缺失' | '可复用' | '可包装后使用'
  candidates: MaterialRetrievalCandidate[]
  retrieval_reason: string
  primary_supplement: string
  supplement_options: MaterialSupplementOption[]
  retrieval_plan: SlotRetrievalPlan
  slot_fill_decision: SlotFillDecision
  slot_query_profile: SlotQueryProfile
  coverage_result: StructureCoverageResult
  graph_search_results: MaterialGraphSearchResult[]
  timeline_patches: TimelinePatch[]
}

type SlotRetrievalPlan = {
  slot_id: string
  slot_label: string
  required_asset: string
  required_expression: string
  query_summary: string
  best_candidate_id: string
  best_candidate_label: string
  matched_evidence: string[]
  missing_evidence: string[]
  recommended_method: string
  generation_action: string
  confidence: number
}

type MaterialSupplementOption = {
  method: '现有素材复用' | '文案/字幕补全' | '包装补全' | '结构重排' | '补拍/AIGC'
  title: string
  action: string
  evidence: string[]
  priority: number
}

type MaterialRetrievalCandidate = {
  asset_id: string
  filename: string
  source_slot_id: string
  public_url: string
  chunk_id: string
  start: number
  end: number
  matched_modalities: string[]
  evidence: string[]
  match_score: number
  score_breakdown: Record<string, number>
  match_reason: string
  reuse_strategy: string
}

export type MaterialTaskStatus = '待补拍' | '已拍' | '已交付'

export type MaterialRequestTask = {
  slot_id: string
  status: MaterialTaskStatus
}

type MaterialRequestSheetItem = {
  task: MaterialRequestTask
  slot: StructureSlot
  gap: MaterialGap | undefined
}

export type MaterialFitAnalysis = {
  duration: number
  shot_count: number
  recommended_slot_id: string
  recommended_slot_label: string
  recommendation_reason: string
  slot_fit_scores: Record<string, number>
  visual_summary: string
  tags: string[]
  usable_for: string[]
  embedding_text: string
  evidence_chunks: MaterialEvidenceChunk[]
  warnings: string[]
}

type MaterialEvidenceChunk = {
  asset_id: string
  chunk_id: string
  start: number
  end: number
  duration: number
  frame_urls: string[]
  ocr_texts: string[]
  asr_texts: string[]
  visual_summary: string
  packaging_signals: string[]
  subject_tags: string[]
  action_tags: string[]
  slot_hints: string[]
  modalities: string[]
  embedding_text: string
}

export type UserSlotAsset = {
  slot_id: string
  filename: string
  local_path: string
  public_url: string
  analysis: MaterialFitAnalysis
}

type PackagingPlan = {
  caption_density: string
  title_card: string
  card_text: string
  emphasis_words: string[]
  transition_hint: string
  cover_hint: string
}

type TransferExplanation = {
  slot_id: string
  source_observation: string
  transferable_principle: string
  target_expression: string
  asset_plan: string
  gap_handling: string
  reasoning: string
  confidence: number
  warnings: string[]
}

export type TransferMapping = {
  slot_id: string
  source_label: string
  target_message: string
  asset_strategy: string
  source_method: string
  target_adaptation: string
  reasoning: string
  asset_requirement: string
  packaging_plan: string
  packaging: PackagingPlan
  fallback_strategy: string
  explanation?: TransferExplanation
}

type CompositionTrack = {
  type: 'video' | 'caption' | 'card'
  start: number
  duration: number
  text: string
  source: string
  slot_id: string
  asset_local_path: string
  asset_public_url: string
}

type GraphPresentationNode = {
  id: string
  label: string
  node_type: 'segment' | 'unit' | 'shot' | 'text' | 'gap'
  summary: string
  shot_indices: number[]
  confidence: number
}

type GraphPresentationEdge = {
  source: string
  target: string
  relation: string
}

type GraphPresentationSummary = {
  headline: string
  summary_points: string[]
  nodes: GraphPresentationNode[]
  edges: GraphPresentationEdge[]
}

export type FrameEvidence = {
  shot_index: number
  frame_index: number
  time: number
  role: 'start' | 'middle' | 'safe_end' | 'end' | 'third' | 'two_thirds'
  public_url: string
}

export type ShotUnderstanding = {
  shot_index: number
  visual_summary: string
  text_summary: string
  subject: string
  scene: string
  action: string
  packaging_signals: string[]
  creative_function_hint: string
  confidence: number
  warnings: string[]
}

export type FrameOCRText = {
  shot_index: number
  frame_index: number
  frame_time: number
  text: string
  position: string
  confidence: number
}

export type ShotTextAlignment = {
  shot_index: number
  text: string
  source_start: number
  source_end: number
  overlap_ratio: number
}

export type ShotEvidenceNode = {
  shot: VideoShot
  frames: FrameEvidence[]
  ocr_texts: FrameOCRText[]
  transcript_texts: ShotTextAlignment[]
  understanding: ShotUnderstanding
}

export type AnalysisUnitUnderstanding = {
  unit_id: string
  visual_summary: string
  text_summary: string
  subject: string
  scene: string
  action: string
  packaging_signals: string[]
  creative_function_hint: string
  confidence: number
  warnings: string[]
}

export type AnalysisUnit = {
  unit_id: string
  shot_indices: number[]
  start: number
  end: number
  duration: number
  representative_frames: FrameEvidence[]
  ocr_texts: FrameOCRText[]
  transcript_texts: ShotTextAlignment[]
  understanding: AnalysisUnitUnderstanding
}

export type ShotRelation = {
  from_shot: number
  to_shot: number
  relation_type: string
  relation_summary: string
  rhythm_change: string
  semantic_shift: string
  confidence: number
}

export type ShotEvidenceGraph = {
  shots: ShotEvidenceNode[]
  analysis_units: AnalysisUnit[]
  relations: ShotRelation[]
  warnings: string[]
}

export type EvaluationSummary = {
  headline: string
  highlights: string[]
  structure_quality: 'low' | 'medium' | 'high'
  retrieval_quality: 'low' | 'medium' | 'high'
  completion_quality: 'low' | 'medium' | 'high'
  result_quality: 'low' | 'medium' | 'high'
}

export type StructurePreviewResponse = {
  template: {
    title: string
    script_pattern: StructureSlot[]
    rhythm_summary: string
    packaging_notes: string[]
    analysis_summary: {
      headline: string
      metrics: Array<{
        label: string
        value: string
        detail: string
      }>
      narrative_beats: Array<{
        slot_id: string
        label: string
        evidence: string
      }>
      packaging_signals: string[]
      source: 'rule' | 'ai' | 'fallback'
      confidence: number
      warnings: string[]
      graph_presentation?: GraphPresentationSummary | null
    }
  }
  transfer_plan: {
    title: string
    target_topic: string
    variant: OutputVariant
    mappings: TransferMapping[]
    gaps: MaterialGap[]
    material_request_sheet: MaterialRequestTask[]
  }
  composition: {
    width: number
    height: number
    fps: number
    duration: number
    tracks: CompositionTrack[]
  }
  shot_evidence_graph?: ShotEvidenceGraph
  evaluation_summary: EvaluationSummary
}

type RenderDemoResponse = {
  video_url: string
  local_path: string
}

type RenderClipPreview = {
  scene_id: string
  local_path: string
  public_url: string
  caption: string
  start_time: number
  duration: number
  source_type: string
  source_label: string
  material_analysis: MaterialFitAnalysis
}

type RunTraceEvent = {
  step: string
  title: string
  message: string
  progress: number
}

export type DemoRunResponse = {
  run_id: string
  batch_id: string
  created_at: string
  status: 'succeeded' | 'failed'
  pinned: boolean
  preferred: boolean
  template_id: string
  template_title: string
  template_tags: string[]
  variant: OutputVariant
  note: string
  preview: StructurePreviewResponse
  evaluation_summary: EvaluationSummary
  prepared_assets: RenderClipPreview[]
  rendered_video: RenderDemoResponse
  trace: RunTraceEvent[]
}

type DemoVariantRunsResponse = {
  runs: DemoRunResponse[]
}

export type RunRecordSummary = {
  run_id: string
  batch_id: string
  created_at: string
  status: 'succeeded' | 'failed'
  pinned: boolean
  preferred: boolean
  template_id: string
  template_title: string
  template_tags: string[]
  variant: OutputVariant
  title: string
  target_topic: string
  duration: number
  hook: string
  cta: string
  gap_count: number
  material_request_count: number
  video_url: string
  note: string
}

export type RunBatchResponse = {
  batch_id: string
  preferred_run_id: string
  runs: RunRecordSummary[]
}

export type StructureVariantSummary = {
  variant: OutputVariant
  title: string
  duration: number
  hook: string
  cta: string
  gap_count: number
  rhythm_summary: string
}

type StructureVariantsResponse = {
  variants: StructureVariantSummary[]
}

export type StructureTemplateRecord = {
  template_id: string
  created_at: string
  source_run_id: string
  tags: string[]
  template: {
    title: string
    rhythm_summary: string
    script_pattern: StructureSlot[]
  }
  versions: Array<{
    version_id: string
    created_at: string
    template: {
      title: string
      rhythm_summary: string
    }
  }>
}

type StructureTemplateSummary = {
  template_id: string
  created_at: string
  source_run_id: string
  title: string
  tags: string[]
  slot_count: number
  rhythm_summary: string
}

type RunStatusFilter = 'all' | 'succeeded'

export type OutputVariant = 'standard' | 'high_click' | 'high_conversion' | 'fast_rhythm'

export type SampleVideoInput = {
  title: string
  duration: number
  shot_count: number
  transcript_summary: string
}

export type VideoShot = {
  index: number
  start: number
  end: number
  duration: number
  keyframe_time: number
}

type VideoSignal = {
  metadata: {
    duration: number
    fps: number
    width: number
    height: number
    format_name: string
  }
  shot_count: number
  detection_method: 'scene_detect' | 'uniform_fallback'
  shots: VideoShot[]
  rhythm_metrics: {
    avg_shot_duration: number
    cut_density: 'slow' | 'medium' | 'fast'
    fastest_window: string
    slowest_window: string
  }
}

export type KeyframeEvidence = {
  shot_index: number
  keyframe_time: number
  local_path: string
  public_url: string
}

export type NewContentInput = {
  topic: string
  product_name: string
  selling_points: string[]
  available_assets: string[]
  uploaded_assets: UserSlotAsset[]
}

export type SampleUploadResponse = {
  sample_id: string
  filename: string
  local_path: string
  public_url: string
  sample: SampleVideoInput
  video_signal: VideoSignal | null
  keyframes: KeyframeEvidence[]
}

export type TranscriptUploadResponse = {
  filename: string
  transcript_summary: string
}

type TransferMappingOverride = {
  slot_id: string
  target_message: string
  sample_evidence: string
  asset_strategy: string
}

type SlotDraft = {
  target_message: string
  sample_evidence: string
  asset_strategy: string
}

type TemplateSlotDraft = {
  duration: string
  required_asset: string
}

type TemplateEditorDraft = {
  title: string
  rhythm_summary: string
  tags: string
  slots: Record<string, TemplateSlotDraft>
}

const workflow = [
  {
    title: '样例输入',
    eyebrow: 'Sample',
    body: '使用内置样例参数模拟爆款视频解析，后续接真实上传。',
    meta: 'demo sample',
  },
  {
    title: '结构拆解',
    eyebrow: 'Structure',
    body: '拆出 hook、卖点展开、使用过程和 CTA，形成可迁移模板。',
    meta: '脚本 + 节奏',
  },
  {
    title: '迁移生成',
    eyebrow: 'Transfer',
    body: '把样例结构映射到新品主题、卖点和可用素材。',
    meta: '脚本 + 时间线',
  },
  {
    title: '成片 demo',
    eyebrow: 'Output',
    body: '复用 ClipForge fixture 素材和 FFmpeg 渲染链路输出 MP4。',
    meta: 'MP4 demo',
  },
]

const defaultSample: SampleVideoInput = {
  title: '咖啡拉花爆款样例',
  duration: 20,
  shot_count: 6,
  transcript_summary: '先用拉花特写吸引注意，再展示手作过程和门店氛围。',
}

const defaultContent: NewContentInput = {
  topic: '精品咖啡店开业短视频',
  product_name: '巷口手作咖啡',
  selling_points: ['手作拉花', '新店开业优惠', '安静办公空间'],
  available_assets: ['开头吸引镜头', '使用过程镜头'],
  uploaded_assets: [],
}

const outputVariants: Array<{ value: OutputVariant; label: string }> = [
  { value: 'standard', label: '默认版' },
  { value: 'high_click', label: '高点击版' },
  { value: 'high_conversion', label: '高转化版' },
  { value: 'fast_rhythm', label: '高节奏版' },
]

const API_ORIGIN = process.env.NEXT_PUBLIC_REELSTRUCT_API_ORIGIN || 'http://127.0.0.1:8010'

function apiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path
  return `${API_ORIGIN}${path.startsWith('/') ? path : `/${path}`}`
}

async function requestJson<T>(url: string, options: { method: 'POST'; body: unknown }): Promise<T> {
  const response = await fetch(apiUrl(url), {
    method: options.method,
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(options.body),
  })

  if (!response.ok) {
    throw new Error(`请求失败：${response.status} ${await readApiError(response)}`)
  }

  return response.json() as Promise<T>
}

async function readApiError(response: Response): Promise<string> {
  const text = await response.text()
  if (!text) return response.statusText || '未知错误'
  try {
    const payload = JSON.parse(text) as { detail?: unknown }
    if (typeof payload.detail === 'string') return payload.detail
  } catch {
    // Keep the raw response text when the backend does not return JSON.
  }
  return text
}

export async function requestAgentPlan(body: {
  prompt: string
  state?: {
    current_plan?: {
      prompt: string
      steps: unknown[]
    }
  }
}): Promise<WorkspaceRuntimeState> {
  return requestJson<WorkspaceRuntimeState>('/api/agent/plan', {
    method: 'POST',
    body,
  })
}

export async function requestAgentToolExecution<TData extends Record<string, unknown> = Record<string, unknown>>(body: {
  tool_name: string
  payload: Record<string, unknown>
}): Promise<{
  tool_name: string
  stage: string
  data: TData
}> {
  return requestJson<{
    tool_name: string
    stage: string
    data: TData
  }>('/api/agent/tools/execute', {
    method: 'POST',
    body,
  })
}
