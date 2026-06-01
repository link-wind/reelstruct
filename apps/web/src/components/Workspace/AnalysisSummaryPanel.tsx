import React from 'react'
import GraphMapPanel from './GraphMapPanel'

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

export type GraphPresentationViewModel = {
  headline: string
  summaryPoints: string[]
  nodes: Array<{
    id: string
    label: string
    nodeType: 'segment' | 'unit' | 'shot' | 'text' | 'gap'
    summary: string
    shotIndices: number[]
    confidence: number
  }>
  edges: Array<{
    source: string
    target: string
    relation: string
  }>
}

export interface AnalysisSummaryViewModel {
  source: AnalysisSource
  confidence: number
  headline: string
  metrics: AnalysisMetric[]
  narrativeBeats: NarrativeBeat[]
  rhythmStructure: {
    density: string
    detail: string
    summary: string
  } | null
  packagingStructure: {
    density: string
    detail: string
    signals: string[]
  } | null
  packagingSignals: string[]
  warnings: string[]
  graphPresentation: GraphPresentationViewModel | null
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

export default function AnalysisSummaryPanel({
  analysis,
  framed = true,
}: {
  analysis: AnalysisSummaryViewModel | null
  framed?: boolean
}) {
  const rootClassName = framed ? 'insight-panel soft-card' : 'insight-panel insight-panel-inline'

  if (!analysis) {
    return (
      <article className={rootClassName}>
        <div className="section-head">
          <div>
            <p className="eyebrow">AI 结构</p>
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
  const regularMetrics = analysis.metrics.filter((metric) => !['节奏结构', '包装结构'].includes(metric.label))

  return (
    <article className={rootClassName}>
      <div className="section-head">
        <div>
          <p className="eyebrow">AI 结构</p>
          <h3>{analysis.headline || '结构拆解解释'}</h3>
        </div>
        <span className="status" data-source={analysis.source}>
          {sourceLabel(analysis.source)}
          {confidence ? ` · ${confidence}` : ''}
        </span>
      </div>

      {analysis.warnings.length ? (
        <div className="warning-list">
          {analysis.warnings.map((warning, index) => (
            <span key={`analysis-warning-${index}-${warning}`}>{warning}</span>
          ))}
        </div>
      ) : null}

      <GraphMapPanel graph={analysis.graphPresentation} />

      {regularMetrics.length ? (
        <details className="evidence-details analysis-metrics-details">
          <summary>展开更多指标</summary>
          <div className="analysis-metrics-summary">
            {regularMetrics.map((metric) => (
              <div className="analysis-metric-item" key={`${metric.label}-${metric.value}`}>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                <p>{metric.detail}</p>
              </div>
            ))}
          </div>
        </details>
      ) : null}

      {analysis.graphPresentation?.summaryPoints.length ? (
        <details className="evidence-details">
          <summary>展开图谱概要</summary>
          <ul className="summary-point-list">
            {analysis.graphPresentation.summaryPoints.map((point, index) => (
              <li key={`graph-summary-${index}-${point}`}>{point}</li>
            ))}
          </ul>
        </details>
      ) : null}

      {analysis.rhythmStructure || analysis.packagingStructure ? (
        <div className="structure-insight-grid">
          {analysis.rhythmStructure ? (
            <section className="structure-insight">
              <span>节奏结构</span>
              <strong>{analysis.rhythmStructure.density || '已识别'}</strong>
              <p>{analysis.rhythmStructure.detail || analysis.rhythmStructure.summary}</p>
            </section>
          ) : null}
          {analysis.packagingStructure ? (
            <section className="structure-insight">
              <span>包装结构</span>
              <strong>{analysis.packagingStructure.density || '已识别'}</strong>
              <p>{analysis.packagingStructure.detail}</p>
              {analysis.packagingStructure.signals.length ? (
                <div className="mini-tag-row">
                  {analysis.packagingStructure.signals.map((signal, index) => (
                    <em key={`packaging-structure-${index}-${signal}`}>{signal}</em>
                  ))}
                </div>
              ) : null}
            </section>
          ) : null}
        </div>
      ) : null}

      {analysis.narrativeBeats.length ? (
        <details className="evidence-details">
          <summary>展开段落证据</summary>
          <div className="explain-list">
            {analysis.narrativeBeats.map((beat) => (
              <div className="explain-row" key={`${beat.slot_id}-${beat.label}`}>
                <strong>{beat.label}</strong>
                <span>{beat.evidence}</span>
              </div>
            ))}
          </div>
        </details>
      ) : null}

      {analysis.packagingSignals.length ? (
        <div className="tag-row">
          {analysis.packagingSignals.map((signal, index) => (
            <span key={`packaging-signal-${index}-${signal}`}>{signal}</span>
          ))}
        </div>
      ) : null}
    </article>
  )
}
