import React from 'react'

export interface TransferExplanationViewModel {
  slotId: string
  label: string
  sampleEvidence: string
  sourceMethod: string
  transferableRule: string
  targetMessage: string
  targetAdaptation: string
  reasoning: string
  assetRequirement: string
  assetStrategy: string
  packagingPlan: string
  fallbackStrategy: string
  confidence: number
  warnings: string[]
}

export default function TransferExplanationPanel({ explanations }: { explanations: TransferExplanationViewModel[] }) {
  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">Transfer logic</p>
          <h3>迁移解释</h3>
        </div>
        <span className="status">{explanations.length ? `${explanations.length} 个节点` : '等待生成'}</span>
      </div>

      {explanations.length ? (
        <div className="transfer-list">
          {explanations.map((item) => (
            <section className="transfer-item" key={item.slotId}>
              <div className="transfer-title">
                <strong>{item.label}</strong>
                <span>{item.assetRequirement}</span>
              </div>
              <div className="transfer-grid">
                <div>
                  <span>样例方法</span>
                  <p>{item.sourceMethod || item.sampleEvidence || '等待拆解'}</p>
                </div>
                <div>
                  <span>新内容表达</span>
                  <p>{item.targetAdaptation || item.targetMessage || '等待生成'}</p>
                </div>
                <div>
                  <span>素材/包装支撑</span>
                  <p>{item.assetStrategy || item.packagingPlan || '等待映射'}</p>
                </div>
              </div>
              <div className="transfer-reason">
                <strong>迁移理由</strong>
                <p>{item.reasoning || item.transferableRule || item.fallbackStrategy || '等待生成迁移解释。'}</p>
              </div>
              <div className="transfer-reason">
                <strong>可信度</strong>
                <p>
                  {item.confidence ? `${Math.round(item.confidence * 100)}%` : '规则兜底'}
                  {item.warnings.length ? ` / ${item.warnings.join('；')}` : ''}
                </p>
              </div>
            </section>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <strong>还没有迁移解释</strong>
          <span>生成结构后，这里会展示“样例方法 {'->'} 新内容表达 {'->'} 素材支撑”的映射过程。</span>
        </div>
      )}
    </article>
  )
}
