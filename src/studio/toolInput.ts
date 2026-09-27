// MCP 도구 노드의 실행 전 호환성 검사.
// 서버에서 사라진 도구를 부르거나, 필수 입력이 빠진 채 호출하지 않는다.

export type ToolLike = {
  name: string
  enabled?: boolean
  inputSchema?: Record<string, unknown>
}

export type ToolCallCheck = { ok: true } | { ok: false; reason: string }

export function checkToolCall(tools: ToolLike[], toolName: string, args: unknown): ToolCallCheck {
  if (!toolName) {
    return { ok: false, reason: '실행할 도구를 선택하세요.' }
  }
  const tool = tools.find((row) => row.name === toolName)
  if (!tool) {
    return {
      ok: false,
      reason: `이 연결에서 도구를 찾을 수 없습니다: ${toolName}. 연결 관리에서 연결 테스트를 다시 실행하세요.`,
    }
  }
  if (tool.enabled === false) {
    return { ok: false, reason: `이 도구는 사용할 수 없습니다: ${toolName}` }
  }
  const schema = tool.inputSchema ?? {}
  const expectsObject =
    schema.type === 'object' || Boolean(schema.properties) || Array.isArray(schema.required)
  const isPlainObject = Boolean(args) && typeof args === 'object' && !Array.isArray(args)
  if (expectsObject && !isPlainObject) {
    return {
      ok: false,
      reason: `이 도구는 JSON 객체 입력이 필요합니다: ${toolName}`,
    }
  }
  const required = Array.isArray(schema.required)
    ? (schema.required as unknown[]).filter((value): value is string => typeof value === 'string')
    : []
  if (required.length === 0) return { ok: true }
  if (!isPlainObject) {
    return {
      ok: false,
      reason: `이 도구에는 필수 입력이 있습니다(${required.join(', ')}). 입력 JSON을 객체로 작성하세요.`,
    }
  }
  const missing = required.filter((key) => !(key in (args as Record<string, unknown>)))
  if (missing.length > 0) {
    return { ok: false, reason: `필수 입력이 빠졌습니다: ${missing.join(', ')}` }
  }
  return { ok: true }
}
