// 0단계 UX 계약. 화면은 이 사전과 capability 결과를 임의로 다시 해석하지 않는다.

export const UX_SURFACES = ['browser-preview', 'tauri'] as const
export type UxSurface = (typeof UX_SURFACES)[number]

export const GOAL_MODES = ['create', 'execute', 'review', 'operate'] as const
export type GoalMode = (typeof GOAL_MODES)[number]

export const CAPABILITY_IDS = [
  'editTemporaryDocument',
  'persistProject',
  'callExternalService',
  'renderLocally',
  'browseSampleState',
] as const
export type CapabilityId = (typeof CAPABILITY_IDS)[number]

export const CONNECTION_HEALTH = ['healthy', 'reconnecting', 'offline', 'expired-login', 'read-only'] as const
export type ConnectionHealth = (typeof CONNECTION_HEALTH)[number]

export const COST_STATES = ['actual', 'estimated', 'unknown', 'pending'] as const
export type CostState = (typeof COST_STATES)[number]

export const JOB_STATUSES = [
  'QUEUED',
  'ASSIGNING',
  'RUNNING',
  'DOWNLOADING',
  'COMPLETED',
  'FAILED',
  'CANCELLED',
] as const
export type JobStatusContract = (typeof JOB_STATUSES)[number]

export const STUDIO_RUN_STATUSES = [
  'queued',
  'running',
  'downloading',
  'prepared',
  'completed',
  'failed',
  'cancel_requested',
  'cancelled',
] as const
export type StudioRunStatusContract = (typeof STUDIO_RUN_STATUSES)[number]

export const NODE_STATUSES = ['draft', 'ready', 'running', 'done', 'stale', 'failed'] as const
export type NodeStatusContract = (typeof NODE_STATUSES)[number]

export const CONNECTION_STATUSES = ['saved', 'tested', 'tools-confirmed', 'execution-verified'] as const
export type ConnectionStatusContract = (typeof CONNECTION_STATUSES)[number]

export const PROJECT_STATUSES = ['new', 'dirty', 'saving', 'saved', 'save-failed'] as const
export type ProjectStatusContract = (typeof PROJECT_STATUSES)[number]

export const MATERIAL_STATUSES = ['temporary', 'imported', 'missing', 'generated'] as const
export type MaterialStatusContract = (typeof MATERIAL_STATUSES)[number]

export const ACCOUNT_STATUSES = ['available', 'unavailable', 'expired', 'archived'] as const
export type AccountStatusContract = (typeof ACCOUNT_STATUSES)[number]

export interface CapabilityContext {
  surface: UxSurface
  connection: ConnectionHealth
  accountAvailable: boolean
  localToolAvailable: boolean
}

export interface CapabilityDecision {
  id: CapabilityId
  allowed: boolean
  reason: string
  nextAction: string
}

export interface StatusDefinition<T extends string> {
  id: T
  label: string
  source: string
  terminal: boolean
  nextAction: string
}

const PERSISTENCE_REASON = '브라우저 미리보기는 이 컴퓨터의 프로젝트 저장소에 기록하지 않습니다.'
const EXTERNAL_REASON = '브라우저 미리보기는 Modal, ChatGPT, MCP 호출을 실행하지 않습니다.'
const RENDER_REASON = '브라우저 미리보기는 로컬 렌더러와 파일 탐색기를 실행하지 않습니다.'

export function capabilityDecision(id: CapabilityId, context: CapabilityContext): CapabilityDecision {
  if (id === 'browseSampleState') {
    return { id, allowed: true, reason: '예시 상태와 화면 이동은 항상 확인할 수 있습니다.', nextAction: '화면 이동' }
  }
  if (id === 'editTemporaryDocument') {
    return context.surface === 'browser-preview'
      ? { id, allowed: true, reason: '편집 내용은 이 브라우저 저장소에만 남습니다.', nextAction: '임시 편집' }
      : { id, allowed: true, reason: '편집 내용은 프로젝트 문서에 기록됩니다.', nextAction: '문서 편집' }
  }
  if (context.surface === 'browser-preview') {
    const reason = id === 'persistProject' ? PERSISTENCE_REASON : id === 'callExternalService' ? EXTERNAL_REASON : RENDER_REASON
    return { id, allowed: false, reason, nextAction: 'Tauri 앱에서 열기' }
  }
  if (id === 'persistProject') {
    return { id, allowed: true, reason: 'Tauri 저장소를 사용할 수 있습니다.', nextAction: '저장' }
  }
  if (id === 'callExternalService') {
    if (!context.accountAvailable || context.connection === 'expired-login') {
      return { id, allowed: false, reason: '사용할 수 있는 계정이 없습니다.', nextAction: '계정 연결 확인' }
    }
    if (context.connection === 'offline' || context.connection === 'reconnecting') {
      return { id, allowed: false, reason: '외부 서비스 연결이 안정되지 않았습니다.', nextAction: '연결 복구' }
    }
    return { id, allowed: true, reason: '선택한 계정과 연결로 호출할 수 있습니다.', nextAction: '실행' }
  }
  if (context.connection === 'read-only') {
    return { id, allowed: false, reason: '현재 연결은 읽기 전용입니다.', nextAction: '연결 상태 확인' }
  }
  return context.localToolAvailable
    ? { id, allowed: true, reason: '로컬 도구와 대상 경로를 사용할 수 있습니다.', nextAction: '렌더' }
    : { id, allowed: false, reason: '로컬 도구 또는 대상 경로를 사용할 수 없습니다.', nextAction: '도구 상태 확인' }
}

