import { isMostlyEnglish, localizeLabel, localizeText } from '../Workspace/localize.ts'
import { buildExecutionStages } from '../../agent/executionProgress.ts'

function localizeList(items = []) {
  return items.map((item) => localizeText(item, item))
}

function formatUnitId(unit) {
  if (unit.shot_indices.length) return `unit_${unit.shot_indices.join('_')}`
  return `${unit.unit_id}_${unit.start}_${unit.end}`.replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '')
}

const WORKSPACE_STAGE_COPY = {
  sample: {
    title: '样例输入',
    description: '上传参考视频后，使用真实接口生成结构节点和素材映射。',
  },
  structure: {
    title: '结构拆解结果',
    description: '这里展示真实生成的结构节点、节奏摘要和素材映射。',
  },
  output: {
    title: '输出检查',
    description: '生成完成后检查 demo 输出、素材映射和后续补充方向。',
  },
}

export function formatSeconds(secs) {
  const minutes = Math.floor(secs / 60)
  const seconds = Math.floor(secs % 60)
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
}

export function extractPromptSignals(prompt) {
  return prompt
    .split(/[，,。；;、\n]/)
    .map((item) => item.trim())
    .filter((item) => item.length >= 3)
    .slice(0, 4)
}

export function deriveProductName(prompt) {
  const [firstSignal] = extractPromptSignals(prompt)
  const base = firstSignal || prompt.trim()
  return base.length > 24 ? `${base.slice(0, 24)}...` : base
}

export function displayStructureLabel(label, fallback) {
  const normalized = label.trim()
  if (!normalized || /^seg(?:ment)?[_-]?\d+$/i.test(normalized)) return fallback
  if (isMostlyEnglish(normalized)) return localizeLabel(normalized, fallback)
  return localizeLabel(normalized, fallback)
}

export function displayStructureDescription(...items) {
  const value = items
    .map((item) => item.trim())
    .find((item) => item && !/^这个节点暂无说明/.test(item))
  return value ? localizeText(value, '该段证据不足，先按镜头时间和上下文保守展示。') : '该段证据不足，先按镜头时间和上下文保守展示。'
}

export function buildStructureNodes(preview, keyframes = []) {
  return (preview?.template?.script_pattern || []).map((slot, index) => {
    const rawConfidence = typeof slot.confidence === 'number' ? slot.confidence : 0
    const confidence = rawConfidence <= 1 ? rawConfidence * 100 : rawConfidence
    const slotEnd = slot.start + slot.duration
    const explicitEvidenceShots = slot.evidence_shot_indices.length
      ? keyframes.filter((keyframe) => slot.evidence_shot_indices.includes(keyframe.shot_index))
      : []
    const timedEvidenceShots = keyframes.filter(
      (keyframe) => keyframe.keyframe_time >= slot.start && keyframe.keyframe_time <= slotEnd,
    )
    const slotMidpoint = slot.start + slot.duration / 2
    const nearestEvidenceShots = [...keyframes]
      .sort((left, right) => Math.abs(left.keyframe_time - slotMidpoint) - Math.abs(right.keyframe_time - slotMidpoint))
      .slice(0, 1)
    const evidenceShots = (explicitEvidenceShots.length
      ? explicitEvidenceShots
      : timedEvidenceShots.length
        ? timedEvidenceShots
        : nearestEvidenceShots
    )
      .slice(0, 3)
      .map((keyframe) => ({
        shotIndex: keyframe.shot_index,
        keyframeTime: keyframe.keyframe_time,
        publicUrl: keyframe.public_url,
      }))

    return {
      key: slot.id,
      start: slot.start,
      end: slotEnd,
      duration: slot.duration,
      time: `${formatSeconds(slot.start)} - ${formatSeconds(slot.start + slot.duration)}`,
      label: displayStructureLabel(slot.label, `段落 ${index + 1}`),
      desc: displayStructureDescription(slot.purpose, slot.intent, slot.method, slot.role),
      score: `置信度 ${Math.round(confidence)}%`,
      sampleEvidence: slot.sample_evidence,
      evidenceShotIndices: slot.evidence_shot_indices,
      evidenceShots,
    }
  })
}

