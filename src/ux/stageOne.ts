import type { Job, JobStage, JobStatus } from '../types'
import type { WorkerEvent } from '../app-config'
import { capabilityDecision, type CapabilityId } from './contract'

const ACTIVE_JOBS = new Set<JobStatus>(['QUEUED', 'ASSIGNING', 'RUNNING', 'DOWNLOADING'])
const TERMINAL_JOBS = new Set<JobStatus>(['COMPLETED', 'FAILED', 'CANCELLED'])

export function browserCapability(id: CapabilityId) {
  return capabilityDecision(id, {
    surface: 'browser-preview',
    connection: 'read-only',
    accountAvailable: false,
    localToolAvailable: false,
  })
}

export function confirmProtectedAction(message: string): boolean {
  return window.confirm(message)
}

export function reconcileJob(current: Job, incoming: Job): Job {
  if (TERMINAL_JOBS.has(current.status) && ACTIVE_JOBS.has(incoming.status)) return current
  return {
    ...current,
    ...incoming,
    logs: incoming.logs.length >= current.logs.length ? incoming.logs : current.logs,
    outputPath: incoming.outputPath ?? current.outputPath,
    error: incoming.error ?? current.error,
    completedAt: incoming.completedAt ?? current.completedAt,
  }
}

export function reconcileJobLists(current: Job[], incoming: Job[]): Job[] {
  const incomingIds = new Set(incoming.map((job) => job.id))
  const reconciledIncoming = incoming.map((job) => {
    const existing = current.find((item) => item.id === job.id)
    return existing ? reconcileJob(existing, job) : job
  })
  const pendingDurable = current.filter((job) => !incomingIds.has(job.id) && ACTIVE_JOBS.has(job.status))
  return [...pendingDurable, ...reconciledIncoming]
}

export function applyWorkerEvent(job: Job, message: WorkerEvent, stageLabels: Record<string, string>, now = new Date().toISOString()): Job {
  if (TERMINAL_JOBS.has(job.status)) return job
  const logs = message.message ? [...job.logs, message.message] : job.logs
  if (message.type === 'completed') {
    return { ...job, status: 'COMPLETED', stage: 'COMPLETED', outputPath: message.local_output_path, completedAt: now, logs: [...logs, '작업이 완료되었습니다.'] }
  }
  if (message.type === 'failed') {
    const error = message.message || message.code || '작업이 실패했습니다.'
    return { ...job, status: 'FAILED', error, logs: [...logs, error] }
  }
  if (message.type === 'cancelled') {
    return { ...job, status: 'CANCELLED', error: message.message, logs: [...logs, message.message || '작업을 취소했습니다.'] }
  }
  if (message.type === 'remote_attached' && !TERMINAL_JOBS.has(job.status)) {
    return { ...job, status: 'RUNNING', functionCallId: message.function_call_id, logs: [...logs, 'Modal 작업에 연결되었습니다.'] }
  }
  if (TERMINAL_JOBS.has(job.status)) return job
  const stage = message.stage && stageLabels[message.stage] ? message.stage as JobStage : job.stage
  const status: JobStatus = stage === 'RESULT_DOWNLOADING' || stage === 'AUDIO_DOWNLOADING' ? 'DOWNLOADING' : 'RUNNING'
  return { ...job, stage, status, logs: message.stage ? [...logs, stageLabels[message.stage] || message.stage] : logs }
}
