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
  shot_evidence_graph?: ShotEvidenceGraph
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

const API_ORIGIN = process.env.NEXT_PUBLIC_REELSTRUCT_API_ORIGIN || 'http://127.0.0.1:8010'

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

type FrameEvidence = {
  shot_index: number
  frame_index: number
  time: number
  role: 'start' | 'middle' | 'safe_end' | 'end' | 'third' | 'two_thirds'
  public_url: string
}

type ShotUnderstanding = {
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

type ShotEvidenceNode = {
  shot: VideoShot
  frames: FrameEvidence[]
  understanding: ShotUnderstanding
}

type ShotRelation = {
  from_shot: number
  to_shot: number
  relation_type: string
  relation_summary: string
  rhythm_change: string
  semantic_shift: string
  confidence: number
}

type ShotEvidenceGraph = {
  shots: ShotEvidenceNode[]
  relations: ShotRelation[]
  warnings: string[]
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
  detection_method: 'scene_detect' | 'pyscenedetect_adaptive' | 'pyscenedetect_content' | 'ffmpeg_scene_detect' | 'uniform_fallback'
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

export function useReelStruct() {
  const [preview, setPreview] = useState<StructurePreviewResponse | null>(null)
  const [run, setRun] = useState<DemoRunResponse | null>(null)
  const [sample, setSample] = useState<SampleVideoInput>(defaultSample)
  const [content, setContent] = useState<NewContentInput>(defaultContent)
  const [sampleUpload, setSampleUpload] = useState<SampleUploadResponse | null>(null)
  const [transcriptUpload, setTranscriptUpload] = useState<TranscriptUploadResponse | null>(null)
  const [slotDrafts, setSlotDrafts] = useState<Record<string, SlotDraft>>({})
  const [selectedGapIds, setSelectedGapIds] = useState<string[]>([])
  const [requestSheetIds, setRequestSheetIds] = useState<string[]>([])
  const [requestSheetStatus, setRequestSheetStatus] = useState<Record<string, MaterialTaskStatus>>({})
  const [requestSheetFeedback, setRequestSheetFeedback] = useState('')
  const [recentRuns, setRecentRuns] = useState<RunRecordSummary[]>([])
  const [runBatch, setRunBatch] = useState<RunBatchResponse | null>(null)
  const [templates, setTemplates] = useState<StructureTemplateSummary[]>([])
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [selectedTemplateDetail, setSelectedTemplateDetail] = useState<StructureTemplateRecord | null>(null)
  const [templateEditorDraft, setTemplateEditorDraft] = useState<TemplateEditorDraft | null>(null)
  const [templateNameDraft, setTemplateNameDraft] = useState('')
  const [templateTagsDraft, setTemplateTagsDraft] = useState('')
  const [templateTagFilter, setTemplateTagFilter] = useState('')
  const [runTemplateFilter, setRunTemplateFilter] = useState('')
  const [runTagFilter, setRunTagFilter] = useState('')
  const [outputVariant, setOutputVariant] = useState<OutputVariant>('standard')
  const [variantSummaries, setVariantSummaries] = useState<StructureVariantSummary[]>([])
  const [runStatusFilter, setRunStatusFilter] = useState<RunStatusFilter>('all')
  const [runSearchKeyword, setRunSearchKeyword] = useState('')
  const [runNoteDraft, setRunNoteDraft] = useState('')
  const [videoUrl, setVideoUrl] = useState('')
  const [status, setStatus] = useState('等待生成')
  const [error, setError] = useState('')

  const gapLookup = useMemo(() => {
    return new Map((preview?.transfer_plan.gaps || []).map((gap) => [gap.slot_id, gap]))
  }, [preview])

  const mappingLookup = useMemo(() => {
    return new Map((preview?.transfer_plan.mappings || []).map((mapping) => [mapping.slot_id, mapping]))
  }, [preview])

  const selectedGaps = useMemo(() => {
    return (preview?.transfer_plan.gaps || []).filter((gap) => selectedGapIds.includes(gap.slot_id))
  }, [preview, selectedGapIds])

  const analysisSummary = preview?.template.analysis_summary
  const analysisSource = analysisSummary?.source || 'rule'
  const analysisConfidence = analysisSummary?.confidence || 0
  const analysisWarnings = analysisSummary?.warnings || []

  const requestSheetItems = useMemo(() => {
    const slotLookup = new Map((preview?.template.script_pattern || []).map((slot) => [slot.id, slot]))
    const serverTaskLookup = new Map((preview?.transfer_plan.material_request_sheet || []).map((task) => [task.slot_id, task]))
    return requestSheetIds
      .map((slotId) => {
        const slot = slotLookup.get(slotId)
        return slot
          ? {
              task: serverTaskLookup.get(slotId) || {
                slot_id: slotId,
                status: requestSheetStatus[slotId] ?? '待补拍',
              },
              slot,
              gap: gapLookup.get(slotId),
            }
          : null
      })
      .filter((item): item is MaterialRequestSheetItem => Boolean(item))
  }, [gapLookup, preview, requestSheetIds, requestSheetStatus])

  const requestSheetText = useMemo(() => {
    return buildMaterialRequestSheetText(requestSheetItems, requestSheetStatus)
  }, [requestSheetItems, requestSheetStatus])

  const uploadedAssetLookup = useMemo(() => {
    return new Map(content.uploaded_assets.map((asset) => [asset.slot_id, asset]))
  }, [content.uploaded_assets])

  const selectedTemplate = useMemo(() => {
    return templates.find((item) => item.template_id === selectedTemplateId) || null
  }, [templates, selectedTemplateId])

  useEffect(() => {
    const nextGapIds = (preview?.transfer_plan.gaps || []).map((gap) => gap.slot_id)
    const nextRequestSheet = preview?.transfer_plan.material_request_sheet || []
    setSelectedGapIds(nextGapIds)
    setRequestSheetIds(nextRequestSheet.map((item) => item.slot_id))
    setRequestSheetStatus(Object.fromEntries(nextRequestSheet.map((item) => [item.slot_id, item.status])))
    setRequestSheetFeedback('')
  }, [preview])

  useEffect(() => {
    setRunNoteDraft(run?.note ?? '')
  }, [run])

  useEffect(() => {
    if (!run?.batch_id) {
      setRunBatch(null)
      return
    }
    void fetchRunBatch(run.batch_id)
  }, [run?.batch_id])

  useEffect(() => {
    if (!requestSheetFeedback) return
    const timer = window.setTimeout(() => setRequestSheetFeedback(''), 1800)
    return () => window.clearTimeout(timer)
  }, [requestSheetFeedback])

  useEffect(() => {
    void fetchRecentRuns()
  }, [runStatusFilter, runSearchKeyword, runTemplateFilter, runTagFilter])

  useEffect(() => {
    void fetchTemplates()
  }, [templateTagFilter])

  useEffect(() => {
    if (!selectedTemplateId) {
      setSelectedTemplateDetail(null)
      setTemplateEditorDraft(null)
      return
    }
    void fetchTemplateDetail(selectedTemplateId)
  }, [selectedTemplateId])

  useEffect(() => {
    if (selectedTemplate) {
      setTemplateNameDraft(selectedTemplate.title)
      setTemplateTagsDraft(selectedTemplate.tags.join('，'))
      return
    }
    if (run?.template_title) {
      setTemplateNameDraft(run.template_title)
      setTemplateTagsDraft(run.template_tags.join('，'))
      return
    }
    if (preview?.template.title) {
      setTemplateNameDraft(preview.template.title)
    }
  }, [selectedTemplate, run?.template_tags, run?.template_title, preview?.template.title])

  const uploadSample = async (file: File | null) => {
    if (!file) return

    setError('')
    setStatus('正在上传样例视频')
    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(apiUrl('/api/samples/upload'), {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        throw new Error(`上传失败：${response.status} ${await readApiError(response)}`)
      }
      const upload = normalizeSampleUpload((await response.json()) as SampleUploadResponse)
      setSampleUpload(upload)
      setSample(upload.sample)
      setStatus('样例已上传')
    } catch (caught) {
      setStatus('上传失败')
      setError(caught instanceof Error ? caught.message : '未知错误')
    }
  }

  const uploadTranscript = async (file: File | null) => {
    if (!file) return

    setError('')
    setStatus('正在上传转写文本')
    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(apiUrl('/api/samples/upload-transcript'), {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        throw new Error(`上传失败：${response.status} ${await readApiError(response)}`)
      }
      const upload = (await response.json()) as TranscriptUploadResponse
      setTranscriptUpload(upload)
      setSample({
        ...sample,
        transcript_summary: upload.transcript_summary,
      })
      setStatus('转写摘要已更新')
    } catch (caught) {
      setStatus('上传失败')
      setError(caught instanceof Error ? caught.message : '未知错误')
    }
  }

  const uploadMaterialAsset = async (slotId: string, file: File | null) => {
    if (!file) return

    setError('')
    setStatus('正在上传补拍素材')
    const formData = new FormData()
    formData.append('slot_id', slotId)
    formData.append('file', file)

    try {
      const response = await fetch(apiUrl('/api/materials/upload'), {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        throw new Error(`上传补拍素材失败：${response.status} ${await readApiError(response)}`)
      }
      const uploadedAsset = normalizeUserSlotAsset((await response.json()) as UserSlotAsset)
      setContent((current) => ({
        ...current,
        uploaded_assets: [
          ...current.uploaded_assets.filter((asset) => asset.slot_id !== uploadedAsset.slot_id),
          uploadedAsset,
        ],
      }))
      setRequestSheetStatus((current) => ({
        ...current,
        [slotId]: '已拍',
      }))
      setRequestSheetFeedback('补拍素材已上传')
      setStatus('补拍素材已绑定')
    } catch (caught) {
      setStatus('上传失败')
      setError(caught instanceof Error ? caught.message : '上传补拍素材失败')
    }
  }

  const runDemo = async (options?: { useDraftOverrides?: boolean }) => {
    setError('')
    setStatus('正在执行迁移任务')
    setVideoUrl('')
    setRun(null)
    setRunBatch(null)

    try {
      const mapping_overrides =
        options?.useDraftOverrides && preview
          ? buildMappingOverrides(preview, slotDrafts)
          : []
      const runResponse = await requestJson<DemoRunResponse>('/api/runs/demo', {
        method: 'POST',
        body: {
          sample,
          content,
          sample_local_path: sampleUpload?.local_path || '',
          use_ai_structure: true,
          use_ai_transfer_explanation: true,
          template_id: selectedTemplateId,
          variant: outputVariant,
          mapping_overrides,
          material_request_sheet: buildMaterialRequestSheetPayload(requestSheetIds, requestSheetStatus),
        },
      })
      setRun(runResponse)
      setPreview(runResponse.preview)
      setSlotDrafts(buildSlotDrafts(runResponse.preview))
      setVideoUrl(mediaUrl(`${runResponse.rendered_video.video_url}?t=${Date.now()}`))
      void fetchRecentRuns()
      setStatus('迁移任务已完成')
    } catch (caught) {
      setStatus('生成失败')
      setError(caught instanceof Error ? caught.message : '未知错误')
    }
  }

  const runDemoVariants = async () => {
    setError('')
    setStatus('正在批量生成四版 demo')
    setVideoUrl('')
    setRun(null)
    setRunBatch(null)

    try {
      const mapping_overrides = preview ? buildMappingOverrides(preview, slotDrafts) : []
      const payload = await requestJson<DemoVariantRunsResponse>('/api/runs/demo-variants', {
        method: 'POST',
        body: {
          sample,
          content,
          sample_local_path: sampleUpload?.local_path || '',
          use_ai_structure: true,
          use_ai_transfer_explanation: true,
          template_id: selectedTemplateId,
          variant: outputVariant,
          mapping_overrides,
          material_request_sheet: buildMaterialRequestSheetPayload(requestSheetIds, requestSheetStatus),
        },
      })
      const selectedRun = payload.runs.find((item) => item.variant === outputVariant) || payload.runs[0]
      setRun(selectedRun)
      setPreview(selectedRun.preview)
      setSlotDrafts(buildSlotDrafts(selectedRun.preview))
      setVideoUrl(mediaUrl(`${selectedRun.rendered_video.video_url}?t=${Date.now()}`))
      await fetchRunBatch(selectedRun.batch_id)
      await fetchRecentRuns()
      setStatus('四版 demo 已生成')
    } catch (caught) {
      setStatus('批量生成失败')
      setError(caught instanceof Error ? caught.message : '批量生成失败')
    }
  }

  const compareOutputVariants = async () => {
    setError('')
    setStatus('正在生成版本对比')
    try {
      const payload = await requestJson<StructureVariantsResponse>('/api/structure/variants', {
        method: 'POST',
        body: {
          sample,
          content,
          sample_local_path: sampleUpload?.local_path || '',
          use_ai_structure: true,
          use_ai_transfer_explanation: true,
          template_id: selectedTemplateId,
          mapping_overrides: preview ? buildMappingOverrides(preview, slotDrafts) : [],
          material_request_sheet: buildMaterialRequestSheetPayload(requestSheetIds, requestSheetStatus),
        },
      })
      setVariantSummaries(payload.variants)
      setStatus('版本对比已生成')
    } catch (caught) {
      setStatus('版本对比失败')
      setError(caught instanceof Error ? caught.message : '版本对比失败')
    }
  }

  const fetchRecentRuns = async () => {
    try {
      const params = new URLSearchParams()
      if (runStatusFilter !== 'all') {
        params.set('status', runStatusFilter)
      }
      if (runTemplateFilter) {
        params.set('template_id', runTemplateFilter)
      }
      if (runTagFilter.trim()) {
        params.set('tag', runTagFilter.trim())
      }
      if (runSearchKeyword.trim()) {
        params.set('q', runSearchKeyword.trim())
      }
      const query = params.toString()
      const response = await fetch(apiUrl(`/api/runs${query ? `?${query}` : ''}`))
      if (!response.ok) {
        throw new Error(`读取记录失败：${response.status}`)
      }
      const runs = (await response.json()) as RunRecordSummary[]
      setRecentRuns(runs)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '读取记录失败')
    }
  }

  const fetchRunBatch = async (batchId: string) => {
    if (!batchId) return
    try {
      const response = await fetch(apiUrl(`/api/runs/batches/${batchId}`))
      if (!response.ok) {
        if (response.status === 404) {
          setRunBatch(null)
          return
        }
        throw new Error(`读取批次失败：${response.status}`)
      }
      const batch = (await response.json()) as RunBatchResponse
      setRunBatch(batch)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '读取批次失败')
    }
  }

  const fetchTemplates = async () => {
    try {
      const params = new URLSearchParams()
      if (templateTagFilter.trim()) {
        params.set('tag', templateTagFilter.trim())
      }
      const query = params.toString()
      const response = await fetch(apiUrl(`/api/templates${query ? `?${query}` : ''}`))
      if (!response.ok) {
        throw new Error(`读取模板失败：${response.status}`)
      }
      const records = (await response.json()) as StructureTemplateSummary[]
      setTemplates(records)
      if (selectedTemplateId && !records.some((item) => item.template_id === selectedTemplateId)) {
        setSelectedTemplateId('')
        setSelectedTemplateDetail(null)
        setTemplateEditorDraft(null)
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '读取模板失败')
    }
  }

  const fetchTemplateDetail = async (templateId: string) => {
    try {
      const response = await fetch(apiUrl(`/api/templates/${templateId}`))
      if (!response.ok) {
        throw new Error(`读取模板详情失败：${response.status}`)
      }
      const record = (await response.json()) as StructureTemplateRecord
      setSelectedTemplateDetail(record)
      setTemplateEditorDraft({
        title: record.template.title,
        rhythm_summary: record.template.rhythm_summary,
        tags: record.tags.join('，'),
        slots: Object.fromEntries(
          record.template.script_pattern.map((slot) => [
            slot.id,
            {
              duration: String(slot.duration),
              required_asset: slot.required_asset,
            },
          ]),
        ),
      })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '读取模板详情失败')
    }
  }

  const addSelectedGapsToRequestSheet = () => {
    setRequestSheetIds((current) => {
      const nextIds = new Set([...current, ...selectedGapIds])
      return (preview?.transfer_plan.gaps || [])
        .map((gap) => gap.slot_id)
        .filter((slotId) => nextIds.has(slotId))
    })
    setRequestSheetStatus((current) => {
      const next = { ...current }
      selectedGapIds.forEach((slotId) => {
        next[slotId] = next[slotId] ?? '待补拍'
      })
      return next
    })
    setRequestSheetFeedback('')
  }

  const updateMaterialTaskStatus = (slotId: string, nextStatus: MaterialTaskStatus) => {
    setRequestSheetStatus((current) => ({
      ...current,
      [slotId]: nextStatus,
    }))
    setRequestSheetFeedback('')
  }

  const removeFromRequestSheet = (slotId: string) => {
    setRequestSheetIds((current) => current.filter((item) => item !== slotId))
    setRequestSheetStatus((current) => {
      const next = { ...current }
      delete next[slotId]
      return next
    })
    setRequestSheetFeedback('已移出任务')
  }

  const clearRequestSheet = () => {
    setRequestSheetIds([])
    setRequestSheetStatus({})
    setRequestSheetFeedback('需求单已清空')
  }

  const copyRequestSheet = async () => {
    if (!requestSheetText) return
    try {
      await navigator.clipboard.writeText(requestSheetText)
      setRequestSheetFeedback('需求单已复制')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '复制失败')
    }
  }

  const exportRequestSheet = () => {
    if (!requestSheetText) return
    const blob = new Blob([requestSheetText], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'material-request-sheet.txt'
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    setRequestSheetFeedback('需求单已导出')
  }

  const exportRunJson = async () => {
    if (!run) return

    try {
      const response = await fetch(apiUrl(`/api/runs/${run.run_id}`))
      const payload = response.ok ? await response.json() : run
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${run.run_id}.json`
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      setStatus('run 记录已导出')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '导出 run 记录失败')
    }
  }

  const downloadRunPackage = () => {
    if (!run) return
    const link = document.createElement('a')
    link.href = apiUrl(`/api/runs/${run.run_id}/export.zip`)
    link.download = `reelstruct-${run.run_id}.zip`
    link.click()
    setStatus('结果包已开始下载')
  }

  const loadRunRecord = async (runId: string) => {
    try {
      const response = await fetch(apiUrl(`/api/runs/${runId}`))
      if (!response.ok) {
        throw new Error(`读取 run 失败：${response.status}`)
      }
      const payload = (await response.json()) as DemoRunResponse
      setRun(payload)
      setOutputVariant(payload.variant || payload.preview.transfer_plan.variant || 'standard')
      setSelectedTemplateId(payload.template_id || '')
      setPreview(payload.preview)
      setSlotDrafts(buildSlotDrafts(payload.preview))
      setVideoUrl(payload.rendered_video.video_url ? mediaUrl(`${payload.rendered_video.video_url}?t=${Date.now()}`) : '')
      setStatus(`已载入 ${payload.run_id}`)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '读取 run 失败')
    }
  }

  const deleteRunRecord = async (runId: string) => {
    try {
      const response = await fetch(apiUrl(`/api/runs/${runId}`), { method: 'DELETE' })
      if (!response.ok) {
        throw new Error(`删除记录失败：${response.status}`)
      }
      setRecentRuns((current) => current.filter((item) => item.run_id !== runId))
      if (run?.run_id === runId) {
        setRun(null)
        setPreview(null)
        setSlotDrafts({})
        setVideoUrl('')
        setStatus('已删除当前记录')
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '删除记录失败')
    }
  }

  const saveRunNote = async () => {
    if (!run) return
    try {
      const response = await fetch(apiUrl(`/api/runs/${run.run_id}/note`), {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ note: runNoteDraft }),
      })
      if (!response.ok) {
        throw new Error(`保存备注失败：${response.status}`)
      }
      const payload = (await response.json()) as DemoRunResponse
      setRun(payload)
      setRecentRuns((current) =>
        current.map((item) => (item.run_id === payload.run_id ? { ...item, note: payload.note } : item)),
      )
      await fetchRecentRuns()
      setStatus('run 备注已保存')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '保存备注失败')
    }
  }

  const toggleRunPinned = async () => {
    if (!run) return
    try {
      const response = await fetch(apiUrl(`/api/runs/${run.run_id}/pin`), {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pinned: !run.pinned }),
      })
      if (!response.ok) {
        throw new Error(`置顶记录失败：${response.status}`)
      }
      const payload = (await response.json()) as DemoRunResponse
      setRun(payload)
      await fetchRecentRuns()
      setStatus(payload.pinned ? 'run 已置顶' : 'run 已取消置顶')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '置顶记录失败')
    }
  }

  const toggleRunPreferred = async (runId = run?.run_id, currentPreferred = run?.preferred || false) => {
    if (!runId) return
    try {
      const response = await fetch(apiUrl(`/api/runs/${runId}/preferred`), {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ preferred: !currentPreferred }),
      })
      if (!response.ok) {
        throw new Error(`设置首选失败：${response.status}`)
      }
      const payload = (await response.json()) as DemoRunResponse
      if (run?.run_id === payload.run_id) {
        setRun(payload)
      } else if (run?.batch_id === payload.batch_id && payload.preferred) {
        setRun({ ...run, preferred: false })
      }
      if (payload.batch_id) {
        await fetchRunBatch(payload.batch_id)
      }
      await fetchRecentRuns()
      setStatus(payload.preferred ? '已设为首选版本' : '已取消首选版本')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '设置首选失败')
    }
  }

  const saveRunAsTemplate = async () => {
    if (!run) return
    try {
      const response = await fetch(apiUrl(`/api/templates/from-run/${run.run_id}`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title: templateNameDraft, tags: splitList(templateTagsDraft) }),
      })
      if (!response.ok) {
        throw new Error(`保存模板失败：${response.status}`)
      }
      const payload = (await response.json()) as StructureTemplateRecord
      setSelectedTemplateId(payload.template_id)
      setTemplateNameDraft(payload.template.title)
      setTemplateTagsDraft(payload.tags.join('，'))
      await fetchTemplates()
      setStatus('已保存模板')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '保存模板失败')
    }
  }

  const deleteTemplate = async (templateId: string) => {
    try {
      const response = await fetch(apiUrl(`/api/templates/${templateId}`), {
        method: 'DELETE',
      })
      if (!response.ok) {
        throw new Error(`删除模板失败：${response.status}`)
      }
      if (selectedTemplateId === templateId) {
        setSelectedTemplateId('')
      }
      if (runTemplateFilter === templateId) {
        setRunTemplateFilter('')
      }
      await fetchTemplates()
      await fetchRecentRuns()
      setStatus('模板已删除')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '删除模板失败')
    }
  }

  const saveTemplateEdits = async () => {
    if (!selectedTemplateId || !templateEditorDraft || !selectedTemplateDetail) return
    try {
      const response = await fetch(apiUrl(`/api/templates/${selectedTemplateId}`), {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title: templateEditorDraft.title,
          rhythm_summary: templateEditorDraft.rhythm_summary,
          tags: splitList(templateEditorDraft.tags),
          slots: selectedTemplateDetail.template.script_pattern.map((slot) => ({
            slot_id: slot.id,
            duration: Number(templateEditorDraft.slots[slot.id]?.duration || slot.duration),
            required_asset: templateEditorDraft.slots[slot.id]?.required_asset || slot.required_asset,
          })),
        }),
      })
      if (!response.ok) {
        throw new Error(`保存模板修改失败：${response.status}`)
      }
      const record = (await response.json()) as StructureTemplateRecord
      setSelectedTemplateDetail(record)
      setTemplateEditorDraft({
        title: record.template.title,
        rhythm_summary: record.template.rhythm_summary,
        tags: record.tags.join('，'),
        slots: Object.fromEntries(
          record.template.script_pattern.map((slot) => [
            slot.id,
            {
              duration: String(slot.duration),
              required_asset: slot.required_asset,
            },
          ]),
        ),
      })
      setTemplateNameDraft(record.template.title)
      setTemplateTagsDraft(record.tags.join('，'))
      await fetchTemplates()
      setStatus('模板修改已保存')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '保存模板修改失败')
    }
  }

  const rollbackTemplateVersion = async (versionId: string) => {
    if (!selectedTemplateId) return
    try {
      const response = await fetch(apiUrl(`/api/templates/${selectedTemplateId}/rollback/${versionId}`), {
        method: 'POST',
      })
      if (!response.ok) {
        throw new Error(`模板回退失败：${response.status}`)
      }
      const record = (await response.json()) as StructureTemplateRecord
      setSelectedTemplateDetail(record)
      setTemplateEditorDraft({
        title: record.template.title,
        rhythm_summary: record.template.rhythm_summary,
        tags: record.tags.join('，'),
        slots: Object.fromEntries(
          record.template.script_pattern.map((slot) => [
            slot.id,
            {
              duration: String(slot.duration),
              required_asset: slot.required_asset,
            },
          ]),
        ),
      })
      setTemplateNameDraft(record.template.title)
      setTemplateTagsDraft(record.tags.join('，'))
      await fetchTemplates()
      setStatus('模板已回退')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '模板回退失败')
    }
  }

  const forkTemplate = async (templateId: string, title: string) => {
    try {
      const response = await fetch(apiUrl(`/api/templates/${templateId}/fork`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title }),
      })
      if (!response.ok) {
        throw new Error(`复制模板失败：${response.status}`)
      }
      const record = (await response.json()) as StructureTemplateRecord
      await fetchTemplates()
      setSelectedTemplateId(record.template_id)
      setTemplateNameDraft(record.template.title)
      setTemplateTagsDraft(record.tags.join('，'))
      setStatus('模板已复制')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '复制模板失败')
    }
  }

  return {
    preview,
    setPreview,
    run,
    setRun,
    sample,
    setSample,
    content,
    setContent,
    sampleUpload,
    setSampleUpload,
    transcriptUpload,
    setTranscriptUpload,
    slotDrafts,
    setSlotDrafts,
    selectedGapIds,
    setSelectedGapIds,
    requestSheetIds,
    setRequestSheetIds,
    requestSheetStatus,
    setRequestSheetStatus,
    requestSheetFeedback,
    setRequestSheetFeedback,
    recentRuns,
    setRecentRuns,
    runBatch,
    setRunBatch,
    templates,
    setTemplates,
    selectedTemplateId,
    setSelectedTemplateId,
    selectedTemplateDetail,
    setSelectedTemplateDetail,
    templateEditorDraft,
    setTemplateEditorDraft,
    templateNameDraft,
    setTemplateNameDraft,
    templateTagsDraft,
    setTemplateTagsDraft,
    templateTagFilter,
    setTemplateTagFilter,
    runTemplateFilter,
    setRunTemplateFilter,
    runTagFilter,
    setRunTagFilter,
    outputVariant,
    setOutputVariant,
    variantSummaries,
    setVariantSummaries,
    runStatusFilter,
    setRunStatusFilter,
    runSearchKeyword,
    setRunSearchKeyword,
    runNoteDraft,
    setRunNoteDraft,
    videoUrl,
    setVideoUrl,
    status,
    setStatus,
    error,
    setError,
    gapLookup,
    mappingLookup,
    selectedGaps,
    analysisSummary,
    analysisSource,
    analysisConfidence,
    analysisWarnings,
    requestSheetItems,
    requestSheetText,
    uploadedAssetLookup,
    selectedTemplate,
    uploadSample,
    uploadTranscript,
    uploadMaterialAsset,
    runDemo,
    runDemoVariants,
    fetchRecentRuns,
    fetchRunBatch,
    deleteRunRecord,
    fetchTemplates,
    fetchTemplateDetail,
    deleteTemplate,
  }
}


function apiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path
  return `${API_ORIGIN}${path.startsWith('/') ? path : `/${path}`}`
}

function mediaUrl(path: string): string {
  if (!path || /^blob:|^data:|^https?:\/\//.test(path)) return path
  const [pathname, query = ''] = path.split('?', 2)
  const normalizedPath = `${pathname.startsWith('/') ? pathname : `/${pathname}`}${query ? `?${query}` : ''}`
  return `${API_ORIGIN}${normalizedPath}`
}

function normalizeSampleUpload(upload: SampleUploadResponse): SampleUploadResponse {
  return {
    ...upload,
    public_url: mediaUrl(upload.public_url),
    keyframes: upload.keyframes.map((keyframe) => ({
      ...keyframe,
      public_url: mediaUrl(keyframe.public_url),
    })),
  }
}

function normalizeUserSlotAsset(asset: UserSlotAsset): UserSlotAsset {
  return {
    ...asset,
    public_url: mediaUrl(asset.public_url),
  }
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

function splitList(value: string): string[] {
  return value
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function updateListItem(items: string[], index: number, value: string): string[] {
  return items.map((item, itemIndex) => (itemIndex === index ? value : item))
}

function removeListItem(items: string[], index: number): string[] {
  return items.filter((_, itemIndex) => itemIndex !== index)
}

function moveListItem(items: string[], index: number, delta: number): string[] {
  const nextIndex = index + delta
  if (nextIndex < 0 || nextIndex >= items.length) return items
  const nextItems = [...items]
  const [item] = nextItems.splice(index, 1)
  nextItems.splice(nextIndex, 0, item)
  return nextItems
}

function buildSlotDrafts(preview: StructurePreviewResponse): Record<string, SlotDraft> {
  const slotLookup = new Map(preview.template.script_pattern.map((slot) => [slot.id, slot]))
  return Object.fromEntries(
    preview.transfer_plan.mappings.map((mapping) => [
      mapping.slot_id,
      {
        target_message: mapping.target_message,
        sample_evidence: slotLookup.get(mapping.slot_id)?.sample_evidence || '',
        asset_strategy: mapping.asset_strategy,
      },
    ]),
  )
}

function buildMappingOverrides(
  preview: StructurePreviewResponse,
  drafts: Record<string, SlotDraft>,
): TransferMappingOverride[] {
  const slotLookup = new Map(preview.template.script_pattern.map((slot) => [slot.id, slot]))
  return preview.transfer_plan.mappings
    .map((mapping) => ({
      slot_id: mapping.slot_id,
      target_message: (drafts[mapping.slot_id]?.target_message ?? '').trim(),
      sample_evidence: (drafts[mapping.slot_id]?.sample_evidence ?? '').trim(),
      asset_strategy: (drafts[mapping.slot_id]?.asset_strategy ?? '').trim(),
      original_message: mapping.target_message,
      original_sample_evidence: slotLookup.get(mapping.slot_id)?.sample_evidence ?? '',
      original_asset_strategy: mapping.asset_strategy,
    }))
    .filter(
      (item) =>
        (item.target_message && item.target_message !== item.original_message) ||
        (item.sample_evidence && item.sample_evidence !== item.original_sample_evidence) ||
        (item.asset_strategy && item.asset_strategy !== item.original_asset_strategy),
    )
    .map(({ slot_id, target_message, sample_evidence, asset_strategy }) => ({
      slot_id,
      target_message,
      sample_evidence,
      asset_strategy,
    }))
}

function labelForSlot(slotId: string): string {
  const labelMap: Record<string, string> = {
    hook: 'Hook',
    selling_points: '卖点展开',
    usage: '使用过程',
    cta: 'CTA',
  }
  return labelMap[slotId] || slotId
}

function variantLabel(variant: OutputVariant): string {
  return outputVariants.find((item) => item.value === variant)?.label || '默认版'
}

function analysisSourceLabel(source: 'rule' | 'ai' | 'fallback'): string {
  if (source === 'ai') return 'AI 视频结构拆解'
  if (source === 'fallback') return '基础兜底拆解'
  return '基础规则拆解'
}

function analysisSourceClass(source: 'rule' | 'ai' | 'fallback'): string {
  if (source === 'ai') return 'bg-sky-50 text-sky-700'
  if (source === 'fallback') return 'bg-amber-50 text-amber-800'
  return 'bg-slate-100 text-slate-600'
}

const materialTaskStatuses: MaterialTaskStatus[] = ['待补拍', '已拍', '已交付']

function buildMaterialRequestSheetEntry(item: MaterialRequestSheetItem, status: MaterialTaskStatus): string {
  const gap = item.gap
  if (!gap) {
    return [
      `当前状态：${status}`,
      `已补齐素材：${item.slot.required_asset}`,
      `补位方式：已进入可用素材池，重新生成时直接参与视频重组`,
    ].join('\n')
  }
  return [
    `当前状态：${status}`,
    `缺口素材：${gap.missing_asset}`,
    `补位方式：${gap.fill_strategy}`,
    `建议镜头：${gap.suggested_shots.join('；')}`,
    `检查清单：${gap.pickup_checklist.join('；')}`,
  ].join('\n')
}

function buildMaterialRequestSheetText(
  items: MaterialRequestSheetItem[],
  statusLookup: Record<string, MaterialTaskStatus>,
): string {
  if (!items.length) return ''
  return [
    '素材需求单',
    '待执行素材任务',
    '',
    ...items.flatMap((item, index) => {
      const status = statusLookup[item.task.slot_id] ?? item.task.status
      return [
        `${index + 1}. ${labelForSlot(item.task.slot_id)} / ${item.gap?.suggested_asset_type || item.slot.required_asset}`,
        buildMaterialRequestSheetEntry(item, status),
        '',
      ]
    }),
  ].join('\n').trim()
}

function buildMaterialRequestSheetPayload(
  requestSheetIds: string[],
  statusLookup: Record<string, MaterialTaskStatus>,
): MaterialRequestTask[] {
  return requestSheetIds.map((slotId) => ({
    slot_id: slotId,
    status: statusLookup[slotId] ?? '待补拍',
  }))
}

function formatRunTime(value: string): string {
  if (!value) return '时间未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

const fallbackSlots: StructureSlot[] = [
  {
    id: 'hook',
    label: 'Hook',
    start: 0,
    duration: 3,
    purpose: '痛点开场 + 快切镜头',
    required_asset: '开头吸引镜头',
    sample_evidence: '等待后端结构预览',
    role: '吸引注意',
    method: '结果先行 + 视觉记忆点',
    intent: '让观众快速知道为什么要继续看',
    rhythm: '前段快进入',
    transferable_rule: '保留先给结果再解释价值的结构',
    non_transferable: '不复制样例具体内容',
    packaging_intent: '大标题和强字幕强化停留',
    evidence_shot_indices: [],
    confidence: 0,
  },
  {
    id: 'selling_points',
    label: '卖点展开',
    start: 3,
    duration: 13,
    purpose: '缺少商品特写，使用卖点卡片补足',
    required_asset: '商品特写镜头',
    sample_evidence: '等待后端结构预览',
    role: '建立兴趣',
    method: '利益点连续推进',
    intent: '让观众理解核心卖点',
    rhythm: '中段信息密集',
    transferable_rule: '保留一镜一卖点的展开方式',
    non_transferable: '不复制样例具体卖点',
    packaging_intent: '卖点卡片和关键词高亮',
    evidence_shot_indices: [],
    confidence: 0,
  },
  {
    id: 'usage',
    label: '使用过程',
    start: 16,
    duration: 8,
    purpose: '复用场景素材 + 字幕解释',
    required_asset: '使用过程镜头',
    sample_evidence: '等待后端结构预览',
    role: '场景证明',
    method: '真实场景证明',
    intent: '让卖点落到可感知场景',
    rhythm: '中后段放慢半拍',
    transferable_rule: '保留用场景证明卖点的结构',
    non_transferable: '不复制样例具体动作和人物',
    packaging_intent: '说明字幕补足动作含义',
    evidence_shot_indices: [],
    confidence: 0,
  },
  {
    id: 'cta',
    label: 'CTA',
    start: 24,
    duration: 4,
    purpose: '结尾行动号召和封面文案',
    required_asset: '结尾 CTA 镜头',
    sample_evidence: '等待后端结构预览',
    role: '推动转化',
    method: '利益收束 + 行动指令',
    intent: '让观众知道下一步动作',
    rhythm: '结尾短暂停留',
    transferable_rule: '保留明确行动词和最后记忆点',
    non_transferable: '不复制样例具体口令和优惠',
    packaging_intent: '结尾标题卡片强化 CTA',
    evidence_shot_indices: [],
    confidence: 0,
  },
]

const fallbackTrace: RunTraceEvent[] = [
  {
    step: 'analyze_structure',
    title: '结构拆解',
    message: '等待后端拆解样例视频结构。',
    progress: 0,
  },
  {
    step: 'transfer_structure',
    title: '结构迁移',
    message: '等待生成新内容映射方案。',
    progress: 0,
  },
  {
    step: 'prepare_assets',
    title: '素材准备',
    message: '等待匹配 fixture 素材。',
    progress: 0,
  },
  {
    step: 'render_video',
    title: '视频渲染',
    message: '等待 FFmpeg 渲染输出。',
    progress: 0,
  },
  {
    step: 'done',
    title: '生成完成',
    message: '等待生成结果。',
    progress: 0,
  },
]

const fallbackAnalysis = {
  metrics: [
    { label: '时长', value: '20.0s', detail: '样例总时长' },
    { label: '镜头数', value: '6', detail: 'scene detect / 节奏估算' },
    { label: '转写', value: '已提供', detail: '用于提取 hook / usage / CTA 依据' },
  ],
  narrative_beats: [
    { slot_id: 'hook', label: 'Hook', evidence: '先用拉花特写吸引注意' },
    { slot_id: 'usage', label: '使用过程', evidence: '再展示手作过程和门店氛围' },
    { slot_id: 'cta', label: 'CTA', evidence: '结尾给到行动引导' },
  ],
  packaging_signals: ['高密度字幕', '卖点标题卡片', '结尾行动号召'],
}