export function buildTargetBrief(content) {
  return {
    topic: content.topic,
    productName: content.product_name,
    sellingPoints: content.selling_points,
    availableAssets: content.available_assets,
  }
}

export function buildSampleAnalysis(sample, sampleUpload, transcriptUpload) {
  const signal = sampleUpload?.video_signal
  return {
    hasUpload: Boolean(sampleUpload),
    title: sample.title,
    duration: sample.duration,
    shotCount: sample.shot_count,
    transcriptSummary: sample.transcript_summary,
    filename: sampleUpload?.filename || '',
    resolution: signal ? `${signal.metadata.width}x${signal.metadata.height}` : '',
    fps: signal?.metadata.fps,
    formatName: signal?.metadata.format_name || '',
    detectionMethod: signal?.detection_method || '',
    avgShotDuration: signal?.rhythm_metrics.avg_shot_duration,
    cutDensity: signal?.rhythm_metrics.cut_density,
    fastestWindow: signal?.rhythm_metrics.fastest_window || '',
    slowestWindow: signal?.rhythm_metrics.slowest_window || '',
    transcriptFilename: transcriptUpload?.filename || '',
    keyframes: (sampleUpload?.keyframes || []).slice(0, 6).map((keyframe) => ({
      shotIndex: keyframe.shot_index,
      keyframeTime: keyframe.keyframe_time,
      publicUrl: keyframe.public_url,
    })),
  }
}

/** @param {any} preview */
export function buildMappingItems(preview) {
  return (preview?.transfer_plan?.mappings || []).map((mapping) => ({
    key: mapping.slot_id,
    label: localizeText(mapping.asset_requirement || mapping.target_message, '待补充素材要求'),
    score: localizeText(mapping.asset_strategy || '已生成映射', '已生成映射'),
    percent: 100,
  }))
}

/** @param {any} preview */
export function buildSlotLabelLookup(preview) {
  return new Map((preview?.template?.script_pattern || []).map((slot) => [slot.id, slot.label]))
}

/**
 * @param {{
 *   uploadedAssets?: any[],
 *   selectedGaps?: any[],
 *   slotLabelLookup?: Map<string, string>,
 *   supplementSelection?: Record<string, string>
 * }} options
 */
