import React, { useState } from 'react'
import type { GraphPresentationViewModel } from './AnalysisSummaryPanel'
import { localizeShotName } from './localize'

function graphNodeTypeLabel(nodeType: GraphPresentationViewModel['nodes'][number]['nodeType']) {
  if (nodeType === 'segment') return '段落'
  if (nodeType === 'unit') return '单元'
  if (nodeType === 'shot') return '镜头'
  if (nodeType === 'text') return '文本'
  return '缺口'
}

type GraphNode = GraphPresentationViewModel['nodes'][number]

function GraphNodeButton({
  node,
  active,
  onClick,
}: {
  node: GraphNode
  active: boolean
  onClick: (node: GraphNode) => void
}) {
  return (
    <button className="graph-node-pill" data-type={node.nodeType} data-active={active} type="button" onClick={() => onClick(node)}>
      <span>{graphNodeTypeLabel(node.nodeType)}</span>
      <strong>{node.label}</strong>
    </button>
  )
}

function GraphConnector({ label }: { label: string }) {
  return (
    <div className="graph-map-connector" aria-hidden="true">
      <svg viewBox="0 0 120 80" preserveAspectRatio="none">
        <path d="M 4 40 C 34 40, 40 14, 62 14 L 116 14" />
        <path d="M 4 40 C 34 40, 40 40, 62 40 L 116 40" />
        <path d="M 4 40 C 34 40, 40 66, 62 66 L 116 66" />
      </svg>
      <span>{label}</span>
    </div>
  )
}

function nodeShotKey(shotIndex: number) {
  return `shot_${shotIndex}`
}

function uniqueNodes(nodes: GraphNode[]) {
  const seen = new Set<string>()
  return nodes.filter((node) => {
    if (seen.has(node.id)) return false
    seen.add(node.id)
    return true
  })
}

function relatedNodes(
  sourceId: string,
  graph: GraphPresentationViewModel,
  nodeLookup: Map<string, GraphNode>,
  fallback: GraphNode[],
) {
  const related = graph.edges
    .filter((edge) => edge.source === sourceId)
    .map((edge) => nodeLookup.get(edge.target))
    .filter((node): node is GraphNode => Boolean(node))
  return related.length ? related : fallback
}

export default function GraphMapPanel({ graph }: { graph: GraphPresentationViewModel | null | undefined }) {
  const [selectedNodeId, setSelectedNodeId] = useState('')
  if (!graph?.nodes.length) return null
  const nodeLookup = new Map(graph.nodes.map((node) => [node.id, node]))
  const segmentNodes = graph.nodes.filter((node) => node.nodeType === 'segment')
  const unitNodes = graph.nodes.filter((node) => node.nodeType === 'unit')
  const shotNodes = graph.nodes.filter((node) => node.nodeType === 'shot')
  const selectedNode = nodeLookup.get(selectedNodeId) || segmentNodes[0] || unitNodes[0] || shotNodes[0]
  const rows = segmentNodes.length
    ? segmentNodes
    : unitNodes.length
      ? [
          {
            id: 'all_units',
            label: '分析单元',
            nodeType: 'segment' as const,
            summary: '当前图谱没有段落节点，先展示分析单元和镜头关系。',
            shotIndices: unitNodes.flatMap((node) => node.shotIndices),
            confidence: 0,
          },
        ]
      : []

  return (
    <section className="graph-presentation graph-map-panel" aria-label="图谱结构概要">
      <div className="graph-presentation-head">
        <span>图谱结构概要</span>
        <strong>段落 → 分析单元 → 镜头</strong>
      </div>

      <div className="graph-map-labels" aria-hidden="true">
        <span>段落</span>
        <span>分析单元</span>
        <span>镜头</span>
      </div>

      <div className="graph-map">
        {rows.map((segment) => {
          const units = segment.id === 'all_units' ? unitNodes : relatedNodes(segment.id, graph, nodeLookup, unitNodes)
          const shots = uniqueNodes(
            units.flatMap((unit) =>
              relatedNodes(
                unit.id,
                graph,
                nodeLookup,
                unit.shotIndices.map((shotIndex) => nodeLookup.get(nodeShotKey(shotIndex))).filter((node): node is GraphNode => Boolean(node)),
              ),
            ),
          )
          return (
            <div className="graph-map-row" key={segment.id}>
              <div className="graph-map-stack">
                <GraphNodeButton node={segment} active={selectedNode?.id === segment.id} onClick={(node) => setSelectedNodeId(node.id)} />
              </div>
              <GraphConnector label="覆盖" />
              <div className="graph-map-stack">
                {units.slice(0, 4).map((unit) => (
                  <GraphNodeButton key={unit.id} node={unit} active={selectedNode?.id === unit.id} onClick={(node) => setSelectedNodeId(node.id)} />
                ))}
              </div>
              <GraphConnector label="包含" />
              <div className="graph-map-stack">
                {shots.slice(0, 6).map((shot) => (
                  <GraphNodeButton key={shot.id} node={shot} active={selectedNode?.id === shot.id} onClick={(node) => setSelectedNodeId(node.id)} />
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {selectedNode ? (
        <div className="graph-node-detail">
          <div>
            <span>{graphNodeTypeLabel(selectedNode.nodeType)}</span>
            <strong>{selectedNode.label}</strong>
          </div>
          <p>{selectedNode.summary || '这个节点暂无摘要，先按图谱关系查看它覆盖的镜头。'}</p>
          <em>{selectedNode.shotIndices.length ? `覆盖 ${selectedNode.shotIndices.map((index) => localizeShotName(index)).join(' / ')}` : '暂无镜头索引'}</em>
        </div>
      ) : null}
    </section>
  )
}
