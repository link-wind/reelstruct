import React, { useRef, useState } from 'react'
import AnalysisSummaryPanel, { AnalysisSummaryViewModel } from './AnalysisSummaryPanel'
import EvaluationSummaryPanel, { EvaluationSummaryViewModel } from './EvaluationSummaryPanel'
import MaterialGapPanel, { MaterialGapViewModel } from './MaterialGapPanel'
import MaterialLibraryPanel, { MaterialLibraryAssetViewModel } from './MaterialLibraryPanel'
import ResultPreviewPanel, { ResultPreviewViewModel } from './ResultPreviewPanel'
import SampleAnalysisPanel, { SampleAnalysisViewModel } from './SampleAnalysisPanel'
import ShotEvidencePanel, { AnalysisUnitViewModel, ShotEvidenceViewModel } from './ShotEvidencePanel'
import ShotRelationPanel, { ShotRelationViewModel } from './ShotRelationPanel'
import TargetBriefPanel, { TargetBriefViewModel } from './TargetBriefPanel'
import TransferExplanationPanel, { TransferExplanationViewModel } from './TransferExplanationPanel'
import { localizeShotName } from './localize'

interface StructureNode {
  key: string
  start: number
  end: number
  duration: number
  time: string
  label: string
  desc: string
  score: string
  sampleEvidence: string
  evidenceShotIndices: number[]
  evidenceShots: Array<{
    shotIndex: number
    keyframeTime: number
    publicUrl: string
  }>
}

interface SampleMeta {
  shotCount?: number
  targetAssetCount?: number
}

interface WorkPanelProps {
  stageTitle: string
  stageDescription: string
  workClock: string
  hasVideo: boolean
  videoUrl?: string
  videoDuration: string
  videoName: string
  sampleMeta: SampleMeta
  nodes: StructureNode[]
  activeNodeKey: string
  onNodeClick: (key: string) => void
  onUploadVideo: (file: File) => void
  onUploadMaterialAsset: (slotId: string, file: File) => void
  onGenerateMaterialEvidence: (slotId: string) => void
  onSelectSupplementOption: (slotId: string, method: string) => void
  onGenerate: () => void
  onGenerateOcrEvidence: () => void
  onGenerateAsrEvidence: () => void
  canGenerate: boolean
  canGenerateEvidence: boolean
  isBusy: boolean
  status: string
  error: string
  sampleAnalysis: SampleAnalysisViewModel
  targetBrief: TargetBriefViewModel
  analysis: AnalysisSummaryViewModel | null
  evaluationSummary: EvaluationSummaryViewModel | null
  analysisUnits: AnalysisUnitViewModel[]
  shotEvidence: ShotEvidenceViewModel[]
  shotEvidenceWarnings: string[]
  shotRelations: ShotRelationViewModel[]
  transferExplanations: TransferExplanationViewModel[]
  materialGaps: MaterialGapViewModel[]
  materialAssets: MaterialLibraryAssetViewModel[]
  result: ResultPreviewViewModel | null
  progressItems: { label: string; v1: string; v2: string; percent: number }[]
  mappingItems: { key: string; label: string; score: string; percent: number }[]
}

type WorkTab = 'sample' | 'evidence' | 'structure' | 'materials' | 'output'
type StructureSubTab = 'script' | 'rhythm' | 'packaging'

function rhythmLabel(duration: number, averageDuration: number) {
  if (duration <= Math.max(0.8, averageDuration * 0.72)) return '快'
  if (duration >= averageDuration * 1.28) return '慢'
  return '中'
}

function rhythmTone(label: string) {
  if (label === '快') return 'fast'
  if (label === '慢') return 'slow'
  return 'medium'
}