export function buildGapItems({ uploadedAssets = [], selectedGaps = [], slotLabelLookup = new Map(), supplementSelection = {} }) {
  const uploadedLookup = new Map(uploadedAssets.map((asset) => [asset.slot_id, asset.filename]))
  return selectedGaps.map((gap) => ({
    slotId: gap.slot_id,
    label: displayStructureLabel(slotLabelLookup.get(gap.slot_id) || gap.slot_id, gap.slot_id),
    missingAsset: localizeText(gap.missing_asset, gap.missing_asset),
    impact: localizeText(gap.impact, gap.impact),
    fillStrategy: localizeText(gap.fill_strategy, gap.fill_strategy),
    suggestedAssetType: localizeText(gap.suggested_asset_type, gap.suggested_asset_type),
    suggestedShots: localizeList(gap.suggested_shots),
    pickupChecklist: localizeList(gap.pickup_checklist),
    uploadedFilename: uploadedLookup.get(gap.slot_id),
    retrievalStatus: gap.retrieval_status || '缺失',
    retrievalReason: localizeText(gap.retrieval_reason || '', gap.retrieval_reason || ''),
    primarySupplement: localizeText(gap.primary_supplement || gap.fill_strategy, gap.primary_supplement || gap.fill_strategy),
    retrievalPlan: {
      requiredExpression: localizeText(gap.retrieval_plan?.required_expression || '', gap.retrieval_plan?.required_expression || ''),
      querySummary: localizeText(gap.retrieval_plan?.query_summary || '', gap.retrieval_plan?.query_summary || ''),
      bestCandidateLabel: gap.retrieval_plan?.best_candidate_label || '',
      matchedEvidence: localizeList(gap.retrieval_plan?.matched_evidence),
      missingEvidence: localizeList(gap.retrieval_plan?.missing_evidence),
      recommendedMethod: gap.retrieval_plan?.recommended_method || '',
      generationAction: localizeText(gap.retrieval_plan?.generation_action || '', gap.retrieval_plan?.generation_action || ''),
      confidence: gap.retrieval_plan?.confidence || 0,
    },
    slotFillDecision: {
      decisionType: gap.slot_fill_decision?.decision_type || '',
      selectedAssetId: gap.slot_fill_decision?.selected_asset_id || '',
      selectedChunkId: gap.slot_fill_decision?.selected_chunk_id || '',
      start: gap.slot_fill_decision?.start || 0,
      end: gap.slot_fill_decision?.end || 0,
      confidence: gap.slot_fill_decision?.confidence || 0,
      why: localizeText(gap.slot_fill_decision?.why || '', gap.slot_fill_decision?.why || ''),
      missing: localizeList(gap.slot_fill_decision?.missing),
      actions: localizeList(gap.slot_fill_decision?.actions),
      timelineHint: localizeText(gap.slot_fill_decision?.timeline_hint || '', gap.slot_fill_decision?.timeline_hint || ''),
      evidencePath: gap.slot_fill_decision?.evidence_path || [],
      timelinePatchId: gap.slot_fill_decision?.timeline_patch_id || '',
    },
    slotQueryProfile: {
      slotLabel: displayStructureLabel(
        gap.slot_query_profile?.slot_label || slotLabelLookup.get(gap.slot_id) || gap.slot_id,
        gap.slot_id,
      ),
      requiredAsset: localizeText(
        gap.slot_query_profile?.required_asset || gap.missing_asset || '',
        gap.slot_query_profile?.required_asset || gap.missing_asset || '',
      ),
      requiredExpression: localizeText(
        gap.slot_query_profile?.required_expression || gap.fill_strategy || '',
        gap.slot_query_profile?.required_expression || gap.fill_strategy || '',
      ),
      semanticTerms: gap.slot_query_profile?.semantic_terms || [],
      visualTerms: gap.slot_query_profile?.visual_terms || [],
      actionTerms: gap.slot_query_profile?.action_terms || [],
      textTerms: gap.slot_query_profile?.text_terms || [],
      packagingTerms: gap.slot_query_profile?.packaging_terms || [],
      targetDuration: gap.slot_query_profile?.target_duration || 0,
      minUsableDuration: gap.slot_query_profile?.min_usable_duration || 0,
      replacementModes: gap.slot_query_profile?.replacement_modes || [],
    },
    coverageResult: {
      slotId: gap.coverage_result?.slot_id || gap.slot_id,
      coverageScore: gap.coverage_result?.coverage_score || 0,
      gapLevel: gap.coverage_result?.gap_level || 'high',
      fillability: gap.coverage_result?.fillability || 'missing',
      summary: localizeText(gap.coverage_result?.summary || '', gap.coverage_result?.summary || ''),
    },
    graphSearchResults: (gap.graph_search_results || []).map((result) => ({
      slotId: result.slot_id,
      assetId: result.asset_id,
      chunkId: result.chunk_id,
      start: result.start,
      end: result.end,
      matchedNodes: (result.matched_nodes || []).map((node) => ({
        nodeId: node.node_id,
        nodeType: node.node_type,
        label: node.label || '',
        text: node.text || '',
        sourceAssetId: node.source_asset_id,
        chunkId: node.chunk_id,
      })),
      evidencePath: result.evidence_path || [],
      missing: localizeList(result.missing),
      scoreBreakdown: result.score_breakdown || {},
      confidence: result.confidence || 0,
    })),
    timelinePatches: (gap.timeline_patches || []).map((patch) => ({
      patchId: patch.patch_id,
      slotId: patch.slot_id,
      operation: patch.operation,
      targetStart: patch.target_start,
      targetEnd: patch.target_end,
      executionSummary: localizeText(patch.execution_summary || '', patch.execution_summary || ''),
      sourceAssetId: patch.source_asset_id || '',
      sourceChunkId: patch.source_chunk_id || '',
      sourceStart: patch.source_start || 0,
      sourceEnd: patch.source_end || 0,
      trackUpdates: (patch.track_updates || []).map((update) => ({
        type: update.type,
        action: update.action,
        text: update.text || '',
        duration: update.duration || 0,
        styleHint: update.style_hint || '',
      })),
      warnings: localizeList(patch.warnings),
    })),
    selectedSupplementMethod: supplementSelection[gap.slot_id],
    supplementOptions: (gap.supplement_options || []).map((option) => ({
      method: option.method,
      title: localizeText(option.title, option.title),
      action: localizeText(option.action, option.action),
      evidence: localizeList(option.evidence),
      priority: option.priority,
    })),
    candidates: (gap.candidates || []).map((candidate) => ({
      assetId: candidate.asset_id,
      filename: candidate.filename,
      chunkId: candidate.chunk_id,
      start: candidate.start,
      end: candidate.end,
      matchedModalities: candidate.matched_modalities || [],
      evidence: localizeList(candidate.evidence),
      matchScore: candidate.match_score,
      scoreBreakdown: candidate.score_breakdown || {},
      matchReason: localizeText(candidate.match_reason, candidate.match_reason),
      reuseStrategy: localizeText(candidate.reuse_strategy, candidate.reuse_strategy),
      publicUrl: candidate.public_url,
    })),
  }))
}

