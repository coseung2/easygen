// 제작 문서 편집 상태: 노드·연결·샷·소재, 되돌리기 기록, 저장 상태.

import { create } from 'zustand'
import { nodeSpec } from './catalog'
import { downstreamIds, evaluateConnection, type ConnectionAttempt, type ConnectionCheck } from './graph'
import {
  emptyDocument,
  uid,
  type AssetKind,
  type ConfigValue,
  type NodeKind,
  type NodeStatus,
  type Shot,
  type StudioAsset,
  type StudioDocument,
  type StudioEdge,
  type StudioNode,
  type StudioRunRow,
} from './types'

const HISTORY_LIMIT = 60

export type StudioSelection = { type: 'node' | 'shot' | 'asset'; id: string } | null

export type SaveState = 'idle' | 'saving' | 'saved' | 'error'

export interface AssetInput {
  name: string
  kind: AssetKind
  storedPath: string
  url: string
  sizeBytes: number
  hash: string
  source: 'imported' | 'browser'
  ephemeral?: boolean
}

export interface NodeOverrides {
  title?: string
  config?: Record<string, ConfigValue>
  status?: NodeStatus
}

interface StudioState {
  projectId: string
  projectName: string
  revision: number
  doc: StudioDocument
  savedDoc: StudioDocument | null
  dirty: boolean
  saveState: SaveState
  saveError: string
  lastSavedAt: string
  notice: string
  runs: StudioRunRow[]
  // app-server가 보내는 대화 이벤트(델타·완료)를 화면 상태로 모은다.
  // 대화 id를 함께 들고 있어야 응답 중 다른 노드를 선택해도 답변이 제 대화에 남는다.
  chatStream: { conversationId: string; threadId: string; turnId: string; text: string; status: string }
  // 마지막으로 끝난 턴. 전송 마무리가 그 턴을 새 스트림으로 다시 시작하지 않게 한다.
  lastFinishedTurnId: string
  selection: StudioSelection
  past: StudioDocument[]
  future: StudioDocument[]
  // 같은 입력 필드를 연속 편집할 때 되돌리기 기록을 한 묶음으로 합치기 위한 키.
  lastEditKey: string
  lastEditAt: number

  openProject: (meta: { id: string; name: string; revision: number; doc: StudioDocument }) => void
  closeProject: () => void
  setProjectName: (name: string) => void
  setNotes: (notes: string) => void
  setNotice: (message: string) => void
  clearNotice: () => void
  setRuns: (runs: StudioRunRow[]) => void
  upsertRun: (run: StudioRunRow) => void
  setChatStream: (stream: { conversationId?: string; threadId: string; turnId: string; text: string; status: string }) => void
  appendChatDelta: (threadId: string, turnId: string, delta: string) => void
  finishChatTurn: (threadId: string, turnId: string, status: string) => void

  addNode: (kind: NodeKind, position: { x: number; y: number }, overrides?: NodeOverrides) => string
  updateNode: (id: string, patch: Partial<Pick<StudioNode, 'title' | 'note' | 'status'>> & { config?: Record<string, ConfigValue> }) => void
  setNodeConfig: (id: string, key: string, value: ConfigValue) => void
  setNodeStatus: (id: string, status: NodeStatus) => void
  moveNodes: (positions: Record<string, { x: number; y: number }>) => void
  beginGesture: () => void
  removeNodes: (ids: string[]) => void
  duplicateNode: (id: string) => void

  addEdge: (attempt: ConnectionAttempt) => ConnectionCheck
  removeEdge: (id: string) => void
  setEdgeRole: (id: string, role: string) => void

  addShot: () => string
  updateShot: (id: string, patch: Partial<Shot>) => void
  removeShot: (id: string) => void
  moveShot: (id: string, delta: number) => void
  expandShot: (id: string, origin: { x: number; y: number }) => void

  addAsset: (input: AssetInput) => string
  registerAssets: (inputs: AssetInput[], positions: Array<{ x: number; y: number }>) => void
  removeAsset: (id: string) => void
  addResultAsset: (nodeId: string, asset: StudioAsset) => void

  setSelection: (selection: StudioSelection) => void

  markSaving: () => void
  markSaved: (revision: number, savedAt: string) => void
  markSaveError: (message: string) => void

  undo: () => void
  redo: () => void
}

function touchDoc(doc: StudioDocument): StudioDocument {
  return { ...doc, updatedAt: new Date().toISOString() }
}

