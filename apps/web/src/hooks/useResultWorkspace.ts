'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  apiUrl,
  buildMappingOverrides,
  buildMaterialRequestSheetPayload,
  buildSlotDrafts,
  buildSupplementSelectionPayload,
  mediaUrl,
  requestJson,
  splitList,
  type MaterialTaskStatus,
  type OutputVariant,
} from './reelStructWorkspaceShared'

type ResultWorkspaceDeps = {
  preview: any | null
  setPreview: (value: any | null) => void
  setSlotDrafts: (value: Record<string, any>) => void
  sample: any
  content: any
  sampleUpload: any
  manualEvidenceGraph: any
  selectedTemplateId: string
  setSelectedTemplateId: (value: string) => void
  outputVariant: OutputVariant
  setOutputVariant: (value: OutputVariant) => void
  requestSheetIds: string[]
  requestSheetStatus: Record<string, MaterialTaskStatus>
  supplementSelection: Record<string, string>
  setStatus: (value: string) => void
  setError: (value: string) => void
}

export function useResultWorkspace(deps: ResultWorkspaceDeps) {
  const [run, setRun] = useState<any | null>(null)
  const [runBatch, setRunBatch] = useState<any | null>(null)
  const [recentRuns, setRecentRuns] = useState<any[]>([])
  const [templates, setTemplates] = useState<any[]>([])
  const [selectedTemplateDetail, setSelectedTemplateDetail] = useState<any | null>(null)
  const [templateEditorDraft, setTemplateEditorDraft] = useState<any | null>(null)
  const [templateNameDraft, setTemplateNameDraft] = useState('')
  const [templateTagsDraft, setTemplateTagsDraft] = useState('')
  const [templateTagFilter, setTemplateTagFilter] = useState('')
  const [runTemplateFilter, setRunTemplateFilter] = useState('')
  const [runTagFilter, setRunTagFilter] = useState('')
  const [runStatusFilter, setRunStatusFilter] = useState<'all' | 'succeeded'>('all')
  const [runSearchKeyword, setRunSearchKeyword] = useState('')
  const [runNoteDraft, setRunNoteDraft] = useState('')
  const [videoUrl, setVideoUrl] = useState('')

  const runRef = useRef(run)
  const selectedTemplateIdRef = useRef(deps.selectedTemplateId)

  useEffect(() => {
    runRef.current = run
  }, [run])

  useEffect(() => {
    selectedTemplateIdRef.current = deps.selectedTemplateId
  }, [deps.selectedTemplateId])

  const selectedTemplate = useMemo(() => {
    return templates.find((item) => item.template_id === deps.selectedTemplateId) || null
  }, [deps.selectedTemplateId, templates])

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
    void fetchRecentRuns()
  }, [runStatusFilter, runSearchKeyword, runTemplateFilter, runTagFilter])

  useEffect(() => {
    void fetchTemplates()
  }, [templateTagFilter])

  useEffect(() => {
    if (!deps.selectedTemplateId) {
      setSelectedTemplateDetail(null)
      setTemplateEditorDraft(null)
      return
    }
    void fetchTemplateDetail(deps.selectedTemplateId)
  }, [deps.selectedTemplateId])

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
    if (deps.preview?.template?.title) {
      setTemplateNameDraft(deps.preview.template.title)
    }
  }, [deps.preview?.template?.title, run?.template_tags, run?.template_title, selectedTemplate])

  const fetchRecentRuns = async () => {
    try {
      const params = new URLSearchParams()
      if (runStatusFilter !== 'all') params.set('status', runStatusFilter)
      if (runTemplateFilter) params.set('template_id', runTemplateFilter)
      if (runTagFilter.trim()) params.set('tag', runTagFilter.trim())
      if (runSearchKeyword.trim()) params.set('q', runSearchKeyword.trim())
      const query = params.toString()
      const response = await fetch(apiUrl(`/api/runs${query ? `?${query}` : ''}`))
      if (!response.ok) throw new Error(`读取记录失败：${response.status}`)
      setRecentRuns((await response.json()) as any[])
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '读取记录失败')
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
      setRunBatch((await response.json()) as any)
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '读取批次失败')
    }
  }

  const fetchTemplates = async () => {
    try {
      const params = new URLSearchParams()
      if (templateTagFilter.trim()) params.set('tag', templateTagFilter.trim())
      const query = params.toString()
      const response = await fetch(apiUrl(`/api/templates${query ? `?${query}` : ''}`))
      if (!response.ok) throw new Error(`读取模板失败：${response.status}`)
      const records = (await response.json()) as any[]
      setTemplates(records)
      if (deps.selectedTemplateId && !records.some((item) => item.template_id === deps.selectedTemplateId)) {
        deps.setSelectedTemplateId('')
        setSelectedTemplateDetail(null)
        setTemplateEditorDraft(null)
      }
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '读取模板失败')
    }
  }

  const fetchTemplateDetail = async (templateId: string) => {
    try {
      const response = await fetch(apiUrl(`/api/templates/${templateId}`))
      if (!response.ok) throw new Error(`读取模板详情失败：${response.status}`)
      const record = (await response.json()) as any
      setSelectedTemplateDetail(record)
      setTemplateEditorDraft({
        title: record.template.title,
        rhythm_summary: record.template.rhythm_summary,
        tags: record.tags.join('，'),
        slots: Object.fromEntries(
          record.template.script_pattern.map((slot: any) => [
            slot.id,
            {
              duration: String(slot.duration),
              required_asset: slot.required_asset,
            },
          ]),
        ),
      })
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '读取模板详情失败')
    }
  }

  const runDemo = async (options?: { useDraftOverrides?: boolean }) => {
    deps.setError('')
    deps.setStatus('正在执行迁移任务')
    setVideoUrl('')
    setRun(null)
    setRunBatch(null)

    try {
      if (deps.preview) {
        const mapping_overrides =
          options?.useDraftOverrides ? buildMappingOverrides(deps.preview, buildSlotDrafts(deps.preview)) : []
        const runResponse = await requestJson<any>('/api/runs/from-preview', {
          method: 'POST',
          body: {
            preview: deps.preview,
            template_id: deps.selectedTemplateId,
            template_title: selectedTemplate?.title || deps.preview.template.title || '',
            template_tags: selectedTemplate?.tags || [],
            variant: deps.outputVariant,
            mapping_overrides,
          },
        })
        setRun(runResponse)
        deps.setPreview(runResponse.preview)
        deps.setSlotDrafts(buildSlotDrafts(runResponse.preview))
        setVideoUrl(mediaUrl(`${runResponse.rendered_video.video_url}?t=${Date.now()}`))
        void fetchRecentRuns()
        deps.setStatus('迁移任务已完成')
        return
      }

      const runResponse = await requestJson<any>('/api/runs/demo', {
        method: 'POST',
        body: {
          sample: deps.sample,
          content: deps.content,
          sample_local_path: deps.sampleUpload?.local_path || '',
          use_ai_structure: true,
          use_ai_transfer_explanation: true,
          shot_evidence_graph: deps.manualEvidenceGraph || undefined,
          template_id: deps.selectedTemplateId,
          variant: deps.outputVariant,
          mapping_overrides: [],
          material_request_sheet: buildMaterialRequestSheetPayload(deps.requestSheetIds, deps.requestSheetStatus),
          supplement_selections: buildSupplementSelectionPayload(deps.supplementSelection),
        },
      })
      setRun(runResponse)
      deps.setPreview(runResponse.preview)
      deps.setSlotDrafts(buildSlotDrafts(runResponse.preview))
      setVideoUrl(mediaUrl(`${runResponse.rendered_video.video_url}?t=${Date.now()}`))
      void fetchRecentRuns()
      deps.setStatus('迁移任务已完成')
    } catch (caught) {
      deps.setStatus('生成失败')
      deps.setError(caught instanceof Error ? caught.message : '未知错误')
    }
  }

  const runDemoVariants = async () => {
    deps.setError('')
    deps.setStatus('正在批量生成四版 demo')
    setVideoUrl('')
    setRun(null)
    setRunBatch(null)

    try {
      const mapping_overrides = deps.preview ? buildMappingOverrides(deps.preview, buildSlotDrafts(deps.preview)) : []
      const payload = await requestJson<any>('/api/runs/demo-variants', {
        method: 'POST',
        body: {
          sample: deps.sample,
          content: deps.content,
          sample_local_path: deps.sampleUpload?.local_path || '',
          use_ai_structure: true,
          use_ai_transfer_explanation: true,
          shot_evidence_graph: deps.manualEvidenceGraph || undefined,
          template_id: deps.selectedTemplateId,
          variant: deps.outputVariant,
          mapping_overrides,
          material_request_sheet: buildMaterialRequestSheetPayload(deps.requestSheetIds, deps.requestSheetStatus),
          supplement_selections: buildSupplementSelectionPayload(deps.supplementSelection),
        },
      })
      const selectedRun = payload.runs.find((item: any) => item.variant === deps.outputVariant) || payload.runs[0]
      setRun(selectedRun)
      deps.setPreview(selectedRun.preview)
      deps.setSlotDrafts(buildSlotDrafts(selectedRun.preview))
      setVideoUrl(mediaUrl(`${selectedRun.rendered_video.video_url}?t=${Date.now()}`))
      await fetchRunBatch(selectedRun.batch_id)
      await fetchRecentRuns()
      deps.setStatus('四版 demo 已生成')
    } catch (caught) {
      deps.setStatus('批量生成失败')
      deps.setError(caught instanceof Error ? caught.message : '批量生成失败')
    }
  }

  const applyDemoRunResponse = (runResponse: any) => {
    setRun(runResponse)
    deps.setPreview(runResponse.preview)
    deps.setSlotDrafts(buildSlotDrafts(runResponse.preview))
    setVideoUrl(mediaUrl(`${runResponse.rendered_video.video_url}?t=${Date.now()}`))
    setRunBatch(null)
    void fetchRecentRuns()
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
      deps.setStatus('run 记录已导出')
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '导出 run 记录失败')
    }
  }

  const downloadRunPackage = () => {
    if (!run) return
    const link = document.createElement('a')
    link.href = apiUrl(`/api/runs/${run.run_id}/export.zip`)
    link.download = `reelstruct-${run.run_id}.zip`
    link.click()
    deps.setStatus('结果包已开始下载')
  }

  const loadRunRecord = async (runId: string) => {
    try {
      const response = await fetch(apiUrl(`/api/runs/${runId}`))
      if (!response.ok) throw new Error(`读取 run 失败：${response.status}`)
      const payload = (await response.json()) as any
      setRun(payload)
      deps.setOutputVariant(payload.variant || payload.preview.transfer_plan.variant || 'standard')
      deps.setSelectedTemplateId(payload.template_id || '')
      deps.setPreview(payload.preview)
      deps.setSlotDrafts(buildSlotDrafts(payload.preview))
      setVideoUrl(payload.rendered_video.video_url ? mediaUrl(`${payload.rendered_video.video_url}?t=${Date.now()}`) : '')
      deps.setStatus(`已载入 ${payload.run_id}`)
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '读取 run 失败')
    }
  }

  const deleteRunRecord = async (runId: string) => {
    try {
      const response = await fetch(apiUrl(`/api/runs/${runId}`), { method: 'DELETE' })
      if (!response.ok) throw new Error(`删除记录失败：${response.status}`)
      setRecentRuns((current) => current.filter((item) => item.run_id !== runId))
      if (run?.run_id === runId) {
        setRun(null)
        deps.setPreview(null)
        deps.setSlotDrafts({})
        setVideoUrl('')
        deps.setStatus('已删除当前记录')
      }
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '删除记录失败')
    }
  }

  const saveRunNote = async () => {
    if (!run) return
    try {
      const response = await fetch(apiUrl(`/api/runs/${run.run_id}/note`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: runNoteDraft }),
      })
      if (!response.ok) throw new Error(`保存备注失败：${response.status}`)
      const payload = (await response.json()) as any
      setRun(payload)
      setRecentRuns((current) =>
        current.map((item) => (item.run_id === payload.run_id ? { ...item, note: payload.note } : item)),
      )
      await fetchRecentRuns()
      deps.setStatus('run 备注已保存')
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '保存备注失败')
    }
  }

  const toggleRunPinned = async () => {
    if (!run) return
    try {
      const response = await fetch(apiUrl(`/api/runs/${run.run_id}/pin`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pinned: !run.pinned }),
      })
      if (!response.ok) throw new Error(`置顶记录失败：${response.status}`)
      const payload = (await response.json()) as any
      setRun(payload)
      await fetchRecentRuns()
      deps.setStatus(payload.pinned ? 'run 已置顶' : 'run 已取消置顶')
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '置顶记录失败')
    }
  }

  const toggleRunPreferred = async (runId = run?.run_id, currentPreferred = run?.preferred || false) => {
    if (!runId) return
    try {
      const response = await fetch(apiUrl(`/api/runs/${runId}/preferred`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preferred: !currentPreferred }),
      })
      if (!response.ok) throw new Error(`设置首选失败：${response.status}`)
      const payload = (await response.json()) as any
      if (run?.run_id === payload.run_id) {
        setRun(payload)
      } else if (run?.batch_id === payload.batch_id && payload.preferred) {
        setRun({ ...run, preferred: false })
      }
      if (payload.batch_id) await fetchRunBatch(payload.batch_id)
      await fetchRecentRuns()
      deps.setStatus(payload.preferred ? '已设为首选版本' : '已取消首选版本')
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '设置首选失败')
    }
  }

  const saveRunAsTemplate = async () => {
    if (!run) return
    try {
      const response = await fetch(apiUrl(`/api/templates/from-run/${run.run_id}`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: templateNameDraft, tags: splitList(templateTagsDraft) }),
      })
      if (!response.ok) throw new Error(`保存模板失败：${response.status}`)
      const payload = (await response.json()) as any
      deps.setSelectedTemplateId(payload.template_id)
      setTemplateNameDraft(payload.template.title)
      setTemplateTagsDraft(payload.tags.join('，'))
      await fetchTemplates()
      deps.setStatus('已保存模板')
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '保存模板失败')
    }
  }

  const deleteTemplate = async (templateId: string) => {
    try {
      const response = await fetch(apiUrl(`/api/templates/${templateId}`), { method: 'DELETE' })
      if (!response.ok) throw new Error(`删除模板失败：${response.status}`)
      if (deps.selectedTemplateId === templateId) {
        deps.setSelectedTemplateId('')
      }
      if (runTemplateFilter === templateId) {
        setRunTemplateFilter('')
      }
      await fetchTemplates()
      await fetchRecentRuns()
      deps.setStatus('模板已删除')
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '删除模板失败')
    }
  }

  const saveTemplateEdits = async () => {
    if (!deps.selectedTemplateId || !templateEditorDraft || !selectedTemplateDetail) return
    try {
      const response = await fetch(apiUrl(`/api/templates/${deps.selectedTemplateId}`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: templateEditorDraft.title,
          rhythm_summary: templateEditorDraft.rhythm_summary,
          tags: splitList(templateEditorDraft.tags),
          slots: selectedTemplateDetail.template.script_pattern.map((slot: any) => ({
            slot_id: slot.id,
            duration: Number(templateEditorDraft.slots[slot.id]?.duration || slot.duration),
            required_asset: templateEditorDraft.slots[slot.id]?.required_asset || slot.required_asset,
          })),
        }),
      })
      if (!response.ok) throw new Error(`保存模板修改失败：${response.status}`)
      const record = (await response.json()) as any
      setSelectedTemplateDetail(record)
      setTemplateEditorDraft({
        title: record.template.title,
        rhythm_summary: record.template.rhythm_summary,
        tags: record.tags.join('，'),
        slots: Object.fromEntries(
          record.template.script_pattern.map((slot: any) => [
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
      deps.setStatus('模板修改已保存')
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '保存模板修改失败')
    }
  }

  const rollbackTemplateVersion = async (versionId: string) => {
    if (!deps.selectedTemplateId) return
    try {
      const response = await fetch(apiUrl(`/api/templates/${deps.selectedTemplateId}/rollback/${versionId}`), { method: 'POST' })
      if (!response.ok) throw new Error(`模板回退失败：${response.status}`)
      const record = (await response.json()) as any
      setSelectedTemplateDetail(record)
      setTemplateEditorDraft({
        title: record.template.title,
        rhythm_summary: record.template.rhythm_summary,
        tags: record.tags.join('，'),
        slots: Object.fromEntries(
          record.template.script_pattern.map((slot: any) => [
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
      deps.setStatus('模板已回退')
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '模板回退失败')
    }
  }

  const forkTemplate = async (templateId: string, title: string) => {
    try {
      const response = await fetch(apiUrl(`/api/templates/${templateId}/fork`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      })
      if (!response.ok) throw new Error(`复制模板失败：${response.status}`)
      const record = (await response.json()) as any
      await fetchTemplates()
      deps.setSelectedTemplateId(record.template_id)
      setTemplateNameDraft(record.template.title)
      setTemplateTagsDraft(record.tags.join('，'))
      deps.setStatus('模板已复制')
    } catch (caught) {
      deps.setError(caught instanceof Error ? caught.message : '复制模板失败')
    }
  }

  return {
    run,
    setRun,
    runBatch,
    setRunBatch,
    recentRuns,
    setRecentRuns,
    templates,
    setTemplates,
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
    runStatusFilter,
    setRunStatusFilter,
    runSearchKeyword,
    setRunSearchKeyword,
    runNoteDraft,
    setRunNoteDraft,
    videoUrl,
    setVideoUrl,
    selectedTemplate,
    loadRunRecord,
    deleteRunRecord,
    saveRunNote,
    toggleRunPinned,
    toggleRunPreferred,
    saveRunAsTemplate,
    deleteTemplate,
    saveTemplateEdits,
    rollbackTemplateVersion,
    forkTemplate,
    fetchRecentRuns,
    fetchRunBatch,
    fetchTemplates,
    fetchTemplateDetail,
    runDemo,
    runDemoVariants,
    applyDemoRunResponse,
    exportRunJson,
    downloadRunPackage,
  }
}
