'use client'

import { useEffect, useMemo, useState } from 'react'

type StructureSlot = {
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

type MaterialGap = {
  slot_id: string
  missing_asset: string
  impact: string
  fill_strategy: string
  suggested_asset_type: string
  suggested_shots: string[]
  pickup_checklist: string[]
}

type MaterialTaskStatus = '待补拍' | '已拍' | '已交付'

type MaterialRequestTask = {
  slot_id: string
  status: MaterialTaskStatus
}

type MaterialRequestSheetItem = {
  task: MaterialRequestTask
  slot: StructureSlot
  gap: MaterialGap | undefined
}

type MaterialFitAnalysis = {
  duration: number
  shot_count: number
  recommended_slot_id: string
  recommended_slot_label: string
  recommendation_reason: string
  slot_fit_scores: Record<string, number>
}

type UserSlotAsset = {
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

type TransferMapping = {
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

type StructurePreviewResponse = {
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

type DemoRunResponse = {
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
  prepared_assets: RenderClipPreview[]
  rendered_video: RenderDemoResponse
  trace: RunTraceEvent[]
}

type DemoVariantRunsResponse = {
  runs: DemoRunResponse[]
}

type RunRecordSummary = {
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

type RunBatchResponse = {
  batch_id: string
  preferred_run_id: string
  runs: RunRecordSummary[]
}

type StructureVariantSummary = {
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

type StructureTemplateRecord = {
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

type OutputVariant = 'standard' | 'high_click' | 'high_conversion' | 'fast_rhythm'

type SampleVideoInput = {
  title: string
  duration: number
  shot_count: number
  transcript_summary: string
}

type VideoShot = {
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

type KeyframeEvidence = {
  shot_index: number
  keyframe_time: number
  local_path: string
  public_url: string
}

type NewContentInput = {
  topic: string
  product_name: string
  selling_points: string[]
  available_assets: string[]
  uploaded_assets: UserSlotAsset[]
}

type SampleUploadResponse = {
  sample_id: string
  filename: string
  local_path: string
  public_url: string
  sample: SampleVideoInput
  video_signal: VideoSignal | null
  keyframes: KeyframeEvidence[]
}

type TranscriptUploadResponse = {
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
