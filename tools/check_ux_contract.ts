import { contractViolations } from '../src/ux/contractCheck'

export function contractCheckReport(): string {
  const violations = contractViolations()
  return violations.length === 0 ? 'UX contract check passed' : violations.map((violation) => `${violation.code}: ${violation.detail}`).join('\n')
}
