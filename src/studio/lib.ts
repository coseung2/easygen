// 스튜디오 데이터 계층: Tauri studio 명령 래퍼와 브라우저 미리보기 대체 구현.
// Rust 구조체는 snake_case로 직렬화되므로 여기서 화면용 이름으로 변환한다.

import { convertFileSrc } from '@tauri-apps/api/core'
import { getCurrentWebview } from '@tauri-apps/api/webview'
import { open } from '@tauri-apps/plugin-dialog'
import { call, isTauri } from '../lib/tauri'
import {
  uid,
  type AssetKind,
  type StudioAsset,
  type StudioDocument,
  type StudioProjectRecord,
  type StudioProjectSummary,
  type StudioRunRow,
} from './types'
import type { AssetInput } from './store'

type StoredProjectSummary = {
  id: string
  name: string
  revision: number
  node_count: number
  asset_count: number
  created_at: string
  updated_at: string
}

type StoredProject = {
  id: string
  name: string
  revision: number
  document_json: string
  created_at: string
  updated_at: string
}

type StoredSaveResult = { id: string; revision: number; updated_at: string }

type StoredImportedAsset = {
  file_name: string
  stored_path: string
  size_bytes: number
  hash: string
  kind: string
}

type StoredRun = {
  id: string
  project_id: string
  node_id: string
  node_title: string | null
  tool: string
  status: string
  stage: string | null
  job_id: string | null
  output_path: string | null
  result_asset_id: string | null
  error_code: string | null
  error_message: string | null
  remote_output_path: string | null
  created_at: string
  updated_at: string
}

