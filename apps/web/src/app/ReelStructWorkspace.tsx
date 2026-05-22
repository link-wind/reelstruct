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

type TransferMapping = {
  slot_id: string
  source_label: string
  target_message: string
  asset_strategy: string
}

type CompositionTrack = {
  type: 'video' | 'caption' | 'card'
  start: number
  duration: number
  text: string
  source: string
  slot_id: string
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
    mappings: TransferMapping[]
    gaps: MaterialGap[]
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
}

type RunTraceEvent = {
  step: string
  title: string
  message: string
  progress: number
}

type DemoRunResponse = {
  run_id: string
  status: 'succeeded' | 'failed'
  preview: StructurePreviewResponse
  prepared_assets: RenderClipPreview[]
  rendered_video: RenderDemoResponse
  trace: RunTraceEvent[]
}

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

type MaterialTaskStatus = '待补拍' | '已拍' | '已交付'

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
}

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

  const requestSheetGaps = useMemo(() => {
    return (preview?.transfer_plan.gaps || []).filter((gap) => requestSheetIds.includes(gap.slot_id))
  }, [preview, requestSheetIds])

  const requestSheetText = useMemo(() => {
    return buildMaterialRequestSheetText(requestSheetGaps, requestSheetStatus)
  }, [requestSheetGaps, requestSheetStatus])

  useEffect(() => {
    const nextGapIds = (preview?.transfer_plan.gaps || []).map((gap) => gap.slot_id)
    setSelectedGapIds(nextGapIds)
    setRequestSheetIds([])
    setRequestSheetStatus({})
    setRequestSheetFeedback('')
  }, [preview])

  useEffect(() => {
    if (!requestSheetFeedback) return
    const timer = window.setTimeout(() => setRequestSheetFeedback(''), 1800)
    return () => window.clearTimeout(timer)
  }, [requestSheetFeedback])

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

  const runDemo = async (options?: { useDraftOverrides?: boolean }) => {
    setError('')
    setStatus('正在执行迁移任务')
    setVideoUrl('')
    setRun(null)

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
          mapping_overrides,
        },
      })
      setRun(runResponse)
      setPreview(runResponse.preview)
      setSlotDrafts(buildSlotDrafts(runResponse.preview))
      setVideoUrl(`${runResponse.rendered_video.video_url}?t=${Date.now()}`)
      setStatus('迁移任务已完成')
    } catch (caught) {
      setStatus('生成失败')
      setError(caught instanceof Error ? caught.message : '未知错误')
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
                  {(preview?.template.analysis_summary.packaging_signals || fallbackAnalysis.packaging_signals).map((item) => (
                    <span key={item} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
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
            <p>Tracks: {preview?.composition.tracks.length ?? 0}</p>
            <p>Assets: {run?.prepared_assets.length ?? 0}</p>
            <p>Gaps: {preview?.transfer_plan.gaps.length ?? 0}</p>
            <p>Video: {videoUrl ? videoUrl.split('?')[0] : '--'}</p>
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
                            {gap.suggested_shots.map((item) => (
                              <li key={item}>- {item}</li>
                            ))}
                          </ul>
                        </div>

                        <div className="mt-3">
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">检查清单</p>
                          <ul className="mt-2 grid gap-2 text-sm leading-6 text-slate-700">
                            {gap.pickup_checklist.map((item) => (
                              <li key={item}>- {item}</li>
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
                    disabled={!requestSheetGaps.length}
                    type="button"
                  >
                    清空需求单
                  </button>
                  <button
                    className="rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
                    onClick={copyRequestSheet}
                    disabled={!requestSheetGaps.length}
                    type="button"
                  >
                    复制需求单
                  </button>
                  <button
                    className="rounded-md border border-line px-3 py-2 text-xs font-medium text-slate-700 disabled:text-slate-300"
                    onClick={exportRequestSheet}
                    disabled={!requestSheetGaps.length}
                    type="button"
                  >
                    导出 txt
                  </button>
                </div>
              </div>
              {requestSheetGaps.length ? (
                <div className="mt-4 grid gap-3">
                  {requestSheetGaps.map((gap) => (
                    <article key={gap.slot_id} className="rounded-md border border-line bg-slate-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <strong className="text-sm">{labelForSlot(gap.slot_id)}</strong>
                          <span className="rounded-full bg-white px-2.5 py-1 text-xs text-slate-600">
                            {gap.suggested_asset_type}
                          </span>
                          <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
                            当前状态：{requestSheetStatus[gap.slot_id] ?? '待补拍'}
                          </span>
                        </div>
                        <button
                          className="rounded-md border border-line bg-white px-3 py-2 text-xs font-medium text-slate-700"
                          onClick={() => removeFromRequestSheet(gap.slot_id)}
                          type="button"
                        >
                          移出需求单
                        </button>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-700">{gap.fill_strategy}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {materialTaskStatuses.map((item) => {
                          const active = (requestSheetStatus[gap.slot_id] ?? '待补拍') === item
                          return (
                            <button
                              key={`${gap.slot_id}-${item}`}
                              className={
                                active
                                  ? 'rounded-md bg-ink px-3 py-2 text-xs font-medium text-white'
                                  : 'rounded-md border border-line bg-white px-3 py-2 text-xs font-medium text-slate-700'
                              }
                              onClick={() => updateMaterialTaskStatus(gap.slot_id, item)}
                              type="button"
                            >
                              {item}
                            </button>
                          )
                        })}
                      </div>
                      <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">需求摘要</p>
                      <p className="mt-2 whitespace-pre-line text-sm leading-6 text-slate-700">
                        {buildMaterialRequestSheetEntry(gap, requestSheetStatus[gap.slot_id] ?? '待补拍')}
                      </p>
                    </article>
                  ))}
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

const materialTaskStatuses: MaterialTaskStatus[] = ['待补拍', '已拍', '已交付']

function buildMaterialRequestSheetEntry(gap: MaterialGap, status: MaterialTaskStatus): string {
  return [
    `当前状态：${status}`,
    `缺口素材：${gap.missing_asset}`,
    `补位方式：${gap.fill_strategy}`,
    `建议镜头：${gap.suggested_shots.join('；')}`,
    `检查清单：${gap.pickup_checklist.join('；')}`,
  ].join('\n')
}

function buildMaterialRequestSheetText(
  gaps: MaterialGap[],
  statusLookup: Record<string, MaterialTaskStatus>,
): string {
  if (!gaps.length) return ''
  return [
    '素材需求单',
    '待执行素材任务',
    '',
    ...gaps.flatMap((gap, index) => {
      const status = statusLookup[gap.slot_id] ?? '待补拍'
      return [
        `${index + 1}. ${labelForSlot(gap.slot_id)} / ${gap.suggested_asset_type}`,
        buildMaterialRequestSheetEntry(gap, status),
        '',
      ]
    }),
  ].join('\n').trim()
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
  },
  {
    id: 'selling_points',
    label: '卖点展开',
    start: 3,
    duration: 13,
    purpose: '缺少商品特写，使用卖点卡片补足',
    required_asset: '商品特写镜头',
    sample_evidence: '等待后端结构预览',
  },
  {
    id: 'usage',
    label: '使用过程',
    start: 16,
    duration: 8,
    purpose: '复用场景素材 + 字幕解释',
    required_asset: '使用过程镜头',
    sample_evidence: '等待后端结构预览',
  },
  {
    id: 'cta',
    label: 'CTA',
    start: 24,
    duration: 4,
    purpose: '结尾行动号召和封面文案',
    required_asset: '结尾 CTA 镜头',
    sample_evidence: '等待后端结构预览',
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
