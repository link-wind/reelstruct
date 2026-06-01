const API_ORIGIN = process.env.NEXT_PUBLIC_REELSTRUCT_API_ORIGIN || 'http://127.0.0.1:8010'

export type MaterialTaskStatus = '待补拍' | '已拍' | '已交付'
export type OutputVariant = 'standard' | 'high_click' | 'high_conversion' | 'fast_rhythm'

export function apiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path
  return `${API_ORIGIN}${path.startsWith('/') ? path : `/${path}`}`
}

export function mediaUrl(path: string): string {
  if (!path || /^blob:|^data:|^https?:\/\//.test(path)) return path
  const [pathname, query = ''] = path.split('?', 2)
  const normalizedPath = `${pathname.startsWith('/') ? pathname : `/${pathname}`}${query ? `?${query}` : ''}`
  return `${API_ORIGIN}${normalizedPath}`
}

export async function requestJson<T>(url: string, options: { method: 'POST'; body: unknown }): Promise<T> {
  const response = await fetch(apiUrl(url), {
    method: options.method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options.body),
  })

  if (!response.ok) {
    throw new Error(`请求失败：${response.status} ${await readApiError(response)}`)
  }

  return response.json() as Promise<T>
}

export async function readApiError(response: Response): Promise<string> {
  const text = await response.text()
  if (!text) return response.statusText || '未知错误'
  try {
    const payload = JSON.parse(text) as { detail?: unknown }
    if (typeof payload.detail === 'string') return payload.detail
  } catch {
    // Keep raw text when the backend does not return JSON.
  }
  return text
}

export function normalizeSampleUpload(upload: any): any {
  return {
    ...upload,
    public_url: mediaUrl(upload.public_url),
    keyframes: (upload.keyframes || []).map((keyframe: any) => ({
      ...keyframe,
      public_url: mediaUrl(keyframe.public_url),
    })),
  }
}

export function normalizeUserSlotAsset(asset: any): any {
  return {
    ...asset,
    public_url: mediaUrl(asset.public_url),
  }
}

