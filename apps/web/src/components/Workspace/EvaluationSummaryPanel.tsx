import React from 'react'

export interface EvaluationSummaryViewModel {
  headline: string
  highlights: string[]
  structureQuality: 'low' | 'medium' | 'high'
  retrievalQuality: 'low' | 'medium' | 'high'
  completionQuality: 'low' | 'medium' | 'high'
  resultQuality: 'low' | 'medium' | 'high'
}

function qualityLabel(value: string) {
  const labels: Record<string, string> = {
    low: '偏弱',
    medium: '中等',
    high: '较强',
  }
  return labels[value] || '偏弱'
}

interface EvaluationSummaryPanelProps {
  summary: EvaluationSummaryViewModel | null
  emptyTitle?: string
  emptyDescription?: string
  statusLabel?: string
}

export default function EvaluationSummaryPanel({
  summary,
  emptyTitle = '还没有质量评估',
  emptyDescription = '生成结构迁移后，这里会汇总结构、检索、补全和结果四项质量判断。',
  statusLabel = '待生成',
}: EvaluationSummaryPanelProps) {
  if (!summary) {
    return (
      <article className="insight-panel soft-card">
        <div className="section-head">
          <div>
            <p className="eyebrow">质量评估</p>
            <h3>{emptyTitle}</h3>
          </div>
          <span className="status">{statusLabel}</span>
        </div>
        <div className="empty-state compact">
          <strong>{emptyTitle}</strong>
          <span>{emptyDescription}</span>
        </div>
      </article>
    )
  }

  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">质量评估</p>
          <h3>{summary.headline || '本次迁移质量评估'}</h3>
        </div>
        <span className="status">结构 / 检索 / 补全 / 结果</span>
      </div>

      <div className="metric-grid">
        <div className="metric-item">
          <span>结构质量</span>
          <strong>{qualityLabel(summary.structureQuality)}</strong>
        </div>
        <div className="metric-item">
          <span>检索质量</span>
          <strong>{qualityLabel(summary.retrievalQuality)}</strong>
        </div>
        <div className="metric-item">
          <span>补全质量</span>
          <strong>{qualityLabel(summary.completionQuality)}</strong>
        </div>
        <div className="metric-item">
          <span>结果质量</span>
          <strong>{qualityLabel(summary.resultQuality)}</strong>
        </div>
      </div>

      {summary.highlights.length ? (
        <ul className="summary-point-list">
          {summary.highlights.map((item, index) => (
            <li key={`evaluation-${index}-${item}`}>{item}</li>
          ))}
        </ul>
      ) : null}
    </article>
  )
}