function withHistory(state: StudioState, doc: StudioDocument, coalesceKey = ''): Partial<StudioState> {
  const now = Date.now()
  const coalesce = coalesceKey !== ''
    && coalesceKey === state.lastEditKey
    && now - state.lastEditAt < 2000
    && state.past[state.past.length - 1] !== state.doc
  const past = coalesce ? state.past : [...state.past, state.doc].slice(-HISTORY_LIMIT)
  const next = touchDoc(doc)
  return {
    doc: next,
    past,
    future: [],
    dirty: next !== state.savedDoc,
    lastEditKey: coalesceKey,
    lastEditAt: now,
  }
}

function createNode(doc: StudioDocument, kind: NodeKind, position: { x: number; y: number }): StudioNode {
  const spec = nodeSpec(kind)
  const config: Record<string, ConfigValue> = {}
  for (const field of spec.fields) {
    if (field.type === 'checkbox') config[field.key] = false
    else if (field.type === 'number') config[field.key] = null
    else if (field.type === 'select') config[field.key] = field.options?.[0]?.value ?? ''
    else config[field.key] = ''
  }
  const sameKind = doc.nodes.filter((node) => node.kind === kind).length
  const now = new Date().toISOString()
  return {
    id: uid('nd'),
    kind,
    title: sameKind === 0 ? spec.label : `${spec.label} ${sameKind + 1}`,
    note: '',
    position,
    config,
    status: kind === 'asset' ? 'ready' : 'draft',
    results: [],
    createdAt: now,
    updatedAt: now,
  }
}

/// 실행 결과 등 사용자 편집이 아닌 변경. 되돌리기 기록은 만들지 않는다.
function commitExternal(state: StudioState, doc: StudioDocument): Partial<StudioState> {
  const next = touchDoc(doc)
  return { doc: next, future: [], dirty: next !== state.savedDoc }
}

function markDownstreamStale(doc: StudioDocument, changedId: string): StudioDocument {
  const affected = new Set(downstreamIds(doc.edges, changedId))
  if (affected.size === 0) return doc
  let changed = false
  const nodes = doc.nodes.map((node) => {
    if (node.status === 'done' && affected.has(node.id)) {
      changed = true
      return { ...node, status: 'stale' as NodeStatus }
    }
    return node
  })
  return changed ? { ...doc, nodes } : doc
}

function createAsset(input: AssetInput): StudioAsset {
  return {
    id: uid('ast'),
    name: input.name,
    kind: input.kind,
    storedPath: input.storedPath,
    url: input.url,
    sizeBytes: input.sizeBytes,
    hash: input.hash,
    source: input.source,
    ephemeral: input.ephemeral,
    addedAt: new Date().toISOString(),
  }
}