function formatSecondsLabel(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

interface RhythmSample {
  key: string
  label: string
  start: number
  end: number
  duration: number
}

function buildRhythmSamples(
  nodes: StructureNode[],
  analysisUnits: AnalysisUnitViewModel[],
  shotEvidence: ShotEvidenceViewModel[],
): RhythmSample[] {
  const shotSamples = shotEvidence
    .filter((shot) => shot.duration > 0)
    .map((shot) => ({
      key: `shot-${shot.shotIndex}`,
      label: localizeShotName(shot.shotIndex),
      start: shot.start,
      end: shot.end,
      duration: shot.duration,
    }))
  if (shotSamples.length) return shotSamples

  const unitSamples = analysisUnits
    .filter((unit) => unit.duration > 0)
    .map((unit) => ({
      key: unit.unitId,
      label: unit.unitId.replace(/^unit_/i, '分析单元 '),
      start: unit.start,
      end: unit.end,
      duration: unit.duration,
    }))
  if (unitSamples.length) return unitSamples

  return nodes
    .filter((node) => node.duration > 0)
    .map((node) => ({
      key: node.key,
      label: node.label,
      start: node.start,
      end: node.end,
      duration: node.duration,
    }))
}

function RhythmStructureChart({
  nodes,
  rhythm,
  analysisUnits,
  shotEvidence,
}: {
  nodes: StructureNode[]
  rhythm: NonNullable<AnalysisSummaryViewModel['rhythmStructure']>
  analysisUnits: AnalysisUnitViewModel[]
  shotEvidence: ShotEvidenceViewModel[]
}) {
  const rhythmSamples = buildRhythmSamples(nodes, analysisUnits, shotEvidence)
  const averageDuration = rhythmSamples.length
    ? rhythmSamples.reduce((total, sample) => total + sample.duration, 0) / rhythmSamples.length
    : 0

  if (!rhythmSamples.length) {
    return (
      <div className="empty-state compact">
        <strong>还没有可画出的节奏图</strong>
        <span>生成段落结构后，这里会按段落时长推导切换频率、快慢变化和高潮位置。</span>
      </div>
    )
  }

  const minStart = Math.min(...rhythmSamples.map((sample) => sample.start))
  const maxEnd = Math.max(...rhythmSamples.map((sample) => sample.end))
  const totalDuration = Math.max(maxEnd - minStart, 0.1)
  const speeds = rhythmSamples.map((sample) => 1 / Math.max(sample.duration, 0.1))
  const minSpeed = Math.min(...speeds)
  const maxSpeed = Math.max(...speeds)
  const peakIndex = speeds.reduce((bestIndex, speed, index) => (speed > speeds[bestIndex] ? index : bestIndex), 0)
  const slowestIndex = rhythmSamples.reduce(
    (bestIndex, sample, index) => (sample.duration > rhythmSamples[bestIndex].duration ? index : bestIndex),
    0,
  )
  const peakSample = rhythmSamples[peakIndex]
  const slowCount = rhythmSamples.filter((sample) => rhythmLabel(sample.duration, averageDuration) === '慢').length
  const fastCount = rhythmSamples.filter((sample) => rhythmLabel(sample.duration, averageDuration) === '快').length
  const density = rhythm.density || (averageDuration <= 1.5 ? '高频切换' : averageDuration <= 3 ? '中等切换' : '低频切换')
  const waveformSegments = rhythmSamples.map((sample, index) => {
    const speed = speeds[index]
    const ratio = maxSpeed === minSpeed ? 0.5 : (speed - minSpeed) / (maxSpeed - minSpeed)
    const x1 = ((sample.start - minStart) / totalDuration) * 100
    const x2 = ((sample.end - minStart) / totalDuration) * 100
    const y = 82 - ratio * 58
    const label = rhythmLabel(sample.duration, averageDuration)
    return { sample, x1, x2, midX: (x1 + x2) / 2, y, label, ratio, isPeak: index === peakIndex }
  })
  const linePath = waveformSegments
    .map((segment, index) => {
      if (index === 0) return `M ${segment.x1} ${segment.y} L ${segment.x2} ${segment.y}`
      return `L ${segment.x1} ${segment.y} L ${segment.x2} ${segment.y}`
    })
    .join(' ')
  const areaPath = `${linePath} L 100 92 L 0 92 Z`
  const timeTicks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => ({
    key: ratio,
    label: formatSecondsLabel(minStart + totalDuration * ratio),
  }))
  const notableSegments = [
    { ...waveformSegments[peakIndex], tag: '节奏爆点' },
    { ...waveformSegments[slowestIndex], tag: '慢速铺垫' },
  ].filter((segment, index, list) => list.findIndex((item) => item.sample.key === segment.sample.key) === index)

  return (
    <div className="rhythm-chart" aria-label="节奏结构可视化">
      <div className="rhythm-stats">
        <div>
          <span>镜头切换频率</span>
          <strong>{density}</strong>
          <em>平均镜头 {averageDuration.toFixed(1)}s</em>
        </div>
        <div>
          <span>段落快慢变化</span>
          <strong>
            快 {fastCount} / 慢 {slowCount}
          </strong>
          <em>按段落时长相对均值判断</em>
        </div>
        <div>
          <span>高潮位置</span>
          <strong>
            {peakSample ? `${formatSecondsLabel(peakSample.start)} - ${formatSecondsLabel(peakSample.end)}` : '证据不足'}
          </strong>
          <em>{peakSample ? peakSample.label : '等待更多镜头证据'}</em>
        </div>
      </div>

      <div className="rhythm-curve-card" role="img" aria-label="节奏波形图，高位平台代表快切，低位平台代表慢速铺垫">
        <strong className="rhythm-curve-title">节奏波形</strong>
        <div className="rhythm-axis rhythm-axis-y">
          <span>快</span>
          <span>慢</span>
        </div>
        <svg className="rhythm-curve" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <line x1="6" y1="22" x2="94" y2="22" />
          <line x1="6" y1="53" x2="94" y2="53" />
          <line x1="6" y1="84" x2="94" y2="84" />
          <path className="rhythm-area" d={areaPath} />
          <path className="rhythm-line" d={linePath} />
          {waveformSegments.map((segment) => (
            <circle
              key={`rhythm-dot-${segment.sample.key}`}
              cx={segment.midX}
              cy={segment.y}
              r={segment.isPeak ? 2.8 : 2.1}
              data-tone={rhythmTone(segment.label)}
              data-peak={segment.isPeak}
            />
          ))}
        </svg>
        {notableSegments.map((segment) => (
          <span
            key={`rhythm-label-${segment.sample.key}-${segment.tag}`}
            className="rhythm-curve-point-label"
            data-peak={segment.isPeak}
            style={{ left: `${segment.midX}%`, top: `${segment.y}%` } as React.CSSProperties}
          >
            {segment.tag}
          </span>
        ))}
        <div className="rhythm-axis rhythm-axis-x">
          {timeTicks.map((tick) => (
            <span key={`rhythm-time-${tick.key}`}>{tick.label}</span>
          ))}
        </div>
      </div>

      <div className="rhythm-legend" aria-label="节奏图图例">
        <span>
          <i data-tone="fast" /> 快段落
        </span>
        <span>
          <i data-tone="medium" /> 中等段落
        </span>
        <span>
          <i data-tone="slow" /> 慢段落
        </span>
      </div>
    </div>
  )
}

