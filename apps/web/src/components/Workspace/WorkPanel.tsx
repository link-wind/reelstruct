import React, { useRef, useState } from 'react'
import AnalysisSummaryPanel, { AnalysisSummaryViewModel } from './AnalysisSummaryPanel'
import MaterialGapPanel, { MaterialGapViewModel } from './MaterialGapPanel'
import ResultPreviewPanel, { ResultPreviewViewModel } from './ResultPreviewPanel'
import SampleAnalysisPanel, { SampleAnalysisViewModel } from './SampleAnalysisPanel'
import TargetBriefPanel, { TargetBriefViewModel } from './TargetBriefPanel'
import TransferExplanationPanel, { TransferExplanationViewModel } from './TransferExplanationPanel'

interface StructureNode {
  key: string
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
  onGenerate: () => void
  canGenerate: boolean
  isBusy: boolean
  status: string
  error: string
  sampleAnalysis: SampleAnalysisViewModel
  targetBrief: TargetBriefViewModel
  analysis: AnalysisSummaryViewModel | null
  transferExplanations: TransferExplanationViewModel[]
  materialGaps: MaterialGapViewModel[]
  result: ResultPreviewViewModel | null
  progressItems: { label: string; v1: string; v2: string; percent: number }[]
  mappingItems: { label: string; score: string; percent: number }[]
}

type WorkTab = 'sample' | 'structure' | 'materials' | 'output'

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
  onGenerate,
  canGenerate,
  isBusy,
  status,
  error,
  sampleAnalysis,
  targetBrief,
  analysis,
  transferExplanations,
  materialGaps,
  result,
  progressItems,
  mappingItems,
}: WorkPanelProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [currentTimecode, setCurrentTimecode] = useState('00:00')
  const [activeTab, setActiveTab] = useState<WorkTab>('sample')
  const activeNode = nodes.find((node) => node.key === activeNodeKey) || null
  const tabs: Array<{ key: WorkTab; label: string; meta: string }> = [
    { key: 'sample', label: '样例解析', meta: sampleAnalysis.hasUpload ? '已上传' : '待上传' },
    { key: 'structure', label: '结构拆解', meta: nodes.length ? `${nodes.length} 节点` : '待生成' },
    { key: 'materials', label: '素材补全', meta: materialGaps.length ? `${materialGaps.length} 缺口` : '待检查' },
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
    onGenerate()
  }

  return (
    <section className="work-panel soft-card" aria-label="当前工作情况">
      <div className="panel-head">
        <div>
          <p className="eyebrow">Workspace</p>
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
                <span>{hasVideo ? 'INPUT VIDEO' : 'UPLOAD VIDEO'}</span>
                <span>16:9 preview</span>
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
              <p className="eyebrow">Reference source</p>
              <h3 id="videoName" title={videoName}>
                {videoName}
              </h3>
              <p id="videoDescription">
                {hasVideo
                  ? '样例视频已进入工作台，可生成真实结构拆解。'
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
                {isBusy ? status : canGenerate ? '生成结构' : '先上传视频'}
              </button>
            </div>
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
                  <p className="eyebrow">Structure breakdown</p>
                  <h3>参考视频结构</h3>
                </div>
                <span id="selectedNode">{activeNodeKey || '等待生成'}</span>
              </div>
              {nodes.length ? (
                <>
                  <div className="structure-list" id="structureList">
                    {nodes.map((node) => (
                      <button
                        key={node.key}
                        type="button"
                        className="structure-node"
                        data-active={activeNodeKey === node.key}
                        onClick={() => onNodeClick(node.key)}
                      >
                        <div className="node-time">{node.time}</div>
                        <div className="node-copy">
                          <strong>{node.label}</strong>
                          <span>{node.desc}</span>
                        </div>
                        <div className="node-score">{node.score}</div>
                      </button>
                    ))}
                  </div>

                  {activeNode ? (
                    <div className="node-evidence">
                      <div className="node-evidence-copy">
                        <span>节点证据</span>
                        <strong>样例证据</strong>
                        <p>{activeNode.sampleEvidence || activeNode.desc}</p>
                      </div>
                      <div className="node-evidence-shots">
                        <div className="node-evidence-head">
                          <strong>引用镜头</strong>
                          <span>
                            {activeNode.evidenceShotIndices.length
                              ? activeNode.evidenceShotIndices.map((index) => `Shot ${index}`).join(' / ')
                              : '按节点时间匹配'}
                          </span>
                        </div>
                        {activeNode.evidenceShots.length ? (
                          <div className="node-keyframes">
                            {activeNode.evidenceShots.map((shot) => (
                              <figure key={`${activeNode.key}-${shot.shotIndex}-${shot.keyframeTime}`}>
                                <img src={shot.publicUrl} alt={`${activeNode.label} Shot ${shot.shotIndex}`} />
                                <figcaption>
                                  Shot {shot.shotIndex} · {shot.keyframeTime.toFixed(2)}s
                                </figcaption>
                              </figure>
                            ))}
                          </div>
                        ) : (
                          <p>暂无可展示关键帧，先使用文本证据判断这个结构节点。</p>
                        )}
                      </div>
                    </div>
                  ) : null}
                </>
              ) : (
                <div className="empty-state">
                  <strong>还没有结构结果</strong>
                  <span>上传样例并点击“生成结构”后，这里会显示真实节点。</span>
                </div>
              )}
            </div>

            <AnalysisSummaryPanel analysis={analysis} />
            <TransferExplanationPanel explanations={transferExplanations} />
          </div>
        ) : null}

        {activeTab === 'materials' ? (
          <div className="tab-panel">
            <div className="lower-grid">
              <article className="quiet-card soft-card">
                <p className="eyebrow">Agent progress</p>
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
                <p className="eyebrow">Material mapping</p>
                <h3>目标素材映射</h3>
                {mappingItems.length ? (
                  <div id="mappingGrid">
                    {mappingItems.map((item) => (
                      <div key={`${item.label}-${item.score}`} className="mapping-item">
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

            <MaterialGapPanel gaps={materialGaps} onUploadAsset={onUploadMaterialAsset} />
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
