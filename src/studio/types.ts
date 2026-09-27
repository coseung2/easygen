// 0단계 공통 형식: 프로젝트 문서(노드·연결·샷·소재)와 포트 자료형.
// 이 문서는 Rust `studio_save_project`가 JSON 그대로 저장하고 복원한다.

export const PORT_TYPES = [
  'Text',
  'Brief',
  'StyleGuide',
  'Image',
  'Video',
  'Audio',
  'Mask',
  'ShotList',
  'MotionSpec',
  'Timeline',
  'ProjectFile',
  'Json',
] as const

export type PortType = (typeof PORT_TYPES)[number]

export type ConnectionKind = 'data' | 'context'

export type NodeKind =
  | 'asset'
  | 'brief'
  | 'moodboard'
  | 'storyboard'
  | 'prompt'
  | 'image'
  | 'video'
  | 'design'
  | 'comfy'
  | 'motion'
  | 'typo'
  | 'audio'
  | 'select'
  | 'edit'
  | 'export'
  | 'tool'
  | 'template'

export type NodeStatus = 'draft' | 'ready' | 'running' | 'done' | 'stale' | 'failed'

export type AssetKind = 'image' | 'video' | 'audio' | 'other'

export type ConfigValue = string | number | boolean | null

export interface Port {
  id: string
  label: string
  type: PortType
  multiple?: boolean
}

export interface StudioNode {
  id: string
  kind: NodeKind
  title: string
  note: string
  position: { x: number; y: number }
  config: Record<string, ConfigValue>
  status: NodeStatus
  // 이 노드의 결과 후보 소재 id. 최신 결과가 앞에 온다.
  results: string[]
  createdAt: string
  updatedAt: string
}

export interface StudioEdge {
  id: string
  source: string
  sourceHandle: string
  target: string
  targetHandle: string
  kind: ConnectionKind
  role: string
}

export interface Shot {
  id: string
  order: number
  role: string
  title: string
  description: string
  expectedSeconds: number
  copy: string
  narration: string
  nodeIds: string[]
  selectedAssetId: string | null
}

export interface StudioAsset {
  id: string
  name: string
  kind: AssetKind
  // Tauri: 프로젝트 폴더로 복사된 실제 경로. 브라우저 미리보기: ''
  storedPath: string
  // 화면 표시용 URL (asset:// 변환, object URL, data URL)
  url: string
  sizeBytes: number
  hash: string
  source: 'imported' | 'browser' | 'generated'
  // 브라우저 미리보기에서만 참조하는 임시 소재
  ephemeral?: boolean
  addedAt: string
}

/** 한 번의 노드 실행. Rust `studio_runs` 행과 같은 이름을 쓴다. */
export interface StudioRunRow {
  id: string
  projectId: string
  nodeId: string
  nodeTitle: string | null
  tool: string
  status: string
  stage: string | null
  jobId: string | null
  outputPath: string | null
  resultAssetId: string | null
  errorCode: string | null
  errorMessage: string | null
  /** 다시 받을 수 있는 원격 결과 위치(있을 때). */
  remotePath: string | null
  createdAt: string
  updatedAt: string
}

export const RUN_STATUS_LABELS: Record<string, string> = {
  queued: '대기',
  running: '실행 중',
  downloading: '결과 수신',
  completed: '완료',
  prepared: '프로젝트 준비됨',
  cancel_requested: '중단 요청됨',
  failed: '실패',
  cancelled: '취소됨',
}

export function runStatusLabel(status: string): string {
  return RUN_STATUS_LABELS[status] ?? status
}

export function isTerminalRun(status: string): boolean {
  return status === 'completed' || status === 'prepared' || status === 'failed' || status === 'cancelled'
}

/** 아직 끝나지 않아 중단을 요청할 수 있는 실행. */
export function isActiveRun(status: string): boolean {
  return !isTerminalRun(status)
}

export interface StudioDocument {
  version: 1
  notes: string
  nodes: StudioNode[]
  edges: StudioEdge[]
  shots: Shot[]
  assets: StudioAsset[]
  updatedAt: string
}

export interface StudioProjectSummary {
  id: string
  name: string
  revision: number
  nodeCount: number
  assetCount: number
  createdAt: string
  updatedAt: string
}

export interface StudioProjectRecord {
  id: string
  name: string
  revision: number
  documentJson: string
  createdAt: string
  updatedAt: string
}

export const SHOT_ROLES = ['hook', '제품 장면', '사용 장면', '마무리', '자유'] as const

export const REFERENCE_ROLES = [
  '제품 외형',
  '스타일',
  '시작 프레임',
  '끝 프레임',
  '인물',
  '동작·카메라',
  '레이아웃',
  '오디오',
  '레퍼런스',
] as const

export function emptyDocument(): StudioDocument {
  return {
    version: 1,
    notes: '',
    nodes: [],
    edges: [],
    shots: [],
    assets: [],
    updatedAt: new Date().toISOString(),
  }
}

/** 이전 버전 문서(단일 resultAssetId)를 후보 목록 형식으로 올린다. */
export function normalizeDocument(value: unknown): StudioDocument {
  const raw = (value ?? {}) as Partial<StudioDocument> & Record<string, unknown>
  const nodes = Array.isArray(raw.nodes) ? raw.nodes : []
  return {
    version: 1,
    notes: typeof raw.notes === 'string' ? raw.notes : '',
    assets: Array.isArray(raw.assets) ? raw.assets : [],
    edges: Array.isArray(raw.edges) ? raw.edges : [],
    shots: Array.isArray(raw.shots) ? raw.shots : [],
    updatedAt: typeof raw.updatedAt === 'string' ? raw.updatedAt : new Date().toISOString(),
    nodes: nodes.map((node) => {
      const legacy = (node as { resultAssetId?: unknown }).resultAssetId
      const results = Array.isArray(node.results)
        ? node.results.filter((id): id is string => typeof id === 'string')
        : typeof legacy === 'string' && legacy
          ? [legacy]
          : []
      return {
        ...node,
        note: typeof node.note === 'string' ? node.note : '',
        config: node.config && typeof node.config === 'object' ? node.config : {},
        results,
      }
    }),
  }
}

export function uid(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
}

export function assetPortType(kind: AssetKind): PortType {
  if (kind === 'image') return 'Image'
  if (kind === 'video') return 'Video'
  if (kind === 'audio') return 'Audio'
  return 'Json'
}

export function isDocument(value: unknown): value is StudioDocument {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return Array.isArray(record.nodes) && Array.isArray(record.edges) && Array.isArray(record.shots) && Array.isArray(record.assets)
}