function toRun(row: StoredRun): StudioRunRow {
  return {
    id: row.id,
    projectId: row.project_id,
    nodeId: row.node_id,
    nodeTitle: row.node_title,
    tool: row.tool,
    status: row.status,
    stage: row.stage,
    jobId: row.job_id,
    outputPath: row.output_path,
    resultAssetId: row.result_asset_id,
    errorCode: row.error_code,
    errorMessage: row.error_message,
    remotePath: row.remote_output_path ?? null,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}

export interface StudioRunRequest {
  projectId: string
  nodeId: string
  nodeTitle: string
  tool: string
  prompt?: string
  inputPath?: string | null
  duration?: number | null
  width?: number | null
  height?: number | null
  seed?: number | null
  profileId?: string | null
  kind?: string | null
  style?: string | null
  lyrics?: string | null
  inputJson?: string | null
}

function runRequestArgs(request: StudioRunRequest) {
  return {
    request: {
      project_id: request.projectId,
      node_id: request.nodeId,
      node_title: request.nodeTitle,
      tool: request.tool,
      prompt: request.prompt ?? '',
      input_path: request.inputPath ?? null,
      duration: request.duration ?? null,
      width: request.width ?? null,
      height: request.height ?? null,
      seed: request.seed ?? null,
      profile_id: request.profileId ?? null,
      kind: request.kind ?? null,
      style: request.style ?? null,
      lyrics: request.lyrics ?? null,
      input_json: request.inputJson ?? null,
    },
  }
}

export async function startNodeRun(request: StudioRunRequest): Promise<StudioRunRow> {
  const row = await call<StoredRun>('studio_start_node_run', runRequestArgs(request))
  return toRun(row)
}

export async function startLocalRun(request: StudioRunRequest): Promise<StudioRunRow> {
  const row = await call<StoredRun>('studio_start_local_run', runRequestArgs(request))
  return toRun(row)
}

export async function finishNodeRun(
  runId: string,
  status: 'running' | 'completed' | 'prepared' | 'failed' | 'cancelled',
  outputPath?: string | null,
  errorMessage?: string | null,
  resultAssetId?: string | null,
): Promise<StudioRunRow> {
  const row = await call<StoredRun>('studio_finish_node_run', {
    runId,
    status,
    outputPath: outputPath ?? null,
    errorMessage: errorMessage ?? null,
    resultAssetId: resultAssetId ?? null,
  })
  return toRun(row)
}

/**
 * 진행 중인 실행에 중단을 요청한다. 원격 취소를 지원하지 않는 도구는
 * `cancel_requested`로 남고, 실제 취소 확인은 worker 이벤트로만 기록한다.
 */
export async function cancelNodeRun(runId: string): Promise<StudioRunRow> {
  const row = await call<StoredRun>('studio_cancel_run', { runId })
  return toRun(row)
}

/**
 * 생성은 끝났는데 결과를 받지 못한 실행을 결과 수신부터 복구한다.
 * 새로 생성하지 않으므로 같은 비용을 다시 쓰지 않는다.
 */
export async function retryRunDownload(runId: string): Promise<StudioRunRow> {
  const row = await call<StoredRun>('studio_retry_download', { runId })
  return toRun(row)
}

export async function listNodeRuns(projectId: string): Promise<StudioRunRow[]> {
  if (!isTauri) return []
  const rows = await call<StoredRun[]>('studio_list_node_runs', { projectId })
  return rows.map(toRun)
}

export type PathProbe = { exists: boolean; isFile: boolean; sizeBytes: number; kind: string }

/** 도구 결과가 실제 파일을 가리키는지 확인한다. 존재가 확인된 경로만 소재로 제안한다. */
export async function probePath(path: string): Promise<PathProbe> {
  const row = await call<{ exists: boolean; is_file: boolean; size_bytes: number; kind: string }>(
    'studio_probe_path',
    { path },
  )
  return { exists: row.exists, isFile: row.is_file, sizeBytes: row.size_bytes, kind: row.kind }
}

const BROWSER_KEY = 'modal-gui.studio.projects'

function toSummary(row: StoredProjectSummary): StudioProjectSummary {
  return {
    id: row.id,
    name: row.name,
    revision: row.revision,
    nodeCount: row.node_count,
    assetCount: row.asset_count,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}

function toRecord(row: StoredProject): StudioProjectRecord {
  return {
    id: row.id,
    name: row.name,
    revision: row.revision,
    documentJson: row.document_json,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}

function browserRows(): Record<string, StoredProject> {
  try {
    const raw = localStorage.getItem(BROWSER_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, StoredProject>
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function writeBrowserRows(rows: Record<string, StoredProject>) {
  try {
    localStorage.setItem(BROWSER_KEY, JSON.stringify(rows))
  } catch {
    // 브라우저 미리보기의 저장 한도를 넘으면 마지막 상태만 남기고 실패를 알린다.
    throw new Error('브라우저 미리보기 저장 한도를 넘었습니다. Tauri 앱에서 실제 프로젝트로 저장하세요.')
  }
}

export async function listProjects(): Promise<StudioProjectSummary[]> {
  if (isTauri) {
    const rows = await call<StoredProjectSummary[]>('studio_list_projects')
    return rows.map(toSummary)
  }
  return Object.values(browserRows())
    .map(browserSummary)
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
}

function browserSummary(row: StoredProject): StudioProjectSummary {
  let nodeCount = 0
  let assetCount = 0
  try {
    const doc = JSON.parse(row.document_json) as { nodes?: unknown[]; assets?: unknown[] }
    nodeCount = Array.isArray(doc.nodes) ? doc.nodes.length : 0
    assetCount = Array.isArray(doc.assets) ? doc.assets.length : 0
  } catch {
    // 문서를 읽지 못하면 개수만 0으로 둔다.
  }
  return {
    id: row.id,
    name: row.name,
    revision: row.revision,
    nodeCount,
    assetCount,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}

export async function createProject(name: string, doc: StudioDocument): Promise<StudioProjectRecord> {
  if (isTauri) {
    const row = await call<StoredProject>('studio_create_project', { name, documentJson: JSON.stringify(doc) })
    return toRecord(row)
  }
  const now = new Date().toISOString()
  const row: StoredProject = {
    id: uid('prj'),
    name,
    revision: 1,
    document_json: JSON.stringify(doc),
    created_at: now,
    updated_at: now,
  }
  const rows = browserRows()
  rows[row.id] = row
  writeBrowserRows(rows)
  return toRecord(row)
}

export async function loadProject(projectId: string): Promise<StudioProjectRecord> {
  if (isTauri) {
    const row = await call<StoredProject>('studio_load_project', { projectId })
    return toRecord(row)
  }
  const row = browserRows()[projectId]
  if (!row) throw new Error('프로젝트를 찾을 수 없습니다')
  return toRecord(row)
}

export async function saveProject(
  projectId: string,
  name: string,
  doc: StudioDocument,
): Promise<{ id: string; revision: number; updatedAt: string }> {
  if (isTauri) {
    const row = await call<StoredSaveResult>('studio_save_project', {
      projectId,
      name,
      documentJson: JSON.stringify(doc),
    })
    return { id: row.id, revision: row.revision, updatedAt: row.updated_at }
  }
  const rows = browserRows()
  const existing = rows[projectId]
  if (!existing) throw new Error('프로젝트를 찾을 수 없습니다')
  const updated: StoredProject = {
    ...existing,
    name,
    revision: existing.revision + 1,
    document_json: JSON.stringify(doc),
    updated_at: new Date().toISOString(),
  }
  rows[projectId] = updated
  writeBrowserRows(rows)
  return { id: projectId, revision: updated.revision, updatedAt: updated.updated_at }
}

export async function deleteProject(projectId: string): Promise<void> {
  if (isTauri) {
    await call('studio_delete_project', { projectId })
    return
  }
  const rows = browserRows()
  delete rows[projectId]
  writeBrowserRows(rows)
}

export function kindFromExtension(name: string): AssetKind {
  const extension = name.toLowerCase().split('.').pop() ?? ''
  if (['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'tif', 'tiff', 'avif'].includes(extension)) return 'image'
  if (['mp4', 'mov', 'webm', 'mkv', 'avi', 'm4v'].includes(extension)) return 'video'
  if (['wav', 'mp3', 'flac', 'm4a', 'aac', 'ogg'].includes(extension)) return 'audio'
  return 'other'
}

export async function importPathAsset(projectId: string, sourcePath: string): Promise<AssetInput> {
  const row = await call<StoredImportedAsset>('studio_import_asset', { projectId, sourcePath })
  return {
    name: row.file_name,
    kind: row.kind as AssetKind,
    storedPath: row.stored_path,
    url: convertFileSrc(row.stored_path),
    sizeBytes: row.size_bytes,
    hash: row.hash,
    source: 'imported',
  }
}

const BROWSER_PERSIST_LIMIT = 400 * 1024

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error ?? new Error('파일을 읽지 못했습니다.'))
    reader.readAsDataURL(file)
  })
}

// 브라우저 미리보기 전용: 작은 이미지만 data URL로 남겨 새로고침 후에도 보인다.
export async function browserAssetInput(file: File): Promise<AssetInput> {
  const kind = kindFromExtension(file.name)
  const persist = kind === 'image' && file.size <= BROWSER_PERSIST_LIMIT
  const url = persist ? await readAsDataUrl(file) : URL.createObjectURL(file)
  return {
    name: file.name,
    kind,
    storedPath: '',
    url,
    sizeBytes: file.size,
    hash: '',
    source: 'browser',
    ephemeral: !persist,
  }
}

export async function pickAssetPaths(): Promise<string[]> {
  if (!isTauri) return []
  const result = await open({
    multiple: true,
    title: '프로젝트 소재 가져오기',
    filters: [
      { name: '이미지', extensions: ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'tif', 'tiff', 'avif'] },
      { name: '영상', extensions: ['mp4', 'mov', 'webm', 'mkv', 'avi', 'm4v'] },
      { name: '오디오', extensions: ['wav', 'mp3', 'flac', 'm4a', 'aac', 'ogg'] },
    ],
  })
  if (!result) return []
  return Array.isArray(result) ? result : [result]
}

/** 폴더 하나를 고른다. 내보내기 위치나 가져올 프로젝트 폴더에 쓴다. */
export async function pickDirectory(title: string): Promise<string | null> {
  if (!isTauri) return null
  const result = await open({ directory: true, multiple: false, title })
  return typeof result === 'string' ? result : null
}

export type ProjectExportResult = {
  dir: string
  assetCount: number
  missingAssets: string[]
  files: string[]
}

export type ProjectImportResult = {
  projectId: string
  name: string
  missing: { connections: string[]; workflows: string[]; fonts: string[] }
}

/** 프로젝트 문서와 선택 소재를 폴더로 내보낸다. 인증값은 포함되지 않는다. */
export async function exportProject(projectId: string, targetDir: string): Promise<ProjectExportResult> {
  const row = await call<{ dir: string; asset_count: number; missing_assets: string[]; files: string[] }>(
    'studio_export_project',
    { projectId, targetDir },
  )
  return { dir: row.dir, assetCount: row.asset_count, missingAssets: row.missing_assets ?? [], files: row.files ?? [] }
}

export async function importProject(sourceDir: string): Promise<ProjectImportResult> {
  const row = await call<{
    project_id: string
    name: string
    missing: { connections?: string[]; workflows?: string[]; fonts?: string[] }
  }>('studio_import_project', { sourceDir })
  return {
    projectId: row.project_id,
    name: row.name,
    missing: {
      connections: row.missing?.connections ?? [],
      workflows: row.missing?.workflows ?? [],
      fonts: row.missing?.fonts ?? [],
    },
  }
}

export type TemplateRow = {
  id: string
  name: string
  description: string | null
  nodeCount: number
  documentJson: string
  createdAt: string
  updatedAt: string
}

type StoredTemplate = {
  id: string
  name: string
  description: string | null
  node_count: number
  document_json: string
  created_at: string
  updated_at: string
}

export async function listTemplates(): Promise<TemplateRow[]> {
  if (!isTauri) return []
  const rows = await call<StoredTemplate[]>('studio_template_list')
  return rows.map((row) => ({
    id: row.id,
    name: row.name,
    description: row.description,
    nodeCount: row.node_count,
    documentJson: row.document_json,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }))
}

export async function saveTemplate(input: {
  name: string
  description?: string | null
  documentJson: string
}): Promise<void> {
  // 중첩 구조는 Tauri가 이름을 바꿔 주지 않으므로 서버 필드 이름 그대로 보낸다.
  await call('studio_template_save', {
    input: {
      name: input.name,
      description: input.description ?? null,
      document_json: input.documentJson,
    },
  })
}

export async function deleteTemplate(templateId: string): Promise<void> {
  await call('studio_template_delete', { templateId })
}

export type RunUsageRow = {
  runId: string
  nodeId: string
  nodeTitle: string | null
  tool: string
  status: string
  amount: number | null
  amountKind: 'confirmed' | 'pending' | 'unknown'
  period: string | null
  observedAt: string | null
}

export type ProjectUsageSummary = {
  runs: RunUsageRow[]
  confirmedTotal: number
  pricedRuns: number
  unpricedRuns: number
}

/** 실행별 비용 귀속. 값이 없으면 0이 아니라 미확인으로 남긴다(문서 14장). */
export async function projectUsageSummary(projectId: string): Promise<ProjectUsageSummary> {
  const value = await call<{
    runs: Array<{
      run_id: string
      node_id: string
      node_title: string | null
      tool: string
      status: string
      amount: number | null
      amount_kind: string
      period: string | null
      observed_at: string | null
    }>
    confirmed_total: number
    priced_runs: number
    unpriced_runs: number
  }>('studio_usage_summary', { projectId })
  return {
    runs: (value.runs ?? []).map((row) => ({
      runId: row.run_id,
      nodeId: row.node_id,
      nodeTitle: row.node_title,
      tool: row.tool,
      status: row.status,
      amount: row.amount,
      amountKind: row.amount_kind === 'confirmed' || row.amount_kind === 'pending' ? row.amount_kind : 'unknown',
      period: row.period,
      observedAt: row.observed_at,
    })),
    confirmedTotal: value.confirmed_total ?? 0,
    pricedRuns: value.priced_runs ?? 0,
    unpricedRuns: value.unpriced_runs ?? 0,
  }
}

// Tauri 창에 파일을 끌어다 놓으면 실제 경로를 받는다. 브라우저에서는 HTML5 드롭을 쓴다.
export async function watchFileDrops(
  handler: (paths: string[], position: { x: number; y: number }) => void,
): Promise<() => void> {
  if (!isTauri) return () => {}
  const webview = getCurrentWebview()
  const unlisten = await webview.onDragDropEvent((event) => {
    const payload = event.payload
    if (payload.type === 'drop') {
      const scale = window.devicePixelRatio || 1
      handler(payload.paths, { x: payload.position.x / scale, y: payload.position.y / scale })
    }
  })
  return unlisten
}

export function assetDisplayUrl(asset: StudioAsset): string {
  if (asset.url) return asset.url
  if (asset.storedPath && isTauri) return convertFileSrc(asset.storedPath)
  return ''
}
