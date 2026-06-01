import React, { useEffect, useMemo, useRef, useState } from 'react'
import WorkflowNav, { Stage } from '../Workspace/WorkflowNav'
import AgentConversationPanel, {
  type AgentConversationMessage,
} from '../Workspace/AgentConversationPanel'
import WorkPanel from '../Workspace/WorkPanel'
import { localizeLabel, localizeText } from '../Workspace/localize'
import type { ConfirmationOption } from '../../agent/types'
import type { AgentWorkspaceController } from '../../hooks/useAgentWorkspace'
import { shouldAutoPlanAfterSampleUpload } from '../../hooks/agentWorkspaceGate.mjs'
import { mergeShotEvidenceGraphs, useReelStruct } from '../../hooks/useReelStruct'
import { runPlannedWorkspaceFlow } from '../../hooks/workspaceExecutionFlow.mjs'
import { requestAgentToolExecution } from '../../hooks/useReelStructApi'
import {
  buildAnalysisView,
  buildAnalysisUnits,
  buildConversationMessages,
  buildEvaluationSummaryView,
  buildExecutionStagesView,
  buildGapItems,
  buildMappingItems,
  buildMaterialAssets,
  buildProgressItems,
  buildResultView,
  buildSampleAnalysis,
  buildShotEvidenceDisplay,
  buildShotEvidenceWarnings,
  buildShotRelations,
  buildSlotLabelLookup,
  buildStructureNodes,
  buildTargetBrief,
  buildTransferExplanations,
  deriveProductName,
  extractPromptSignals,
  formatSeconds,
  buildWorkspaceStageView,
} from './workspaceViewModels.mjs'

function isBusyStatus(status: string) {
  return status.startsWith('正在')
}

const AGENT_STATUS_COPY = {
  idle: '待命',
  planning: '正在规划',
  awaiting_start_confirm: '等待开始确认',
  running: '执行中',
  awaiting_tool_confirm: '等待工具确认',
  paused: '已暂停',
  completed: '已完成',
  failed: '执行失败',
} as const

interface WorkspaceViewProps {
  taskText: string
  reelStruct: ReturnType<typeof useReelStruct>
  agentWorkspace: AgentWorkspaceController
}

