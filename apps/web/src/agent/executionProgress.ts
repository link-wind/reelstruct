import type { AgentPlanStep, AgentStatus, ToolRunRecord } from './types'

export type AgentExecutionStageState = 'pending' | 'running' | 'completed' | 'failed'

export type AgentExecutionStage = {
  key: string
  label: string
  detail: string
  state: AgentExecutionStageState
}

const TOOL_STAGE_META: Record<
  string,
  {
    label: string
    running: string
    completed: string
  }
> = {
  analyze_structure: {
    label: '结构分析',
    running: '正在分析结构',
    completed: '结构预览已生成',
  },
  run_ocr: {
    label: 'OCR 证据',
    running: '正在补充 OCR',
    completed: 'OCR 证据已更新',
  },
  run_asr: {
    label: 'ASR 证据',
    running: '正在补充 ASR',
    completed: 'ASR 证据已更新',
  },
  preview_refresh: {
    label: '结构刷新',
    running: '正在刷新结构预览',
    completed: '结构预览已刷新',
  },
  complete_materials: {
    label: '素材补全',
    running: '正在补全素材',
    completed: '素材补全已完成',
  },
  generate_result: {
    label: '结果生成',
    running: '正在生成结果',
    completed: '结果已生成',
  },
}

function normalizeToolState(status: string): AgentExecutionStageState {
  if (status === 'failed') return 'failed'
  if (status === 'completed' || status === 'succeeded') return 'completed'
  if (status === 'running') return 'running'
  return 'pending'
}

function pickToolState(
  toolName: string,
  currentStep: string,
  toolRuns: ToolRunRecord[],
  busyStatus: string,
): AgentExecutionStageState {
  const latestRun = [...toolRuns].reverse().find((item) => item.tool_name === toolName)
  if (latestRun) return normalizeToolState(latestRun.status)

  if (currentStep === toolName) return 'running'

  if (toolName === 'analyze_structure' && busyStatus.includes('结构预览')) return 'running'
  if (toolName === 'run_ocr' && busyStatus.includes('OCR')) return 'running'
  if (toolName === 'run_asr' && busyStatus.includes('ASR')) return 'running'
  if (toolName === 'generate_result' && busyStatus.includes('迁移任务')) return 'running'

  return 'pending'
}

function buildStageDetail(toolName: string, state: AgentExecutionStageState, busyStatus: string) {
  const meta = TOOL_STAGE_META[toolName]
  if (!meta) return busyStatus || '等待执行'
  if (state === 'failed') return '执行失败'
  if (state === 'completed') return meta.completed
  if (state === 'running') return busyStatus || meta.running
  return '等待执行'
}

export function buildExecutionStages(params: {
  steps: AgentPlanStep[]
  toolRuns: ToolRunRecord[]
  currentStep: string
  agentStatus: AgentStatus
  busyStatus: string
  pendingConfirmationTitle?: string
  hasStructurePreview?: boolean
  hasMaterialAnalysis?: boolean
  hasResultVideo?: boolean
}) {
  const {
    steps,
    toolRuns,
    currentStep,
    agentStatus,
    busyStatus,
    pendingConfirmationTitle,
    hasStructurePreview = false,
    hasMaterialAnalysis = false,
    hasResultVideo = false,
  } = params

  const inferredCompletedTools = new Set<string>()
  if (hasStructurePreview) {
    inferredCompletedTools.add('analyze_structure')
    inferredCompletedTools.add('preview_refresh')
  }
  if (hasMaterialAnalysis) {
    inferredCompletedTools.add('complete_materials')
  }
  if (hasResultVideo) {
    inferredCompletedTools.add('generate_result')
  }

  const plannedStages = steps.map((step) => {
    const toolState = inferredCompletedTools.has(step.tool_name)
      ? 'completed'
      : pickToolState(step.tool_name, currentStep, toolRuns, busyStatus)
    const meta = TOOL_STAGE_META[step.tool_name] || {
      label: step.title,
      running: busyStatus || '正在执行',
      completed: '已完成',
    }
    return {
      key: step.id || step.tool_name,
      label: meta.label,
      detail: buildStageDetail(step.tool_name, toolState, busyStatus),
      state: toolState,
    } satisfies AgentExecutionStage
  })

  const hasPreviewRefreshRun = toolRuns.some((item) => item.tool_name === 'preview_refresh')
  const isPreviewRefreshRunning =
    currentStep === 'preview_refresh' ||
    busyStatus.includes('结构预览') ||
    busyStatus.includes('刷新结构')
  if (hasPreviewRefreshRun || isPreviewRefreshRunning || inferredCompletedTools.has('preview_refresh')) {
    const previewRefreshRun = [...toolRuns].reverse().find((item) => item.tool_name === 'preview_refresh')
    const refreshState = inferredCompletedTools.has('preview_refresh')
      ? 'completed'
      : previewRefreshRun
        ? normalizeToolState(previewRefreshRun.status)
        : isPreviewRefreshRunning
          ? 'running'
          : 'pending'
    const insertIndex = plannedStages.findIndex((stage) => stage.label === '素材补全')
    const refreshStage: AgentExecutionStage = {
      key: 'preview_refresh',
      label: '结构刷新',
      detail: buildStageDetail('preview_refresh', refreshState, busyStatus),
      state: refreshState,
    }
    if (insertIndex >= 0) {
      plannedStages.splice(insertIndex, 0, refreshStage)
    } else {
      plannedStages.push(refreshStage)
    }
  }

  if (!plannedStages.length) {
    if (agentStatus === 'planning') {
      return [
        {
          key: 'planning',
          label: '执行规划',
          detail: '正在生成执行计划',
          state: 'running',
        } satisfies AgentExecutionStage,
      ]
    }

    return []
  }

  if (agentStatus === 'awaiting_start_confirm' || agentStatus === 'awaiting_tool_confirm') {
    const current = plannedStages.find((item) => item.state === 'running') || plannedStages[0]
    if (current) {
      current.detail = pendingConfirmationTitle ? `等待确认：${pendingConfirmationTitle}` : '等待确认后开始执行'
      if (current.state === 'pending') current.state = 'running'
    }
  }

  if (agentStatus === 'completed') {
    return plannedStages.map(
      (stage): AgentExecutionStage => ({
        ...stage,
        state: stage.state === 'failed' ? 'failed' : 'completed',
        detail: stage.state === 'failed' ? stage.detail : '已完成',
      }),
    )
  }

  return plannedStages
}
