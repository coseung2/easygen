import { call } from './tauri'
import type { Job, JobKind, JobStage, JobStatus } from '../types'

/** Row shape of `list_recent_jobs`: the stored `jobs` table, not UI state. */
export type StoredJob = {
  id: string
  profile_id: string | null
  function_call_id: string | null
  kind: string | null
  status: string
  stage: string
  prompt: string
  input_path: string
  output_path: string | null
  thumbnail_path: string | null
  duration: number | null
  resolution: string | null
  seed: number | null
  progress: number | null
  error_code: string | null
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export const listRecentJobs = (jobLimit = 100) =>
  call<StoredJob[]>('list_recent_jobs', { jobLimit })

/** Rebuilds a queue entry from the database so it survives a restart. */
export function storedJobToJob(row: StoredJob): Job {
  return {
    id: row.id,
    profileId: row.profile_id ?? undefined,
    functionCallId: row.function_call_id ?? undefined,
    kind: (row.kind as JobKind | null) ?? undefined,
    status: row.status as JobStatus,
    stage: row.stage as JobStage,
    prompt: row.prompt,
    inputPath: row.input_path,
    outputPath: row.output_path ?? undefined,
    thumbnailPath: row.thumbnail_path ?? undefined,
    duration: row.duration ?? 0,
    resolution: row.resolution ?? '',
    seed: row.seed ?? undefined,
    progress: row.progress ?? undefined,
    error: row.error_message ?? row.error_code ?? undefined,
    createdAt: row.created_at,
    startedAt: row.started_at ?? undefined,
    completedAt: row.completed_at ?? undefined,
    logs: [],
  }
}