/** @param {any[]} uploadedAssets */
export function buildMaterialAssets(uploadedAssets = []) {
  return uploadedAssets.map((asset) => ({
    slotId: asset.slot_id,
    filename: asset.filename,
    publicUrl: asset.public_url,
    duration: asset.analysis.duration,
    shotCount: asset.analysis.shot_count,
    recommendedSlot: asset.analysis.recommended_slot_label || asset.analysis.recommended_slot_id,
    visualSummary: localizeText(asset.analysis.visual_summary, asset.analysis.visual_summary),
    tags: localizeList(asset.analysis.tags),
    usableFor: localizeList(asset.analysis.usable_for),
    warnings: localizeList(asset.analysis.warnings),
    nodes: (asset.analysis.evidence_chunks || []).map((chunk) => ({
      chunkId: chunk.chunk_id,
      time: chunk.end > chunk.start ? `${chunk.start}s-${chunk.end}s` : '整段素材',
      visualSummary: localizeText(chunk.visual_summary, chunk.visual_summary),
      modalities: chunk.modalities,
      ocrTexts: chunk.ocr_texts,
      asrTexts: chunk.asr_texts,
      packagingSignals: localizeList(chunk.packaging_signals),
      subjectTags: localizeList(chunk.subject_tags),
      actionTags: localizeList(chunk.action_tags),
      slotHints: localizeList(chunk.slot_hints),
      frameUrls: chunk.frame_urls,
    })),
  }))
}

/** @param {any} preview */
export function buildTransferExplanations(preview) {
  if (!preview) return []
  const mappingLookup = new Map((preview.transfer_plan?.mappings || []).map((mapping) => [mapping.slot_id, mapping]))
  return (preview.template?.script_pattern || []).map((slot, index) => {
    const mapping = mappingLookup.get(slot.id)
    const explanation = mapping?.explanation
    return {
      slotId: slot.id,
      label: displayStructureLabel(slot.label, `段落 ${index + 1}`),
      sampleEvidence: localizeText(slot.sample_evidence, slot.sample_evidence),
      sourceMethod: localizeText(explanation?.source_observation || mapping?.source_method || slot.method, ''),
      transferableRule: localizeText(explanation?.transferable_principle || slot.transferable_rule, ''),
      targetMessage: localizeText(mapping?.target_message || '', ''),
      targetAdaptation: localizeText(explanation?.target_expression || mapping?.target_adaptation || '', ''),
      reasoning: localizeText(explanation?.reasoning || mapping?.reasoning || '', ''),
      assetRequirement: localizeText(mapping?.asset_requirement || slot.required_asset, ''),
      assetStrategy: localizeText(explanation?.asset_plan || mapping?.asset_strategy || '', ''),
      packagingPlan: localizeText(mapping?.packaging_plan || slot.packaging_intent, ''),
      fallbackStrategy: localizeText(explanation?.gap_handling || mapping?.fallback_strategy || '', ''),
      confidence: explanation?.confidence || 0,
      warnings: localizeList(explanation?.warnings),
    }
  })
}

