type TextEvidenceItem = {
  text?: unknown
}

type TextEvidenceNode = {
  ocr_texts?: TextEvidenceItem[]
  transcript_texts?: TextEvidenceItem[]
}

type TextEvidenceGraph = {
  shots?: TextEvidenceNode[]
  analysis_units?: TextEvidenceNode[]
} | null | undefined

function hasText(items: TextEvidenceItem[] | undefined): boolean {
  return Boolean(items?.some((item) => typeof item.text === 'string' && item.text.trim().length > 0))
}

export function shotEvidenceGraphHasTextEvidence(graph: TextEvidenceGraph): boolean {
  if (!graph) return false
  const nodes = [...(graph.shots || []), ...(graph.analysis_units || [])]
  return nodes.some((node) => hasText(node.ocr_texts) || hasText(node.transcript_texts))
}
