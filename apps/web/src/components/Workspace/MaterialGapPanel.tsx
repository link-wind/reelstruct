import React from 'react'

export interface MaterialGapViewModel {
  slotId: string
  label: string
  missingAsset: string
  impact: string
  fillStrategy: string
  suggestedAssetType: string
  suggestedShots: string[]
  pickupChecklist: string[]
  uploadedFilename?: string
}

interface MaterialGapPanelProps {
  gaps: MaterialGapViewModel[]
  onUploadAsset: (slotId: string, file: File) => void
}

export default function MaterialGapPanel({ gaps, onUploadAsset }: MaterialGapPanelProps) {
  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">Material gaps</p>
          <h3>素材缺口与补全</h3>
        </div>
        <span className="status">{gaps.length ? `${gaps.length} 个缺口` : '无缺口'}</span>
      </div>

      {gaps.length ? (
        <div className="gap-list">
          {gaps.map((gap) => (
            <section className="gap-item" key={gap.slotId}>
              <div className="gap-title">
                <strong>{gap.label}</strong>
                <span>{gap.suggestedAssetType || gap.missingAsset}</span>
              </div>
              <p>{gap.impact}</p>
              <div className="gap-strategy">{gap.fillStrategy}</div>
              {gap.uploadedFilename ? (
                <div className="gap-uploaded">已上传：{gap.uploadedFilename}</div>
              ) : null}
              {gap.suggestedShots.length ? (
                <ul>
                  {gap.suggestedShots.map((shot, index) => (
                    <li key={`${gap.slotId}-suggested-shot-${index}-${shot}`}>{shot}</li>
                  ))}
                </ul>
              ) : null}
              <label className="btn upload gap-upload">
                上传补拍素材
                <input
                  aria-label={`${gap.label} 上传补拍素材`}
                  type="file"
                  accept="video/*"
                  onChange={(event) => {
                    const file = event.currentTarget.files?.[0]
                    if (file) onUploadAsset(gap.slotId, file)
                    event.currentTarget.value = ''
                  }}
                />
              </label>
            </section>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <strong>暂时没有素材缺口</strong>
          <span>生成迁移方案后，系统会按结构槽位检查缺失素材。</span>
        </div>
      )}
    </article>
  )
}
