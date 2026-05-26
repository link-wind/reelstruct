import React, { useEffect, useMemo, useState } from 'react'
import WorkflowNav, { Stage } from '../Workspace/WorkflowNav'
import AgentActionPanel, { ChatMessage } from '../Workspace/AgentActionPanel'
import WorkPanel from '../Workspace/WorkPanel'
import { mergeShotEvidenceGraphs, useReelStruct } from '../../hooks/useReelStruct'

function formatSeconds(secs: number) {
  const minutes = Math.floor(secs / 60)
  const seconds = Math.floor(secs % 60)
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
}

function formatUnitId(unit: { unit_id: string; shot_indices: number[]; start: number; end: number }) {
  if (unit.shot_indices.length) return `unit_${unit.shot_indices.join('_')}`
  return `${unit.unit_id}_${unit.start}_${unit.end}`.replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '')
}

function isBusyStatus(status: string) {
  return status.startsWith('正在')
}

function extractPromptSignals(prompt: string) {
  return prompt
    .split(/[，,。；;、\n]/)
    .map((item) => item.trim())
    .filter((item) => item.length >= 3)
    .slice(0, 4)
}

function deriveProductName(prompt: string) {
  const [firstSignal] = extractPromptSignals(prompt)
  const base = firstSignal || prompt.trim()
  return base.length > 24 ? `${base.slice(0, 24)}...` : base
}

