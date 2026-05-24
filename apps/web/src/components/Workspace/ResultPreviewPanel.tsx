import React from 'react'

const API_ORIGIN = process.env.NEXT_PUBLIC_REELSTRUCT_API_ORIGIN || 'http://127.0.0.1:8010'

export interface PreparedAssetViewModel {
  sceneId: string
  sourceType: string
  sourceLabel: string
  caption: string
  duration: number
}

export interface TraceViewModel {
  step: string
  title: string
  message: string
  progress: number
}

export interface ResultPreviewViewModel {
  runId: string
  batchId: string
  videoUrl: string
  assets: PreparedAssetViewModel[]
  trace: TraceViewModel[]
}

function assetSourceLabel(sourceType: string) {
  if (sourceType === 'uploaded') return '用户上传'
  if (sourceType === 'fixture') return 'fixture 匹配'
  return sourceType || '未知来源'
}

function countAssetsBySource(assets: PreparedAssetViewModel[], sourceType: string) {
  return assets.filter((asset) => asset.sourceType === sourceType).length
}

function apiUrl(path: string) {
  if (/^https?:\/\//.test(path)) return path
  return `${API_ORIGIN}${path.startsWith('/') ? path : `/${path}`}`
}

export default function ResultPreviewPanel({ result }: { result: ResultPreviewViewModel | null }) {
  const uploadedCount = result ? countAssetsBySource(result.assets, 'uploaded') : 0
  const fixtureCount = result ? countAssetsBySource(result.assets, 'fixture') : 0

  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">Output</p>
          <h3>结果验证</h3>
        </div>
        <span className="status">{result?.runId || '等待生成'}</span>
      </div>

      {result?.videoUrl ? (
        <div className="result-preview-grid">
          <video className="result-video" src={result.videoUrl} controls preload="metadata" />
          <div className="result-meta">
            <p>Run: {result.runId}</p>
            <p>Batch: {result.batchId || '-'}</p>
            <p>素材片段: {result.assets.length}</p>
            <div className="source-summary">
              <span>用户上传 {uploadedCount}</span>
              <span>fixture 匹配 {fixtureCount}</span>
            </div>
            <a className="btn" href={apiUrl(`/api/runs/${result.runId}/export.zip`)}>
              下载结果包
            </a>
          </div>
        </div>
      ) : (
        <div className="empty-state">
          <strong>还没有成片 demo</strong>
          <span>点击生成结构后，后端会渲染 MP4 demo，并标明每段素材来自用户上传还是 fixture 匹配。</span>
        </div>
      )}

      {result?.assets.length ? (
        <div className="asset-list">
          <div className="asset-list-head">
            <strong>素材来源验证</strong>
            <span>重新生成后，上传素材会优先进入对应结构槽位。</span>
          </div>
          {result.assets.map((asset) => (
            <div className="asset-row" key={`${asset.sceneId}-${asset.sourceLabel}`}>
              <div>
                <strong>{asset.sceneId || 'segment'}</strong>
                <span>{asset.sourceLabel || asset.sourceType}</span>
                {asset.caption ? <p>{asset.caption}</p> : null}
              </div>
              <div className="asset-source-meta">
                <span data-source={asset.sourceType}>{assetSourceLabel(asset.sourceType)}</span>
                <span>{asset.duration}s</span>
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {result?.trace.length ? (
        <div className="trace-list">
          {result.trace.map((event) => (
            <div className="trace-item" key={`${event.step}-${event.progress}`}>
              <strong>{event.title}</strong>
              <span>{event.message}</span>
              <div className="bar">
                <span style={{ '--value': `${event.progress}%` } as React.CSSProperties} />
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  )
}