/**
 * @param {{
 *   analysisSummary: any,
 *   analysisSource: 'rule' | 'ai' | 'fallback',
 *   analysisConfidence: number,
 *   analysisWarnings?: string[],
 *   rhythmSummary?: string
 * }} options
 */
export function buildAnalysisView({ analysisSummary, analysisSource, analysisConfidence, analysisWarnings = [], rhythmSummary = '' }) {
  if (!analysisSummary) return null
  const rhythmMetric = analysisSummary.metrics.find((metric) => metric.label === '节奏结构')
  const packagingMetric = analysisSummary.metrics.find((metric) => metric.label === '包装结构')
  return {
    source: analysisSource,
    confidence: analysisConfidence,
    headline: localizeText(analysisSummary.headline, analysisSummary.headline || '结构拆解解释'),
    metrics: analysisSummary.metrics.map((metric) => ({
      label: localizeLabel(metric.label, metric.label),
      value: localizeLabel(metric.value, metric.value),
      detail: localizeText(metric.detail, metric.detail),
    })),
    narrativeBeats: analysisSummary.narrative_beats.map((beat) => ({
      slot_id: beat.slot_id,
      label: displayStructureLabel(beat.label, beat.slot_id),
      evidence: localizeText(beat.evidence, beat.evidence),
    })),
    rhythmStructure: rhythmMetric
      ? {
          density: localizeLabel(rhythmMetric.value, rhythmMetric.value),
          detail: localizeText(rhythmMetric.detail, rhythmMetric.detail),
          summary: localizeText(rhythmSummary || '', ''),
        }
      : rhythmSummary
        ? {
            density: '',
            detail: '',
            summary: localizeText(rhythmSummary, rhythmSummary),
          }
        : null,
    packagingStructure: packagingMetric
      ? {
          density: localizeLabel(packagingMetric.value, packagingMetric.value),
          detail: localizeText(packagingMetric.detail, packagingMetric.detail),
          signals: localizeList(analysisSummary.packaging_signals),
        }
      : analysisSummary.packaging_signals.length
        ? {
            density: '',
            detail: '',
            signals: localizeList(analysisSummary.packaging_signals),
          }
        : null,
    packagingSignals: localizeList(analysisSummary.packaging_signals),
    warnings: localizeList(analysisWarnings),
    graphPresentation: analysisSummary.graph_presentation
      ? {
          headline: localizeText(analysisSummary.graph_presentation.headline, analysisSummary.graph_presentation.headline),
          summaryPoints: localizeList(analysisSummary.graph_presentation.summary_points),
          nodes: analysisSummary.graph_presentation.nodes.map((node) => ({
            id: node.id,
            label: displayStructureLabel(node.label, node.id),
            nodeType: node.node_type,
            summary: localizeText(node.summary, node.summary),
            shotIndices: node.shot_indices,
            confidence: node.confidence,
          })),
          edges: analysisSummary.graph_presentation.edges.map((edge) => ({
            source: edge.source,
            target: edge.target,
            relation: localizeLabel(edge.relation, edge.relation),
          })),
        }
      : null,
  }
}

/**
 * @param {any} preview
 * @param {any} run
 */
