const EXACT_LABELS: Record<string, string> = {
  hook: '开头钩子',
  pain_point: '痛点铺垫',
  product_intro: '产品引入',
  product_demo: '产品演示',
  proof: '信任证明',
  comparison: '对比展示',
  transition: '转场承接',
  offer: '利益点',
  cta: '行动引导',
  atmosphere: '氛围镜头',
  unknown: '功能未识别',
  fast: '快节奏',
  medium: '中等节奏',
  slow: '慢节奏',
  adjacent_cut: '相邻剪切',
  contrast: '对比关系',
  continuation: '连续承接',
  semantic_shift: '语义转折',
  title_card: '标题卡',
  sticker: '贴纸',
  caption: '字幕',
  start: '开头帧',
  middle: '中间帧',
  end: '结尾帧',
  uploaded: '用户上传',
  fixture: '样例素材匹配',
}

const PHRASE_REPLACEMENTS: Array<[RegExp, string | ((substring: string, ...args: string[]) => string)]> = [
  [
    /Only\s+(\d+)\s+镜头\s+are available,\s+so relation and rhythm aggregation are structurally limited\./gi,
    '当前只有 $1 个镜头可用，镜头关系和节奏聚合会受到结构限制。',
  ],
  [
    /Only\s+(\d+)\s+镜头\s+are available,\s+so beat\/segment granularity is coarse\./gi,
    '当前只有 $1 个镜头可用，节拍和段落划分粒度会比较粗。',
  ],
  [
    /Both segments are single-shot segments;\s*internal beat subdivision inside 镜头\s+(\d+) is not strongly evidenced by explicit graph relations\./gi,
    '两个段落都是单镜头段落；镜头 $1 内部继续拆分节拍，缺少明确的图关系证据。',
  ],
  [
    /镜头\s+(\d+) contains OCR noise and some low-confidence English\/Chinese fragments;\s*packaging\/title conclusions rely on repeated higher-confidence OCR plus 理解结果 summaries\./gi,
    '镜头 $1 存在 OCR 噪声和低置信度中英文片段；包装/标题判断主要依赖重复出现且置信度较高的 OCR，以及理解结果摘要。',
  ],
  [
    /镜头\s+(\d+) contains OCR recognition errors in some English and a few Chinese fragments;\s*aggregation relies on repeated high-confidence core text and unit 理解结果\./gi,
    '镜头 $1 存在部分英文和少量中文片段的 OCR 识别错误；聚合主要依赖重复出现的高置信度核心文本和分析单元理解结果。',
  ],
  [
    /No ASR support for 镜头\s+(\d+);\s*beat and packaging interpretation there is based on OCR and 理解结果 only\./gi,
    '镜头 $1 没有 ASR 口播证据；节拍和包装判断仅基于 OCR 与理解结果。',
  ],
  [
    /No explicit transition effect evidence beyond adjacency timing;\s*"?hard cut"? is inferred conservatively from the provided relation\./gi,
    '除相邻时序外，图中没有明确的转场效果证据；“硬切”是基于已提供关系的保守推断。',
  ],
  [
    /Transition style beyond adjacency\/hard cut is not directly evidenced in the graph\./gi,
    '图中没有直接证据支持相邻硬切以外的转场风格判断。',
  ],
  [
    /镜头\s+(\d+)\s+包括 platform watermark\/account-related OCR,\s*but its exact packaging role inside the poster segment is less explicit than in 镜头\s+(\d+)\./gi,
    '镜头 $1 包含平台水印/账号相关 OCR，但它在海报段落中的具体包装作用不如镜头 $2 明确。',
  ],
  [
    /Rhythm inference is limited by sparse shot count and lacks finer intra-shot motion timing evidence\./gi,
    '节奏推断受镜头数量稀疏限制，并且缺少更细的镜头内部运动时序证据。',
  ],
  [/analysis[_\s]+units?\.?\s*(分析单元\s*\d+)/gi, '$1'],
  [/analysis[_\s]+units?\.?\s*unit[_\s-]?(\d+)/gi, '分析单元 $1 '],
  [/analysis[_\s]+units?\.?/gi, '分析单元 '],
  [/understanding[._\s]+visual[._\s]+summary/gi, '画面理解'],
  [/understanding[._\s]+text[._\s]+summary/gi, '文字理解'],
  [/understanding[._\s]+packaging[._\s]+signals\s+includes/gi, '包装信号包括'],
  [/packaging[._\s]+signals\s+includes/gi, '包装信号包括'],
  [/visual[._\s]+summary/gi, '画面理解'],
  [/text[._\s]+summary/gi, '文字理解'],
  [/packaging[._\s]+signals/gi, '包装信号'],
  [/\bunderstanding\b/gi, '理解结果'],
  [/\bincludes\b/gi, '包括'],
  [/\bShot\s*(\d+)/gi, '镜头 $1'],
  [/\bshots\s*/gi, '镜头 '],
  [/\bframe\s*(\d+)/gi, '帧 $1'],
  [/\bunit_(\d+(?:_\d+)*)\b/gi, (_match, id: string) => `分析单元 ${id.replaceAll('_', '-')}`],
  [/\bOpenAI\b/g, 'AI 模型'],
  [/Service temporarily unavailable/gi, '服务暂时不可用'],
  [/shot understanding failed/gi, '镜头理解失败'],
  [/unit understanding failed/gi, '分析单元理解失败'],
  [/no extracted frames/gi, '未抽取到可用画面'],
  [/adjacent temporal continuity/gi, '相邻时间连续'],
  [/baseline temporal continuity/gi, '基础时间连续关系'],
  [/title[_ ]card/gi, '标题卡'],
  [/solid blue transition card/gi, '蓝色转场卡'],
  [/opening beat/gi, '开头节拍'],
  [/\brelation and rhythm aggregation\b/gi, '关系和节奏聚合'],
  [/\bstructurally limited\b/gi, '受到结构限制'],
  [/\bBoth segments\b/gi, '两个段落'],
  [/\bsingle-shot segments\b/gi, '单镜头段落'],
  [/\binternal beat subdivision\b/gi, '内部节拍细分'],
  [/\bexplicit graph relations\b/gi, '明确的图关系证据'],
  [/\bOCR noise\b/gi, 'OCR 噪声'],
  [/\bOCR recognition errors\b/gi, 'OCR 识别错误'],
  [/\blow-confidence\b/gi, '低置信度'],
  [/\baggregation relies on\b/gi, '聚合依赖'],
  [/\brepeated high-confidence core text\b/gi, '重复出现的高置信度核心文本'],
  [/\bunit 理解结果\b/gi, '分析单元理解结果'],
  [/\bNo ASR support\b/gi, '没有 ASR 口播证据'],
  [/\bNo explicit transition effect evidence beyond adjacency timing\b/gi, '除相邻时序外，没有明确转场效果证据'],
  [/\bbeat and packaging interpretation\b/gi, '节拍和包装判断'],
  [/\bOCR and 理解结果 only\b/gi, '仅基于 OCR 与理解结果'],
  [/\bbeat\/segment granularity\b/gi, '节拍/段落粒度'],
  [/\bcoarse\b/gi, '较粗'],
  [/\bTransition style\b/gi, '转场风格'],
  [/\badjacency\/hard cut\b/gi, '相邻硬切'],
  [/\bhard cut\b/gi, '硬切'],
  [/\bis inferred conservatively\b/gi, '是保守推断'],
  [/\bprovided relation\b/gi, '已提供的关系'],
  [/\bnot directly evidenced in the graph\b/gi, '图中没有直接证据支持'],
  [/\bplatform watermark\/account-related OCR\b/gi, '平台水印/账号相关 OCR'],
  [/\bposter segment\b/gi, '海报段落'],
  [/\bless explicit\b/gi, '不够明确'],
  [/\bRhythm inference\b/gi, '节奏推断'],
  [/\bsparse shot count\b/gi, '镜头数量稀疏'],
  [/\bfiner intra-shot motion timing evidence\b/gi, '更细的镜头内部运动时序证据'],
  [/\bare available\b/gi, '可用'],
  [/\bcontains\b/gi, '包含'],
]

