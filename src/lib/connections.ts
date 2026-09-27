// 연결 관리와 MCP 도구 호출의 프런트엔드 래퍼.
// Rust 구조체는 snake_case로 직렬화되므로 중첩 입력은 snake_case로 보낸다.

import { call, isTauri } from './tauri'

export type ConnectionRow = {
  id: string
  name: string
  kind: string
  enabled: boolean
  config: Record<string, unknown>
  authRef: string | null
  status: string
  lastError: string | null
  lastCheckedAt: string | null
  createdAt: string
  updatedAt: string
  toolCount: number
}

export type ConnectionToolRow = {
  connectionId: string
  name: string
  description: string | null
  inputSchema: Record<string, unknown>
  enabled: boolean
}

export type ConnectionTestResult = {
  connectionId: string
  status: string
  serverInfo: Record<string, unknown>
  protocolVersion: string | null
  tools: ConnectionToolRow[]
  message: string | null
}

type StoredConnection = {
  id: string
  name: string
  kind: string
  enabled: boolean
  config: Record<string, unknown>
  auth_ref: string | null
  status: string
  last_error: string | null
  last_checked_at: string | null
  created_at: string
  updated_at: string
  tool_count: number
}

type StoredTool = {
  connection_id: string
  name: string
  description: string | null
  input_schema: Record<string, unknown>
  enabled: boolean
}

type StoredTestResult = {
  connection_id: string
  status: string
  server_info: Record<string, unknown>
  protocol_version: string | null
  tools: StoredTool[]
  message: string | null
}

export const CONNECTION_KIND_LABELS: Record<string, string> = {
  'mcp-stdio': '로컬 MCP',
  'mcp-http': '원격 MCP',
  'service-api': '서비스 API',
  modal: 'Modal',
  'local-tool': '로컬 제작 도구',
}

export const CONNECTION_STATUS_LABELS: Record<string, string> = {
  saved: '저장됨',
  connected: '서버 연결됨',
  'tools-ready': '도구 확인됨',
  verified: '실행 검증됨',
  error: '오류',
}

export interface ConnectionInputPayload {
  id?: string | null
  name: string
  kind: string
  config: Record<string, unknown>
  authRef?: string | null
  enabled?: boolean | null
}

function mapConnection(row: StoredConnection): ConnectionRow {
  return {
    id: row.id,
    name: row.name,
    kind: row.kind,
    enabled: row.enabled,
    config: row.config ?? {},
    authRef: row.auth_ref,
    status: row.status,
    lastError: row.last_error,
    lastCheckedAt: row.last_checked_at,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    toolCount: row.tool_count,
  }
}

function mapTool(row: StoredTool): ConnectionToolRow {
  return {
    connectionId: row.connection_id,
    name: row.name,
    description: row.description,
    inputSchema: row.input_schema ?? {},
    enabled: row.enabled,
  }
}

export async function listConnections(): Promise<ConnectionRow[]> {
  if (!isTauri) return []
  const rows = await call<StoredConnection[]>('connection_list')
  return rows.map(mapConnection)
}

export async function saveConnection(input: ConnectionInputPayload): Promise<ConnectionRow> {
  const row = await call<StoredConnection>('connection_save', {
    input: {
      id: input.id ?? null,
      name: input.name,
      kind: input.kind,
      config: input.config,
      auth_ref: input.authRef ?? null,
      enabled: input.enabled ?? null,
    },
  })
  return mapConnection(row)
}

export async function deleteConnection(connectionId: string): Promise<void> {
  await call('connection_delete', { connectionId })
}

export async function setConnectionEnabled(connectionId: string, enabled: boolean): Promise<ConnectionRow> {
  const row = await call<StoredConnection>('connection_set_enabled', { connectionId, enabled })
  return mapConnection(row)
}

export async function setConnectionToolEnabled(connectionId: string, name: string, enabled: boolean): Promise<void> {
  await call('connection_set_tool_enabled', { connectionId, name, enabled })
}

export async function listConnectionTools(connectionId: string): Promise<ConnectionToolRow[]> {
  if (!isTauri) return []
  const rows = await call<StoredTool[]>('connection_tools', { connectionId })
  return rows.map(mapTool)
}

export async function testConnection(connectionId: string, timeoutMs?: number): Promise<ConnectionTestResult> {
  const row = await call<StoredTestResult>('connection_test', { connectionId, timeoutMs: timeoutMs ?? null })
  return {
    connectionId: row.connection_id,
    status: row.status,
    serverInfo: row.server_info ?? {},
    protocolVersion: row.protocol_version,
    tools: row.tools.map(mapTool),
    message: row.message,
  }
}

export async function callConnectionTool(
  connectionId: string,
  tool: string,
  args: unknown,
  timeoutMs?: number,
): Promise<unknown> {
  return call('connection_call_tool', { connectionId, tool, arguments: args, timeoutMs: timeoutMs ?? null })
}