export function buildEvaluationSummaryView(preview, run) {
  const summary = run?.evaluation_summary || preview?.evaluation_summary
  if (!summary) return null
  return {
    headline: localizeText(summary.headline || '', summary.headline || ''),
    highlights: localizeList(summary.highlights),
    structureQuality: summary.structure_quality || 'low',
    retrievalQuality: summary.retrieval_quality || 'low',
    completionQuality: summary.completion_quality || 'low',
    resultQuality: summary.result_quality || 'low',
  }
}

/**
 * @param {any} run
 * @param {string} videoUrl
 */
export function buildResultView(run, videoUrl) {
  if (!run || !videoUrl) return null
  return {
    runId: run.run_id,
    batchId: run.batch_id,
    videoUrl,
    assets: (run.prepared_assets || []).map((asset) => ({
      sceneId: asset.scene_id,
      sourceType: asset.source_type,
      sourceLabel: asset.source_label,
      caption: asset.caption,
      duration: asset.duration,
    })),
    trace: run.trace || [],
  }
}

/**
 * @param {{
 *   mergedShotEvidenceGraph: any,
 *   sampleUpload: any,
 *   resolveMediaUrl: (path: string) => string
 * }} options
 */
export function buildShotEvidence({ mergedShotEvidenceGraph, sampleUpload, resolveMediaUrl }) {
  const graph = mergedShotEvidenceGraph || null
  if (graph?.shots?.length) {
    const graphShotLookup = new Map(graph.shots.map((node) => [node.shot.index, node]))
    const signalShots = sampleUpload?.video_signal?.shots || []
    const displayShots = signalShots.length ? signalShots : graph.shots.map((node) => node.shot)
    return displayShots.map((shot) => {
      const node = graphShotLookup.get(shot.index)
      return {
        shotIndex: shot.index,
        start: shot.start,
        end: shot.end,
        duration: shot.duration,
        time: `${formatSeconds(shot.start)} - ${formatSeconds(shot.end)}`,
        frames: (node?.frames || []).map((frame) => ({
          role: frame.role,
          time: frame.time,
          publicUrl: resolveMediaUrl(frame.public_url),
        })),
        ocrTexts: (node?.ocr_texts || []).map((item) => ({
          text: item.text,
          frameIndex: item.frame_index,
          frameTime: item.frame_time,
          position: item.position,
          confidence: item.confidence,
        })),
        transcriptTexts: (node?.transcript_texts || []).map((item) => ({
          text: item.text,
          sourceStart: item.source_start,
          sourceEnd: item.source_end,
          overlapRatio: item.overlap_ratio,
        })),
        visualSummary: localizeText(node?.understanding?.visual_summary || '', ''),
        textSummary: localizeText(node?.understanding?.text_summary || '', ''),
        functionHint: localizeLabel(node?.understanding?.creative_function_hint || '', ''),
        confidence: node?.understanding?.confidence || 0,
        warnings: localizeList(node?.understanding?.warnings),
      }
    })
  }

  const signal = sampleUpload?.video_signal
  const keyframeLookup = new Map((sampleUpload?.keyframes || []).map((keyframe) => [keyframe.shot_index, keyframe]))
  return (signal?.shots || []).map((shot) => {
    const keyframe = keyframeLookup.get(shot.index)
    return {
      shotIndex: shot.index,
      start: shot.start,
      end: shot.end,
      duration: shot.duration,
      time: `${formatSeconds(shot.start)} - ${formatSeconds(shot.end)}`,
      frames: keyframe
        ? [
            {
              role: 'middle',
              time: keyframe.keyframe_time,
              publicUrl: resolveMediaUrl(keyframe.public_url),
            },
          ]
        : [],
      visualSummary: '',
      ocrTexts: [],
      transcriptTexts: [],
      textSummary: '',
      functionHint: '',
      confidence: 0,
      warnings: [],
    }
  })
}

/**
 * @param {{
 *   mergedShotEvidenceGraph: any,
 *   shotEvidence: any[],
 *   resolveMediaUrl: (path: string) => string
 * }} options
 */