function SegmentTimelinePanel({
  nodes,
  activeNodeKey,
  onNodeClick,
}: {
  nodes: StructureNode[]
  activeNodeKey: string
  onNodeClick: (key: string) => void
}) {
  if (!nodes.length) return null

  const minStart = Math.min(...nodes.map((node) => node.start))
  const maxEnd = Math.max(...nodes.map((node) => node.end))

  return (
    <section className="segment-timeline-panel" aria-label="段落时间线">
      <div className="segment-timeline-head">
        <div>
          <span>段落时间线</span>
          <strong>{formatSecondsLabel(minStart)} - {formatSecondsLabel(maxEnd)}</strong>
        </div>
        <em>{nodes.length} 个段落</em>
      </div>

      <div className="segment-timeline-track">
        {nodes.map((node) => {
          return (
            <button
              key={`segment-bar-${node.key}`}
              type="button"
              className="segment-timeline-bar"
              data-active={activeNodeKey === node.key}
              style={{ flex: `${Math.max(node.duration, 0.15)} 1 0%` } as React.CSSProperties}
              onClick={() => onNodeClick(node.key)}
            >
              <strong>{node.label}</strong>
              <span>{node.time}</span>
              <em>{node.score}</em>
            </button>
          )
        })}
      </div>

      <div className="segment-timeline-list">
        {nodes.map((node) => (
          <button
            key={node.key}
            type="button"
            className="structure-node segment-timeline-item"
            data-active={activeNodeKey === node.key}
            onClick={() => onNodeClick(node.key)}
          >
            <div className="node-time">{node.time}</div>
            <div className="node-copy">
              <strong>{node.label}</strong>
              <span>{node.desc}</span>
              <em className="segment-key-shot-label">
                关键镜头：
                {node.evidenceShotIndices.length
                  ? node.evidenceShotIndices.map((index) => localizeShotName(index)).join(' / ')
                  : '按段落时间匹配'}
              </em>
            </div>
            <div className="node-score">{node.score}</div>
          </button>
        ))}
      </div>
    </section>
  )
}

