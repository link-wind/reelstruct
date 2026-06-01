import React from 'react'

export interface TargetBriefViewModel {
  topic: string
  productName: string
  sellingPoints: string[]
  availableAssets: string[]
}

export default function TargetBriefPanel({ brief }: { brief: TargetBriefViewModel }) {
  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">目标简报</p>
          <h3>目标内容</h3>
        </div>
        <span className="status">{brief.productName || '待补充'}</span>
      </div>

      <div className="brief-body">
        <p>{brief.topic || '还没有目标任务，请返回首页输入迁移目标。'}</p>
        {brief.sellingPoints.length ? (
          <div className="tag-row">
            {brief.sellingPoints.map((point, index) => (
              <span key={`selling-point-${index}-${point}`}>{point}</span>
            ))}
          </div>
        ) : null}
        {brief.availableAssets.length ? (
          <div className="brief-assets">
            <strong>已有素材</strong>
            <span>{brief.availableAssets.join(' / ')}</span>
          </div>
        ) : null}
      </div>
    </article>
  )
}
