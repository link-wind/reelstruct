import React, { useState } from 'react'

export interface ChatMessage {
  id: string
  role: 'agent' | 'user'
  label: string
  body: string
  steps?: { title: string; time: string }[]
}

interface AgentActionPanelProps {
  messages: ChatMessage[]
  onSendMessage: (msg: string) => void
  status: string
  error: string
  isBusy: boolean
}

export default function AgentActionPanel({
  messages,
  onSendMessage,
  status,
  error,
  isBusy,
}: AgentActionPanelProps) {
  const [inputStr, setInputStr] = useState('')

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    const next = inputStr.trim()
    if (!next) return
    onSendMessage(next)
    setInputStr('')
  }

  return (
    <aside className="agent-panel soft-card" aria-label="Agent 对话区">
      <div className="panel-head">
        <div>
          <p className="eyebrow">Agent</p>
          <h2>结构迁移对话</h2>
          <p>记录任务、补充约束，并展示真实接口状态。</p>
        </div>
        <span className="status" id="agentState" data-busy={isBusy}>
          {status}
        </span>
      </div>

      {error ? (
        <div className="panel-alert" role="alert">
          <strong>执行失败</strong>
          <span>{error}</span>
        </div>
      ) : null}

      <div className="chat" id="chatBody" aria-live="polite">
        {messages.map((msg) => (
          <div key={msg.id} className="message" data-role={msg.role}>
            <div className="message-head">
              <span>{msg.label}</span>
            </div>
            <p>{msg.body}</p>
            {msg.steps?.length ? (
              <div className="agent-steps">
                {msg.steps.map((step) => (
                  <div key={`${msg.id}-${step.title}`} className="agent-step">
                    <span className="step-mark">✓</span>
                    <div>
                      <span>{step.title}</span>
                      <br />
                      <span className="step-time">{step.time}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>

      <form className="composer" id="chatForm" onSubmit={handleSubmit}>
        <textarea
          id="chatInput"
          aria-label="继续向 Agent 输入指令"
          placeholder="例如：缩短 Hook，保留参考片字幕节奏，不要使用纯 UI B-roll。"
          value={inputStr}
          onChange={(event) => setInputStr(event.target.value)}
          onKeyDown={(event) => {
            if (event.nativeEvent.isComposing) return
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              handleSubmit(event)
            }
          }}
        />
        <button className="btn btn-primary" type="submit">
          记录
        </button>
      </form>
    </aside>
  )
}
