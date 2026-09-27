// 그래프 규칙: 포트 자료형 검사, 순환 방지, 하위 노드 전파.

import { nodeSpec } from './catalog'
import { assetPortType, type AssetKind, type Port, type StudioAsset, type StudioDocument, type StudioEdge, type StudioNode } from './types'

export function assetKindOf(doc: StudioDocument, node: StudioNode): AssetKind {
  const assetId = typeof node.config.assetId === 'string' ? node.config.assetId : ''
  const asset = doc.assets.find((item) => item.id === assetId)
  return asset?.kind ?? 'other'
}

export function inputsOf(node: StudioNode): Port[] {
  return nodeSpec(node.kind).inputs
}

export function outputPortsFor(node: StudioNode, asset: StudioAsset | undefined): Port[] {
  if (node.kind === 'asset') {
    return [{ id: 'out', label: '소재', type: assetPortType(asset?.kind ?? 'other') }]
  }
  if (node.kind === 'select') {
    if (!asset) return []
    return [{ id: 'out', label: '선택 소재', type: assetPortType(asset.kind) }]
  }
  return nodeSpec(node.kind).outputs
}

export function outputsOf(doc: StudioDocument, node: StudioNode): Port[] {
  return outputPortsFor(node, referencedAssetOf(doc.assets, node))
}

export function referencedAssetOf(assets: StudioAsset[], node: StudioNode): StudioAsset | undefined {
  const key = node.kind === 'asset' ? 'assetId' : node.kind === 'select' ? 'selectedAssetId' : ''
  if (!key) return undefined
  const assetId = typeof node.config[key] === 'string' ? (node.config[key] as string) : ''
  if (!assetId) return undefined
  return assets.find((item) => item.id === assetId)
}

export function specContextIn(node: StudioNode): boolean {
  return nodeSpec(node.kind).contextIn
}

export function specContextOut(node: StudioNode): boolean {
  return nodeSpec(node.kind).contextOut
}

export function wouldCreateCycle(edges: StudioEdge[], source: string, target: string): boolean {
  if (source === target) return true
  const adjacency = new Map<string, string[]>()
  for (const edge of edges) {
    const list = adjacency.get(edge.source) ?? []
    list.push(edge.target)
    adjacency.set(edge.source, list)
  }
  const stack = [target]
  const seen = new Set<string>()
  while (stack.length > 0) {
    const current = stack.pop() as string
    if (current === source) return true
    if (seen.has(current)) continue
    seen.add(current)
    for (const next of adjacency.get(current) ?? []) stack.push(next)
  }
  return false
}

export interface ConnectionAttempt {
  source: string
  sourceHandle: string | null
  target: string
  targetHandle: string | null
  kind: 'data' | 'context'
}

export type ConnectionCheck = { ok: true } | { ok: false; reason: string }

export function evaluateConnection(doc: StudioDocument, attempt: ConnectionAttempt): ConnectionCheck {
  const sourceNode = doc.nodes.find((node) => node.id === attempt.source)
  const targetNode = doc.nodes.find((node) => node.id === attempt.target)
  if (!sourceNode || !targetNode) return { ok: false, reason: '연결할 노드를 찾을 수 없습니다.' }
  if (sourceNode.id === targetNode.id) return { ok: false, reason: '노드 자신에는 연결할 수 없습니다.' }

  if (attempt.kind === 'context') {
    if (attempt.sourceHandle !== 'context' || attempt.targetHandle !== 'context') {
      return { ok: false, reason: '맥락 연결은 맥락 포트끼리 연결합니다.' }
    }
    if (!specContextOut(sourceNode)) return { ok: false, reason: `${nodeSpec(sourceNode.kind).label} 노드에는 맥락 출력이 없습니다.` }
    if (!specContextIn(targetNode)) return { ok: false, reason: `${nodeSpec(targetNode.kind).label} 노드에는 맥락 입력이 없습니다.` }
  } else {
    const sourcePort = outputsOf(doc, sourceNode).find((port) => port.id === attempt.sourceHandle)
    if (!sourcePort) return { ok: false, reason: '출력 포트를 찾을 수 없습니다.' }
    const targetPort = inputsOf(targetNode).find((port) => port.id === attempt.targetHandle)
    if (!targetPort) return { ok: false, reason: '입력 포트를 찾을 수 없습니다.' }
    if (sourcePort.type !== targetPort.type) {
      const hint = sourcePort.type === 'Json' || targetPort.type === 'Json'
        ? ' Json 결과는 형식 변환이 확인된 뒤에 연결할 수 있습니다.'
        : ''
      return {
        ok: false,
        reason: `자료형이 맞지 않습니다: ${sourcePort.type} → ${targetPort.type}.${hint}`,
      }
    }
  }

  if (wouldCreateCycle(doc.edges, attempt.source, attempt.target)) {
    return { ok: false, reason: '순환 연결은 만들 수 없습니다. 반복 수정은 노드를 다시 실행해 처리합니다.' }
  }
  return { ok: true }
}

export function downstreamIds(edges: StudioEdge[], start: string): string[] {
  const adjacency = new Map<string, string[]>()
  for (const edge of edges) {
    const list = adjacency.get(edge.source) ?? []
    list.push(edge.target)
    adjacency.set(edge.source, list)
  }
  const result: string[] = []
  const seen = new Set<string>([start])
  const stack = [...(adjacency.get(start) ?? [])]
  while (stack.length > 0) {
    const current = stack.pop() as string
    if (seen.has(current)) continue
    seen.add(current)
    result.push(current)
    for (const next of adjacency.get(current) ?? []) stack.push(next)
  }
  return result
}

export function upstreamIds(edges: StudioEdge[], start: string): string[] {
  const reverse: StudioEdge[] = edges.map((edge) => ({ ...edge, source: edge.target, target: edge.source }))
  return downstreamIds(reverse, start)
}

export function configSummary(node: StudioNode): string {
  const value = (key: string): string => {
    const raw = node.config[key]
    return typeof raw === 'string' ? raw.trim() : typeof raw === 'number' ? String(raw) : ''
  }
  const spec = nodeSpec(node.kind)
  if (node.kind === 'asset') return typeof node.config.assetName === 'string' ? node.config.assetName : '소재 미지정'
  if (node.kind === 'select') return typeof node.config.selectedName === 'string' ? `선택: ${node.config.selectedName}` : '후보 선택 전'
  const prompt = value('prompt') || value('copy') || value('brief') || value('goal') || value('notes')
  if (prompt) return prompt.replace(/\s+/g, ' ').slice(0, 72)
  const tool = value('tool') || value('workflow')
  if (tool) return `도구: ${tool}`
  return spec.description.slice(0, 64)
}