export function buildAnalysisUnits({ mergedShotEvidenceGraph, shotEvidence, resolveMediaUrl }) {
  const graph = mergedShotEvidenceGraph || null
  if (!graph?.analysis_units?.length) return []
  const shotLookup = new Map(shotEvidence.map((shot) => [shot.shotIndex, shot]))
  return graph.analysis_units.map((unit) => ({
    unitId: formatUnitId(unit),
    time: `${formatSeconds(unit.start)} - ${formatSeconds(unit.end)}`,
    start: unit.start,
    end: unit.end,
    duration: unit.duration,
    shotIndices: unit.shot_indices,
    representativeFrames: (unit.representative_frames || []).map((frame) => ({
      role: frame.role,
      time: frame.time,
      publicUrl: resolveMediaUrl(frame.public_url),
      shotIndex: frame.shot_index,
    })),
    ocrTexts: (unit.ocr_texts || []).map((item) => ({
      text: item.text,
      frameIndex: item.frame_index,
      frameTime: item.frame_time,
      position: item.position,
      confidence: item.confidence,
    })),
    transcriptTexts: (unit.transcript_texts || []).map((item) => ({
      text: item.text,
      sourceStart: item.source_start,
      sourceEnd: item.source_end,
      overlapRatio: item.overlap_ratio,
    })),
    visualSummary: localizeText(unit.understanding?.visual_summary || '', ''),
    textSummary: localizeText(unit.understanding?.text_summary || '', ''),
    functionHint: localizeLabel(unit.understanding?.creative_function_hint || '', ''),
    confidence: unit.understanding?.confidence || 0,
    warnings: localizeList(unit.understanding?.warnings),
    shots: unit.shot_indices
      .map((shotIndex) => shotLookup.get(shotIndex))
      .filter(Boolean),
  }))
}

/** @param {any} mergedShotEvidenceGraph */
export function buildShotEvidenceWarnings(mergedShotEvidenceGraph) {
  return localizeList(mergedShotEvidenceGraph?.warnings || [])
}

/** @param {any} mergedShotEvidenceGraph */
export function buildShotRelations(mergedShotEvidenceGraph) {
  const graph = mergedShotEvidenceGraph || null
  return (graph?.relations || []).map((relation) => ({
    fromShot: relation.from_shot,
    toShot: relation.to_shot,
    relationType: localizeLabel(relation.relation_type, relation.relation_type),
    summary: localizeText(relation.relation_summary, ''),
    semanticShift: localizeText(relation.semantic_shift, ''),
    confidence: relation.confidence,
  }))
}

/**
 * @param {{
 *   sampleUpload: any,
 *   preview: any,
 *   nodes: any[],
 *   status: string,
 *   busy: boolean
 * }} options
 */
export function buildProgressItems({ sampleUpload, preview, nodes, status, busy }) {
  return [
    {
      label: '样例视频',
      v1: sampleUpload ? '已上传' : '未上传',
      v2: '',
      percent: sampleUpload ? 100 : 0,
    },
    {
      label: '结构拆解',
      v1: preview ? String(nodes.length) : '未生成',
      v2: preview ? '节点' : '',
      percent: preview ? 100 : 0,
    },
    {
      label: '当前状态',
      v1: status,
      v2: '',
      percent: busy ? 60 : status === '等待生成' ? 0 : 100,
    },
  ]
}

/**
 * @param {{
 *   mergedShotEvidenceGraph: any,
 *   sampleUpload: any
 * }} options
 */