export default function WorkspaceView({
  taskText,
  reelStruct,
  agentWorkspace,
}: WorkspaceViewProps) {
  const [currentStage, setCurrentStage] = useState<Stage>('sample')
  const [activeNodeKey, setActiveNodeKey] = useState('')
  const [localVideoFile, setLocalVideoFile] = useState<File | null>(null)
  const [localVideoUrl, setLocalVideoUrl] = useState<string | undefined>()
  const latestTaskTextRef = React.useRef(taskText)
  const autoPlanPromptRef = useRef('')

  const {
    preview,
    sample,
    sampleUpload,
    status,
    error,
    uploadSample,
    uploadMaterialAsset,
    generateMaterialEvidence,
    generateOcrEvidence,
    generateAsrEvidence,
    generateStructurePreview,
    applyPreviewResponse,
    applyDemoRunResponse,
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
    outputVariant,
    supplementSelection,
    selectSupplementOption,
  } = reelStruct
  const busy = isBusyStatus(status)
  const agentStatusLabel = AGENT_STATUS_COPY[agentWorkspace.state.agentStatus] || status
  const panelError = agentWorkspace.state.errors[0] || error

  useEffect(() => {
    latestTaskTextRef.current = taskText
  }, [taskText])

  useEffect(() => {
    if (!sampleUpload) {
      autoPlanPromptRef.current = ''
      return
    }

    const prompt = taskText.trim()
    if (
      shouldAutoPlanAfterSampleUpload({
        hasSampleUpload: Boolean(sampleUpload),
        prompt,
        agentStatus: agentWorkspace.state.agentStatus,
        hasPlan: agentWorkspace.state.currentPlan.steps.length > 0,
      }) &&
      autoPlanPromptRef.current !== prompt
    ) {
      autoPlanPromptRef.current = prompt
      void agentWorkspace.submitPrompt(prompt)
    }
  }, [
    agentWorkspace.state.agentStatus,
    agentWorkspace.state.currentPlan.steps.length,
    agentWorkspace.submitPrompt,
    sampleUpload,
    taskText,
  ])

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
    return buildStructureNodes(preview, sampleUpload?.keyframes || [])
  }, [preview, sampleUpload?.keyframes])

  useEffect(() => {
    if (!nodes.length) {
      setActiveNodeKey('')
      return
    }

    setActiveNodeKey((current) => (nodes.some((node: { key: string }) => node.key === current) ? current : nodes[0].key))
  }, [nodes])

  const mappingItems = useMemo(() => {
    return buildMappingItems(preview)
  }, [preview])

  const slotLabelLookup = useMemo(() => {
    return buildSlotLabelLookup(preview)
  }, [preview])

  const gapItems = useMemo(() => {
    return buildGapItems({
      uploadedAssets: content.uploaded_assets,
      selectedGaps,
      slotLabelLookup,
      supplementSelection,
    })
  }, [content.uploaded_assets, selectedGaps, slotLabelLookup, supplementSelection])

  const materialAssets = useMemo(() => {
    return buildMaterialAssets(content.uploaded_assets)
  }, [content.uploaded_assets])

  const transferExplanations = useMemo(() => {
    return buildTransferExplanations(preview)
  }, [preview])

  const analysisView = useMemo(() => {
    return buildAnalysisView({
      analysisSummary,
      analysisSource,
      analysisConfidence,
      analysisWarnings,
      rhythmSummary: preview?.template.rhythm_summary || '',
    })
  }, [analysisConfidence, analysisSource, analysisSummary, analysisWarnings, preview?.template.rhythm_summary])

  const evaluationSummaryView = useMemo(() => {
    return buildEvaluationSummaryView(preview, run)
  }, [preview?.evaluation_summary, run?.evaluation_summary])

  const mergedShotEvidenceGraph = useMemo(() => {
    const baseGraph = run?.preview.shot_evidence_graph || preview?.shot_evidence_graph || null
    return manualEvidenceGraph ? mergeShotEvidenceGraphs(baseGraph, manualEvidenceGraph) : baseGraph
  }, [manualEvidenceGraph, preview?.shot_evidence_graph, run?.preview.shot_evidence_graph])

  const shotEvidence = useMemo(() => {
    return buildShotEvidenceDisplay({ mergedShotEvidenceGraph, sampleUpload })
  }, [mergedShotEvidenceGraph, sampleUpload])

  const analysisUnits = useMemo(() => {
    return buildAnalysisUnits({
      mergedShotEvidenceGraph,
      shotEvidence,
      resolveMediaUrl: (path) => {
        const apiOrigin = process.env.NEXT_PUBLIC_REELSTRUCT_API_ORIGIN || 'http://127.0.0.1:8010'
        if (!path) return ''
        if (/^https?:\/\//.test(path)) return path
        return `${apiOrigin}${path.startsWith('/') ? path : `/${path}`}`
      },
    })
  }, [mergedShotEvidenceGraph, shotEvidence])

  const shotEvidenceWarnings = useMemo(() => {
    return buildShotEvidenceWarnings(mergedShotEvidenceGraph)
  }, [mergedShotEvidenceGraph])

  const shotRelations = useMemo(() => {
    return buildShotRelations(mergedShotEvidenceGraph)
  }, [mergedShotEvidenceGraph])

  const progressItems = useMemo(() => {
    return buildProgressItems({
      sampleUpload,
      preview,
      nodes,
      status,
      busy,
    })
  }, [busy, nodes, preview, sampleUpload, status])

  const resultView = useMemo(() => {
    return buildResultView(run, videoUrl)
  }, [run, videoUrl])

  const targetBrief = useMemo(() => {
    return buildTargetBrief(content)
  }, [content])

  const sampleAnalysis = useMemo(() => {
    return buildSampleAnalysis(sample, sampleUpload, transcriptUpload)
  }, [sample, sampleUpload, transcriptUpload])

  const conversationMessages = useMemo<AgentConversationMessage[]>(() => {
    return buildConversationMessages({
      steps: agentWorkspace.state.currentPlan.steps,
      pendingConfirmation: agentWorkspace.state.pendingConfirmation,
      errors: agentWorkspace.state.errors,
      messages: agentWorkspace.state.messages,
      taskText,
      sampleUpload,
    })
  }, [
    agentWorkspace.state.currentPlan.steps,
    agentWorkspace.state.errors,
    agentWorkspace.state.messages,
    agentWorkspace.state.pendingConfirmation,
    taskText,
    sampleUpload,
  ])

  const executionStages = useMemo(() => {
    return buildExecutionStagesView({
      steps: agentWorkspace.state.currentPlan.steps,
      toolRuns: agentWorkspace.state.toolRuns,
      currentStep: agentWorkspace.state.currentStep,
      agentStatus: agentWorkspace.state.agentStatus,
      busyStatus: status,
      pendingConfirmationTitle: agentWorkspace.state.pendingConfirmation?.title,
      hasStructurePreview: Boolean(preview),
      hasMaterialAnalysis: Boolean(evaluationSummaryView || gapItems.length || materialAssets.length),
      hasResultVideo: Boolean(resultView?.videoUrl),
    })
  }, [
    agentWorkspace.state.agentStatus,
    agentWorkspace.state.currentPlan.steps,
    agentWorkspace.state.currentStep,
    agentWorkspace.state.pendingConfirmation?.title,
    agentWorkspace.state.toolRuns,
    evaluationSummaryView,
    gapItems.length,
    materialAssets.length,
    preview,
    resultView?.videoUrl,
    status,
  ])

  const handleAgentMessage = (text: string) => {
    const messageId = Date.now().toString()
    const normalizedText = text.trim()
    if (!normalizedText) return

    setContent((current) => ({
      ...current,
      selling_points: [...current.selling_points.filter((item) => item !== normalizedText), normalizedText].slice(-5),
    }))

    agentWorkspace.addMessage({
      id: `user-${messageId}`,
      role: 'user',
      content: normalizedText,
      createdAt: new Date().toISOString(),
    })
    agentWorkspace.addMessage({
      id: `assistant-${messageId}`,
      role: 'assistant',
      content: '已收到，我会据此刷新执行计划。',
      createdAt: new Date().toISOString(),
    })

    const basePrompt = agentWorkspace.state.currentPlan.prompt || latestTaskTextRef.current
    const nextPrompt = [basePrompt, `补充要求：${normalizedText}`].filter(Boolean).join('\n')
    void agentWorkspace.submitPrompt(nextPrompt)
  }

  const handleConfirmationSelect = (option: ConfirmationOption) => {
    const pendingConfirmation = agentWorkspace.stateRef.current.pendingConfirmation
    const suffix = pendingConfirmation ? `（${pendingConfirmation.title}）` : ''
    agentWorkspace.addMessage({
      id: `confirm-${Date.now()}`,
      role: 'assistant',
      content: `已记录：${option.label}${suffix}`,
      createdAt: new Date().toISOString(),
    })
    agentWorkspace.clearConfirmation()

    if (option.action === 'pause') {
      return
    }

    if (option.action !== 'continue') {
      return
    }
    const executePlannedFlow = async () => {
      try {
        const stepNames = agentWorkspace.stateRef.current.currentPlan.steps.map((step) => step.tool_name)
        console.log('[agent-flow] start', { stepNames })
        await runPlannedWorkspaceFlow({
          stepNames,
          preview,
          sample,
          content,
          sampleUpload,
          manualEvidenceGraph,
          outputVariant,
          setCurrentStage,
          addMessage: agentWorkspace.addMessage,
          patchRuntime: agentWorkspace.patchRuntime,
          generateStructurePreview,
          generateOcrEvidence,
          generateAsrEvidence,
          requestAgentToolExecution,
          applyPreviewResponse,
          applyDemoRunResponse,
          runDemo,
        })
        console.log('[agent-flow] end')
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : '执行失败'
        console.error('[agent-flow] failed', caught)
        void message
      }
    }

    void executePlannedFlow()
  }

  const handleUploadVideo = (file: File) => {
    setCurrentStage('sample')
    setLocalVideoFile(file)
    void uploadSample(file)
  }

  const handleGenerate = () => {
    const pendingConfirmation = agentWorkspace.stateRef.current.pendingConfirmation
    if (pendingConfirmation?.kind === 'start_run') {
      const continueOption =
        pendingConfirmation.options.find((option) => option.action === 'continue') || null
      if (continueOption) {
        handleConfirmationSelect(continueOption)
        return
      }
    }

    if (!preview) {
      setCurrentStage('structure')
      void generateStructurePreview()
      return
    }
    setCurrentStage('output')
    void runDemo({ useDraftOverrides: true })
  }

  const { stageTitle, stageDescription, displayVideoUrl, displayVideoName, stageStates } = buildWorkspaceStageView({
    currentStage,
    preview,
    sampleUpload,
    run,
    videoUrl,
    localVideoUrl,
    localVideoFileName: localVideoFile?.name,
  })

  return (
    <section className="view workspace" id="workspaceView" data-active="true">
      <div className="workspace-frame">
        <WorkflowNav currentStage={currentStage} onStageChange={setCurrentStage} stageStates={stageStates} />

        <div className="workspace-shell">
          <AgentConversationPanel
            messages={conversationMessages}
            executionStages={executionStages}
            pendingConfirmation={agentWorkspace.state.pendingConfirmation}
            statusLabel={agentStatusLabel}
            error={panelError}
            onConfirm={handleConfirmationSelect}
            onSendMessage={handleAgentMessage}
          />

          <WorkPanel
            stageTitle={stageTitle}
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
            onGenerateMaterialEvidence={(slotId) => void generateMaterialEvidence(slotId)}
            onSelectSupplementOption={selectSupplementOption}
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
              evaluationSummary={evaluationSummaryView}
              analysisUnits={analysisUnits}
            shotEvidence={shotEvidence}
            shotEvidenceWarnings={shotEvidenceWarnings}
            shotRelations={shotRelations}
            transferExplanations={transferExplanations}
            materialGaps={gapItems}
            materialAssets={materialAssets}
            result={resultView}
            progressItems={progressItems}
            mappingItems={mappingItems}
          />
        </div>
      </div>
    </section>
  )
}
