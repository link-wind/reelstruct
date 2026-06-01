import React from 'react'

type CutDensity = 'slow' | 'medium' | 'fast'

export interface SampleKeyframeViewModel {
  shotIndex: number
  keyframeTime: number
  publicUrl: string
}

export interface SampleAnalysisViewModel {
  hasUpload: boolean
  title: string
  duration: number
  shotCount: number
  transcriptSummary: string
  filename: string
  resolution: string
  fps?: number
  formatName: string
  detectionMethod: string
  avgShotDuration?: number
  cutDensity?: CutDensity
  fastestWindow: string
  slowestWindow: string
  transcriptFilename: string
  keyframes: SampleKeyframeViewModel[]
}

function formatNumber(value?: number, suffix = '') {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  return `${value.toFixed(value >= 10 ? 1 : 2)}${suffix}`
}

function densityLabel(value?: CutDensity) {
  if (value === 'fast') return '快节奏'
  if (value === 'medium') return '中等节奏'
  if (value === 'slow') return '慢节奏'
  return '-'
}

function detectionLabel(value: string) {
  if (value === 'scene_detect') return '镜头切分'
  if (value === 'uniform_fallback') return '均匀兜底'
  return value || '-'
}

export default function SampleAnalysisPanel({ sample }: { sample: SampleAnalysisViewModel }) {
  if (!sample.hasUpload) {
    return (
      <article className="insight-panel soft-card">
        <div className="section-head">
          <div>
            <p className="eyebrow">样例解析</p>
            <h3>样例解析概览</h3>
          </div>
          <span className="status">等待上传</span>
        </div>
        <div className="empty-state">
          <strong>还没有样例解析结果</strong>
          <span>上传样例后，这里会展示视频基础信息、节奏指标和关键帧证据。</span>
        </div>
      </article>
    )
  }

  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">样例解析</p>
          <h3>样例解析概览</h3>
        </div>
        <span className="status">{sample.filename || sample.title}</span>
      </div>

      <div className="sample-summary">
        <div>
          <span>样例标题</span>
          <strong>{sample.title}</strong>
        </div>
        <div>
          <span>转写/语音概览</span>
          <p>{sample.transcriptSummary || '暂无转写摘要。'}</p>
          {sample.transcriptFilename ? <small>转写文件：{sample.transcriptFilename}</small> : null}
        </div>
      </div>

      <div className="metric-grid">
        <div className="metric-item">
          <span>时长</span>
          <strong>{formatNumber(sample.duration, 's')}</strong>
          <p>样例视频总时长</p>
        </div>
        <div className="metric-item">
          <span>镜头数</span>
          <strong>{sample.shotCount || '-'}</strong>
          <p>{detectionLabel(sample.detectionMethod)}</p>
        </div>
        <div className="metric-item">
          <span>分辨率 / FPS</span>
          <strong>{sample.resolution || '-'}</strong>
          <p>{formatNumber(sample.fps)} 帧/秒</p>
        </div>
        <div className="metric-item">
          <span>平均镜头</span>
          <strong>{formatNumber(sample.avgShotDuration, 's')}</strong>
          <p>{densityLabel(sample.cutDensity)}</p>
        </div>
        <div className="metric-item">
          <span>最快窗口</span>
          <strong>{sample.fastestWindow || '-'}</strong>
          <p>切换最密集片段</p>
        </div>
        <div className="metric-item">
          <span>最慢窗口</span>
          <strong>{sample.slowestWindow || '-'}</strong>
          <p>节奏最舒缓片段</p>
        </div>
      </div>

      {sample.keyframes.length ? (
        <div className="keyframe-grid">
          {sample.keyframes.map((keyframe) => (
            <figure key={`${keyframe.shotIndex}-${keyframe.keyframeTime}`}>
              <img src={keyframe.publicUrl} alt={`镜头 ${keyframe.shotIndex}`} />
              <figcaption>
                镜头 {keyframe.shotIndex} · {formatNumber(keyframe.keyframeTime, 's')}
              </figcaption>
            </figure>
          ))}
        </div>
      ) : (
        <div className="empty-state compact">
          <strong>未生成关键帧</strong>
          <span>后端没有返回关键帧时，仍可先使用基础信息和节奏指标。</span>
        </div>
      )}
    </article>
  )
}
