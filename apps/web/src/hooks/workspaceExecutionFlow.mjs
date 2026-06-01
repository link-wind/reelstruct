function createAssistantMessage(content) {
  return {
    id: `assistant-note-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    role: 'assistant',
    content,
    createdAt: new Date().toISOString(),
  }
}

export async function runPlannedWorkspaceFlow(params) {
  const {
    stepNames,
    preview,
    sample,
    content,
    sampleUpload,
    manualEvidenceGraph,
    outputVariant,
    setCurrentStage,
    addMessage,
    patchRuntime,
    generateStructurePreview,
    generateOcrEvidence,
    generateAsrEvidence,
    requestAgentToolExecution,
    applyPreviewResponse,
    applyDemoRunResponse,
    runDemo,
  } = params

  let evidenceUpdated = false
  let latestPreview = preview

  const pushAgentNote = (contentText) => {
    addMessage(createAssistantMessage(contentText))
  }

  const markStep = (toolName, statusValue, summary) => {
    patchRuntime({
      agentStatus: statusValue === 'failed' ? 'failed' : statusValue === 'completed' && toolName === 'generate_result' ? 'completed' : 'running',
      currentStep: toolName,
      currentStepStatus: statusValue,
      pendingConfirmation: null,
      toolRun: {
        id: `tool-run-${toolName}`,
        tool_name: toolName,
        status: statusValue,
        summary,
      },
    })
  }

  patchRuntime({
    agentStatus: 'running',
    currentStep: stepNames[0] || '',
    currentStepStatus: 'running',
    pendingConfirmation: null,
  })

  try {
    if (stepNames.includes('analyze_structure')) {
      pushAgentNote('开始分析结构。')
      markStep('analyze_structure', 'running', '正在分析结构')
      setCurrentStage('structure')
      const previewResponse = await generateStructurePreview({ useDraftOverrides: true })
      if (previewResponse) latestPreview = previewResponse
      markStep('analyze_structure', 'completed', '结构预览已生成')
    }

    if (stepNames.includes('run_ocr')) {
      pushAgentNote('开始补充 OCR 证据。')
      markStep('run_ocr', 'running', '正在补充 OCR')
      const hasOcrTextEvidence = await generateOcrEvidence()
      markStep('run_ocr', 'completed', 'OCR 证据已更新')
      evidenceUpdated ||= hasOcrTextEvidence
    }

    if (stepNames.includes('run_asr')) {
      pushAgentNote('开始补充 ASR 证据。')
      markStep('run_asr', 'running', '正在补充 ASR')
      const hasAsrTextEvidence = await generateAsrEvidence()
      markStep('run_asr', 'completed', 'ASR 证据已更新')
      evidenceUpdated ||= hasAsrTextEvidence
    }

    if (evidenceUpdated) {
      pushAgentNote('已更新证据，重新生成结构预览。')
      markStep('preview_refresh', 'running', '正在刷新结构预览')
      setCurrentStage('structure')
      const previewResponse = await generateStructurePreview({ useDraftOverrides: true })
      if (previewResponse) latestPreview = previewResponse
      markStep('preview_refresh', 'completed', '结构预览已刷新')
      pushAgentNote('结构预览刷新完成。')
    }

    if (stepNames.includes('complete_materials')) {
      pushAgentNote('开始整理素材缺口与补全建议。')
      markStep('complete_materials', 'running', '正在补全素材')
      setCurrentStage('structure')
      const completeMaterialsResult = await requestAgentToolExecution({
        tool_name: 'complete_materials',
        payload: {
          sample,
          content,
          sample_local_path: sampleUpload?.local_path || '',
          use_ai_structure: true,
          use_ai_transfer_explanation: false,
          shot_evidence_graph: manualEvidenceGraph || undefined,
          variant: outputVariant,
        },
      })
      latestPreview = completeMaterialsResult.data.preview
      applyPreviewResponse(latestPreview)
      markStep('complete_materials', 'completed', '素材补全已完成')
      pushAgentNote('素材缺口与补全建议已整理完成。')
    }

    if (stepNames.includes('generate_result')) {
      pushAgentNote('开始生成结果。')
      markStep('generate_result', 'running', '正在生成结果')
      setCurrentStage('output')
      if (latestPreview) {
        const result = await requestAgentToolExecution({
          tool_name: 'generate_result',
          payload: {
            preview: latestPreview,
            variant: outputVariant,
          },
        })
        applyDemoRunResponse(result.data.run)
      } else {
        await runDemo({ useDraftOverrides: true })
      }
      markStep('generate_result', 'completed', '结果已生成')
      pushAgentNote('结果已生成，可以开始检查输出。')
    }

    patchRuntime({
      agentStatus: 'completed',
      currentStep: '',
      pendingConfirmation: null,
    })
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : '执行失败'
    patchRuntime({
      agentStatus: 'failed',
      currentStepStatus: 'failed',
      errors: [message],
    })
    pushAgentNote(`执行中断：${message}`)
    throw caught
  }
}
