'use client'

import { useEffect, useMemo, useRef } from 'react'
import { requestAgentToolExecution } from './useReelStructApi'
import {
  buildMappingOverrides,
  buildMaterialRequestSheetPayload,
  buildSlotDrafts,
  buildSupplementSelectionPayload,
  requestJson,
  type MaterialTaskStatus,
  type OutputVariant,
} from './reelStructWorkspaceShared'

type StructureWorkspaceDeps = {
  preview: any | null
  setPreview: (value: any | null) => void
  slotDrafts: Record<string, any>
  setSlotDrafts: (value: Record<string, any>) => void
  outputVariant: OutputVariant
  setOutputVariant: (value: OutputVariant) => void
  variantSummaries: any[]
  setVariantSummaries: (value: any[]) => void
  sample: any
  content: any
  sampleUpload: any
  manualEvidenceGraph: any
  requestSheetIds: string[]
  requestSheetStatus: Record<string, MaterialTaskStatus>
  supplementSelection: Record<string, string>
  selectedTemplateId: string
  setStatus: (value: string) => void
  setError: (value: string) => void
  setRun: (value: any) => void
  setRunBatch: (value: any) => void
  setVideoUrl: (value: string) => void
}

export function useStructureWorkspace(deps: StructureWorkspaceDeps) {
  const previewRef = useRef(deps.preview)
  const slotDraftsRef = useRef(deps.slotDrafts)

  useEffect(() => {
    previewRef.current = deps.preview
  }, [deps.preview])

  useEffect(() => {
    slotDraftsRef.current = deps.slotDrafts
  }, [deps.slotDrafts])

  const gapLookup = useMemo(() => {
    return new Map((deps.preview?.transfer_plan?.gaps || []).map((gap: any) => [gap.slot_id, gap]))
  }, [deps.preview])

  const mappingLookup = useMemo(() => {
    return new Map((deps.preview?.transfer_plan?.mappings || []).map((mapping: any) => [mapping.slot_id, mapping]))
  }, [deps.preview])

  const analysisSummary = deps.preview?.template?.analysis_summary
  const analysisSource = analysisSummary?.source || 'rule'
  const analysisConfidence = analysisSummary?.confidence || 0
  const analysisWarnings = analysisSummary?.warnings || []

  const generateStructurePreview = async (options?: { useDraftOverrides?: boolean }) => {
    deps.setError('')
    deps.setStatus('正在生成结构预览')
    deps.setRun(null)
    deps.setRunBatch(null)
    deps.setVideoUrl('')

    try {
      const mapping_overrides =
        options?.useDraftOverrides && previewRef.current ? buildMappingOverrides(previewRef.current, slotDraftsRef.current) : []
      const previewResponse = (
        await requestAgentToolExecution<{ preview: any }>({
          tool_name: 'analyze_structure',
          payload: {
            sample: deps.sample,
            content: deps.content,
            sample_local_path: deps.sampleUpload?.local_path || '',
            use_ai_structure: true,
            use_ai_transfer_explanation: false,
            shot_evidence_graph: deps.manualEvidenceGraph || undefined,
            template_id: deps.selectedTemplateId,
            mapping_overrides,
            material_request_sheet: buildMaterialRequestSheetPayload(deps.requestSheetIds, deps.requestSheetStatus),
            supplement_selections: buildSupplementSelectionPayload(deps.supplementSelection),
            variant: deps.outputVariant,
          },
        })
      ).data.preview
      deps.setPreview(previewResponse)
      deps.setSlotDrafts(buildSlotDrafts(previewResponse))
      deps.setStatus('结构预览已生成')
      return previewResponse
    } catch (caught) {
      deps.setStatus('结构预览失败')
      deps.setError(caught instanceof Error ? caught.message : '结构预览失败')
      return null
    }
  }

  const compareOutputVariants = async () => {
    deps.setError('')
    deps.setStatus('正在生成版本对比')
    try {
      const result = await requestJson<{ variants?: any[] }>('/api/structure/variants', {
        method: 'POST',
        body: {
          sample: deps.sample,
          content: deps.content,
          sample_local_path: deps.sampleUpload?.local_path || '',
          use_ai_structure: true,
          use_ai_transfer_explanation: true,
          shot_evidence_graph: deps.manualEvidenceGraph || undefined,
          template_id: deps.selectedTemplateId,
          mapping_overrides: deps.preview ? buildMappingOverrides(deps.preview, deps.slotDrafts) : [],
          material_request_sheet: buildMaterialRequestSheetPayload(deps.requestSheetIds, deps.requestSheetStatus),
          supplement_selections: buildSupplementSelectionPayload(deps.supplementSelection),
        },
      })
      deps.setVariantSummaries(result.variants || [])
      deps.setStatus('版本对比已生成')
    } catch (caught) {
      deps.setStatus('版本对比失败')
      deps.setError(caught instanceof Error ? caught.message : '版本对比失败')
    }
  }

  const applyPreviewResponse = (previewResponse: any) => {
    deps.setPreview(previewResponse)
    deps.setSlotDrafts(buildSlotDrafts(previewResponse))
  }

  return {
    preview: deps.preview,
    setPreview: deps.setPreview,
    slotDrafts: deps.slotDrafts,
    setSlotDrafts: deps.setSlotDrafts,
    outputVariant: deps.outputVariant,
    setOutputVariant: deps.setOutputVariant,
    variantSummaries: deps.variantSummaries,
    setVariantSummaries: deps.setVariantSummaries,
    gapLookup,
    mappingLookup,
    analysisSummary,
    analysisSource,
    analysisConfidence,
    analysisWarnings,
    generateStructurePreview,
    compareOutputVariants,
    applyPreviewResponse,
    previewRef,
    slotDraftsRef,
  }
}