export const useStudioStore = create<StudioState>((set, get) => ({
  projectId: '',
  projectName: '',
  revision: 0,
  doc: emptyDocument(),
  savedDoc: null,
  dirty: false,
  saveState: 'idle',
  saveError: '',
  lastSavedAt: '',
  notice: '',
  runs: [],
  chatStream: { conversationId: '', threadId: '', turnId: '', text: '', status: 'idle' },
  lastFinishedTurnId: '',
  selection: null,
  past: [],
  future: [],
  lastEditKey: '',
  lastEditAt: 0,

  openProject: ({ id, name, revision, doc }) => set({
    projectId: id,
    projectName: name,
    revision,
    doc,
    savedDoc: doc,
    dirty: false,
    saveState: 'saved',
    saveError: '',
    lastSavedAt: doc.updatedAt,
    notice: '',
    runs: [],
    selection: null,
    past: [],
    future: [],
  }),

  closeProject: () => set({
    projectId: '',
    projectName: '',
    revision: 0,
    doc: emptyDocument(),
    savedDoc: null,
    dirty: false,
    saveState: 'idle',
    saveError: '',
    lastSavedAt: '',
    notice: '',
    runs: [],
    selection: null,
    past: [],
    future: [],
  }),

  setProjectName: (name) => set({ projectName: name, dirty: true }),

  setNotice: (message) => set({ notice: message }),
  clearNotice: () => set({ notice: '' }),
  setRuns: (runs) => set({ runs }),
  upsertRun: (run) => set((state) => {
    const existing = state.runs.findIndex((item) => item.id === run.id)
    if (existing === -1) return { runs: [...state.runs, run] }
    const runs = [...state.runs]
    runs[existing] = run
    return { runs }
  }),
  setChatStream: (stream) => set((state) => ({
    chatStream: { conversationId: stream.conversationId ?? state.chatStream.conversationId, ...stream },
  })),
  appendChatDelta: (threadId, turnId, delta) => set((state) => ({
    chatStream: {
      conversationId: state.chatStream.conversationId,
      threadId,
      turnId,
      text: state.chatStream.turnId === turnId ? state.chatStream.text + delta : delta,
      status: 'streaming',
    },
  })),
  finishChatTurn: (threadId, turnId, status) => set((state) => ({
    lastFinishedTurnId: turnId,
    chatStream: state.chatStream.turnId === turnId
      ? { ...state.chatStream, threadId, status }
      : { conversationId: state.chatStream.conversationId, threadId, turnId, text: '', status },
  })),

  setNotes: (notes) => set((state) => {
    const next = { ...state.doc, notes }
    return withHistory(state, next)
  }),

  addNode: (kind, position, overrides) => {
    const id = uid('nd')
    set((state) => {
      const base = createNode(state.doc, kind, position)
      const node: StudioNode = {
        ...base,
        ...overrides,
        id,
        config: { ...base.config, ...(overrides?.config ?? {}) },
      }
      return withHistory(state, { ...state.doc, nodes: [...state.doc.nodes, node] })
    })
    return id
  },

  updateNode: (id, patch) => set((state) => {
    const now = new Date().toISOString()
    let changed = false
    const nodes = state.doc.nodes.map((node) => {
      if (node.id !== id) return node
      changed = true
      return {
        ...node,
        ...patch,
        config: patch.config ? { ...node.config, ...patch.config } : node.config,
        updatedAt: now,
      }
    })
    if (!changed) return {}
    return withHistory(state, { ...state.doc, nodes }, `node:${id}:${Object.keys(patch).sort().join('+')}`)
  }),

  setNodeConfig: (id, key, value) => set((state) => {
    const node = state.doc.nodes.find((item) => item.id === id)
    if (!node) return {}
    const next: StudioNode = {
      ...node,
      config: { ...node.config, [key]: value },
      updatedAt: new Date().toISOString(),
    }
    let doc: StudioDocument = { ...state.doc, nodes: state.doc.nodes.map((item) => (item.id === id ? next : item)) }
    if (node.kind !== 'asset') doc = markDownstreamStale(doc, id)
    return withHistory(state, doc, `cfg:${id}:${key}`)
  }),

  setNodeStatus: (id, status) => set((state) => {
    const nodes = state.doc.nodes.map((node) => (node.id === id ? { ...node, status } : node))
    // 실행 상태는 사용자 편집이 아니므로 되돌리기 기록을 만들지 않는다.
    return commitExternal(state, { ...state.doc, nodes })
  }),

  // 드래그 중 위치 갱신은 되돌리기 기록을 만들지 않는다. 기록은 드래그 시작 시점에 만든다.
  moveNodes: (positions) => set((state) => {
    let changed = false
    const nodes = state.doc.nodes.map((node) => {
      const next = positions[node.id]
      if (!next) return node
      if (next.x === node.position.x && next.y === node.position.y) return node
      changed = true
      return { ...node, position: next }
    })
    if (!changed) return {}
    return { doc: { ...state.doc, nodes }, dirty: true }
  }),

  beginGesture: () => set((state) => {
    if (state.past[state.past.length - 1] === state.doc) return {}
    return { past: [...state.past, state.doc].slice(-HISTORY_LIMIT), future: [] }
  }),

  removeNodes: (ids) => set((state) => {
    const removing = new Set(ids)
    if (removing.size === 0) return {}
    const nodes = state.doc.nodes.filter((node) => !removing.has(node.id))
    if (nodes.length === state.doc.nodes.length) return {}
    const edges = state.doc.edges.filter((edge) => !removing.has(edge.source) && !removing.has(edge.target))
    const shots = state.doc.shots.map((shot) => ({ ...shot, nodeIds: shot.nodeIds.filter((id) => !removing.has(id)) }))
    const selection = state.selection && state.selection.type === 'node' && removing.has(state.selection.id) ? null : state.selection
    const next = withHistory(state, { ...state.doc, nodes, edges, shots })
    return { ...next, selection }
  }),

  duplicateNode: (id) => set((state) => {
    const source = state.doc.nodes.find((node) => node.id === id)
    if (!source) return {}
    const now = new Date().toISOString()
    const copy: StudioNode = {
      ...source,
      id: uid('nd'),
      title: `${source.title} 복사`,
      position: { x: source.position.x + 48, y: source.position.y + 56 },
      status: source.kind === 'asset' ? 'ready' : 'draft',
      results: [],
      createdAt: now,
      updatedAt: now,
      config: { ...source.config },
    }
    return withHistory(state, { ...state.doc, nodes: [...state.doc.nodes, copy] })
  }),

  addEdge: (attempt) => {
    const check = evaluateConnection(get().doc, attempt)
    if (!check.ok) return check
    set((state) => {
      const targetNode = state.doc.nodes.find((node) => node.id === attempt.target)
      const targetPort = targetNode ? nodeSpec(targetNode.kind).inputs.find((port) => port.id === attempt.targetHandle) : undefined
      let edges = state.doc.edges
      if (attempt.kind === 'data' && targetPort && !targetPort.multiple) {
        edges = edges.filter((edge) => !(edge.target === attempt.target && edge.targetHandle === attempt.targetHandle))
      }
      const edge: StudioEdge = {
        id: uid('ed'),
        source: attempt.source,
        sourceHandle: attempt.sourceHandle ?? '',
        target: attempt.target,
        targetHandle: attempt.targetHandle ?? '',
        kind: attempt.kind,
        role: '',
      }
      return withHistory(state, { ...state.doc, edges: [...edges, edge] })
    })
    return check
  },

  removeEdge: (id) => set((state) => {
    const edges = state.doc.edges.filter((edge) => edge.id !== id)
    if (edges.length === state.doc.edges.length) return {}
    return withHistory(state, { ...state.doc, edges })
  }),

  setEdgeRole: (id, role) => set((state) => {
    const edges = state.doc.edges.map((edge) => (edge.id === id ? { ...edge, role } : edge))
    return withHistory(state, { ...state.doc, edges })
  }),

  addShot: () => {
    const id = uid('shot')
    set((state) => {
      const shot: Shot = {
        id,
        order: state.doc.shots.length,
        role: state.doc.shots.length === 0 ? 'hook' : '자유',
        title: `샷 ${state.doc.shots.length + 1}`,
        description: '',
        expectedSeconds: 5,
        copy: '',
        narration: '',
        nodeIds: [],
        selectedAssetId: null,
      }
      return withHistory(state, { ...state.doc, shots: [...state.doc.shots, shot] })
    })
    return id
  },

  updateShot: (id, patch) => set((state) => {
    const shots = state.doc.shots.map((shot) => (shot.id === id ? { ...shot, ...patch } : shot))
    return withHistory(state, { ...state.doc, shots }, `shot:${id}:${Object.keys(patch).sort().join('+')}`)
  }),

  removeShot: (id) => set((state) => {
    const remaining = state.doc.shots.filter((shot) => shot.id !== id)
    if (remaining.length === state.doc.shots.length) return {}
    const shots = remaining.map((shot, index) => ({ ...shot, order: index }))
    const selection = state.selection && state.selection.type === 'shot' && state.selection.id === id ? null : state.selection
    return { ...withHistory(state, { ...state.doc, shots }), selection }
  }),

  moveShot: (id, delta) => set((state) => {
    const shots = [...state.doc.shots].sort((a, b) => a.order - b.order)
    const index = shots.findIndex((shot) => shot.id === id)
    const target = index + delta
    if (index < 0 || target < 0 || target >= shots.length) return {}
    const swapped = shots[index]
    shots[index] = shots[target]
    shots[target] = swapped
    return withHistory(state, { ...state.doc, shots: shots.map((shot, order) => ({ ...shot, order })) })
  }),

  expandShot: (id, origin) => set((state) => {
    const shot = state.doc.shots.find((item) => item.id === id)
    if (!shot) return {}
    const promptNode = createNode(state.doc, 'prompt', { x: origin.x, y: origin.y })
    promptNode.title = `${shot.title} 프롬프트`
    promptNode.config = { ...promptNode.config, prompt: [shot.description, shot.copy].filter(Boolean).join('\n\n') }
    const videoNode = createNode({ ...state.doc, nodes: [...state.doc.nodes, promptNode] }, 'video', { x: origin.x + 340, y: origin.y })
    videoNode.title = `${shot.title} 영상`
    const selectNode = createNode({ ...state.doc, nodes: [...state.doc.nodes, promptNode, videoNode] }, 'select', { x: origin.x + 700, y: origin.y })
    selectNode.title = `${shot.title} 후보 선택`
    const edges: StudioEdge[] = [
      { id: uid('ed'), source: promptNode.id, sourceHandle: 'out', target: videoNode.id, targetHandle: 'prompt', kind: 'data', role: '' },
      { id: uid('ed'), source: videoNode.id, sourceHandle: 'out', target: selectNode.id, targetHandle: 'video', kind: 'data', role: '' },
    ]
    const nodes = [...state.doc.nodes, promptNode, videoNode, selectNode]
    const shots = state.doc.shots.map((item) => (item.id === id ? { ...item, nodeIds: [...item.nodeIds, promptNode.id, videoNode.id, selectNode.id] } : item))
    const next = withHistory(state, { ...state.doc, nodes, edges: [...state.doc.edges, ...edges], shots })
    return { ...next, selection: { type: 'node', id: videoNode.id } }
  }),

  addAsset: (input) => {
    const asset = createAsset(input)
    set((state) => withHistory(state, { ...state.doc, assets: [...state.doc.assets, asset] }))
    return asset.id
  },

  registerAssets: (inputs, positions) => set((state) => {
    if (inputs.length === 0) return {}
    const assets = inputs.map(createAsset)
    const nodes: StudioNode[] = assets.map((asset, index) => {
      const node = createNode(state.doc, 'asset', positions[index] ?? { x: 80 + index * 48, y: 80 + index * 48 })
      return {
        ...node,
        title: asset.name,
        status: 'ready' as NodeStatus,
        config: { ...node.config, assetId: asset.id, assetName: asset.name },
      }
    })
    return withHistory(state, { ...state.doc, assets: [...state.doc.assets, ...assets], nodes: [...state.doc.nodes, ...nodes] })
  }),

  removeAsset: (id) => set((state) => {
    const assets = state.doc.assets.filter((asset) => asset.id !== id)
    if (assets.length === state.doc.assets.length) return {}
    const removingNodeIds = state.doc.nodes.filter((node) => node.config.assetId === id).map((node) => node.id)
    const removing = new Set(removingNodeIds)
    const nodes = state.doc.nodes.filter((node) => !removing.has(node.id))
    const edges = state.doc.edges.filter((edge) => !removing.has(edge.source) && !removing.has(edge.target))
    const shots = state.doc.shots.map((shot) => ({
      ...shot,
      nodeIds: shot.nodeIds.filter((nodeId) => !removing.has(nodeId)),
      selectedAssetId: shot.selectedAssetId === id ? null : shot.selectedAssetId,
    }))
    return withHistory(state, { ...state.doc, assets, nodes, edges, shots })
  }),

  // 실행이 끝나면 결과 소재를 문서에 등록하고 노드 후보 목록 맨 앞에 넣는다.
  addResultAsset: (nodeId, asset) => set((state) => {
    const node = state.doc.nodes.find((item) => item.id === nodeId)
    if (!node) return {}
    const already = state.doc.assets.find((item) => item.id === asset.id)
    const assets = already
      ? state.doc.assets.map((item) => (item.id === asset.id ? { ...item, ...asset } : item))
      : [...state.doc.assets, asset]
    const nodes = state.doc.nodes.map((item) => item.id === nodeId
      ? {
        ...item,
        status: (item.status === 'failed' ? 'failed' : 'done') as NodeStatus,
        results: item.results.includes(asset.id) ? item.results : [asset.id, ...item.results],
        updatedAt: new Date().toISOString(),
      }
      : item)
    return commitExternal(state, { ...state.doc, assets, nodes })
  }),

  setSelection: (selection) => set({ selection }),

  markSaving: () => set({ saveState: 'saving', saveError: '' }),
  markSaved: (revision, savedAt) => set((state) => ({
    revision,
    savedDoc: state.doc,
    dirty: false,
    saveState: 'saved',
    saveError: '',
    lastSavedAt: savedAt,
  })),
  markSaveError: (message) => set({ saveState: 'error', saveError: message }),

  undo: () => set((state) => {
    if (state.past.length === 0) return {}
    const previous = state.past[state.past.length - 1]
    return {
      doc: previous,
      past: state.past.slice(0, -1),
      future: [state.doc, ...state.future].slice(0, HISTORY_LIMIT),
      dirty: previous !== state.savedDoc,
    }
  }),

  redo: () => set((state) => {
    if (state.future.length === 0) return {}
    const next = state.future[0]
    return {
      doc: next,
      past: [...state.past, state.doc].slice(-HISTORY_LIMIT),
      future: state.future.slice(1),
      dirty: next !== state.savedDoc,
    }
  }),
}))
