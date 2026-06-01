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
  retrievalStatus: string
  retrievalReason: string
  primarySupplement: string
  retrievalPlan: {
    requiredExpression: string
    querySummary: string
    bestCandidateLabel: string
    matchedEvidence: string[]
    missingEvidence: string[]
    recommendedMethod: string
    generationAction: string
    confidence: number
  }
  slotFillDecision: {
    decisionType: string
    selectedAssetId: string
    selectedChunkId: string
    start: number
    end: number
    confidence: number
    why: string
    missing: string[]
    actions: string[]
    timelineHint: string
    evidencePath: string[]
    timelinePatchId: string
  }
  slotQueryProfile: {
    slotLabel: string
    requiredAsset: string
    requiredExpression: string
    semanticTerms: string[]
    visualTerms: string[]
    actionTerms: string[]
    textTerms: string[]
    packagingTerms: string[]
    targetDuration: number
    minUsableDuration: number
    replacementModes: string[]
  }
  coverageResult: {
    slotId: string
    coverageScore: number
    gapLevel: string
    fillability: string
    summary: string
  }
  graphSearchResults: Array<{
    slotId: string
    assetId: string
    chunkId: string
    start: number
    end: number
    matchedNodes: Array<{
      nodeId: string
      nodeType: string
      label: string
      text: string
      sourceAssetId: string
      chunkId: string
    }>
    evidencePath: string[]
    missing: string[]
    scoreBreakdown: Record<string, number>
    confidence: number
  }>
  timelinePatches: Array<{
    patchId: string
    slotId: string
    operation: string
    targetStart: number
    targetEnd: number
    executionSummary: string
    sourceAssetId: string
    sourceChunkId: string
    sourceStart: number
    sourceEnd: number
    trackUpdates: Array<{
      type: string
      action: string
      text: string
      duration: number
      styleHint: string
    }>
    warnings: string[]
  }>
  supplementOptions: Array<{
    method: string
    title: string
    action: string
    evidence: string[]
    priority: number
  }>
  selectedSupplementMethod?: string
  candidates: Array<{
    assetId: string
    filename: string
    chunkId: string
    start: number
    end: number
    matchedModalities: string[]
    evidence: string[]
    matchScore: number
    scoreBreakdown: Record<string, number>
    matchReason: string
    reuseStrategy: string
    publicUrl: string
  }>
}

interface MaterialGapPanelProps {
  gaps: MaterialGapViewModel[]
  onUploadAsset: (slotId: string, file: File) => void
  onGenerateEvidence: (slotId: string) => void
  onSelectSupplementOption: (slotId: string, method: string) => void
  emptyState?: {
    title: string
    description: string
    statusLabel?: string
  }
}