export default function WorkPanel({
  stageTitle,
  stageDescription,
  workClock,
  hasVideo,
  videoUrl,
  videoDuration,
  videoName,
  sampleMeta,
  nodes,
  activeNodeKey,
  onNodeClick,
  onUploadVideo,
  onUploadMaterialAsset,
  onGenerateMaterialEvidence,
  onSelectSupplementOption,
  onGenerate,
  onGenerateOcrEvidence,
  onGenerateAsrEvidence,
  canGenerate,
  canGenerateEvidence,
  isBusy,
  status,
  error,
  sampleAnalysis,
  targetBrief,
  analysis,
  evaluationSummary,
  analysisUnits,
  shotEvidence,
  shotEvidenceWarnings,
  shotRelations,
  transferExplanations,
  materialGaps,
  materialAssets,
  result,
  progressItems,
  mappingItems,
}: WorkPanelProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [currentTimecode, setCurrentTimecode] = useState('00:00')
  const [activeTab, setActiveTab] = useState<WorkTab>('sample')
  const [activeStructureTab, setActiveStructureTab] = useState<StructureSubTab>('script')
  const activeNode = nodes.find((node) => node.key === activeNodeKey) || null
  const materialsReady = Boolean(evaluationSummary || materialGaps.length || materialAssets.length || mappingItems.length)
  const structureReady = Boolean(nodes.length || analysis || analysisUnits.length || shotEvidence.length)
  const primaryActionLabel = !hasVideo ? '先上传视频' : structureReady ? (result ? '重新生成结果' : '生成结果') : '生成结构'
  const materialsEmptyState = !hasVideo
    ? {
        title: '还没开始素材补全分析',
        description: '先上传参考视频。系统需要先读取样例结构，后面才能判断缺哪些素材。',
        statusLabel: '等待样例',
      }
    : !materialsReady
      ? {
          title: '素材补全分析还没生成',
          description: '参考视频已经就位，下一步点击“生成结构”，这里会出现质量评估、素材缺口和补全方案。',
          statusLabel: '待分析',
        }
      : {
          title: '暂时没有素材缺口',
          description: '当前结构槽位已经被现有素材覆盖；如需继续补拍或上传素材，系统会在这里继续给出建议。',
          statusLabel: '无缺口',
        }
  const evaluationEmptyState = !hasVideo
    ? {
        title: '还没有质量评估',
        description: '先上传参考视频，系统才会开始评估结构拆解、检索命中、补全策略和结果质量。',
        statusLabel: '等待样例',
      }
    : {
        title: '质量评估待生成',
        description: '点击“生成结构”后，这里会给出四维质量判断，并总结当前迁移链路的主要风险。',
        statusLabel: '待分析',
      }
  const tabs: Array<{ key: WorkTab; label: string; meta: string }> = [
    { key: 'sample', label: '样例解析', meta: sampleAnalysis.hasUpload ? '已上传' : '待上传' },
    {
      key: 'evidence',
      label: '镜头证据',
      meta: analysisUnits.length
        ? `${analysisUnits.length} 个分析单元`
        : shotEvidence.length
          ? `${shotEvidence.length} 个镜头`
          : '待生成',
    },
    { key: 'structure', label: '结构拆解', meta: nodes.length ? `${nodes.length} 节点` : '待生成' },
    { key: 'materials', label: '素材补全', meta: materialGaps.length ? `${materialGaps.length} 缺口` : hasVideo ? '待分析' : '待检查' },
    { key: 'output', label: '结果验证', meta: result ? '已生成' : '待生成' },
  ]

  const handleTimeUpdate = () => {
    if (!videoRef.current) return
    const currentTime = videoRef.current.currentTime
    const minutes = Math.floor(currentTime / 60).toString().padStart(2, '0')
    const seconds = Math.floor(currentTime % 60).toString().padStart(2, '0')
    setCurrentTimecode(`${minutes}:${seconds}`)
  }

  const handleGenerateClick = () => {
    setActiveTab('structure')
    setActiveStructureTab('script')
    onGenerate()
  }

  return (
    <section className="work-panel soft-card" aria-label="当前工作情况">
      <div className="panel-head">
        <div>
          <p className="eyebrow">工作台</p>
          <h2 id="stageTitle">{stageTitle}</h2>
          <p id="stageDescription">{stageDescription}</p>
        </div>
        <span className="status" id="workClock">
          {workClock}
        </span>
      </div>

      {error ? (
        <div className="panel-alert panel-alert-inline" role="alert">
          <strong>需要处理</strong>
          <span>{error}</span>
        </div>
      ) : null}

      <div className="work-body">
        <article className="video-block soft-card" aria-label="输入视频">
          <div className="video-player" id="videoPlayer" data-has-video={hasVideo}>
            <video
              id="inputVideo"
              controls
              playsInline
              preload="metadata"
              ref={videoRef}
              src={videoUrl}
              onTimeUpdate={handleTimeUpdate}
            />
            <div className="video-placeholder" aria-hidden={hasVideo ? 'true' : 'false'}>
              <div className="video-label">
                <span>{hasVideo ? '输入视频' : '上传视频'}</span>
                <span>16:9 预览</span>
              </div>
              <div className="play" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                  <path d="M8 5l11 7-11 7z" />
                </svg>
              </div>
              <div className="video-time">
                <div className="timebar">
                  <span />
                </div>
                <span id="videoTimecode">
                  {currentTimecode} / {videoDuration}
                </span>
              </div>
            </div>
          </div>

          <div className="video-side">
            <div>
              <p className="eyebrow">参考来源</p>
              <h3 id="videoName" title={videoName}>
                {videoName}
              </h3>
              <p id="videoDescription">
                {hasVideo
                  ? structureReady
                    ? result
                      ? '结构预览和结果都已生成，可以继续检查素材缺口、映射和最终输出。'
                      : '结构预览已完成。确认结构和素材缺口后，下一步可以生成结果。'
                    : '样例视频已进入工作台。下一步点击“生成结构”，开始真实结构拆解与素材补全分析。'
                  : '上传参考视频后，这里会显示真实视频和基础解析信息。'}
              </p>
            </div>
            <div className="facts">
              <div className="fact">
                <span>参考时长</span>
                <strong id="videoDuration">{videoDuration}</strong>
              </div>
              <div className="fact">
                <span>结构节点</span>
                <strong>{nodes.length || '-'}</strong>
              </div>
              <div className="fact">
                <span>镜头数量</span>
                <strong>{sampleMeta.shotCount ?? '-'}</strong>
              </div>
              <div className="fact">
                <span>素材映射</span>
                <strong>{sampleMeta.targetAssetCount ?? '-'}</strong>
              </div>
            </div>
            <div className="video-actions">
              <label className="btn upload">
                上传视频
                <input
                  id="videoUpload"
                  type="file"
                  accept="video/*"
                  aria-label="上传输入视频"
                  onChange={(event) => {
                    const file = event.currentTarget.files?.[0]
                    if (file) onUploadVideo(file)
                    event.currentTarget.value = ''
                  }}
                />
              </label>
              <button className="btn btn-primary" id="generateDemo" type="button" onClick={handleGenerateClick} disabled={!canGenerate}>
                {isBusy ? status : canGenerate ? primaryActionLabel : '先上传视频'}
              </button>
            </div>
            {hasVideo && !structureReady ? (
              <div className="panel-inline-tip" role="note" aria-label="下一步操作提示">
                <strong>下一步</strong>
                <span>点击“生成结构”，系统会输出段落结构、节奏结构、素材缺口和补全建议。</span>
              </div>
            ) : null}
            {hasVideo && structureReady && !result ? (
              <div className="panel-inline-tip" role="note" aria-label="结果生成提示">
                <strong>下一步</strong>
                <span>结构预览已经完成。确认段落、节奏和素材缺口后，可以点击“生成结果”继续合成 demo。</span>
              </div>
            ) : null}
          </div>
        </article>

        <div className="workspace-tabs" role="tablist" aria-label="工作台内容标签">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-label={`打开${tab.label}标签`}
              aria-selected={activeTab === tab.key}
              className="workspace-tab"
              data-active={activeTab === tab.key}
              onClick={() => setActiveTab(tab.key)}
            >
              <span>{tab.label}</span>
              <strong>{tab.meta}</strong>
            </button>
          ))}
        </div>

        {activeTab === 'sample' ? (
          <div className="tab-panel">
            <TargetBriefPanel brief={targetBrief} />
            <SampleAnalysisPanel sample={sampleAnalysis} />
          </div>
        ) : null}

        {activeTab === 'structure' ? (
          <div className="tab-panel">
            <div className="structure-card soft-card">
              <div className="structure-header">
                <div>
                  <p className="eyebrow">结构拆解</p>
                  <h3>参考视频结构拆解</h3>
                </div>
                <span id="selectedNode">{activeStructureTab === 'script' ? activeNodeKey || '等待生成' : '结构视图'}</span>
              </div>
              <div className="structure-subtabs" role="tablist" aria-label="结构拆解类型">
                {[
                  { key: 'script' as const, label: '段落结构', meta: nodes.length ? `${nodes.length} 段` : '待生成' },
                  { key: 'rhythm' as const, label: '节奏结构', meta: analysis?.rhythmStructure?.density || '待识别' },
                  { key: 'packaging' as const, label: '包装结构', meta: analysis?.packagingStructure?.density || '待识别' },
                ].map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    role="tab"
                    aria-label={`查看${tab.label}`}
                    aria-selected={activeStructureTab === tab.key}
                    className="structure-subtab"
                    data-active={activeStructureTab === tab.key}
                    onClick={() => setActiveStructureTab(tab.key)}
                  >
                    <span>{tab.label}</span>
                    <strong>{tab.meta}</strong>
                  </button>
                ))}
              </div>
              {activeStructureTab === 'script' && nodes.length ? (
                <>
                  <SegmentTimelinePanel nodes={nodes} activeNodeKey={activeNodeKey} onNodeClick={onNodeClick} />

                  {activeNode ? (
                    <details className="node-evidence-details">
                      <summary>查看段落证据</summary>
                      <div className="node-evidence">
                        <div className="node-evidence-copy">
                          <span>段落证据</span>
                          <strong>样例证据</strong>
                          <p>{activeNode.sampleEvidence || activeNode.desc}</p>
                        </div>
                        <div className="node-evidence-shots">
                          <div className="node-evidence-head">
                            <strong>引用镜头</strong>
                            <span>
                              {activeNode.evidenceShotIndices.length
                                ? activeNode.evidenceShotIndices.map((index) => localizeShotName(index)).join(' / ')
                                : '按节点时间匹配'}
                            </span>
                          </div>
                          {activeNode.evidenceShots.length ? (
                            <div className="node-keyframes">
                              {activeNode.evidenceShots.map((shot) => (
                                <figure key={`${activeNode.key}-${shot.shotIndex}-${shot.keyframeTime}`}>
                                  <img src={shot.publicUrl} alt={`${activeNode.label} ${localizeShotName(shot.shotIndex)}`} />
                                  <figcaption>
                                    {localizeShotName(shot.shotIndex)} · {shot.keyframeTime.toFixed(2)}s
                                  </figcaption>
                                </figure>
                              ))}
                            </div>
                          ) : (
                            <p>暂无可展示关键帧，先使用文本证据判断这个结构节点。</p>
                          )}
                        </div>
                      </div>
                    </details>
                  ) : null}
                </>
              ) : null}

              {activeStructureTab === 'script' && !nodes.length ? (
                <div className="empty-state">
                  <strong>还没有结构结果</strong>
                  <span>上传样例并点击“生成结构”后，这里会显示真实节点。</span>
                </div>
              ) : null}

              {activeStructureTab === 'rhythm' ? (
                <div className="structure-detail-panel">
                  {analysis?.rhythmStructure ? (
                    <>
                      <div className="structure-detail-head">
                        <span>节奏结构</span>
                        <strong>{analysis.rhythmStructure.density || '已识别'}</strong>
                      </div>
                      <RhythmStructureChart
                        nodes={nodes}
                        rhythm={analysis.rhythmStructure}
                        analysisUnits={analysisUnits}
                        shotEvidence={shotEvidence}
                      />
                      <p>{analysis.rhythmStructure.detail || analysis.rhythmStructure.summary}</p>
                    </>
                  ) : (
                    <div className="empty-state compact">
                      <strong>还没有节奏结构</strong>
                      <span>生成结构后，这里会显示镜头快慢、密集区间和节奏说明。</span>
                    </div>
                  )}
                </div>
              ) : null}

              {activeStructureTab === 'packaging' ? (
                <div className="structure-detail-panel">
                  {analysis?.packagingStructure ? (
                    <>
                      <div className="structure-detail-head">
                        <span>包装结构</span>
                        <strong>{analysis.packagingStructure.density || '已识别'}</strong>
                      </div>
                      {analysis.packagingStructure.detail ? <p>{analysis.packagingStructure.detail}</p> : null}
                      {analysis.packagingStructure.signals.length ? (
                        <div className="tag-row">
                          {analysis.packagingStructure.signals.map((signal, index) => (
                            <span key={`packaging-detail-${index}-${signal}`}>{signal}</span>
                          ))}
                        </div>
                      ) : null}
                    </>
                  ) : (
                    <div className="empty-state compact">
                      <strong>还没有包装结构</strong>
                      <span>生成结构后，这里会显示字幕密度、标题卡、转场和封面风格。</span>
                    </div>
                  )}
                </div>
              ) : null}
            </div>

            {analysis ? <AnalysisSummaryPanel analysis={analysis} framed={false} /> : null}
            {transferExplanations.length ? (
              <TransferExplanationPanel explanations={transferExplanations} framed={false} />
            ) : null}
          </div>
        ) : null}

        {activeTab === 'evidence' ? (
          <div className="tab-panel">
            <ShotEvidencePanel units={analysisUnits} shots={shotEvidence} warnings={shotEvidenceWarnings} />
            <div className="evidence-actions">
              <button className="btn" type="button" onClick={onGenerateOcrEvidence} disabled={!canGenerateEvidence}>
                生成 OCR 文本
              </button>
              <button className="btn" type="button" onClick={onGenerateAsrEvidence} disabled={!canGenerateEvidence}>
                生成 ASR 口播
              </button>
            </div>
            <ShotRelationPanel relations={shotRelations} />
          </div>
        ) : null}

        {activeTab === 'materials' ? (
          <div className="tab-panel">
            <EvaluationSummaryPanel
              summary={evaluationSummary}
              emptyTitle={evaluationEmptyState.title}
              emptyDescription={evaluationEmptyState.description}
              statusLabel={evaluationEmptyState.statusLabel}
            />
            <div className="lower-grid">
              <article className="quiet-card soft-card">
                <p className="eyebrow">执行进度</p>
                <h3>当前执行</h3>
                <div id="progressList">
                  {progressItems.map((item) => (
                    <div key={item.label} className="progress-row">
                      <div className="progress-meta">
                        <span>{item.label}</span>
                        <span>{item.v2 ? `${item.v1} / ${item.v2}` : item.v1}</span>
                      </div>
                      <div className="bar">
                        <span style={{ '--value': `${item.percent}%` } as React.CSSProperties} />
                      </div>
                    </div>
                  ))}
                </div>
              </article>

              <article className="quiet-card soft-card">
                <p className="eyebrow">素材映射</p>
                <h3>目标素材映射</h3>
                {mappingItems.length ? (
                  <div id="mappingGrid">
                    {mappingItems.map((item, index) => (
                      <div key={item.key || `mapping-${index}`} className="mapping-item">
                        <strong>
                          <span>{item.label}</span>
                          <span>{item.score}</span>
                        </strong>
                        <div className="bar">
                          <span style={{ '--value': `${item.percent}%` } as React.CSSProperties} />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state">
                    <strong>还没有素材映射</strong>
                    <span>生成迁移方案后，这里会显示每个结构节点需要的目标素材。</span>
                  </div>
                )}
              </article>
            </div>

            <MaterialGapPanel
              gaps={materialGaps}
              onUploadAsset={onUploadMaterialAsset}
              onGenerateEvidence={onGenerateMaterialEvidence}
              onSelectSupplementOption={onSelectSupplementOption}
              emptyState={materialsEmptyState}
            />
            <MaterialLibraryPanel assets={materialAssets} />
          </div>
        ) : null}

        {activeTab === 'output' ? (
          <div className="tab-panel">
            <ResultPreviewPanel result={result} />
          </div>
        ) : null}
      </div>
    </section>
  )
}
