// 노드 그룹 템플릿: 자주 쓰는 구성을 저장하고 다른 프로젝트에서 다시 놓는다.
// 소재 파일 경로는 템플릿에 넣지 않는다. 새 프로젝트에서 다시 연결한다.

import { downstreamIds } from './graph'
import { useStudioStore } from './store'
import type { StudioEdge, StudioNode } from './types'

export interface TemplateDocument {
  nodes: StudioNode[]
  edges: StudioEdge[]
}

function withoutAssets(node: StudioNode): StudioNode {
  if (node.kind !== 'asset') return node
  const config = { ...node.config }
  delete config.assetId
  delete config.assetName
  return { ...node, config, results: [] }
}

/** 선택한 노드와 그 하위 노드를 템플릿 문서로 만든다. 선택이 없으면 전체를 쓴다. */
export function templateFromSelection(): TemplateDocument {
  const state = useStudioStore.getState()
  const selection = state.selection
  const seed = selection?.type === 'node' ? selection.id : ''
  const ids = new Set<string>()
  if (seed) {
    ids.add(seed)
    for (const id of downstreamIds(state.doc.edges, seed)) ids.add(id)
  } else {
    for (const node of state.doc.nodes) ids.add(node.id)
  }
  const nodes = state.doc.nodes.filter((node) => ids.has(node.id)).map(withoutAssets)
  const edges = state.doc.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target))
  return { nodes, edges }
}

/** 템플릿 문서를 캔버스에 놓는다. 노드 id는 새로 발급하고 위치는 기준점에 맞춘다. */
export function insertTemplate(documentJson: string, origin: { x: number; y: number }): number {
  const parsed = JSON.parse(documentJson) as Partial<TemplateDocument>
  const nodes = Array.isArray(parsed.nodes) ? parsed.nodes : []
  if (nodes.length === 0) throw new Error('템플릿에 노드가 없습니다.')
  const minX = Math.min(...nodes.map((node) => node.position?.x ?? 0))
  const minY = Math.min(...nodes.map((node) => node.position?.y ?? 0))
  const store = useStudioStore.getState()
  const idMap = new Map<string, string>()
  for (const node of nodes) {
    const id = store.addNode(
      node.kind,
      { x: origin.x + ((node.position?.x ?? 0) - minX), y: origin.y + ((node.position?.y ?? 0) - minY) },
      { title: node.title, config: node.config },
    )
    idMap.set(node.id, id)
  }
  const edges = Array.isArray(parsed.edges) ? parsed.edges : []
  for (const edge of edges) {
    const source = idMap.get(edge.source)
    const target = idMap.get(edge.target)
    if (!source || !target) continue
    useStudioStore.getState().addEdge({
      source,
      sourceHandle: edge.sourceHandle,
      target,
      targetHandle: edge.targetHandle,
      kind: edge.kind,
    })
  }
  return nodes.length
}