export function capabilityMatrix(context: CapabilityContext): Record<CapabilityId, CapabilityDecision> {
  return Object.fromEntries(CAPABILITY_IDS.map((id) => [id, capabilityDecision(id, context)])) as Record<CapabilityId, CapabilityDecision>
}

export const JOB_STATUS_DICTIONARY: Record<JobStatusContract, StatusDefinition<JobStatusContract>> = {
  QUEUED: { id: 'QUEUED', label: '요청 접수', source: 'jobs.status', terminal: false, nextAction: '계정 할당 대기' },
  ASSIGNING: { id: 'ASSIGNING', label: '계정 할당 중', source: 'jobs.status', terminal: false, nextAction: '할당 결과 확인' },
  RUNNING: { id: 'RUNNING', label: '실행 중', source: 'jobs.status + job_events', terminal: false, nextAction: '진행 또는 중단' },
  DOWNLOADING: { id: 'DOWNLOADING', label: '결과 받는 중', source: 'jobs.stage', terminal: false, nextAction: '수신 완료 대기' },
  COMPLETED: { id: 'COMPLETED', label: '완료', source: 'jobs.status', terminal: true, nextAction: '결과와 비용 확인' },
  FAILED: { id: 'FAILED', label: '실패', source: 'jobs.error_code', terminal: true, nextAction: '원인 확인 후 재시도' },
  CANCELLED: { id: 'CANCELLED', label: '취소됨', source: 'jobs.status', terminal: true, nextAction: '취소 범위 확인' },
}

export const STUDIO_RUN_DICTIONARY: Record<StudioRunStatusContract, StatusDefinition<StudioRunStatusContract>> = {
  queued: { id: 'queued', label: '실행 대기', source: 'studio_runs.status', terminal: false, nextAction: '실행 시작 대기' },
  running: { id: 'running', label: '실행 중', source: 'studio_runs.status', terminal: false, nextAction: '중단 또는 진행 확인' },
  downloading: { id: 'downloading', label: '결과 받는 중', source: 'studio_runs.stage', terminal: false, nextAction: '수신 완료 대기' },
  prepared: { id: 'prepared', label: '프로젝트 준비됨', source: 'studio_runs.status', terminal: false, nextAction: '외부 도구에서 이어서 작업한 뒤 완료 확인' },
  completed: { id: 'completed', label: '완료', source: 'studio_runs.status', terminal: true, nextAction: '후보 선택' },
  failed: { id: 'failed', label: '실패', source: 'studio_runs.error_code', terminal: true, nextAction: '원인 확인 후 재시도' },
  cancel_requested: { id: 'cancel_requested', label: '중단 요청됨', source: 'studio_runs.status', terminal: false, nextAction: '원격 중단 확인 대기' },
  cancelled: { id: 'cancelled', label: '취소됨', source: 'studio_runs.status', terminal: true, nextAction: '원격 중단 여부 확인' },
}

export const NODE_STATUS_DICTIONARY: Record<NodeStatusContract, StatusDefinition<NodeStatusContract>> = {
  draft: { id: 'draft', label: '편집 중', source: 'studio document node.status', terminal: false, nextAction: '입력 작성' },
  ready: { id: 'ready', label: '준비됨', source: 'studio document node.status', terminal: false, nextAction: '실행' },
  running: { id: 'running', label: '실행 중', source: 'studio document node.status', terminal: false, nextAction: '실행 기록 확인' },
  done: { id: 'done', label: '완료', source: 'studio document node.status', terminal: false, nextAction: '결과 확인' },
  stale: { id: 'stale', label: '입력 변경됨', source: 'studio document downstream invalidation', terminal: false, nextAction: '다시 실행 또는 이전 결과 보기' },
  failed: { id: 'failed', label: '실패', source: 'studio document node.status', terminal: false, nextAction: '원인 확인 후 재시도' },
}

export const CONNECTION_STATUS_DICTIONARY: Record<ConnectionStatusContract, StatusDefinition<ConnectionStatusContract>> = {
  saved: { id: 'saved', label: '저장됨', source: 'connections row', terminal: false, nextAction: '연결 테스트' },
  tested: { id: 'tested', label: '연결 테스트됨', source: 'connections.last_checked_at', terminal: false, nextAction: '도구 목록 확인' },
  'tools-confirmed': { id: 'tools-confirmed', label: '도구 확인됨', source: 'connection_tools', terminal: false, nextAction: '실제 호출 검증' },
  'execution-verified': { id: 'execution-verified', label: '실행 검증됨', source: 'successful tool invocation', terminal: true, nextAction: '노드에서 사용' },
}

