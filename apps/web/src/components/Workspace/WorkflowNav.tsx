import React from 'react'

export type Stage = 'sample' | 'structure' | 'output'
export interface StageState {
  enabled: boolean
  completed?: boolean
}

interface WorkflowNavProps {
  currentStage: Stage
  onStageChange: (stage: Stage) => void
  stageStates?: Partial<Record<Stage, StageState>>
}

const STAGES: Array<{
  id: Stage
  index: string
  title: string
  description: string
}> = [
  {
    id: 'sample',
    index: '01',
    title: '样例输入',
    description: '上传参考视频，读取真实视频信息。',
  },
  {
    id: 'structure',
    index: '02',
    title: '结构拆解',
    description: '生成结构节点、节奏和素材映射。',
  },
  {
    id: 'output',
    index: '03',
    title: '输出检查',
    description: '检查 demo、缺口和后续版本输出。',
  },
]

export default function WorkflowNav({ currentStage, onStageChange, stageStates }: WorkflowNavProps) {
  return (
    <nav className="workflow-steps soft-card" id="workflowSteps" aria-label="工作台步骤">
      {STAGES.map((stage) => {
        const state = stageStates?.[stage.id]
        const enabled = state?.enabled ?? true

        return (
          <button
            className="workflow-step"
            type="button"
            key={stage.id}
            data-stage={stage.id}
            data-active={currentStage === stage.id}
            data-completed={Boolean(state?.completed)}
            disabled={!enabled}
            onClick={() => onStageChange(stage.id)}
          >
            <span className="workflow-index">{stage.index}</span>
            <span className="workflow-copy">
              <strong>{stage.title}</strong>
              <span>{stage.description}</span>
            </span>
          </button>
        )
      })}
    </nav>
  )
}
