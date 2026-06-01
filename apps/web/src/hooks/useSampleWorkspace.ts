'use client'

import { useEffect, useRef, useState } from 'react'
import { shotEvidenceGraphHasTextEvidence } from './evidenceGraph'
import { requestAgentToolExecution } from './useReelStructApi'
import { apiUrl, mergeShotEvidenceGraphs, normalizeSampleUpload } from './reelStructWorkspaceShared'

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
  uploaded_assets: any[]
}

type SampleUploadResponse = any
type TranscriptUploadResponse = any
type ShotEvidenceGraph = any

type SampleWorkspaceDeps = {
  setStatus: (value: string) => void
  setError: (value: string) => void
}

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

export function useSampleWorkspace(deps: SampleWorkspaceDeps) {
  const [sample, setSample] = useState<SampleVideoInput>(defaultSample)
  const [content, setContent] = useState<NewContentInput>(defaultContent)
  const [sampleUpload, setSampleUpload] = useState<SampleUploadResponse | null>(null)
  const [transcriptUpload, setTranscriptUpload] = useState<TranscriptUploadResponse | null>(null)
  const [manualEvidenceGraph, setManualEvidenceGraph] = useState<ShotEvidenceGraph | null>(null)

  const sampleRef = useRef(sample)
  const contentRef = useRef(content)
  const sampleUploadRef = useRef(sampleUpload)
  const manualEvidenceGraphRef = useRef(manualEvidenceGraph)

  useEffect(() => {
    sampleRef.current = sample
  }, [sample])

  useEffect(() => {
    contentRef.current = content
  }, [content])

  useEffect(() => {
    sampleUploadRef.current = sampleUpload
  }, [sampleUpload])

  useEffect(() => {
    manualEvidenceGraphRef.current = manualEvidenceGraph
  }, [manualEvidenceGraph])

  const uploadSample = async (file: File | null) => {
    if (!file) return

    deps.setError('')
    deps.setStatus('正在上传样例视频')
    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(apiUrl('/api/samples/upload'), {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        throw new Error(`上传失败：${response.status}`)
      }
      const upload = normalizeSampleUpload((await response.json()) as SampleUploadResponse)
      setSampleUpload(upload)
      setManualEvidenceGraph(null)
      setSample(upload.sample)
      deps.setStatus('样例已上传')
    } catch (caught) {
      deps.setStatus('上传失败')
      deps.setError(caught instanceof Error ? caught.message : '未知错误')
    }
  }

  const uploadTranscript = async (file: File | null) => {
    if (!file) return

    deps.setError('')
    deps.setStatus('正在上传转写文本')
    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(apiUrl('/api/samples/upload-transcript'), {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        throw new Error(`上传失败：${response.status}`)
      }
      const upload = (await response.json()) as TranscriptUploadResponse
      setTranscriptUpload(upload)
      setSample({
        ...sampleRef.current,
        transcript_summary: upload.transcript_summary,
      })
      deps.setStatus('转写摘要已更新')
    } catch (caught) {
      deps.setStatus('上传失败')
      deps.setError(caught instanceof Error ? caught.message : '未知错误')
    }
  }

  const generateTextEvidence = async (tool_name: 'run_ocr' | 'run_asr') => {
    const currentSampleUpload = sampleUploadRef.current
    if (!currentSampleUpload?.video_signal) {
      deps.setError('请先上传样例视频')
      return false
    }

    deps.setError('')
    const shots = currentSampleUpload.video_signal.shots || []
    if (!shots.length) {
      deps.setError('当前样例没有可识别的镜头')
      return false
    }

    deps.setStatus(`正在生成 ${tool_name === 'run_ocr' ? 'OCR' : 'ASR'} 证据 0/${shots.length}`)
    try {
      let hasTextEvidence = false
      for (const [shotPosition, shot] of shots.entries()) {
        deps.setStatus(`正在生成 ${tool_name === 'run_ocr' ? 'OCR' : 'ASR'} 证据 ${shotPosition + 1}/${shots.length}：镜头 ${shot.index}`)
        const result = await requestAgentToolExecution<{ shot_evidence_graph: ShotEvidenceGraph }>({
          tool_name,
          payload: {
            sample_id: currentSampleUpload.sample_id,
            sample_local_path: currentSampleUpload.local_path,
            video_signal: currentSampleUpload.video_signal,
            shot_indices: [shot.index],
          },
        })
        const graph = result.data.shot_evidence_graph
        hasTextEvidence ||= shotEvidenceGraphHasTextEvidence(graph)
        setManualEvidenceGraph((current: ShotEvidenceGraph | null) => mergeShotEvidenceGraphs(current, graph))
      }
      deps.setStatus(`${tool_name === 'run_ocr' ? 'OCR' : 'ASR'} 证据已生成 ${shots.length}/${shots.length}`)
      return hasTextEvidence
    } catch (caught) {
      deps.setStatus(`${tool_name === 'run_ocr' ? 'OCR' : 'ASR'} 证据生成失败`)
      deps.setError(caught instanceof Error ? caught.message : `${tool_name === 'run_ocr' ? 'OCR' : 'ASR'} 证据生成失败`)
      return false
    }
  }

  const generateOcrEvidence = () => generateTextEvidence('run_ocr')
  const generateAsrEvidence = () => generateTextEvidence('run_asr')

  return {
    sample,
    setSample,
    content,
    setContent,
    sampleUpload,
    setSampleUpload,
    transcriptUpload,
    setTranscriptUpload,
    manualEvidenceGraph,
    setManualEvidenceGraph,
    uploadSample,
    uploadTranscript,
    generateOcrEvidence,
    generateAsrEvidence,
  }
}
