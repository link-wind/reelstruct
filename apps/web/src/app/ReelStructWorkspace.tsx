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
  fallback_strategy: string
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
  public_url: string
  sample: SampleVideoInput
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

export default function ReelStructWorkspace() {
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
      const response = await fetch('/api/samples/upload', {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        throw new Error(`上传失败：${response.status} ${await response.text()}`)
      }
      const upload = (await response.json()) as SampleUploadResponse
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
      const response = await fetch('/api/samples/upload-transcript', {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        throw new Error(`上传失败：${response.status} ${await response.text()}`)
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
      const response = await fetch('/api/materials/upload', {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        throw new Error(`上传补拍素材失败：${response.status} ${await response.text()}`)
      }
      const uploadedAsset = (await response.json()) as UserSlotAsset
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
          template_id: selectedTemplateId,
          variant: outputVariant,
          mapping_overrides,
          material_request_sheet: buildMaterialRequestSheetPayload(requestSheetIds, requestSheetStatus),
        },
      })
      setRun(runResponse)
      setPreview(runResponse.preview)
      setSlotDrafts(buildSlotDrafts(runResponse.preview))
      setVideoUrl(`${runResponse.rendered_video.video_url}?t=${Date.now()}`)
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
      setVideoUrl(`${selectedRun.rendered_video.video_url}?t=${Date.now()}`)
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
      const response = await fetch(`/api/runs${query ? `?${query}` : ''}`)
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
      const response = await fetch(`/api/runs/batches/${batchId}`)
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
      const response = await fetch(`/api/templates${query ? `?${query}` : ''}`)
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
      const response = await fetch(`/api/templates/${templateId}`)
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
      const response = await fetch(`/api/runs/${run.run_id}`)
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
    link.href = `/api/runs/${run.run_id}/export.zip`
    link.download = `reelstruct-${run.run_id}.zip`
    link.click()
    setStatus('结果包已开始下载')
  }

  const loadRunRecord = async (runId: string) => {
    try {
      const response = await fetch(`/api/runs/${runId}`)
      if (!response.ok) {
        throw new Error(`读取 run 失败：${response.status}`)
      }
      const payload = (await response.json()) as DemoRunResponse
      setRun(payload)
      setOutputVariant(payload.variant || payload.preview.transfer_plan.variant || 'standard')
      setSelectedTemplateId(payload.template_id || '')
      setPreview(payload.preview)
      setSlotDrafts(buildSlotDrafts(payload.preview))
      setVideoUrl(payload.rendered_video.video_url ? `${payload.rendered_video.video_url}?t=${Date.now()}` : '')
      setStatus(`已载入 ${payload.run_id}`)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '读取 run 失败')
    }
  }

  const deleteRunRecord = async (runId: string) => {
    try {
      const response = await fetch(`/api/runs/${runId}`, { method: 'DELETE' })
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
      const response = await fetch(`/api/runs/${run.run_id}/note`, {
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
      const response = await fetch(`/api/runs/${run.run_id}/pin`, {
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
      const response = await fetch(`/api/runs/${runId}/preferred`, {
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
      const response = await fetch(`/api/templates/from-run/${run.run_id}`, {
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
      const response = await fetch(`/api/templates/${templateId}`, {
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
      const response = await fetch(`/api/templates/${selectedTemplateId}`, {
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
      const response = await fetch(`/api/templates/${selectedTemplateId}/rollback/${versionId}`, {
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
      const response = await fetch(`/api/templates/${templateId}/fork`, {
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

  return (
    <main className="min-h-screen bg-paper text-ink">
      <section className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold uppercase tracking-wide text-signal">ReelStruct</p>
            <h1 className="mt-3 text-4xl font-semibold leading-tight sm:text-5xl">
              爆款结构迁移引擎
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
              从样例结构到新内容映射，再到 fixture 素材准备和 FFmpeg 成片 demo，一条链路跑通 P0 演示。
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              className="rounded-md bg-ink px-4 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
              onClick={() => runDemo()}
              disabled={status === '正在执行迁移任务'}
            >
              生成迁移 demo
            </button>
            <span className="rounded-md border border-line bg-white px-4 py-2.5 text-sm font-medium text-slate-700">
              {status}
            </span>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-5 px-6 py-6 lg:grid-cols-4">
        {workflow.map((item) => (
          <article key={item.title} className="rounded-lg border border-line bg-white p-5 shadow-panel">
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {item.eyebrow}
              </span>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                {item.meta}
              </span>
            </div>
            <h2 className="mt-4 text-lg font-semibold">{item.title}</h2>
            <p className="mt-3 text-sm leading-6 text-slate-600">{item.body}</p>
          </article>
        ))}
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 pb-6 lg:grid-cols-[380px_1fr]">
        <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <p className="text-sm font-semibold text-signal">样例视频</p>
          <h2 className="mt-1 text-xl font-semibold">上传或使用默认样例</h2>
          <label className="mt-4 block rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-600">
            <span className="font-medium text-ink">选择视频文件</span>
            <input
              className="mt-3 block w-full text-sm"
              type="file"
              accept="video/*"
              onChange={(event) => uploadSample(event.target.files?.[0] || null)}
            />
          </label>
          <label className="mt-4 block rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-600">
            <span className="font-medium text-ink">上传 txt / srt 转写</span>
            <input
              className="mt-3 block w-full text-sm"
              type="file"
              accept=".txt,.srt,text/plain,application/x-subrip"
              onChange={(event) => uploadTranscript(event.target.files?.[0] || null)}
            />
          </label>
          <label className="mt-4 grid gap-2 text-sm font-medium text-slate-700">
            转写摘要
            <textarea
              className="min-h-28 rounded-md border border-line px-3 py-2 text-sm leading-6 text-ink outline-none focus:border-signal"
              value={sample.transcript_summary}
              onChange={(event) =>
                setSample({
                  ...sample,
                  transcript_summary: event.target.value,
                })
              }
            />
          </label>
          <div className="mt-4 grid gap-2 rounded-md bg-slate-950 p-4 text-xs leading-5 text-slate-100">
            <p>Title: {sample.title}</p>
            <p>Duration: {sample.duration}s</p>
            <p>Shots: {sample.shot_count}</p>
            <p>Source: {sampleUpload?.public_url || 'default fixture input'}</p>
            <p>Analysis: {sampleUpload ? 'scene detect' : 'default sample preset'}</p>
            <p>Transcript: {transcriptUpload?.filename || 'manual / default summary'}</p>
          </div>
        </div>

        <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <p className="text-sm font-semibold text-signal">新内容输入</p>
          <h2 className="mt-1 text-xl font-semibold">主题、商品和素材条件</h2>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="grid gap-2 text-sm font-medium text-slate-700">
              目标主题
              <input
                className="rounded-md border border-line px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                value={content.topic}
                onChange={(event) => setContent({ ...content, topic: event.target.value })}
              />
            </label>
            <label className="grid gap-2 text-sm font-medium text-slate-700">
              商品/账号名称
              <input
                className="rounded-md border border-line px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                value={content.product_name}
                onChange={(event) => setContent({ ...content, product_name: event.target.value })}
              />
            </label>
            <label className="grid gap-2 text-sm font-medium text-slate-700 md:col-span-2">
              卖点，用逗号分隔
              <div className="grid gap-2">
                {content.selling_points.map((point, index) => (
                  <div key={`${index}-${point}`} className="grid gap-2 sm:grid-cols-[1fr_auto_auto_auto]">
                    <input
                      className="rounded-md border border-line px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                      value={point}
                      onChange={(event) =>
                        setContent({
                          ...content,
                          selling_points: updateListItem(content.selling_points, index, event.target.value),
                        })
                      }
                    />
                    <button
                      className="rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
                      onClick={() => setContent({ ...content, selling_points: moveListItem(content.selling_points, index, -1) })}
                      disabled={index === 0}
                      type="button"
                    >
                      上移
                    </button>
                    <button
                      className="rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
                      onClick={() => setContent({ ...content, selling_points: moveListItem(content.selling_points, index, 1) })}
                      disabled={index === content.selling_points.length - 1}
                      type="button"
                    >
                      下移
                    </button>
                    <button
                      className="rounded-md border border-line px-3 py-2 text-xs font-medium text-coral"
                      onClick={() => setContent({ ...content, selling_points: removeListItem(content.selling_points, index) })}
                      type="button"
                    >
                      删除
                    </button>
                  </div>
                ))}
                <button
                  className="w-fit rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700"
                  onClick={() =>
                    setContent({
                      ...content,
                      selling_points: [...content.selling_points, `新卖点 ${content.selling_points.length + 1}`],
                    })
                  }
                  type="button"
                >
                  添加卖点
                </button>
              </div>
            </label>
            <label className="grid gap-2 text-sm font-medium text-slate-700 md:col-span-2">
              已有素材，用逗号分隔
              <input
                className="rounded-md border border-line px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                value={content.available_assets.join('，')}
                onChange={(event) => setContent({ ...content, available_assets: splitList(event.target.value) })}
              />
            </label>
            <div className="grid gap-3 md:col-span-2">
              <div className="grid gap-2 text-sm font-medium text-slate-700">
                <label htmlFor="output-variant">输出版本</label>
                <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto]">
                  <select
                    id="output-variant"
                    aria-label="输出版本"
                    className="rounded-md border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                    value={outputVariant}
                    onChange={(event) => setOutputVariant(event.target.value as OutputVariant)}
                  >
                    {outputVariants.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                  <button
                    className="rounded-md border border-line px-3 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:text-slate-300"
                    onClick={compareOutputVariants}
                    disabled={status === '正在生成版本对比' || status === '正在执行迁移任务'}
                    type="button"
                  >
                    生成版本对比
                  </button>
                  <button
                    className="rounded-md bg-ink px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
                    onClick={runDemoVariants}
                    disabled={status === '正在批量生成四版 demo' || status === '正在生成版本对比' || status === '正在执行迁移任务'}
                    type="button"
                  >
                    批量生成四版 demo
                  </button>
                </div>
              </div>

              {variantSummaries.length > 0 ? (
                <div className="grid gap-3 lg:grid-cols-4">
                  {variantSummaries.map((item) => {
                    const isActive = item.variant === outputVariant
                    return (
                      <article
                        key={item.variant}
                        className={`grid gap-3 rounded-md border p-3 text-sm ${
                          isActive ? 'border-signal bg-sky-50' : 'border-line bg-slate-50'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="font-semibold text-ink">{variantLabel(item.variant)}</p>
                            <p className="mt-1 text-xs text-slate-500">{item.rhythm_summary}</p>
                          </div>
                          <span className="shrink-0 rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600">
                            {item.duration}s
                          </span>
                        </div>
                        <div className="grid gap-2 text-xs leading-5 text-slate-600">
                          <p className="font-medium text-slate-700">{item.title}</p>
                          <p>Hook：{item.hook}</p>
                          <p>CTA：{item.cta}</p>
                          <p>缺口 {item.gap_count}</p>
                        </div>
                        <button
                          className={`rounded-md px-3 py-2 text-xs font-medium ${
                            isActive
                              ? 'bg-ink text-white'
                              : 'border border-line bg-white text-slate-700 hover:border-signal'
                          }`}
                          onClick={() => setOutputVariant(item.variant)}
                          type="button"
                        >
                          {isActive ? '当前版本' : '选择这个版本'}
                        </button>
                      </article>
                    )
                  })}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </section>

      {error ? (
        <section className="mx-auto max-w-7xl px-6 pb-6">
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        </section>
      ) : null}

      <section className="mx-auto max-w-7xl px-6 pb-6">
        <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <div className="flex items-center justify-between gap-4 border-b border-line pb-4">
            <div>
              <p className="text-sm font-semibold text-signal">样例拆解依据</p>
              <h2 className="mt-1 text-2xl font-semibold">
                {preview?.template.analysis_summary.headline || '样例解析结果'}
              </h2>
            </div>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-600">
              {preview?.template.rhythm_summary || '等待生成后展示'}
            </span>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-[320px_1fr]">
            <div className="grid gap-3">
              {(preview?.template.analysis_summary.metrics || fallbackAnalysis.metrics).map((metric) => (
                <article key={metric.label} className="rounded-md border border-line p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{metric.label}</p>
                  <p className="mt-2 text-2xl font-semibold text-ink">{metric.value}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{metric.detail}</p>
                </article>
              ))}
            </div>

            <div className="grid gap-4">
              <div className="grid gap-3 md:grid-cols-3">
                {(preview?.template.analysis_summary.narrative_beats || fallbackAnalysis.narrative_beats).map((beat) => (
                  <article key={beat.slot_id} className="rounded-md border border-line p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{beat.label}</p>
                    <p className="mt-3 text-sm leading-6 text-slate-700">{beat.evidence}</p>
                  </article>
                ))}
              </div>

              <div className="rounded-md border border-line p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">包装信号</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(preview?.template.analysis_summary.packaging_signals || fallbackAnalysis.packaging_signals).map((item, index) => (
                    <span key={`${item}-${index}`} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 pb-10 lg:grid-cols-[1fr_420px]">
        <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <div className="flex items-center justify-between gap-4 border-b border-line pb-4">
            <div>
              <p className="text-sm font-semibold text-signal">结构迁移预览</p>
              <h2 className="mt-1 text-2xl font-semibold">
                {preview?.template.title || '样例结构到新视频时间线'}
              </h2>
            </div>
            <div className="flex items-center gap-3">
              <span className="rounded-full bg-sky-50 px-3 py-1 text-sm font-medium text-sky-700">
                {variantLabel(preview?.transfer_plan.variant || outputVariant)}
              </span>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-mint">
                {preview ? `${preview.composition.duration}s` : 'P0 闭环'}
              </span>
              <button
                className="rounded-md border border-line px-3 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:text-slate-300"
                onClick={() => runDemo({ useDraftOverrides: true })}
                disabled={!preview || status === '正在执行迁移任务'}
                type="button"
              >
                应用改稿并重生成
              </button>
            </div>
          </div>

          <div className="mt-5 grid gap-4">
            {(preview?.template.script_pattern || fallbackSlots).map((slot) => {
              const gap = gapLookup.get(slot.id)
              const mapping = mappingLookup.get(slot.id)
              const draft = slotDrafts[slot.id] ?? {
                target_message: mapping?.target_message ?? slot.purpose,
                sample_evidence: slot.sample_evidence,
                asset_strategy: mapping?.asset_strategy ?? gap?.fill_strategy ?? `使用已有素材：${slot.required_asset}`,
              }
              return (
                <article key={slot.id} className="grid gap-4 rounded-md border border-line p-4">
                  <div className="grid gap-2 sm:grid-cols-[108px_110px_1fr] sm:items-start">
                    <strong>{slot.label}</strong>
                    <span className="text-sm text-slate-500">
                      {slot.start}-{Math.round((slot.start + slot.duration) * 10) / 10}s
                    </span>
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className={gap ? 'font-semibold text-coral' : 'font-semibold text-mint'}>
                        {gap ? '缺口补全' : '已映射'}
                      </span>
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                        需求素材：{slot.required_asset}
                      </span>
                    </div>
                  </div>

                  <div className="grid gap-3 lg:grid-cols-3">
                    <div className="rounded-md border border-line bg-slate-50 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">样例方法</p>
                      <div className="mt-3 grid gap-2 text-sm leading-6 text-slate-700">
                        <p><strong className="text-ink">结构角色：</strong>{slot.role || slot.purpose}</p>
                        <p><strong className="text-ink">爆款手法：</strong>{slot.method || mapping?.source_method || '等待拆解'}</p>
                        <p><strong className="text-ink">节奏意图：</strong>{slot.rhythm || '等待拆解'}</p>
                        <p><strong className="text-ink">可迁移规则：</strong>{slot.transferable_rule || mapping?.reasoning || '等待拆解'}</p>
                      </div>
                    </div>

                    <div className="rounded-md border border-line bg-slate-50 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">新内容迁移</p>
                      <div className="mt-3 grid gap-2 text-sm leading-6 text-slate-700">
                        <p><strong className="text-ink">迁移结果：</strong>{mapping?.target_adaptation || draft.target_message}</p>
                        <p><strong className="text-ink">迁移理由：</strong>{mapping?.reasoning || slot.intent || '等待生成'}</p>
                        <p><strong className="text-ink">不可复制：</strong>{slot.non_transferable || '只迁移方法，不复制样例内容。'}</p>
                      </div>
                    </div>

                    <div className="rounded-md border border-line bg-slate-50 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">素材/包装支撑</p>
                      <div className="mt-3 grid gap-2 text-sm leading-6 text-slate-700">
                        <p><strong className="text-ink">素材要求：</strong>{mapping?.asset_requirement || slot.required_asset}</p>
                        <p><strong className="text-ink">包装计划：</strong>{mapping?.packaging_plan || slot.packaging_intent || '字幕和卡片辅助表达'}</p>
                        <p><strong className="text-ink">缺口策略：</strong>{mapping?.fallback_strategy || draft.asset_strategy}</p>
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-3 lg:grid-cols-3">
                    <label className="grid gap-2 text-sm font-medium text-slate-700">
                      样例依据
                      <textarea
                        className="min-h-24 w-full rounded-md border border-line px-3 py-2 text-sm leading-6 text-ink outline-none focus:border-signal"
                        value={draft.sample_evidence}
                        onChange={(event) =>
                          setSlotDrafts({
                            ...slotDrafts,
                            [slot.id]: {
                              ...draft,
                              sample_evidence: event.target.value,
                            },
                          })
                        }
                      />
                    </label>

                    <label className="grid gap-2 text-sm font-medium text-slate-700">
                      迁移文案
                      <textarea
                        className="min-h-24 w-full rounded-md border border-line px-3 py-2 text-sm leading-6 text-ink outline-none focus:border-signal"
                        value={draft.target_message}
                        onChange={(event) =>
                          setSlotDrafts({
                            ...slotDrafts,
                            [slot.id]: {
                              ...draft,
                              target_message: event.target.value,
                            },
                          })
                        }
                      />
                    </label>

                    <label className="grid gap-2 text-sm font-medium text-slate-700">
                      补位策略
                      <textarea
                        className="min-h-24 w-full rounded-md border border-line px-3 py-2 text-sm leading-6 text-ink outline-none focus:border-signal"
                        value={draft.asset_strategy}
                        onChange={(event) =>
                          setSlotDrafts({
                            ...slotDrafts,
                            [slot.id]: {
                              ...draft,
                              asset_strategy: event.target.value,
                            },
                          })
                        }
                      />
                    </label>
                  </div>
                  {gap ? (
                    <p className="text-xs leading-5 text-coral">
                      当前缺口：{gap.missing_asset}。{gap.impact}
                    </p>
                  ) : null}
                </article>
              )
            })}
          </div>
        </div>

        <aside className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <p className="text-sm font-semibold text-signal">Demo Output</p>
          <h2 className="mt-1 text-xl font-semibold">FFmpeg 成片预览</h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            结构预览会生成 `CompositionSpec`，后端复用 fixture 素材并渲染成 MP4。
          </p>

          <div className="mt-4 aspect-[9/16] overflow-hidden rounded-md border border-line bg-slate-950">
            {videoUrl ? (
              <video className="h-full w-full object-cover" src={videoUrl} controls preload="metadata" />
            ) : (
              <div className="flex h-full items-center justify-center px-5 text-center text-sm leading-6 text-slate-300">
                点击“生成迁移 demo”后，这里会显示后端渲染出的 MP4。
              </div>
            )}
          </div>

          <div className="mt-4 rounded-md bg-slate-950 p-4 text-xs leading-5 text-slate-100">
            <p>Run: {run?.run_id ?? '--'}</p>
            <p>Batch: {run?.batch_id || '--'}</p>
            <p>Tracks: {preview?.composition.tracks.length ?? 0}</p>
            <p>Assets: {run?.prepared_assets.length ?? 0}</p>
            <p>Gaps: {preview?.transfer_plan.gaps.length ?? 0}</p>
            <p>Video: {videoUrl ? videoUrl.split('?')[0] : '--'}</p>
            <p>Pinned: {run?.pinned ? '已置顶' : '未置顶'}</p>
            <p>Preferred: {run?.preferred ? '首选版本' : '未设首选'}</p>
            <p>Variant: {variantLabel(run?.variant || preview?.transfer_plan.variant || outputVariant)}</p>
            <p>Template: {run?.template_title || selectedTemplate?.title || '默认样例结构'}</p>
            <p>Tags: {(run?.template_tags.length ? run.template_tags : selectedTemplate?.tags || []).join(' / ') || '--'}</p>
          </div>

          {run?.prepared_assets.length ? (
            <div className="mt-4 rounded-md border border-line bg-slate-50 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-signal">素材来源</p>
                  <h3 className="mt-1 text-lg font-semibold">本次重组素材说明</h3>
                </div>
                <span className="rounded-full bg-white px-2.5 py-1 text-xs text-slate-600">
                  {run.prepared_assets.length} 段
                </span>
              </div>
              <div className="mt-4 grid gap-2">
                {run.prepared_assets.map((asset) => (
                  <article key={`${asset.scene_id}-${asset.public_url}`} className="rounded-md border border-line bg-white p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <strong className="text-sm">{labelForSlot(asset.scene_id)}</strong>
                      <span className="rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700">
                        {asset.source_type === 'uploaded' ? '用户上传' : 'fixture 匹配'}
                      </span>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-slate-600">{asset.source_label || asset.public_url}</p>
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          {runBatch ? (
            <div className="mt-4 rounded-md border border-line bg-slate-50 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-signal">批次工作台</p>
                  <h3 className="mt-1 text-lg font-semibold">四版批次对比</h3>
                  <p className="mt-1 text-xs text-slate-500">{runBatch.batch_id}</p>
                </div>
                <span className="rounded-full bg-white px-2.5 py-1 text-xs text-slate-600">
                  {runBatch.runs.length} 个版本
                </span>
              </div>
              <div className="mt-4 grid gap-3">
                {runBatch.runs.map((item) => {
                  const isCurrentRun = item.run_id === run?.run_id
                  return (
                    <article
                      key={`batch-${item.run_id}`}
                      className={`rounded-md border p-3 ${
                        isCurrentRun ? 'border-signal bg-white' : 'border-line bg-white/70'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <strong className="text-sm">{variantLabel(item.variant)}</strong>
                            {item.preferred ? (
                              <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
                                首选版本
                              </span>
                            ) : null}
                            {isCurrentRun ? (
                              <span className="rounded-full bg-ink px-2.5 py-1 text-xs font-medium text-white">
                                当前预览
                              </span>
                            ) : null}
                          </div>
                          <p className="mt-1 text-xs text-slate-500">{item.run_id}</p>
                        </div>
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                          {item.duration}s
                        </span>
                      </div>
                      <div className="mt-3 grid gap-2 rounded-md bg-slate-50 p-3 text-xs leading-5 text-slate-600">
                        <p>
                          <span className="font-semibold text-slate-700">Hook：</span>
                          {item.hook || '--'}
                        </p>
                        <p>
                          <span className="font-semibold text-slate-700">CTA：</span>
                          {item.cta || '--'}
                        </p>
                        <p>
                          缺口 {item.gap_count} / 需求单 {item.material_request_count}
                        </p>
                      </div>
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <button
                          className="rounded-md border border-line bg-white px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
                          onClick={() => void loadRunRecord(item.run_id)}
                          disabled={isCurrentRun}
                          type="button"
                        >
                          {isCurrentRun ? '正在预览' : '载入这个版本'}
                        </button>
                        <button
                          className="rounded-md border border-line bg-white px-3 py-2 text-xs font-medium text-slate-700"
                          onClick={() => void toggleRunPreferred(item.run_id, item.preferred)}
                          type="button"
                        >
                          {item.preferred ? '取消首选' : '设为首选'}
                        </button>
                      </div>
                    </article>
                  )
                })}
              </div>
            </div>
          ) : null}

          <div className="mt-3 grid gap-2">
            <label className="grid gap-2 text-xs font-medium text-slate-700">
              模板名称
              <input
                aria-label="模板名称"
                className="rounded-md border border-line px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                value={templateNameDraft}
                onChange={(event) => setTemplateNameDraft(event.target.value)}
                placeholder="给当前结构起个模板名"
              />
            </label>
            <label className="grid gap-2 text-xs font-medium text-slate-700">
              模板标签
              <input
                aria-label="模板标签"
                className="rounded-md border border-line px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                value={templateTagsDraft}
                onChange={(event) => setTemplateTagsDraft(event.target.value)}
                placeholder="餐饮，本地生活"
              />
            </label>
            <label className="grid gap-2 text-xs font-medium text-slate-700">
              run 备注
              <textarea
                aria-label="run 备注"
                className="min-h-20 rounded-md border border-line px-3 py-2 text-sm leading-6 text-ink outline-none focus:border-signal"
                value={runNoteDraft}
                onChange={(event) => setRunNoteDraft(event.target.value)}
                placeholder="给这次迁移记录补一条备注"
              />
            </label>
            <button
              className="w-fit rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
              onClick={saveRunNote}
              disabled={!run}
              type="button"
            >
              保存备注
            </button>
            <button
              className="w-fit rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
              onClick={toggleRunPinned}
              disabled={!run}
              type="button"
            >
              {run?.pinned ? '取消置顶' : '置顶记录'}
            </button>
            <button
              className="w-fit rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
              onClick={() => void toggleRunPreferred()}
              disabled={!run}
              type="button"
            >
              {run?.preferred ? '取消首选' : '设为首选版本'}
            </button>
            <button
              className="w-fit rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
              onClick={saveRunAsTemplate}
              disabled={!run}
              type="button"
            >
              保存为模板
            </button>
            {run?.note ? <p className="text-sm leading-6 text-slate-700">{run.note}</p> : null}
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              className="rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
              onClick={exportRunJson}
              disabled={!run}
              type="button"
            >
              导出 run JSON
            </button>
            <button
              className="rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
              onClick={downloadRunPackage}
              disabled={!run}
              type="button"
            >
              下载结果包
            </button>
            <button
              className="rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700"
              onClick={() => void fetchRecentRuns()}
              type="button"
            >
              刷新记录
            </button>
            <label className="flex items-center gap-2 text-xs text-slate-600">
              <span className="sr-only">搜索记录</span>
              <input
                aria-label="搜索记录"
                className="rounded-md border border-line px-3 py-2 text-xs text-ink outline-none focus:border-signal"
                placeholder="搜索记录"
                value={runSearchKeyword}
                onChange={(event) => setRunSearchKeyword(event.target.value)}
              />
            </label>
            <label className="flex items-center gap-2 text-xs text-slate-600">
              <span className="sr-only">按 run 标签筛选</span>
              <input
                aria-label="按 run 标签筛选"
                className="rounded-md border border-line px-3 py-2 text-xs text-ink outline-none focus:border-signal"
                placeholder="按标签筛选"
                value={runTagFilter}
                onChange={(event) => setRunTagFilter(event.target.value)}
              />
            </label>
            <button
              className={
                runStatusFilter === 'all'
                  ? 'rounded-md bg-ink px-3 py-2 text-xs font-medium text-white'
                  : 'rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700'
              }
              onClick={() => setRunStatusFilter('all')}
              type="button"
            >
              全部记录
            </button>
            <button
              className={
                runStatusFilter === 'succeeded'
                  ? 'rounded-md bg-ink px-3 py-2 text-xs font-medium text-white'
                  : 'rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700'
              }
              onClick={() => setRunStatusFilter('succeeded')}
              type="button"
            >
              只看成功
            </button>
          </div>

          <div className="mt-5 border-t border-line pt-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-signal">结构模板库</p>
                <h3 className="mt-1 text-lg font-semibold">保存可复用结构</h3>
              </div>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                {templates.length} 条
              </span>
            </div>
            <div className="mt-4 rounded-md border border-line bg-slate-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">当前使用模板</p>
                  <p className="mt-1 text-sm font-medium text-slate-800">
                    {selectedTemplate ? selectedTemplate.title : '默认样例结构'}
                  </p>
                  {selectedTemplate?.tags.length ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {selectedTemplate.tags.map((tag, index) => (
                        <span key={`${tag}-${index}`} className="rounded-full bg-white px-2.5 py-1 text-xs text-slate-600">
                          标签 {tag}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
                <button
                  className="rounded-md border border-line bg-white px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
                  onClick={() => setSelectedTemplateId('')}
                  disabled={!selectedTemplateId}
                  type="button"
                >
                  使用默认样例结构
                </button>
              </div>
            </div>
            <label className="mt-4 grid gap-2 text-xs font-medium text-slate-700">
              按模板筛选
              <select
                aria-label="按模板筛选"
                className="rounded-md border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                value={runTemplateFilter}
                onChange={(event) => setRunTemplateFilter(event.target.value)}
              >
                <option value="">全部模板</option>
                {templates.map((item) => (
                  <option key={item.template_id} value={item.template_id}>
                    {item.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="mt-3 grid gap-2 text-xs font-medium text-slate-700">
              按模板标签筛选
              <input
                aria-label="按模板标签筛选"
                className="rounded-md border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                value={templateTagFilter}
                onChange={(event) => setTemplateTagFilter(event.target.value)}
                placeholder="本地生活"
              />
            </label>
            {templates.length ? (
              <div className="mt-4 grid gap-3">
                {templates.slice(0, 5).map((item) => (
                  <article key={item.template_id} className="rounded-md border border-line bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <strong className="text-sm">{item.title}</strong>
                        <p className="mt-1 text-xs text-slate-500">{item.template_id}</p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          className={
                            item.template_id === selectedTemplateId
                              ? 'rounded-md bg-ink px-3 py-2 text-xs font-medium text-white'
                              : 'rounded-md border border-line bg-white px-3 py-2 text-xs font-medium text-slate-700'
                          }
                          onClick={() => setSelectedTemplateId(item.template_id)}
                          type="button"
                        >
                          {item.template_id === selectedTemplateId ? '当前使用' : '使用这个模板'}
                        </button>
                        <button
                          className="rounded-md border border-line bg-white px-3 py-2 text-xs font-medium text-slate-700"
                          onClick={() => void forkTemplate(item.template_id, `${item.title} 副本`)}
                          type="button"
                        >
                          复制模板
                        </button>
                        <button
                          className="rounded-md border border-line bg-white px-3 py-2 text-xs font-medium text-coral"
                          onClick={() => void deleteTemplate(item.template_id)}
                          type="button"
                        >
                          删除模板
                        </button>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
                      <span className="rounded-full bg-white px-2.5 py-1">槽位 {item.slot_count}</span>
                      <span className="rounded-full bg-white px-2.5 py-1">来源 {item.source_run_id}</span>
                      {item.tags.map((tag, index) => (
                        <span key={`${item.template_id}-${tag}-${index}`} className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
                          标签 {tag}
                        </span>
                      ))}
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.rhythm_summary}</p>
                    <p className="mt-2 text-xs text-slate-500">{formatRunTime(item.created_at)}</p>
                  </article>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm leading-6 text-slate-600">
                先生成一个 run，再把当前结构保存成模板。
              </p>
            )}
            {selectedTemplateDetail && templateEditorDraft ? (
              <div className="mt-5 border-t border-line pt-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-signal">模板编辑</p>
                    <h3 className="mt-1 text-lg font-semibold">修改当前模板</h3>
                  </div>
                  <button
                    className="rounded-md border border-line bg-white px-3 py-2 text-xs font-medium text-slate-700"
                    onClick={saveTemplateEdits}
                    type="button"
                  >
                    保存模板修改
                  </button>
                </div>
                <div className="mt-4 grid gap-4">
                  <label className="grid gap-2 text-sm font-medium text-slate-700">
                    编辑模板标题
                    <input
                      aria-label="编辑模板标题"
                      className="rounded-md border border-line px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                      value={templateEditorDraft.title}
                      onChange={(event) =>
                        setTemplateEditorDraft({
                          ...templateEditorDraft,
                          title: event.target.value,
                        })
                      }
                    />
                  </label>
                  <label className="grid gap-2 text-sm font-medium text-slate-700">
                    模板节奏摘要
                    <input
                      aria-label="模板节奏摘要"
                      className="rounded-md border border-line px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                      value={templateEditorDraft.rhythm_summary}
                      onChange={(event) =>
                        setTemplateEditorDraft({
                          ...templateEditorDraft,
                          rhythm_summary: event.target.value,
                        })
                      }
                    />
                  </label>
                  <label className="grid gap-2 text-sm font-medium text-slate-700">
                    编辑模板标签
                    <input
                      aria-label="编辑模板标签"
                      className="rounded-md border border-line px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                      value={templateEditorDraft.tags}
                      onChange={(event) =>
                        setTemplateEditorDraft({
                          ...templateEditorDraft,
                          tags: event.target.value,
                        })
                      }
                    />
                  </label>
                  <div className="grid gap-3">
                    {selectedTemplateDetail.template.script_pattern.map((slot) => (
                      <article key={`template-edit-${slot.id}`} className="rounded-md border border-line bg-slate-50 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <strong className="text-sm">{labelForSlot(slot.id)}</strong>
                          <span className="text-xs text-slate-500">
                            {slot.start}-{Math.round((slot.start + slot.duration) * 10) / 10}s
                          </span>
                        </div>
                        <div className="mt-3 grid gap-3 sm:grid-cols-2">
                          <label className="grid gap-2 text-xs font-medium text-slate-700">
                            {labelForSlot(slot.id)} 时长
                            <input
                              aria-label={`${labelForSlot(slot.id)} 时长`}
                              className="rounded-md border border-line px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                              type="number"
                              min="0.5"
                              step="0.5"
                              value={templateEditorDraft.slots[slot.id]?.duration ?? String(slot.duration)}
                              onChange={(event) =>
                                setTemplateEditorDraft({
                                  ...templateEditorDraft,
                                  slots: {
                                    ...templateEditorDraft.slots,
                                    [slot.id]: {
                                      ...templateEditorDraft.slots[slot.id],
                                      duration: event.target.value,
                                    },
                                  },
                                })
                              }
                            />
                          </label>
                          <label className="grid gap-2 text-xs font-medium text-slate-700">
                            {labelForSlot(slot.id)} 素材要求
                            <input
                              aria-label={`${labelForSlot(slot.id)} 素材要求`}
                              className="rounded-md border border-line px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                              value={templateEditorDraft.slots[slot.id]?.required_asset ?? slot.required_asset}
                              onChange={(event) =>
                                setTemplateEditorDraft({
                                  ...templateEditorDraft,
                                  slots: {
                                    ...templateEditorDraft.slots,
                                    [slot.id]: {
                                      ...templateEditorDraft.slots[slot.id],
                                      required_asset: event.target.value,
                                    },
                                  },
                                })
                              }
                            />
                          </label>
                        </div>
                      </article>
                    ))}
                  </div>
                  <div className="rounded-md border border-line bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-signal">模板版本</p>
                        <h4 className="mt-1 text-base font-semibold">最近快照</h4>
                      </div>
                      <span className="rounded-full bg-white px-2.5 py-1 text-xs text-slate-600">
                        {selectedTemplateDetail.versions.length} 条
                      </span>
                    </div>
                    {selectedTemplateDetail.versions.length ? (
                      <div className="mt-4 grid gap-3">
                        {selectedTemplateDetail.versions.slice(0, 5).map((version) => (
                          <article key={version.version_id} className="rounded-md border border-line bg-white p-4">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <strong className="text-sm">{version.template.title}</strong>
                                <p className="mt-1 text-xs text-slate-500">{version.version_id}</p>
                              </div>
                              <button
                                className="rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700"
                                onClick={() => void rollbackTemplateVersion(version.version_id)}
                                type="button"
                              >
                                回退到这一版
                              </button>
                            </div>
                            <p className="mt-3 text-sm leading-6 text-slate-600">{version.template.rhythm_summary}</p>
                            <p className="mt-2 text-xs text-slate-500">{formatRunTime(version.created_at)}</p>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-3 text-sm leading-6 text-slate-600">
                        先保存一次模板修改，这里才会生成版本快照。
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <div className="mt-5 border-t border-line pt-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-signal">最近 run 记录</p>
                <h3 className="mt-1 text-lg font-semibold">最近生成结果</h3>
              </div>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                {recentRuns.length} 条
              </span>
            </div>
            {recentRuns.length ? (
              <div className="mt-4 grid gap-3">
                {recentRuns.slice(0, 5).map((item) => {
                  const isCurrentRun = item.run_id === run?.run_id
                  return (
                    <article
                      key={item.run_id}
                      className={`rounded-md border p-4 ${
                        isCurrentRun ? 'border-signal bg-sky-50' : 'border-line bg-slate-50'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <strong className="text-sm">{item.title}</strong>
                          <p className="mt-1 text-xs text-slate-500">{item.run_id}</p>
                          {item.batch_id ? <p className="mt-1 text-xs text-slate-500">{item.batch_id}</p> : null}
                        </div>
                        <div className="flex gap-2">
                          <button
                            className="rounded-md border border-line bg-white px-3 py-2 text-xs font-medium text-slate-700"
                            onClick={() => void loadRunRecord(item.run_id)}
                            type="button"
                          >
                            载入记录
                          </button>
                          <button
                            className="rounded-md border border-line bg-white px-3 py-2 text-xs font-medium text-coral"
                            onClick={() => void deleteRunRecord(item.run_id)}
                            type="button"
                          >
                            删除记录
                          </button>
                        </div>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
                        {isCurrentRun ? <span className="rounded-full bg-ink px-2.5 py-1 text-white">当前预览</span> : null}
                        {item.pinned ? <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">已置顶</span> : null}
                        {item.preferred ? <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">首选版本</span> : null}
                        {item.batch_id ? <span className="rounded-full bg-white px-2.5 py-1">批次 {item.batch_id.replace('batch-', '')}</span> : null}
                        <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                          {variantLabel(item.variant)}
                        </span>
                        {item.template_title ? (
                          <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">模板 {item.template_title}</span>
                        ) : null}
                        {item.template_tags.map((tag, index) => (
                          <span key={`${item.run_id}-${tag}-${index}`} className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
                            标签 {tag}
                          </span>
                        ))}
                        <span className="rounded-full bg-white px-2.5 py-1">缺口 {item.gap_count}</span>
                        <span className="rounded-full bg-white px-2.5 py-1">需求单 {item.material_request_count}</span>
                        <span className="rounded-full bg-white px-2.5 py-1">{item.duration}s</span>
                        <span className="rounded-full bg-white px-2.5 py-1">{item.status}</span>
                      </div>
                      <div className="mt-3 grid gap-2 rounded-md bg-white/75 p-3 text-xs leading-5 text-slate-600">
                        <p>
                          <span className="font-semibold text-slate-700">Hook：</span>
                          {item.hook || '--'}
                        </p>
                        <p>
                          <span className="font-semibold text-slate-700">CTA：</span>
                          {item.cta || '--'}
                        </p>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-slate-600">{item.target_topic}</p>
                      {item.note ? <p className="mt-2 text-sm leading-6 text-slate-700">{item.note}</p> : null}
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <button
                          className="rounded-md border border-line bg-white px-3 py-2 text-xs font-medium text-slate-700"
                          onClick={() => void toggleRunPreferred(item.run_id, item.preferred)}
                          type="button"
                        >
                          {item.preferred ? '取消首选' : '设为首选'}
                        </button>
                        <p className="text-xs text-slate-500">{formatRunTime(item.created_at)}</p>
                      </div>
                    </article>
                  )
                })}
              </div>
            ) : (
              <p className="mt-3 text-sm leading-6 text-slate-600">
                {runSearchKeyword.trim() ? '没有匹配的 run 记录。' : '生成后这里会保留最近几次 run 记录。'}
              </p>
            )}
          </div>

          <div className="mt-5 border-t border-line pt-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-signal">素材补位建议</p>
                <h3 className="mt-1 text-lg font-semibold">建议补拍清单</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  className="rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
                  onClick={() => setSelectedGapIds((preview?.transfer_plan.gaps || []).map((gap) => gap.slot_id))}
                  disabled={!preview?.transfer_plan.gaps.length}
                  type="button"
                >
                  全选缺口
                </button>
                <button
                  className="rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
                  onClick={() => setSelectedGapIds([])}
                  disabled={!selectedGapIds.length}
                  type="button"
                >
                  清空选择
                </button>
                <button
                  className="rounded-md bg-ink px-3 py-2 text-xs font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
                  onClick={addSelectedGapsToRequestSheet}
                  disabled={!selectedGapIds.length}
                  type="button"
                >
                  加入需求单
                </button>
              </div>
            </div>
            {preview?.transfer_plan.gaps.length ? (
              <div className="mt-4 grid gap-3">
                {preview.transfer_plan.gaps.map((gap) => (
                  <article key={gap.slot_id} className="rounded-md border border-line p-4">
                    <div className="flex items-start gap-3">
                      <input
                        className="mt-1 h-4 w-4 rounded border-line"
                        type="checkbox"
                        checked={selectedGapIds.includes(gap.slot_id)}
                        onChange={(event) =>
                          setSelectedGapIds((current) =>
                            event.target.checked
                              ? [...current, gap.slot_id]
                              : current.filter((item) => item !== gap.slot_id),
                          )
                        }
                      />
                      <div className="flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <strong className="text-sm">{labelForSlot(gap.slot_id)}</strong>
                          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                            {gap.suggested_asset_type}
                          </span>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-slate-600">{gap.fill_strategy}</p>

                        <div className="mt-3">
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">建议镜头</p>
                          <ul className="mt-2 grid gap-2 text-sm leading-6 text-slate-700">
                            {gap.suggested_shots.map((item, index) => (
                              <li key={`${item}-${index}`}>- {item}</li>
                            ))}
                          </ul>
                        </div>

                        <div className="mt-3">
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">检查清单</p>
                          <ul className="mt-2 grid gap-2 text-sm leading-6 text-slate-700">
                            {gap.pickup_checklist.map((item, index) => (
                              <li key={`${item}-${index}`}>- {item}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm leading-6 text-slate-600">
                {preview ? '当前结构段都有对应素材，暂时不需要补拍。' : '生成后会根据缺口自动给出补拍建议。'}
              </p>
            )}

            <div className="mt-5 border-t border-line pt-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-signal">素材需求单</p>
                  <h3 className="mt-1 text-lg font-semibold">待执行素材任务</h3>
                </div>
                <div className="flex flex-wrap items-center justify-end gap-2">
                  {requestSheetFeedback ? (
                    <span className="text-xs font-medium text-mint">{requestSheetFeedback}</span>
                  ) : null}
                  <button
                    className="rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
                    onClick={clearRequestSheet}
                    disabled={!requestSheetItems.length}
                    type="button"
                  >
                    清空需求单
                  </button>
                  <button
                    className="rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
                    onClick={copyRequestSheet}
                    disabled={!requestSheetItems.length}
                    type="button"
                  >
                    复制需求单
                  </button>
                  <button
                    className="rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
                    onClick={exportRequestSheet}
                    disabled={!requestSheetItems.length}
                    type="button"
                  >
                    导出 txt
                  </button>
                </div>
              </div>
              {requestSheetItems.length ? (
                <div className="mt-4 grid gap-3">
                  {requestSheetItems.map((item) => {
                    const status = requestSheetStatus[item.task.slot_id] ?? item.task.status
                    const uploadedAsset = uploadedAssetLookup.get(item.task.slot_id)
                    return (
                      <article key={item.task.slot_id} className="rounded-md border border-line bg-slate-50 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <strong className="text-sm">{labelForSlot(item.task.slot_id)}</strong>
                            <span className="rounded-full bg-white px-2.5 py-1 text-xs text-slate-600">
                              {item.gap?.suggested_asset_type || item.slot.required_asset}
                            </span>
                            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
                              当前状态：{status}
                            </span>
                            {!item.gap ? (
                              <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
                                已补齐素材
                              </span>
                            ) : null}
                            {uploadedAsset ? (
                              <span className="rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700">
                                已上传 {uploadedAsset.filename}
                              </span>
                            ) : null}
                          </div>
                          <button
                            className="rounded-md border border-line bg-white px-3 py-2 text-xs font-medium text-slate-700"
                            onClick={() => removeFromRequestSheet(item.task.slot_id)}
                            type="button"
                          >
                            移出需求单
                          </button>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-slate-700">
                          {item.gap?.fill_strategy || `已可使用素材：${item.slot.required_asset}`}
                        </p>
                        {uploadedAsset?.analysis?.recommended_slot_id ? (
                          <div className="mt-3 rounded-md border border-sky-100 bg-sky-50 p-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">素材适配分析</p>
                              <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-sky-700">
                                推荐槽位：{uploadedAsset.analysis.recommended_slot_label}
                              </span>
                              <span className="rounded-full bg-white px-2.5 py-1 text-xs text-slate-600">
                                {uploadedAsset.analysis.duration}s / {uploadedAsset.analysis.shot_count} 镜头
                              </span>
                            </div>
                            <p className="mt-2 text-sm leading-6 text-slate-700">
                              {uploadedAsset.analysis.recommendation_reason}
                            </p>
                            <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-600">
                              <span>Hook {uploadedAsset.analysis.slot_fit_scores.hook ?? 0}</span>
                              <span>卖点 {uploadedAsset.analysis.slot_fit_scores.selling_points ?? 0}</span>
                              <span>使用过程 {uploadedAsset.analysis.slot_fit_scores.usage ?? 0}</span>
                              <span>CTA {uploadedAsset.analysis.slot_fit_scores.cta ?? 0}</span>
                            </div>
                          </div>
                        ) : null}
                        <label className="mt-3 grid gap-2 text-xs font-medium text-slate-700">
                          上传补拍素材
                          <input
                            aria-label={`${labelForSlot(item.task.slot_id)} 上传补拍素材`}
                            className="block w-full text-xs"
                            type="file"
                            accept="video/*"
                            onChange={(event) => void uploadMaterialAsset(item.task.slot_id, event.target.files?.[0] || null)}
                          />
                        </label>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {materialTaskStatuses.map((nextStatus) => {
                            const active = status === nextStatus
                            return (
                              <button
                                key={`${item.task.slot_id}-${nextStatus}`}
                                className={
                                  active
                                    ? 'rounded-md bg-ink px-3 py-2 text-xs font-medium text-white'
                                    : 'rounded-md border border-line bg-white px-3 py-2 text-xs font-medium text-slate-700'
                                }
                                onClick={() => updateMaterialTaskStatus(item.task.slot_id, nextStatus)}
                                type="button"
                              >
                                {nextStatus}
                              </button>
                            )
                          })}
                        </div>
                        <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">需求摘要</p>
                        <p className="mt-2 whitespace-pre-line text-sm leading-6 text-slate-700">
                          {buildMaterialRequestSheetEntry(item, status)}
                        </p>
                      </article>
                    )
                  })}
                </div>
              ) : (
                <p className="mt-3 text-sm leading-6 text-slate-600">
                  先从补拍建议里勾选缺口，再点“加入需求单”。
                </p>
              )}
            </div>
          </div>
        </aside>
      </section>

      <section className="mx-auto max-w-7xl px-6 pb-12">
        <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <div className="flex items-center justify-between gap-4 border-b border-line pb-4">
            <div>
              <p className="text-sm font-semibold text-signal">执行过程</p>
              <h2 className="mt-1 text-2xl font-semibold">迁移任务 trace</h2>
            </div>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-600">
              {run?.status ?? 'idle'}
            </span>
          </div>

          <div className="mt-5 grid gap-3 lg:grid-cols-5">
            {(run?.trace || fallbackTrace).map((event) => (
              <article key={event.step} className="rounded-md border border-line p-4">
                <div className="flex items-center justify-between gap-3">
                  <strong className="text-sm">{event.title}</strong>
                  <span className="text-xs font-semibold text-mint">{event.progress}%</span>
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-600">{event.message}</p>
                <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-mint" style={{ width: `${event.progress}%` }} />
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  )
}

async function requestJson<T>(url: string, options: { method: 'POST'; body: unknown }): Promise<T> {
  const response = await fetch(url, {
    method: options.method,
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(options.body),
  })

  if (!response.ok) {
    throw new Error(`请求失败：${response.status} ${await response.text()}`)
  }

  return response.json() as Promise<T>
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
