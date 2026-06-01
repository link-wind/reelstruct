import React from 'react'

export interface MaterialLibraryAssetViewModel {
  slotId: string
  filename: string
  publicUrl: string
  duration: number
  shotCount: number
  recommendedSlot: string
  visualSummary: string
  tags: string[]
  usableFor: string[]
  warnings: string[]
  nodes: Array<{
    chunkId: string
    time: string
    visualSummary: string
    modalities: string[]
    ocrTexts: string[]
    asrTexts: string[]
    packagingSignals: string[]
    subjectTags: string[]
    actionTags: string[]
    slotHints: string[]
    frameUrls: string[]
  }>
}

interface MaterialLibraryPanelProps {
  assets: MaterialLibraryAssetViewModel[]
}

export default function MaterialLibraryPanel({ assets }: MaterialLibraryPanelProps) {
  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">素材库</p>
          <h3>素材库节点</h3>
        </div>
        <span className="status">{assets.length ? `${assets.length} 条素材` : '等待素材'}</span>
      </div>

      {assets.length ? (
        <div className="material-library-list">
          {assets.map((asset) => (
            <section className="material-library-item" key={`${asset.slotId}-${asset.filename}`}>
              <div className="material-library-head">
                <div>
                  <strong>{asset.filename || asset.slotId}</strong>
                  <span>
                    {asset.duration ? `${asset.duration}s` : '时长待识别'} / {asset.shotCount || 0} 镜头 / {asset.recommendedSlot || '槽位待判断'}
                  </span>
                </div>
                <span>{asset.nodes.length ? `${asset.nodes.length} 个节点` : '轻量卡'}</span>
              </div>
              {asset.visualSummary ? <p>{asset.visualSummary}</p> : null}
              {asset.tags.length || asset.usableFor.length ? (
                <div className="material-library-tags">
                  {[...asset.tags, ...asset.usableFor].slice(0, 8).map((tag) => (
                    <span key={`${asset.slotId}-${asset.filename}-${tag}`}>{tag}</span>
                  ))}
                </div>
              ) : null}
              {asset.nodes.length ? (
                <div className="material-node-list">
                  {asset.nodes.map((node) => (
                    <div className="material-node" key={`${asset.slotId}-${asset.filename}-${node.chunkId}`}>
                      <div className="material-node-head">
                        <strong>{node.chunkId}</strong>
                        <span>{node.time}</span>
                      </div>
                      <p>{node.visualSummary || '该节点还没有视觉摘要。'}</p>
                      <div className="material-node-tags">
                        {[...node.modalities, ...node.slotHints].slice(0, 8).map((tag) => (
                          <span key={`${asset.slotId}-${node.chunkId}-${tag}`}>{nodeTagLabel(tag)}</span>
                        ))}
                      </div>
                      {node.ocrTexts.length || node.asrTexts.length || node.packagingSignals.length ? (
                        <ul>
                          {node.ocrTexts.slice(0, 2).map((text, index) => (
                            <li key={`${node.chunkId}-ocr-${index}`}>OCR：{text}</li>
                          ))}
                          {node.asrTexts.slice(0, 2).map((text, index) => (
                            <li key={`${node.chunkId}-asr-${index}`}>ASR：{text}</li>
                          ))}
                          {node.packagingSignals.slice(0, 2).map((signal, index) => (
                            <li key={`${node.chunkId}-packaging-${index}`}>包装：{signal}</li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state compact">
                  <strong>还没有真实素材节点</strong>
                  <span>上传素材后点击“生成素材证据”，这里会显示片段、OCR/ASR、包装信号和可用槽位。</span>
                </div>
              )}
              {asset.warnings.length ? (
                <div className="material-library-warning">{asset.warnings.slice(0, 2).join('；')}</div>
              ) : null}
            </section>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <strong>还没有素材库节点</strong>
          <span>上传补拍素材并生成素材证据后，系统会把视频片段拆成可检索节点。</span>
        </div>
      )}
    </article>
  )
}

function nodeTagLabel(value: string): string {
  const labels: Record<string, string> = {
    visual: '画面',
    ocr: 'OCR',
    asr: 'ASR',
    packaging: '包装',
    slot: '槽位',
    vector: '向量',
  }
  return labels[value] || value
}