export const COST_STATE_DICTIONARY: Record<CostState, StatusDefinition<CostState>> = {
  actual: { id: 'actual', label: '실제 계량', source: 'usage_records from provider billing', terminal: true, nextAction: '비용 근거 확인' },
  estimated: { id: 'estimated', label: '예산 기준 추정', source: 'user-entered budget', terminal: false, nextAction: '실제 계량과 구분해서 보기' },
  unknown: { id: 'unknown', label: '미확인', source: 'missing usage record', terminal: false, nextAction: '동기화 또는 근거 확인' },
  pending: { id: 'pending', label: '반영 대기', source: 'completed run before billing attribution', terminal: false, nextAction: '다음 동기화까지 0으로 확정하지 않음' },
}

export const PROJECT_STATUS_DICTIONARY: Record<ProjectStatusContract, StatusDefinition<ProjectStatusContract>> = {
  new: { id: 'new', label: '새 프로젝트', source: 'studio_projects before first save', terminal: false, nextAction: '첫 저장' },
  dirty: { id: 'dirty', label: '저장되지 않은 변경', source: 'studio store dirty', terminal: false, nextAction: '저장 또는 나가기 확인' },
  saving: { id: 'saving', label: '저장 중', source: 'studio store saveState', terminal: false, nextAction: '저장 결과 대기' },
  saved: { id: 'saved', label: '저장됨', source: 'studio_projects.revision', terminal: true, nextAction: '작업 계속' },
  'save-failed': { id: 'save-failed', label: '저장 실패', source: 'studio store saveError', terminal: false, nextAction: '저장 재시도' },
}

export const MATERIAL_STATUS_DICTIONARY: Record<MaterialStatusContract, StatusDefinition<MaterialStatusContract>> = {
  temporary: { id: 'temporary', label: '브라우저 임시 소재', source: 'studio asset source=browser', terminal: false, nextAction: 'Tauri에서 다시 가져오기' },
  imported: { id: 'imported', label: '가져온 소재', source: 'studio_assets.stored_path', terminal: true, nextAction: '노드에 연결' },
  missing: { id: 'missing', label: '파일을 찾을 수 없음', source: 'studio asset path probe', terminal: false, nextAction: '경로 다시 연결' },
  generated: { id: 'generated', label: '생성된 소재', source: 'studio run output asset', terminal: true, nextAction: '후보로 확인' },
}

export const ACCOUNT_STATUS_DICTIONARY: Record<AccountStatusContract, StatusDefinition<AccountStatusContract>> = {
  available: { id: 'available', label: '사용 가능', source: 'modal_profiles.enabled + fresh credentials', terminal: false, nextAction: '작업에 선택' },
  unavailable: { id: 'unavailable', label: '사용 불가', source: 'modal_profiles.enabled=false or connection failure', terminal: false, nextAction: '다른 계정으로 대체하지 않고 복구' },
  expired: { id: 'expired', label: '인증 만료', source: 'provider account status', terminal: false, nextAction: '다시 로그인' },
  archived: { id: 'archived', label: '보관됨', source: 'modal_profiles.archived_at', terminal: true, nextAction: '기록 유지, 새 실행 차단' },
}

export interface VerificationScenario {
  id: string
  mode: GoalMode
  path: string
  requiredStates: string[]
}

export const VERIFICATION_SCENARIOS: VerificationScenario[] = [
  {
    id: 'generate-to-cost',
    mode: 'execute',
    path: '생성 → 큐 → 결과 → 비용',
    requiredStates: ['QUEUED', 'ASSIGNING', 'RUNNING', 'DOWNLOADING', 'COMPLETED', 'FAILED', 'CANCELLED', 'queued', 'ready', 'actual', 'pending'],
  },
  {
    id: 'studio-to-export',
    mode: 'create',
    path: 'Studio → 결과 후보 → 내보내기',
    requiredStates: ['draft', 'running', 'done', 'downloading', 'prepared', 'completed', 'failed', 'cancel_requested', 'cancelled', 'stale', 'new', 'dirty', 'saving', 'save-failed', 'temporary', 'imported', 'generated', 'missing'],
  },
  {
    id: 'connection-to-run',
    mode: 'operate',
    path: '연결 → 도구 확인 → 실행 검증',
    requiredStates: ['saved', 'tested', 'tools-confirmed', 'execution-verified', 'healthy', 'reconnecting', 'offline', 'expired-login', 'read-only', 'available', 'unavailable', 'expired', 'archived', 'estimated', 'unknown'],
  },
]

export function isTerminalStatus(kind: 'job' | 'studio-run', status: string): boolean {
  return kind === 'job'
    ? JOB_STATUSES.includes(status as JobStatusContract) && JOB_STATUS_DICTIONARY[status as JobStatusContract].terminal
    : STUDIO_RUN_STATUSES.includes(status as StudioRunStatusContract) && STUDIO_RUN_DICTIONARY[status as StudioRunStatusContract].terminal
}
