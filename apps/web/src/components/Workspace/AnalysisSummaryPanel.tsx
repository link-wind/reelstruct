import React from 'react'

type AnalysisSource = 'rule' | 'ai' | 'fallback'

type AnalysisMetric = {
  label: string
  value: string
  detail: string
}

type NarrativeBeat = {
  slot_id: string
  label: string
  evidence: string
}

export interface AnalysisSummaryViewModel {
  source: AnalysisSource
  confidence: number
  headline: string
  metrics: AnalysisMetric[]
  narrativeBeats: NarrativeBeat[]
  packagingSignals: string[]
  warnings: string[]
}

function sourceLabel(source: AnalysisSource) {
  if (source === 'ai') return 'AI 视频结构拆解'
  if (source === 'fallback') return 'AI 失败兜底'
  return '基础结构拆解'
}

function confidenceLabel(confidence: number) {
  if (!confidence) return ''
  const normalized = confidence <= 1 ? confidence * 100 : confidence
  return `${Math.round(normalized)}%`
}

export default function AnalysisSummaryPanel({ analysis }: { analysis: AnalysisSummaryViewModel | null }) {
  if (!analysis) {
    return (
      <article className="insight-panel soft-card">
        <div className="section-head">
          <div>
            <p className="eyebrow">AI structure</p>
            <h3>结构拆解解释</h3>
          </div>
          <span className="status">等待生成</span>
        </div>
        <div className="empty-state">
          <strong>还没有 AI 拆解结果</strong>
          <span>上传样例并生成结构后，这里会显示来源、置信度、证据和包装信号。</span>
        </div>
      </article>
    )
  }

  const confidence = confidenceLabel(analysis.confidence)

  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">AI structure</p>
          <h3>{analysis.headline || '结构拆解解释'}</h3>
        </div>
        <span className="status" data-source={analysis.source}>
          {sourceLabel(analysis.source)}
          {confidence ? ` · ${confidence}` : ''}
        </span>
      </div>

      {analysis.warnings.length ? (
        <div className="warning-list">
          {analysis.warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}

      {analysis.metrics.length ? (
        <div className="metric-grid">
          {analysis.metrics.map((metric) => (
            <div className="metric-item" key={`${metric.label}-${metric.value}`}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <p>{metric.detail}</p>
            </div>
          ))}
        </div>
      ) : null}

      {analysis.narrativeBeats.length ? (
        <div className="explain-list">
          {analysis.narrativeBeats.map((beat) => (
            <div className="explain-row" key={`${beat.slot_id}-${beat.label}`}>
              <strong>{beat.label}</strong>
              <span>{beat.evidence}</span>
            </div>
          ))}
        </div>
      ) : null}

      {analysis.packagingSignals.length ? (
        <div className="tag-row">
          {analysis.packagingSignals.map((signal) => (
            <span key={signal}>{signal}</span>
          ))}
        </div>
      ) : null}
    </article>
  )
}