export function buildShotEvidenceDisplay({ mergedShotEvidenceGraph, sampleUpload }) {
  return buildShotEvidence({
    mergedShotEvidenceGraph,
    sampleUpload,
    resolveMediaUrl: (path) => {
      const apiOrigin = process.env.NEXT_PUBLIC_REELSTRUCT_API_ORIGIN || 'http://127.0.0.1:8010'
      if (!path) return ''
      if (/^https?:\/\//.test(path)) return path
      return `${apiOrigin}${path.startsWith('/') ? path : `/${path}`}`
    },
  })
}

/**
 * @param {{
 *   steps?: Array<{ title: string }>,
 *   pendingConfirmation?: { id: string, title: string, message?: string } | null,
 *   errors?: string[],
 *   messages?: Array<{ id: string, role: 'assistant' | 'user' | 'system', content: string }>,
 *   taskText?: string,
 *   sampleUpload?: any
 * }} options
 */
export function buildConversationMessages({
  steps = [],
  pendingConfirmation = null,
  errors = [],
  messages = [],
  taskText = '',
  sampleUpload = null,
}) {
  const readyMessage = sampleUpload
    ? '参考视频已上传，我会先生成执行计划并等待你确认。'
    : '请先上传参考视频，上传后我会自动生成执行计划。'

  /** @type {Array<{ id: string, role: 'assistant' | 'user' | 'system', label: string, body: string }>} */
  const result = [
    {
      id: 'conversation-task',
      role: 'user',
      label: '任务',
      body: taskText || '未填写任务，可先上传参考视频再补充目标。',
    },
    {
      id: 'conversation-ready',
      role: 'assistant',
      label: 'ReelStruct',
      body: readyMessage,
    },
  ]

  if (steps.length) {
    result.push({
      id: 'conversation-plan',
      role: 'assistant',
      label: '执行计划',
      body: `当前计划：${steps.map((step) => step.title).join(' -> ')}`,
    })
  }

  if (pendingConfirmation) {
    result.push({
      id: `conversation-confirm-${pendingConfirmation.id}`,
      role: 'assistant',
      label: '等待确认',
      body: pendingConfirmation.message
        ? `${pendingConfirmation.title}：${pendingConfirmation.message}`
        : pendingConfirmation.title,
    })
  }

  errors.forEach((item, index) => {
    result.push({
      id: `conversation-error-${index}`,
      role: 'system',
      label: '错误',
      body: item,
    })
  })

  messages.forEach((message) => {
    result.push({
      id: message.id,
      role: message.role,
      label: message.role === 'user' ? '补充要求' : message.role === 'assistant' ? 'ReelStruct' : '系统',
      body: message.content,
    })
  })

  return result
}

/**
 * @param {{
 *   steps: any[],
 *   toolRuns: any[],
 *   currentStep: string,
 *   agentStatus: string,
 *   busyStatus: string,
 *   pendingConfirmationTitle?: string,
 *   hasStructurePreview?: boolean,
 *   hasMaterialAnalysis?: boolean,
 *   hasResultVideo?: boolean
 * }} options
 */
export function buildExecutionStagesView(options) {
  return buildExecutionStages(options)
}

/**
 * @param {{
 *   currentStage: 'sample' | 'structure' | 'output',
 *   preview: any,
 *   sampleUpload: any,
 *   run: any,
 *   videoUrl: string,
 *   localVideoUrl?: string,
 *   localVideoFileName?: string
 * }} options
 */
export function buildWorkspaceStageView({
  currentStage,
  preview,
  sampleUpload,
  run,
  videoUrl,
  localVideoUrl,
  localVideoFileName,
}) {
  const stageCopy = WORKSPACE_STAGE_COPY[currentStage]
  const stageDescription = preview?.template?.rhythm_summary || stageCopy.description
  const displayVideoUrl = currentStage === 'output' && videoUrl ? videoUrl : sampleUpload?.public_url || localVideoUrl
  const displayVideoName =
    currentStage === 'output' && run?.run_id
      ? `${run.run_id}.mp4`
      : localVideoFileName || sampleUpload?.filename || '尚未上传参考视频'
  const stageStates = {
    sample: { enabled: true, completed: Boolean(sampleUpload) },
    structure: { enabled: Boolean(sampleUpload || preview), completed: Boolean(preview) },
    output: { enabled: Boolean(videoUrl), completed: Boolean(videoUrl) },
  }

  return {
    stageTitle: preview ? stageCopy.title : '样例输入',
    stageDescription,
    displayVideoUrl,
    displayVideoName,
    stageStates,
  }
}
