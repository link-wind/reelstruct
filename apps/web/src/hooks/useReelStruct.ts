'use client'

import type React from 'react'
import { useState } from 'react'
import { mergeShotEvidenceGraphs, type MaterialTaskStatus, type OutputVariant } from './reelStructWorkspaceShared'
import type {
  DemoRunResponse,
  MaterialGap,
  NewContentInput,
  SampleUploadResponse,
  SampleVideoInput,
  ShotEvidenceGraph,
  StructurePreviewResponse,
  TranscriptUploadResponse,
} from './useReelStructApi'
import { useMaterialWorkspace } from './useMaterialWorkspace'
import { useResultWorkspace } from './useResultWorkspace'
import { useSampleWorkspace } from './useSampleWorkspace'
import { useStructureWorkspace } from './useStructureWorkspace'

export { mergeShotEvidenceGraphs }

export type ReelStructController = {
  preview: StructurePreviewResponse | null
  sample: SampleVideoInput
  sampleUpload: SampleUploadResponse | null
  selectedTemplateId: string
  setSelectedTemplateId: React.Dispatch<React.SetStateAction<string>>
  status: string
  setStatus: React.Dispatch<React.SetStateAction<string>>
  error: string
  setError: React.Dispatch<React.SetStateAction<string>>
  uploadSample: (file: File | null) => Promise<void>
  uploadMaterialAsset: (slotId: string, file: File | null) => Promise<void>
  generateMaterialEvidence: (slotId: string) => Promise<void>
  generateOcrEvidence: () => Promise<boolean>
  generateAsrEvidence: () => Promise<boolean>
  generateStructurePreview: (options?: { useDraftOverrides?: boolean }) => Promise<StructurePreviewResponse | null>
  applyPreviewResponse: (previewResponse: StructurePreviewResponse) => void
  applyDemoRunResponse: (runResponse: DemoRunResponse) => void
  runDemo: (options?: { useDraftOverrides?: boolean }) => Promise<void>
  videoUrl: string
  run: DemoRunResponse | null
  transcriptUpload: TranscriptUploadResponse | null
  analysisSummary: StructurePreviewResponse['template']['analysis_summary'] | undefined
  analysisSource: 'rule' | 'ai' | 'fallback'
  analysisConfidence: number
  analysisWarnings: string[]
  manualEvidenceGraph: ShotEvidenceGraph | null
  selectedGaps: MaterialGap[]
  content: NewContentInput
  setContent: React.Dispatch<React.SetStateAction<NewContentInput>>
  outputVariant: OutputVariant
  supplementSelection: Record<string, string>
  selectSupplementOption: (slotId: string, method: string) => void
}

export function useReelStruct(): ReelStructController {
  const [status, setStatus] = useState('等待生成')
  const [error, setError] = useState('')
  const [selectedTemplateId, setSelectedTemplateId] = useState('')

  const [preview, setPreview] = useState<any | null>(null)
  const [slotDrafts, setSlotDrafts] = useState<Record<string, any>>({})
  const [outputVariant, setOutputVariant] = useState<OutputVariant>('standard')
  const [variantSummaries, setVariantSummaries] = useState<any[]>([])

  const [selectedGapIds, setSelectedGapIds] = useState<string[]>([])
  const [requestSheetIds, setRequestSheetIds] = useState<string[]>([])
  const [requestSheetStatus, setRequestSheetStatus] = useState<Record<string, MaterialTaskStatus>>({})
  const [requestSheetFeedback, setRequestSheetFeedback] = useState('')
  const [supplementSelection, setSupplementSelection] = useState<Record<string, string>>({})

  const sampleWorkspace = useSampleWorkspace({
    setStatus,
    setError,
  })

  const resultWorkspace = useResultWorkspace({
    preview,
    setPreview,
    setSlotDrafts,
    sample: sampleWorkspace.sample,
    content: sampleWorkspace.content,
    sampleUpload: sampleWorkspace.sampleUpload,
    manualEvidenceGraph: sampleWorkspace.manualEvidenceGraph,
    selectedTemplateId,
    setSelectedTemplateId,
    outputVariant,
    setOutputVariant,
    requestSheetIds,
    requestSheetStatus,
    supplementSelection,
    setStatus,
    setError,
  })

  const structureWorkspace = useStructureWorkspace({
    preview,
    setPreview,
    slotDrafts,
    setSlotDrafts,
    outputVariant,
    setOutputVariant,
    variantSummaries,
    setVariantSummaries,
    sample: sampleWorkspace.sample,
    content: sampleWorkspace.content,
    sampleUpload: sampleWorkspace.sampleUpload,
    manualEvidenceGraph: sampleWorkspace.manualEvidenceGraph,
    requestSheetIds,
    requestSheetStatus,
    supplementSelection,
    selectedTemplateId,
    setStatus,
    setError,
    setRun: resultWorkspace.setRun,
    setRunBatch: resultWorkspace.setRunBatch,
    setVideoUrl: resultWorkspace.setVideoUrl,
  })

  const materialWorkspace = useMaterialWorkspace({
    preview,
    content: sampleWorkspace.content,
    setContent: sampleWorkspace.setContent,
    selectedGapIds,
    setSelectedGapIds,
    requestSheetIds,
    setRequestSheetIds,
    requestSheetStatus,
    setRequestSheetStatus,
    requestSheetFeedback,
    setRequestSheetFeedback,
    supplementSelection,
    setSupplementSelection,
    setStatus,
    setError,
  })

  return {
    ...sampleWorkspace,
    ...structureWorkspace,
    ...materialWorkspace,
    ...resultWorkspace,
    selectedTemplateId,
    setSelectedTemplateId,
    status,
    setStatus,
    error,
    setError,
  }
}
