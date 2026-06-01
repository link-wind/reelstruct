import React from 'react'
import { localizeShotName } from './localize'

export interface ShotRelationViewModel {
  fromShot: number
  toShot: number
  relationType: string
  summary: string
  semanticShift: string
  confidence: number
}

export default function ShotRelationPanel({ relations }: { relations: ShotRelationViewModel[] }) {
  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">镜头关系</p>
          <h3>前后镜头关系</h3>
        </div>
        <span className="status">{relations.length ? `${relations.length} 个关系` : '等待生成'}</span>
      </div>

      {relations.length ? (
        <div className="transfer-list">
          {relations.map((relation) => (
            <section className="transfer-item" key={`${relation.fromShot}-${relation.toShot}-${relation.relationType}`}>
              <div className="transfer-title">
                <strong>
                  {localizeShotName(relation.fromShot)} → {localizeShotName(relation.toShot)}
                </strong>
                <span>{relation.relationType}</span>
              </div>
              <p>{relation.summary || '等待关系解释'}</p>
              {relation.semanticShift ? <small>{relation.semanticShift}</small> : null}
            </section>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <strong>还没有关系结果</strong>
          <span>AI 聚合结构后，这里会展示相邻镜头如何承接、对比或转折。</span>
        </div>
      )}
    </article>
  )
}