export function splitList(value: string): string[] {
  return value
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

export function updateListItem(items: string[], index: number, value: string): string[] {
  return items.map((item, itemIndex) => (itemIndex === index ? value : item))
}

export function removeListItem(items: string[], index: number): string[] {
  return items.filter((_, itemIndex) => itemIndex !== index)
}

export function moveListItem(items: string[], index: number, delta: number): string[] {
  const nextIndex = index + delta
  if (nextIndex < 0 || nextIndex >= items.length) return items
  const nextItems = [...items]
  const [item] = nextItems.splice(index, 1)
  nextItems.splice(nextIndex, 0, item)
  return nextItems
}

export function buildSlotDrafts(preview: any): Record<string, { target_message: string; sample_evidence: string; asset_strategy: string }> {
  const slotLookup = new Map<string, any>((preview?.template?.script_pattern || []).map((slot: any) => [slot.id, slot]))
  return Object.fromEntries(
    (preview?.transfer_plan?.mappings || []).map((mapping: any) => [
      mapping.slot_id,
      {
        target_message: mapping.target_message,
        sample_evidence: slotLookup.get(mapping.slot_id)?.sample_evidence || '',
        asset_strategy: mapping.asset_strategy,
      },
    ]),
  )
}

export function buildMappingOverrides(preview: any, drafts: Record<string, any>): any[] {
  const slotLookup = new Map<string, any>((preview?.template?.script_pattern || []).map((slot: any) => [slot.id, slot]))
  return (preview?.transfer_plan?.mappings || [])
    .map((mapping: any) => ({
      slot_id: mapping.slot_id,
      target_message: (drafts[mapping.slot_id]?.target_message ?? '').trim(),
      sample_evidence: (drafts[mapping.slot_id]?.sample_evidence ?? '').trim(),
      asset_strategy: (drafts[mapping.slot_id]?.asset_strategy ?? '').trim(),
      original_message: mapping.target_message,
      original_sample_evidence: slotLookup.get(mapping.slot_id)?.sample_evidence ?? '',
      original_asset_strategy: mapping.asset_strategy,
    }))
    .filter(
      (item: any) =>
        (item.target_message && item.target_message !== item.original_message) ||
        (item.sample_evidence && item.sample_evidence !== item.original_sample_evidence) ||
        (item.asset_strategy && item.asset_strategy !== item.original_asset_strategy),
    )
    .map(({ slot_id, target_message, sample_evidence, asset_strategy }: any) => ({
      slot_id,
      target_message,
      sample_evidence,
      asset_strategy,
    }))
}

function labelForSlot(slotId: string): string {
  const labelMap: Record<string, string> = {
    hook: '开头钩子',
    selling_points: '卖点展开',
    usage: '使用过程',
    cta: 'CTA',
  }
  return labelMap[slotId] || slotId
}

function formatSupplementOptions(options: any[]): string {
  if (!options.length) return '暂无结构化补全方案'
  return options.map((option) => `${option.method}-${option.action}`).join('；')
}

function buildMaterialRequestSheetEntry(item: any, status: MaterialTaskStatus, selectedMethod?: string): string {
  const gap = item.gap
  if (!gap) {
    return [
      `当前状态：${status}`,
      `已补齐素材：${item.slot.required_asset}`,
      `补位方式：已进入可用素材池，重新生成时直接参与视频重组`,
    ].join('\n')
  }
  const selectedOption = gap.supplement_options.find((option: any) => option.method === selectedMethod)
  return [
    `当前状态：${status}`,
    `缺口素材：${gap.missing_asset}`,
    `补位方式：${gap.fill_strategy}`,
    `首选补全：${gap.primary_supplement || gap.fill_strategy}`,
    `已选补全：${selectedOption ? `${selectedOption.method}-${selectedOption.action}` : '未选择，默认使用首选补全'}`,
    `补全方案：${formatSupplementOptions(gap.supplement_options)}`,
    `建议镜头：${gap.suggested_shots.join('；')}`,
    `检查清单：${gap.pickup_checklist.join('；')}`,
  ].join('\n')
}

export function buildMaterialRequestSheetText(
  items: any[],
  statusLookup: Record<string, MaterialTaskStatus>,
  supplementSelection: Record<string, string> = {},
): string {
  if (!items.length) return ''
  return [
    '素材需求单',
    '待执行素材任务',
    '',
    ...items.flatMap((item, index) => {
      const status = statusLookup[item.task.slot_id] ?? item.task.status
      return [
        `${index + 1}. ${labelForSlot(item.task.slot_id)} / ${item.gap?.suggested_asset_type || item.slot.required_asset}`,
        buildMaterialRequestSheetEntry(item, status, supplementSelection[item.task.slot_id]),
        '',
      ]
    }),
  ].join('\n').trim()
}

export function buildMaterialRequestSheetPayload(
  requestSheetIds: string[],
  statusLookup: Record<string, MaterialTaskStatus>,
): Array<{ slot_id: string; status: MaterialTaskStatus }> {
  return requestSheetIds.map((slotId) => ({
    slot_id: slotId,
    status: statusLookup[slotId] ?? '待补拍',
  }))
}

export function buildSupplementSelectionPayload(selection: Record<string, string>): Array<{ slot_id: string; method: string }> {
  return Object.entries(selection)
    .filter(([, method]) => method.trim())
    .map(([slotId, method]) => ({
      slot_id: slotId,
      method,
    }))
}

export function analysisSourceLabel(source: 'rule' | 'ai' | 'fallback'): string {
  if (source === 'ai') return 'AI 视频结构拆解'
  if (source === 'fallback') return '基础兜底拆解'
  return '基础规则拆解'
}

export function analysisSourceClass(source: 'rule' | 'ai' | 'fallback'): string {
  if (source === 'ai') return 'bg-sky-50 text-sky-700'
  if (source === 'fallback') return 'bg-amber-50 text-amber-800'
  return 'bg-slate-100 text-slate-600'
}

export function formatRunTime(value: string): string {
  if (!value) return '时间未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

export function mergeShotEvidenceGraphs(current: any | null, next: any): any {
  if (!current) return normalizeShotEvidenceGraph(next)
  const normalizedCurrent = normalizeShotEvidenceGraph(current)
  const normalizedNext = normalizeShotEvidenceGraph(next)

  const nextShotLookup = new Map<number, any>(normalizedNext.shots.map((node: any) => [node.shot.index, node]))
  const mergedShots = normalizedCurrent.shots.map((node: any) => {
    const nextNode = nextShotLookup.get(node.shot.index)
    if (!nextNode) return node
    return {
      ...node,
      frames: mergeByKey(node.frames, nextNode.frames, (frame: any) => `${frame.shot_index}:${frame.frame_index}:${frame.time}`),
      ocr_texts: mergeByKey(
        node.ocr_texts,
        nextNode.ocr_texts,
        (item: any) => `${item.shot_index}:${item.frame_index}:${item.frame_time}:${item.text}`,
      ),
      transcript_texts: mergeByKey(
        node.transcript_texts,
        nextNode.transcript_texts,
        (item: any) => `${item.shot_index}:${item.source_start}:${item.source_end}:${item.text}`,
      ),
      understanding: node.understanding || nextNode.understanding,
    }
  })

  for (const nextNode of normalizedNext.shots) {
    if (!normalizedCurrent.shots.some((node: any) => node.shot.index === nextNode.shot.index)) {
      mergedShots.push(nextNode)
    }
  }

  return {
    ...normalizedCurrent,
    shots: mergedShots,
    analysis_units: mergeAnalysisUnits(normalizedCurrent.analysis_units, normalizedNext.analysis_units),
    relations: normalizedCurrent.relations.length ? normalizedCurrent.relations : normalizedNext.relations,
    warnings: mergeByKey(normalizedCurrent.warnings, normalizedNext.warnings, (warning: string) => warning),
  }
}

function mergeAnalysisUnits(current: any[], next: any[]): any[] {
  const unitLookup = new Map(current.map((unit) => [analysisUnitMergeKey(unit), normalizeAnalysisUnit(unit)]))
  for (const rawNextUnit of next) {
    const nextUnit = normalizeAnalysisUnit(rawNextUnit)
    const unitKey = analysisUnitMergeKey(nextUnit)
    const currentUnit = unitLookup.get(unitKey)
    if (!currentUnit) {
      unitLookup.set(unitKey, nextUnit)
      continue
    }
    unitLookup.set(unitKey, {
      ...currentUnit,
      unit_id: analysisUnitStableId(currentUnit),
      representative_frames: mergeByKey(
        currentUnit.representative_frames,
        nextUnit.representative_frames,
        (frame: any) => `${frame.shot_index}:${frame.frame_index}:${frame.time}`,
      ),
      ocr_texts: mergeByKey(
        currentUnit.ocr_texts,
        nextUnit.ocr_texts,
        (item: any) => `${item.shot_index}:${item.frame_index}:${item.frame_time}:${item.text}`,
      ),
      transcript_texts: mergeByKey(
        currentUnit.transcript_texts,
        nextUnit.transcript_texts,
        (item: any) => `${item.shot_index}:${item.source_start}:${item.source_end}:${item.text}`,
      ),
      understanding: currentUnit.understanding || nextUnit.understanding,
    })
  }

  return [...unitLookup.values()].sort((left: any, right: any) => left.start - right.start)
}

function normalizeShotEvidenceGraph(graph: any): any {
  return {
    ...graph,
    shots: graph.shots || [],
    analysis_units: (graph.analysis_units || []).map(normalizeAnalysisUnit),
    relations: graph.relations || [],
    warnings: graph.warnings || [],
  }
}

function normalizeAnalysisUnit(unit: any): any {
  const stableUnitId = analysisUnitStableId(unit)
  return {
    ...unit,
    unit_id: stableUnitId,
    understanding: {
      ...(unit.understanding || {}),
      unit_id: stableUnitId,
    },
  }
}

function analysisUnitStableId(unit: any): string {
  const key = analysisUnitMergeKey(unit).replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '')
  return key ? `unit_${key}` : unit.unit_id
}

function analysisUnitMergeKey(unit: any): string {
  return unit.shot_indices?.length ? unit.shot_indices.join(':') : `${unit.start}:${unit.end}`
}

function mergeByKey<T>(left: T[] = [], right: T[] = [], keyOf: (item: T) => string): T[] {
  const seen = new Set<string>()
  const merged: T[] = []
  for (const item of [...left, ...right]) {
    const key = keyOf(item)
    if (seen.has(key)) continue
    seen.add(key)
    merged.push(item)
  }
  return merged
}
