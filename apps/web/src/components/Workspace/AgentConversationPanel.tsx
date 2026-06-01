import React, { useState } from 'react'
import type { ConfirmationOption, ConfirmationRequest } from '../../agent/types'
import AgentConfirmationMenu from './AgentConfirmationMenu'
import type { AgentExecutionStage } from '../../agent/executionProgress'

export interface AgentConversationMessage {
  id: string
  role: 'assistant' | 'user' | 'system'
  label: string
  body: string
}

interface AgentConversationPanelProps {
  messages: AgentConversationMessage[]
  executionStages: AgentExecutionStage[]
  pendingConfirmation: ConfirmationRequest | null
  statusLabel: string
  error: string
  onConfirm: (option: ConfirmationOption) => void
  onSendMessage: (message: string) => void
}

export default function AgentConversationPanel({
  messages,
  executionStages,
  pendingConfirmation,
  statusLabel,
  error,
  onConfirm,
  onSendMessage,
}: AgentConversationPanelProps) {
  const [draft, setDraft] = useState('')

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const next = draft.trim()
    if (!next) return
    onSendMessage(next)
    setDraft('')
  }

  return (
    <aside
      className="agent-conversation-panel soft-card"
      aria-label="智能助手对话区"
      data-agent-conversation-panel="true"
    >
      <div className="agent-conversation-panel__header">
        <div>
          <span className="agent-conversation-panel__eyebrow">智能助手</span>
          <strong>执行对话</strong>
        </div>
        <span className="agent-conversation-panel__status">{statusLabel}</span>
      </div>

      {error ? (
        <div className="panel-alert panel-alert-inline" role="alert">
          <strong>执行失败</strong>
          <span>{error}</span>
        </div>
      ) : null}

      {executionStages.length ? (
        <div
          className="agent-stage-strip"
          aria-label="当前执行阶段"
          data-agent-stage-strip="true"
        >
          {executionStages.map((stage) => (
            <div
              key={stage.key}
              className="agent-stage-chip"
              data-state={stage.state}
            >
              <strong>{stage.label}</strong>
              <span>{stage.detail}</span>
            </div>
          ))}
        </div>
      ) : null}

      <div className="agent-conversation-panel__messages" aria-live="polite">
        {messages.map((message) => (
          <div
            key={message.id}
            className="agent-conversation-message"
            data-role={message.role}
          >
            <span className="agent-conversation-message__label">{message.label}</span>
            <p>{message.body}</p>
          </div>
        ))}
      </div>

      <div className="agent-conversation-panel__composer">
        <AgentConfirmationMenu request={pendingConfirmation} onSelect={onConfirm} />
        <form className="agent-conversation-panel__form" onSubmit={handleSubmit}>
          <textarea
            aria-label="继续向智能助手输入指令"
            placeholder="继续补充要求，或告诉我跳过 OCR、强调卖点、调整节奏。"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.nativeEvent.isComposing) return
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                const form = event.currentTarget.form
                if (form) {
                  form.requestSubmit()
                }
              }
            }}
          />
          <button className="btn btn-primary" type="submit">
            发送
          </button>
        </form>
      </div>
    </aside>
  )
}
