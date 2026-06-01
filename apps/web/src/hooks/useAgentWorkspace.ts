'use client'

import { useCallback, useEffect, useReducer, useRef } from 'react'
import {
  agentReducer,
  initialAgentState,
  type AgentWorkspaceState,
} from '../agent/reducers'
import type { AgentMessage } from '../agent/types'
import { requestAgentPlan } from './useReelStructApi'

function toErrorMessage(error: unknown) {
  if (error instanceof Error && error.message) return error.message
  return '规划请求失败，请稍后重试。'
}

export function useAgentWorkspace(_initialPrompt?: string) {
  const [state, dispatch] = useReducer(agentReducer, initialAgentState)
  const stateRef = useRef(state)
  const currentPlanRef = useRef<AgentWorkspaceState['currentPlan']>(initialAgentState.currentPlan)

  useEffect(() => {
    stateRef.current = state
  }, [state])

  useEffect(() => {
    currentPlanRef.current = state.currentPlan
  }, [state.currentPlan])

  const submitPrompt = useCallback(async (prompt: string) => {
    const normalizedPrompt = prompt.trim()
    if (!normalizedPrompt) return

    dispatch({
      type: 'planningStarted',
      payload: { prompt: normalizedPrompt },
    })

    try {
      const runtime = await requestAgentPlan({
        prompt: normalizedPrompt,
        state: {
          current_plan: currentPlanRef.current,
        },
      })

      dispatch({
        type: 'planLoaded',
        payload: runtime,
      })
    } catch (error) {
      dispatch({
        type: 'planFailed',
        payload: {
          error: toErrorMessage(error),
        },
      })
    }
  }, [])

  const clearConfirmation = useCallback(() => {
    dispatch({ type: 'confirmationCleared' })
  }, [])

  const addMessage = useCallback((message: AgentMessage) => {
    dispatch({
      type: 'messageAdded',
      payload: message,
    })
  }, [])

  const patchRuntime = useCallback((payload: Parameters<typeof dispatch>[0] extends infer Action
    ? Action extends { type: 'runtimePatched'; payload: infer Payload }
      ? Payload
      : never
    : never) => {
    dispatch({
      type: 'runtimePatched',
      payload,
    })
  }, [])

  return {
    state,
    stateRef,
    submitPrompt,
    clearConfirmation,
    addMessage,
    patchRuntime,
  }
}

export type AgentWorkspaceController = ReturnType<typeof useAgentWorkspace>
