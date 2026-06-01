// @ts-nocheck
export {}
import test from 'node:test'
import assert from 'node:assert/strict'

const { buildExecutionStages } = await import('../executionProgress.ts')

test('buildExecutionStages exposes waiting confirmation state on first planned step', () => {
  const stages = buildExecutionStages({
    steps: [
      { id: 'step_1', tool_name: 'analyze_structure', title: '分析结构', status: 'pending' },
      { id: 'step_2', tool_name: 'run_asr', title: '执行 ASR', status: 'pending' },
    ],
    toolRuns: [],
    currentStep: '',
    agentStatus: 'awaiting_start_confirm',
    busyStatus: '等待生成',
    pendingConfirmationTitle: '开始执行计划？',
  })

  assert.equal(stages[0]?.label, '结构分析')
  assert.equal(stages[0]?.state, 'running')
  assert.equal(stages[0]?.detail, '等待确认：开始执行计划？')
  assert.equal(stages[1]?.state, 'pending')
})

test('buildExecutionStages reflects running and completed stages from tool runs and status text', () => {
  const stages = buildExecutionStages({
    steps: [
      { id: 'step_1', tool_name: 'analyze_structure', title: '分析结构', status: 'completed' },
      { id: 'step_2', tool_name: 'run_asr', title: '执行 ASR', status: 'running' },
      { id: 'step_3', tool_name: 'generate_result', title: '生成结果', status: 'pending' },
    ],
    toolRuns: [
      { id: 'run_1', tool_name: 'analyze_structure', status: 'completed', summary: 'done' },
    ],
    currentStep: 'run_asr',
    agentStatus: 'running',
    busyStatus: '正在生成 ASR 证据 1/8：镜头 3',
  })

  assert.equal(stages[0]?.state, 'completed')
  assert.equal(stages[0]?.detail, '结构预览已生成')
  assert.equal(stages[1]?.state, 'running')
  assert.equal(stages[1]?.detail, '正在生成 ASR 证据 1/8：镜头 3')
  assert.equal(stages[2]?.state, 'pending')
})

test('buildExecutionStages backfills completion from real outputs', () => {
  const stages = buildExecutionStages({
    steps: [
      { id: 'step_1', tool_name: 'analyze_structure', title: '分析结构', status: 'pending' },
      { id: 'step_2', tool_name: 'run_asr', title: '执行 ASR', status: 'pending' },
      { id: 'step_3', tool_name: 'complete_materials', title: '补全素材', status: 'pending' },
      { id: 'step_4', tool_name: 'generate_result', title: '生成结果', status: 'pending' },
    ],
    toolRuns: [
      { id: 'run_1', tool_name: 'run_asr', status: 'completed', summary: 'ASR 证据已更新' },
    ],
    currentStep: '',
    agentStatus: 'running',
    busyStatus: '迁移任务已完成',
    hasStructurePreview: true,
    hasMaterialAnalysis: true,
    hasResultVideo: true,
  })

  const byLabel = new Map(stages.map((stage) => [stage.label, stage]))
  assert.equal(byLabel.get('结构分析')?.state, 'completed')
  assert.equal(byLabel.get('结构刷新')?.state, 'completed')
  assert.equal(byLabel.get('素材补全')?.state, 'completed')
  assert.equal(byLabel.get('结果生成')?.state, 'completed')
})