export default function MaterialGapPanel({
  gaps,
  onUploadAsset,
  onGenerateEvidence,
  onSelectSupplementOption,
  emptyState,
}: MaterialGapPanelProps) {
  const emptyTitle = emptyState?.title || '暂时没有素材缺口'
  const emptyDescription = emptyState?.description || '生成迁移方案后，系统会按结构槽位检查缺失素材。'
  const statusLabel = emptyState?.statusLabel || '无缺口'

  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">素材缺口</p>
          <h3>素材缺口与补全</h3>
        </div>
        <span className="status">{gaps.length ? `${gaps.length} 个缺口` : statusLabel}</span>
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
              <div className="gap-rag-summary" data-status={gap.retrievalStatus}>
                <strong>{gap.retrievalStatus || '缺失'}</strong>
                <span>{gap.retrievalReason || '素材库暂时没有检索到可直接支撑该段落的候选。'}</span>
              </div>
              <div className="gap-coverage-summary" data-level={gap.coverageResult.gapLevel || 'high'}>
                <strong>结构覆盖率 {Math.round((gap.coverageResult.coverageScore || 0) * 100)}%</strong>
                <span>
                  缺口等级 {gapLevelLabel(gap.coverageResult.gapLevel)} / 可补全性 {fillabilityLabel(gap.coverageResult.fillability)}
                </span>
                {gap.coverageResult.summary ? <em>{gap.coverageResult.summary}</em> : null}
              </div>
              <div className="gap-retrieval-plan">
                <div className="gap-retrieval-row">
                  <strong>槽位需求</strong>
                  <span>{gap.retrievalPlan.requiredExpression || gap.fillStrategy}</span>
                </div>
                <div className="gap-retrieval-row">
                  <strong>推荐动作</strong>
                  <span>{gap.retrievalPlan.generationAction || gap.primarySupplement}</span>
                </div>
                {gap.retrievalPlan.bestCandidateLabel ? (
                  <div className="gap-retrieval-row">
                    <strong>命中素材</strong>
                    <span>
                      {gap.retrievalPlan.bestCandidateLabel} / 置信度 {Math.round(gap.retrievalPlan.confidence * 100)}%
                    </span>
                  </div>
                ) : null}
                {gap.retrievalPlan.missingEvidence.length ? (
                  <ul className="gap-retrieval-missing">
                    {gap.retrievalPlan.missingEvidence.slice(0, 3).map((item, index) => (
                      <li key={`${gap.slotId}-missing-${index}`}>{item}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
              {gap.slotFillDecision.actions.length ? (
                <div className="gap-fill-decision">
                  <div className="gap-fill-decision-head">
                    <strong>{decisionTypeLabel(gap.slotFillDecision.decisionType)}</strong>
                    <span>{Math.round(gap.slotFillDecision.confidence * 100)}%</span>
                  </div>
                  {gap.slotFillDecision.selectedAssetId ? (
                    <p>
                      命中素材：{gap.slotFillDecision.selectedAssetId}
                      {gap.slotFillDecision.selectedChunkId ? ` / ${gap.slotFillDecision.selectedChunkId}` : ''}
                    </p>
                  ) : null}
                  {gap.slotFillDecision.why ? <p>{gap.slotFillDecision.why}</p> : null}
                  <ul>
                    {gap.slotFillDecision.actions.slice(0, 3).map((item, index) => (
                      <li key={`${gap.slotId}-decision-action-${index}`}>{item}</li>
                    ))}
                  </ul>
                  {gap.slotFillDecision.timelineHint ? <em>{gap.slotFillDecision.timelineHint}</em> : null}
                </div>
              ) : null}
              {gap.timelinePatches[0]?.executionSummary ? (
                <div className="gap-applied-summary">
                  <strong>已应用结果</strong>
                  <span>{gap.timelinePatches[0].executionSummary}</span>
                </div>
              ) : null}
              <details className="gap-completion-chain" aria-label={`${gap.label} 补全链路`}>
                <summary>
                  补全链路
                  {gap.timelinePatches.length ? ` · ${patchOperationLabel(gap.timelinePatches[0].operation)}` : ''}
                </summary>
                <div className="gap-completion-block">
                  <div className="gap-completion-head">
                    <strong>槽位需求</strong>
                    {gap.slotQueryProfile.targetDuration > 0 ? (
                      <span>目标 {formatDuration(gap.slotQueryProfile.targetDuration)}</span>
                    ) : null}
                  </div>
                  <div className="gap-completion-meta">
                    <span>{gap.slotQueryProfile.slotLabel || gap.label}</span>
                    <span>{gap.slotQueryProfile.requiredAsset || gap.missingAsset}</span>
                  </div>
                  {gap.slotQueryProfile.requiredExpression ? <p>{gap.slotQueryProfile.requiredExpression}</p> : null}
                  <div className="gap-term-groups">
                    {termGroupLabel(gap.slotQueryProfile.semanticTerms, '语义').map(renderTermChip)}
                    {termGroupLabel(gap.slotQueryProfile.visualTerms, '画面').map(renderTermChip)}
                    {termGroupLabel(gap.slotQueryProfile.actionTerms, '动作').map(renderTermChip)}
                    {termGroupLabel(gap.slotQueryProfile.textTerms, '文字').map(renderTermChip)}
                    {termGroupLabel(gap.slotQueryProfile.packagingTerms, '包装').map(renderTermChip)}
                  </div>
                  {gap.slotQueryProfile.replacementModes.length ? (
                    <div className="gap-completion-list">
                      <strong>替代模式</strong>
                      <div className="gap-inline-tags">
                        {gap.slotQueryProfile.replacementModes.map((mode) => (
                          <span key={`${gap.slotId}-replacement-${mode}`}>{decisionTypeLabel(mode)}</span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>

                {gap.graphSearchResults.length ? (
                  <div className="gap-completion-block">
                    <div className="gap-completion-head">
                      <strong>图谱命中</strong>
                      <span>{gap.graphSearchResults.length} 条</span>
                    </div>
                    <div className="gap-graph-result-list">
                      {gap.graphSearchResults.slice(0, 1).map((result, index) => (
                        <div
                          className="gap-graph-result"
                          key={`${gap.slotId}-${result.assetId}-${result.chunkId || 'full'}-${result.start}-${result.end}-${index}`}
                        >
                          <div className="gap-graph-result-head">
                            <strong>{result.assetId || '候选素材'}</strong>
                            <span>{Math.round(result.confidence * 100)}%</span>
                          </div>
                          <p>
                            {result.chunkId ? `${result.chunkId} / ` : ''}
                            {result.end > result.start ? `${formatDuration(result.start)} - ${formatDuration(result.end)}` : '整段素材'}
                          </p>
                          {scoreBreakdownItems(result.scoreBreakdown).length ? (
                            <div className="gap-score-breakdown" aria-label="图谱命中分来源">
                              {scoreBreakdownItems(result.scoreBreakdown).map(([key, value]) => (
                                <span key={`${result.assetId}-${result.chunkId}-${key}`}>{scoreLabel(key)} {value}</span>
                              ))}
                            </div>
                          ) : null}
                          {result.matchedNodes.length ? (
                            <ul className="gap-graph-node-list">
                              {result.matchedNodes.map((node, nodeIndex) => (
                                <li key={`${result.assetId}-${result.chunkId}-${node.nodeId || node.nodeType}-${nodeIndex}`}>
                                  <strong>{graphNodeTypeLabel(node.nodeType)}</strong>
                                  <span>{node.label || node.text || node.nodeId}</span>
                                </li>
                              ))}
                            </ul>
                          ) : null}
                          {result.missing.length ? (
                            <div className="gap-completion-list">
                              <strong>缺失证据</strong>
                              <ul>
                                {result.missing.map((item, itemIndex) => (
                                  <li key={`${result.assetId}-${result.chunkId}-missing-${itemIndex}`}>{item}</li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {gap.timelinePatches.length ? (
                  <div className="gap-completion-block">
                    <div className="gap-completion-head">
                      <strong>时间线结果</strong>
                      <span>{gap.timelinePatches.length} 个 patch</span>
                    </div>
                    <div className="gap-timeline-patch-list">
                      {gap.timelinePatches.slice(0, 1).map((patch) => (
                        <div
                          className="gap-timeline-patch"
                          key={`${gap.slotId}-${patch.patchId}`}
                          data-active={gap.slotFillDecision.timelinePatchId === patch.patchId}
                        >
                          <div className="gap-timeline-patch-head">
                            <strong>{patchOperationLabel(patch.operation)}</strong>
                            <span>{formatDuration(patch.targetStart)} - {formatDuration(patch.targetEnd)}</span>
                          </div>
                          {patch.executionSummary ? <p>{patch.executionSummary}</p> : null}
                          {(patch.sourceAssetId || patch.sourceChunkId) ? (
                            <p>
                              来源：{patch.sourceAssetId || '待生成'}
                              {patch.sourceChunkId ? ` / ${patch.sourceChunkId}` : ''}
                            </p>
                          ) : null}
                          {patch.trackUpdates.length ? (
                            <div className="gap-completion-list">
                              <strong>Track updates</strong>
                              <ul>
                                {patch.trackUpdates.map((update, updateIndex) => (
                                  <li key={`${patch.patchId}-update-${updateIndex}`}>
                                    {trackUpdateLabel(update)}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                          {patch.warnings.length ? (
                            <div className="gap-completion-list">
                              <strong>注意事项</strong>
                              <ul>
                                {patch.warnings.map((warning, warningIndex) => (
                                  <li key={`${patch.patchId}-warning-${warningIndex}`}>{warning}</li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {(gap.slotFillDecision.evidencePath.length || gap.graphSearchResults.some((result) => result.evidencePath.length)) ? (
                  <details className="gap-evidence-path">
                    <summary>
                      证据路径
                      {gap.slotFillDecision.evidencePath.length ? ` · ${gap.slotFillDecision.evidencePath.length} 步` : ''}
                    </summary>
                    <div className="gap-evidence-path-body">
                      {gap.slotFillDecision.evidencePath.length ? (
                        <div className="gap-completion-list">
                          <strong>决策路径</strong>
                          <ol>
                            {gap.slotFillDecision.evidencePath.map((item, index) => (
                              <li key={`${gap.slotId}-decision-path-${index}`}>{item}</li>
                            ))}
                          </ol>
                        </div>
                      ) : null}
                      {gap.graphSearchResults.slice(0, 1).map((result, index) =>
                        result.evidencePath.length ? (
                          <div
                            className="gap-completion-list"
                            key={`${gap.slotId}-graph-path-${result.assetId}-${result.chunkId || 'full'}-${index}`}
                          >
                            <strong>{result.assetId || `候选 ${index + 1}`}</strong>
                            <ol>
                              {result.evidencePath.map((item, itemIndex) => (
                                <li key={`${gap.slotId}-graph-path-${result.assetId}-${itemIndex}`}>{item}</li>
                              ))}
                            </ol>
                          </div>
                        ) : null,
                      )}
                    </div>
                  </details>
                ) : null}
              </details>
              <div className="gap-supplement-summary">
                <strong>首选补全</strong>
                <span>{gap.primarySupplement || gap.fillStrategy}</span>
              </div>
              {gap.supplementOptions.length ? (
                <div className="gap-supplement-list" aria-label={`${gap.label} 补全方案`}>
                  {gap.supplementOptions.map((option) => (
                    <button
                      className="gap-supplement-option"
                      key={`${gap.slotId}-${option.method}-${option.priority}`}
                      type="button"
                      data-selected={gap.selectedSupplementMethod === option.method}
                      onClick={() => onSelectSupplementOption(gap.slotId, option.method)}
                    >
                      <div className="gap-supplement-head">
                        <span>{option.method}</span>
                        <strong>{option.title}</strong>
                      </div>
                      <p>{option.action}</p>
                      {option.evidence.length ? (
                        <em>{option.evidence.slice(0, 2).join(' / ')}</em>
                      ) : null}
                    </button>
                  ))}
                </div>
              ) : null}
              {gap.candidates.length ? (
                <div className="gap-candidate-list" aria-label={`${gap.label} RAG 候选素材`}>
                  {gap.candidates.map((candidate, candidateIndex) => (
                    <div
                      className="gap-candidate"
                      key={`${gap.slotId}-${candidate.assetId}-${candidate.chunkId || 'full'}-${candidate.start}-${candidate.end}-${candidateIndex}`}
                    >
                      <div className="gap-candidate-head">
                        <strong>{candidate.filename || candidate.assetId}</strong>
                        <span>
                          {candidate.chunkId ? `${candidate.start}s-${candidate.end}s` : '整段素材'} / 匹配分 {candidate.matchScore}
                        </span>
                      </div>
                      {scoreBreakdownItems(candidate.scoreBreakdown).length ? (
                        <div className="gap-score-breakdown" aria-label="匹配分来源">
                          {scoreBreakdownItems(candidate.scoreBreakdown).map(([key, value]) => (
                            <span key={`${candidate.assetId}-${candidate.chunkId}-${key}`}>
                              {scoreLabel(key)} {value}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      <p>{candidate.matchReason}</p>
                      {candidate.matchedModalities.length ? (
                        <div className="gap-candidate-tags" aria-label="命中模态">
                          {candidate.matchedModalities.map((modality) => (
                            <span key={`${candidate.assetId}-${candidate.chunkId}-${modality}`}>{modalityLabel(modality)}</span>
                          ))}
                        </div>
                      ) : null}
                      {candidate.evidence.length ? (
                        <ul className="gap-candidate-evidence">
                          {candidate.evidence.slice(0, 4).map((item, index) => (
                            <li key={`${candidate.assetId}-${candidate.chunkId}-evidence-${index}`}>{item}</li>
                          ))}
                        </ul>
                      ) : null}
                      <em>{candidate.reuseStrategy}</em>
                    </div>
                  ))}
                </div>
              ) : null}
              <div className="gap-strategy">{gap.fillStrategy}</div>
              {gap.uploadedFilename ? (
                <div className="gap-uploaded">
                  <span>已上传：{gap.uploadedFilename}</span>
                  <button type="button" onClick={() => onGenerateEvidence(gap.slotId)}>
                    生成素材证据
                  </button>
                </div>
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
          <strong>{emptyTitle}</strong>
          <span>{emptyDescription}</span>
        </div>
      )}
    </article>
  )
}

function modalityLabel(modality: string): string {
  const labels: Record<string, string> = {
    visual: '画面',
    ocr: 'OCR',
    asr: 'ASR',
    packaging: '包装',
    slot: '槽位',
    vector: '向量',
  }
  return labels[modality] || modality
}

function scoreBreakdownItems(scoreBreakdown: Record<string, number>): Array<[string, number]> {
  return Object.entries(scoreBreakdown || {})
    .filter(([, value]) => value > 0)
    .sort((left, right) => right[1] - left[1])
    .slice(0, 4)
}

function scoreLabel(key: string): string {
  const labels: Record<string, string> = {
    vector: '向量',
    semantic: '语义',
    visual: '画面',
    slot_hint: '槽位',
    ocr_asr: '文字',
    packaging: '包装',
    duration_fit: '时长',
  }
  return labels[key] || key
}

function decisionTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    reuse_direct: '直接复用',
    reuse_with_packaging: '包装后复用',
    caption_only: '字幕补全',
    structure_reorder: '结构重排',
    shoot_or_aigc: '补拍/AIGC',
  }
  return labels[value] || '推荐决策'
}

function gapLevelLabel(value: string): string {
  const labels: Record<string, string> = {
    low: '低',
    medium: '中',
    high: '高',
  }
  return labels[value] || '高'
}

function fillabilityLabel(value: string): string {
  const labels: Record<string, string> = {
    direct: '可直接复用',
    packaging: '包装后可用',
    reorder: '需结构重排',
    missing: '需要补素材',
  }
  return labels[value] || '需要补素材'
}

function patchOperationLabel(value: string): string {
  const labels: Record<string, string> = {
    replace_slot_media: '替换槽位素材',
    insert_caption_card: '插入字幕卡',
    request_asset: '请求补拍素材',
  }
  return labels[value] || '时间线 patch'
}

function trackUpdateLabel(update: { type: string; action: string; text: string; duration: number; styleHint: string }): string {
  const typeLabel = modalityLabel(update.type)
  const actionLabels: Record<string, string> = {
    replace: '替换',
    insert: '插入',
    request: '请求',
  }
  const actionLabel = actionLabels[update.action] || update.action
  const detail = [update.text, update.duration > 0 ? formatDuration(update.duration) : '', update.styleHint]
    .filter(Boolean)
    .join(' / ')
  return `${actionLabel}${typeLabel}${detail ? `：${detail}` : ''}`
}

function graphNodeTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    shot: '镜头',
    unit: '分析单元',
    chunk: '片段',
    ocr: 'OCR',
    asr: 'ASR',
    packaging: '包装',
    visual: '画面',
    semantic: '语义',
  }
  return labels[value] || value
}

function formatDuration(value: number): string {
  return `${Number.isFinite(value) ? value.toFixed(value >= 10 ? 0 : 1) : '0'}s`
}

function termGroupLabel(items: string[], label: string): string[] {
  return (items || []).filter(Boolean).map((item) => `${label} · ${item}`)
}

function renderTermChip(label: string, index: number) {
  return <span className="gap-term-chip" key={`${label}-${index}`}>{label}</span>
}
