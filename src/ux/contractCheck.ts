import { REQUIRED_FIXTURES } from './fixtures'
import {
  ACCOUNT_STATUSES,
  CAPABILITY_IDS,
  CONNECTION_HEALTH,
  CONNECTION_STATUSES,
  COST_STATES,
  JOB_STATUSES,
  MATERIAL_STATUSES,
  NODE_STATUSES,
  PROJECT_STATUSES,
  STUDIO_RUN_STATUSES,
  VERIFICATION_SCENARIOS,
  capabilityMatrix,
  isTerminalStatus,
  type CapabilityContext,
} from './contract'

export interface ContractViolation {
  code: string
  detail: string
}

function context(surface: CapabilityContext['surface'], connection: CapabilityContext['connection'] = 'healthy'): CapabilityContext {
  return { surface, connection, accountAvailable: connection === 'healthy', localToolAvailable: connection === 'healthy' }
}

export function contractViolations(): ContractViolation[] {
  const violations: ContractViolation[] = []
  const browser = capabilityMatrix(context('browser-preview'))
  for (const id of ['persistProject', 'callExternalService', 'renderLocally'] as const) {
    if (browser[id].allowed || !browser[id].reason || browser[id].nextAction !== 'Tauri 앱에서 열기') {
      violations.push({ code: 'browser-mutation', detail: `${id} must stay blocked in browser preview` })
    }
  }
  if (!browser.editTemporaryDocument.allowed || !browser.browseSampleState.allowed) {
    violations.push({ code: 'browser-read', detail: 'temporary editing and sample browsing must remain available' })
  }

  for (const health of CONNECTION_HEALTH) {
    const decision = capabilityMatrix(context('tauri', health))
    for (const id of CAPABILITY_IDS) {
      if (!decision[id].reason || !decision[id].nextAction) {
        violations.push({ code: 'missing-reason', detail: `${health}/${id} has no user-facing reason` })
      }
    }
  }

  const expired = capabilityMatrix({ surface: 'tauri', connection: 'expired-login', accountAvailable: false, localToolAvailable: true })
  if (expired.callExternalService.allowed) violations.push({ code: 'expired-account', detail: 'expired login cannot call an external service' })
  if (!expired.renderLocally.allowed) violations.push({ code: 'local-tool', detail: 'local rendering depends on the tool, not account expiry' })
  const readOnly = capabilityMatrix({ surface: 'tauri', connection: 'read-only', accountAvailable: true, localToolAvailable: true })
  if (!readOnly.persistProject.allowed || readOnly.renderLocally.allowed) {
    violations.push({ code: 'capability-scope', detail: 'read-only gating must not block unrelated Tauri capabilities' })
  }

  if (isTerminalStatus('job', 'RUNNING') || !isTerminalStatus('job', 'CANCELLED')) {
    violations.push({ code: 'job-terminal', detail: 'job terminal states drifted' })
  }
  if (isTerminalStatus('studio-run', 'prepared') || isTerminalStatus('studio-run', 'cancel_requested') || !isTerminalStatus('studio-run', 'cancelled')) {
    violations.push({ code: 'run-terminal', detail: 'studio run terminal states drifted' })
  }

  const covered = new Set(VERIFICATION_SCENARIOS.flatMap((scenario) => scenario.requiredStates))
  for (const state of [...JOB_STATUSES, ...STUDIO_RUN_STATUSES, ...NODE_STATUSES, ...CONNECTION_STATUSES, ...CONNECTION_HEALTH, ...COST_STATES, ...PROJECT_STATUSES, ...MATERIAL_STATUSES, ...ACCOUNT_STATUSES, ...REQUIRED_FIXTURES]) {
    if (!covered.has(state)) violations.push({ code: 'scenario-gap', detail: `${state} is not covered by a verification scenario` })
  }
  const expected = ['empty', 'loading', 'pending', 'failed', 'cancelled', 'stale', 'offline', 'expired-login', 'cost-unknown']
  if (REQUIRED_FIXTURES.length !== expected.length || expected.some((state) => !REQUIRED_FIXTURES.includes(state as typeof REQUIRED_FIXTURES[number])) || new Set(REQUIRED_FIXTURES).size !== expected.length) {
    violations.push({ code: 'fixture-gap', detail: 'the exact nine unique renderable state fixtures are required' })
  }
  return violations
}
