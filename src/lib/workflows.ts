// 등록된 생성 워크플로(Modal/Comfy) 래퍼.
import { call, isTauri } from './tauri'

export type WorkflowRow = {
  id: string
  name: string
  tool: string
  location: string | null
  status: string
  inputs: Record<string, unknown>
  outputs: Record<string, unknown>
  notes: string | null
  createdAt: string
  updatedAt: string
}

type StoredWorkflow = {
  id: string
  name: string
  tool: string
  location: string | null
  status: string
  inputs: Record<string, unknown>
  outputs: Record<string, unknown>
  notes: string | null
  created_at: string
  updated_at: string
}

export const WORKFLOW_STATUS_LABELS: Record<string, string> = {
  registered: '등록됨',
  verified: '실행 검증됨',
}

function mapWorkflow(row: StoredWorkflow): WorkflowRow {
  return {
    id: row.id,
    name: row.name,
    tool: row.tool,
    location: row.location,
    status: row.status,
    inputs: row.inputs ?? {},
    outputs: row.outputs ?? {},
    notes: row.notes,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}

export async function listWorkflows(): Promise<WorkflowRow[]> {
  if (!isTauri) return []
  const rows = await call<StoredWorkflow[]>('workflow_list')
  return rows.map(mapWorkflow)
}

export async function saveWorkflow(input: {
  id?: string | null
  name: string
  tool: string
  location?: string | null
  inputs?: Record<string, unknown>
  outputs?: Record<string, unknown>
  notes?: string | null
  status?: string | null
}): Promise<WorkflowRow> {
  const row = await call<StoredWorkflow>('workflow_save', { input })
  return mapWorkflow(row)
}

export async function deleteWorkflow(workflowId: string): Promise<void> {
  await call('workflow_delete', { workflowId })
}