function mediaUrl(path: string) {
  const apiOrigin = process.env.NEXT_PUBLIC_REELSTRUCT_API_ORIGIN || 'http://127.0.0.1:8010'
  if (!path) return ''
  if (/^https?:\/\//.test(path)) return path
  return `${apiOrigin}${path.startsWith('/') ? path : `/${path}`}`
}

const STAGE_COPY: Record<Stage, { title: string; description: string }> = {
  sample: {
    title: '样例输入',
    description: '上传参考视频后，使用真实接口生成结构节点和素材映射。',
  },
  structure: {
    title: '结构拆解结果',
    description: '这里展示真实生成的结构节点、节奏摘要和素材映射。',
  },
  output: {
    title: '输出检查',
    description: '生成完成后检查 demo 输出、素材映射和后续补充方向。',
  },
}

interface WorkspaceViewProps {
  taskText: string
  reelStruct: ReturnType<typeof useReelStruct>
}

export default function WorkspaceView({ taskText, reelStruct }: WorkspaceViewProps) {
  const [currentStage, setCurrentStage] = useState<Stage>('sample')
  const [activeNodeKey, setActiveNodeKey] = useState('')
  const [localVideoFile, setLocalVideoFile] = useState<File | null>(null)
  const [localVideoUrl, setLocalVideoUrl] = useState<string | undefined>()
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      role: 'user',
      label: '任务',
      body: taskText || '未填写任务，可先上传参考视频再补充目标。',
    },
    {
      id: '2',
      role: 'agent',
      label: 'ReelStruct',
      body: '工作台已准备好。上传参考视频后，我会使用真实接口生成结构拆解和素材映射。',
    },
  ])

  const {
    preview,
    sample,
    sampleUpload,
    status,
    error,
    uploadSample,
    uploadMaterialAsset,
    generateOcrEvidence,
    generateAsrEvidence,
    runDemo,
    videoUrl,
    run,
    transcriptUpload,
    analysisSummary,
    analysisSource,
    analysisConfidence,
    analysisWarnings,
    manualEvidenceGraph,
    selectedGaps,
    content,
    setContent,
  } = reelStruct
  const busy = isBusyStatus(status)

  useEffect(() => {
    const prompt = taskText.trim()
    if (!prompt) return

    setContent((current) => {
      if (current.topic === prompt) return current
      const promptSignals = extractPromptSignals(prompt)
      return {
        ...current,
        topic: prompt,
        product_name: deriveProductName(prompt),
        selling_points: promptSignals.length ? promptSignals : current.selling_points,
      }
    })
  }, [setContent, taskText])

  useEffect(() => {
    if (!localVideoFile) {
      setLocalVideoUrl(undefined)
      return
    }

    const objectUrl = URL.createObjectURL(localVideoFile)
    setLocalVideoUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [localVideoFile])

  const nodes = useMemo(() => {
    const keyframes = sampleUpload?.keyframes || []
    return (preview?.template.script_pattern || []).map((slot) => {
      const rawConfidence = typeof slot.confidence === 'number' ? slot.confidence : 0
      const confidence = rawConfidence <= 1 ? rawConfidence * 100 : rawConfidence
      const slotEnd = slot.start + slot.duration
      const explicitEvidenceShots = slot.evidence_shot_indices.length
        ? keyframes.filter((keyframe) => slot.evidence_shot_indices.includes(keyframe.shot_index))
        : []
      const timedEvidenceShots = keyframes.filter(
        (keyframe) => keyframe.keyframe_time >= slot.start && keyframe.keyframe_time <= slotEnd,
      )
      const slotMidpoint = slot.start + slot.duration / 2
      const nearestEvidenceShots = [...keyframes]
        .sort((left, right) => Math.abs(left.keyframe_time - slotMidpoint) - Math.abs(right.keyframe_time - slotMidpoint))
        .slice(0, 1)
      const evidenceShots = (explicitEvidenceShots.length
        ? explicitEvidenceShots
        : timedEvidenceShots.length
          ? timedEvidenceShots
          : nearestEvidenceShots
      )
        .slice(0, 3)
        .map((keyframe) => ({
          shotIndex: keyframe.shot_index,
          keyframeTime: keyframe.keyframe_time,
          publicUrl: keyframe.public_url,
        }))

      return {
        key: slot.id,
        time: `${formatSeconds(slot.start)} - ${formatSeconds(slot.start + slot.duration)}`,
        label: slot.label,
        desc: slot.purpose || slot.intent || slot.role || '这个节点暂无说明。',
        score: `置信度 ${Math.round(confidence)}%`,
        sampleEvidence: slot.sample_evidence,
        evidenceShotIndices: slot.evidence_shot_indices,
        evidenceShots,
      }
    })
  }, [preview, sampleUpload?.keyframes])

  useEffect(() => {
    if (!nodes.length) {
      setActiveNodeKey('')
      return
    }

    setActiveNodeKey((current) => (nodes.some((node) => node.key === current) ? current : nodes[0].key))
  }, [nodes])

  const mappingItems = useMemo(() => {
    return (preview?.transfer_plan.mappings || []).map((mapping) => ({
      key: mapping.slot_id,
      label: mapping.asset_requirement || mapping.target_message,
      score: mapping.asset_strategy || '已生成映射',
      percent: 100,
    }))
  }, [preview])

  const slotLabelLookup = useMemo(() => {
    return new Map((preview?.template.script_pattern || []).map((slot) => [slot.id, slot.label]))
  }, [preview])

  const gapItems = useMemo(() => {
    const uploadedLookup = new Map(content.uploaded_assets.map((asset) => [asset.slot_id, asset.filename]))
    return selectedGaps.map((gap) => ({
      slotId: gap.slot_id,
      label: slotLabelLookup.get(gap.slot_id) || gap.slot_id,
      missingAsset: gap.missing_asset,
      impact: gap.impact,
      fillStrategy: gap.fill_strategy,
      suggestedAssetType: gap.suggested_asset_type,
      suggestedShots: gap.suggested_shots,
      pickupChecklist: gap.pickup_checklist,
      uploadedFilename: uploadedLookup.get(gap.slot_id),
    }))
  }, [content.uploaded_assets, selectedGaps, slotLabelLookup])

  const transferExplanations = useMemo(() => {
    if (!preview) return []
    const mappingLookup = new Map(preview.transfer_plan.mappings.map((mapping) => [mapping.slot_id, mapping]))
    return preview.template.script_pattern.map((slot) => {
      const mapping = mappingLookup.get(slot.id)
      const explanation = mapping?.explanation
      return {
        slotId: slot.id,
        label: slot.label,
        sampleEvidence: slot.sample_evidence,
        sourceMethod: explanation?.source_observation || mapping?.source_method || slot.method,
        transferableRule: explanation?.transferable_principle || slot.transferable_rule,
        targetMessage: mapping?.target_message || '',
        targetAdaptation: explanation?.target_expression || mapping?.target_adaptation || '',
        reasoning: explanation?.reasoning || mapping?.reasoning || '',
        assetRequirement: mapping?.asset_requirement || slot.required_asset,
        assetStrategy: explanation?.asset_plan || mapping?.asset_strategy || '',
        packagingPlan: mapping?.packaging_plan || slot.packaging_intent,
        fallbackStrategy: explanation?.gap_handling || mapping?.fallback_strategy || '',
        confidence: explanation?.confidence || 0,
        warnings: explanation?.warnings || [],
      }
    })
  }, [preview])

  const analysisView = useMemo(() => {
    if (!analysisSummary) return null
    return {
      source: analysisSource,
      confidence: analysisConfidence,
      headline: analysisSummary.headline,
      metrics: analysisSummary.metrics,
      narrativeBeats: analysisSummary.narrative_beats,
      packagingSignals: analysisSummary.packaging_signals,
      warnings: analysisWarnings,
    }
  }, [analysisConfidence, analysisSource, analysisSummary, analysisWarnings])

  const mergedShotEvidenceGraph = useMemo(() => {
    const baseGraph = run?.preview.shot_evidence_graph || preview?.shot_evidence_graph || null
    return manualEvidenceGraph ? mergeShotEvidenceGraphs(baseGraph, manualEvidenceGraph) : baseGraph
  }, [manualEvidenceGraph, preview?.shot_evidence_graph, run?.preview.shot_evidence_graph])

  const shotEvidence = useMemo(() => {
    const graph = mergedShotEvidenceGraph
    if (graph?.shots?.length) {
      const graphShotLookup = new Map(graph.shots.map((node) => [node.shot.index, node]))
      const signalShots = sampleUpload?.video_signal?.shots || []
      const displayShots = signalShots.length ? signalShots : graph.shots.map((node) => node.shot)
      return displayShots.map((shot) => {
        const node = graphShotLookup.get(shot.index)
        return {
          shotIndex: shot.index,
          time: `${formatSeconds(shot.start)} - ${formatSeconds(shot.end)}`,
          frames: (node?.frames || []).map((frame) => ({
            role: frame.role,
            time: frame.time,
            publicUrl: mediaUrl(frame.public_url),
          })),
          ocrTexts: (node?.ocr_texts || []).map((item) => ({
            text: item.text,
            frameIndex: item.frame_index,
            frameTime: item.frame_time,
            position: item.position,
            confidence: item.confidence,
          })),
          transcriptTexts: (node?.transcript_texts || []).map((item) => ({
            text: item.text,
            sourceStart: item.source_start,
            sourceEnd: item.source_end,
            overlapRatio: item.overlap_ratio,
          })),
          visualSummary: node?.understanding?.visual_summary || '',
          textSummary: node?.understanding?.text_summary || '',
          functionHint: node?.understanding?.creative_function_hint || '',
          confidence: node?.understanding?.confidence || 0,
          warnings: node?.understanding?.warnings || [],
        }
      })
    }

    const signal = sampleUpload?.video_signal
    const keyframeLookup = new Map((sampleUpload?.keyframes || []).map((keyframe) => [keyframe.shot_index, keyframe]))
    return (signal?.shots || []).map((shot) => {
      const keyframe = keyframeLookup.get(shot.index)
      return {
        shotIndex: shot.index,
        time: `${formatSeconds(shot.start)} - ${formatSeconds(shot.end)}`,
        frames: keyframe
          ? [
              {
                role: 'middle',
                time: keyframe.keyframe_time,
                publicUrl: mediaUrl(keyframe.public_url),
              },
            ]
          : [],
        visualSummary: '',
        ocrTexts: [],
        transcriptTexts: [],
        textSummary: '',
        functionHint: '',
        confidence: 0,
        warnings: [],
      }
    })
  }, [
    mergedShotEvidenceGraph,
    sampleUpload?.keyframes,
    sampleUpload?.video_signal,
  ])

  const analysisUnits = useMemo(() => {
    const graph = mergedShotEvidenceGraph
    if (!graph?.analysis_units?.length) return []
    const shotLookup = new Map(shotEvidence.map((shot) => [shot.shotIndex, shot]))
    return graph.analysis_units.map((unit) => ({
      unitId: formatUnitId(unit),
      time: `${formatSeconds(unit.start)} - ${formatSeconds(unit.end)}`,
      duration: unit.duration,
      shotIndices: unit.shot_indices,
      representativeFrames: (unit.representative_frames || []).map((frame) => ({
        role: frame.role,
        time: frame.time,
        publicUrl: mediaUrl(frame.public_url),
        shotIndex: frame.shot_index,
      })),
      ocrTexts: (unit.ocr_texts || []).map((item) => ({
        text: item.text,
        frameIndex: item.frame_index,
        frameTime: item.frame_time,
        position: item.position,
        confidence: item.confidence,
      })),
      transcriptTexts: (unit.transcript_texts || []).map((item) => ({
        text: item.text,
        sourceStart: item.source_start,
        sourceEnd: item.source_end,
        overlapRatio: item.overlap_ratio,
      })),
      visualSummary: unit.understanding?.visual_summary || '',
      textSummary: unit.understanding?.text_summary || '',
      functionHint: unit.understanding?.creative_function_hint || '',
      confidence: unit.understanding?.confidence || 0,
      warnings: unit.understanding?.warnings || [],
      shots: unit.shot_indices
        .map((shotIndex) => shotLookup.get(shotIndex))
        .filter((shot): shot is NonNullable<typeof shot> => Boolean(shot)),
    }))
  }, [mergedShotEvidenceGraph, shotEvidence])

  const shotEvidenceWarnings = useMemo(() => {
    return mergedShotEvidenceGraph?.warnings || []
  }, [mergedShotEvidenceGraph])

  const shotRelations = useMemo(() => {
    const graph = mergedShotEvidenceGraph
    return (graph?.relations || []).map((relation) => ({
      fromShot: relation.from_shot,
      toShot: relation.to_shot,
      relationType: relation.relation_type,
      summary: relation.relation_summary,
      semanticShift: relation.semantic_shift,
      confidence: relation.confidence,
    }))
  }, [mergedShotEvidenceGraph])

  const progressItems = useMemo(() => {
    return [
      {
        label: '样例视频',
        v1: sampleUpload ? '已上传' : '未上传',
        v2: '',
        percent: sampleUpload ? 100 : 0,
      },
      {
        label: '结构拆解',
        v1: preview ? String(nodes.length) : '未生成',
        v2: preview ? '节点' : '',
        percent: preview ? 100 : 0,
      },
      {
        label: '当前状态',
        v1: status,
        v2: '',
        percent: busy ? 60 : status === '等待生成' ? 0 : 100,
      },
    ]
  }, [busy, nodes.length, preview, sampleUpload, status])

  const resultView = useMemo(() => {
    if (!run || !videoUrl) return null
    return {
      runId: run.run_id,
      batchId: run.batch_id,
      videoUrl,
      assets: run.prepared_assets.map((asset) => ({
        sceneId: asset.scene_id,
        sourceType: asset.source_type,
        sourceLabel: asset.source_label,
        caption: asset.caption,
        duration: asset.duration,
      })),
      trace: run.trace,
    }
  }, [run, videoUrl])

  const targetBrief = useMemo(() => {
    return {
      topic: content.topic,
      productName: content.product_name,
      sellingPoints: content.selling_points,
      availableAssets: content.available_assets,
    }
  }, [content.available_assets, content.product_name, content.selling_points, content.topic])

  const sampleAnalysis = useMemo(() => {
    const signal = sampleUpload?.video_signal
    return {
      hasUpload: Boolean(sampleUpload),
      title: sample.title,
      duration: sample.duration,
      shotCount: sample.shot_count,
      transcriptSummary: sample.transcript_summary,
      filename: sampleUpload?.filename || '',
      resolution: signal ? `${signal.metadata.width}x${signal.metadata.height}` : '',
      fps: signal?.metadata.fps,
      formatName: signal?.metadata.format_name || '',
      detectionMethod: signal?.detection_method || '',
      avgShotDuration: signal?.rhythm_metrics.avg_shot_duration,
      cutDensity: signal?.rhythm_metrics.cut_density,
      fastestWindow: signal?.rhythm_metrics.fastest_window || '',
      slowestWindow: signal?.rhythm_metrics.slowest_window || '',
      transcriptFilename: transcriptUpload?.filename || '',
      keyframes: (sampleUpload?.keyframes || []).slice(0, 6).map((keyframe) => ({
        shotIndex: keyframe.shot_index,
        keyframeTime: keyframe.keyframe_time,
        publicUrl: keyframe.public_url,
      })),
    }
  }, [sample.duration, sample.shot_count, sample.title, sample.transcript_summary, sampleUpload, transcriptUpload?.filename])

  const handleSendMessage = (text: string) => {
    const messageId = Date.now().toString()
    setContent((current) => ({
      ...current,
      selling_points: [...current.selling_points.filter((item) => item !== text), text].slice(-5),
    }))
    setMessages((current) => [
      ...current,
      { id: messageId, role: 'user', label: '补充要求', body: text },
      {
        id: `${messageId}-local`,
        role: 'agent',
        label: 'ReelStruct',
        body: '我已记录这条补充要求。第一阶段不会自动重跑后端，请点击生成按钮重新执行。',
      },
    ])
  }

  const handleUploadVideo = (file: File) => {
    setCurrentStage('sample')
    setLocalVideoFile(file)
    void uploadSample(file)
  }

  const handleGenerate = () => {
    setCurrentStage('structure')
    void runDemo()
  }

  const stageCopy = STAGE_COPY[currentStage]
  const stageDescription = preview?.template.rhythm_summary || stageCopy.description
  const displayVideoUrl = currentStage === 'output' && videoUrl ? videoUrl : sampleUpload?.public_url || localVideoUrl
  const displayVideoName =
    currentStage === 'output' && run?.run_id
      ? `${run.run_id}.mp4`
      : localVideoFile?.name || sampleUpload?.filename || '尚未上传参考视频'
  const stageStates = {
    sample: { enabled: true, completed: Boolean(sampleUpload) },
    structure: { enabled: Boolean(sampleUpload || preview), completed: Boolean(preview) },
    output: { enabled: Boolean(videoUrl), completed: Boolean(videoUrl) },
  }

  return (
    <section className="view workspace" id="workspaceView" data-active="true">
      <div className="workspace-frame">
        <WorkflowNav currentStage={currentStage} onStageChange={setCurrentStage} stageStates={stageStates} />

        <div className="workspace-shell">
          <AgentActionPanel
            messages={messages}
            onSendMessage={handleSendMessage}
            status={status}
            error={error}
            isBusy={busy}
          />

          <WorkPanel
            stageTitle={preview ? stageCopy.title : '样例输入'}
            stageDescription={stageDescription}
            workClock={status}
            hasVideo={Boolean(displayVideoUrl)}
            videoUrl={displayVideoUrl}
            videoName={displayVideoName}
            videoDuration={formatSeconds(sample.duration)}
            sampleMeta={{
              shotCount: sampleUpload?.sample.shot_count,
              targetAssetCount: mappingItems.length || undefined,
            }}
            nodes={nodes}
            activeNodeKey={activeNodeKey}
            onNodeClick={setActiveNodeKey}
            onUploadVideo={handleUploadVideo}
            onUploadMaterialAsset={(slotId, file) => void uploadMaterialAsset(slotId, file)}
            onGenerate={handleGenerate}
            onGenerateOcrEvidence={() => void generateOcrEvidence()}
            onGenerateAsrEvidence={() => void generateAsrEvidence()}
            canGenerate={Boolean(sampleUpload) && !busy}
            canGenerateEvidence={Boolean(sampleUpload) && !busy}
            isBusy={busy}
            status={status}
            error={error}
            sampleAnalysis={sampleAnalysis}
            targetBrief={targetBrief}
            analysis={analysisView}
            analysisUnits={analysisUnits}
            shotEvidence={shotEvidence}
            shotEvidenceWarnings={shotEvidenceWarnings}
            shotRelations={shotRelations}
            transferExplanations={transferExplanations}
            materialGaps={gapItems}
            result={resultView}
            progressItems={progressItems}
            mappingItems={mappingItems}
          />
        </div>
      </div>
    </section>
  )
}