export function localizeLabel(value: string, fallback = '证据不足') {
  const normalized = value.trim()
  if (!normalized) return fallback
  const exact = EXACT_LABELS[normalized.toLowerCase()]
  if (exact) return exact
  return localizeText(normalized, fallback)
}

export function localizeText(value: string, fallback = '证据不足') {
  let text = value.trim()
  if (!text) return fallback

  const exact = EXACT_LABELS[text.toLowerCase()]
  if (exact) return exact

  for (const [pattern, replacement] of PHRASE_REPLACEMENTS) {
    text =
      typeof replacement === 'string'
        ? text.replace(pattern, replacement)
        : text.replace(pattern, replacement as (...args: string[]) => string)
  }

  text = text.replace(/_/g, ' ')
  if (isMostlyEnglish(text)) return fallback
  return text
}

export function localizeShotName(index: number) {
  return `镜头 ${index}`
}

export function localizeUnitName(unitId: string) {
  const normalized = unitId.replace(/^unit_/i, '').replaceAll('_', '-')
  return normalized ? `分析单元 ${normalized}` : '分析单元'
}

export function isMostlyEnglish(value: string) {
  const normalized = value.trim()
  if (!normalized) return false
  const hasLatinLetters = /[a-zA-Z]/.test(normalized)
  const hasCjkText = /[\u3400-\u9fff]/.test(normalized)
  return hasLatinLetters && !hasCjkText
}
