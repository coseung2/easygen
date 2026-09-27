// 대화 전송 마무리와 첨부 전달 표시의 판단만 모아 둔 곳.
// 화면 코드에서 쓰고, 같은 규칙을 실제 모듈로 실행해 확인할 수 있게 한다.

/**
 * 전송이 끝난 뒤 스트림을 새로 만들지 판단한다.
 *
 * 델타나 완료가 전송보다 먼저 도착하면 화면은 이미 그 턴을 따라가고 있다.
 * 그때 빈 텍스트·streaming으로 되돌리면 받은 응답이 지워지거나 완료된 턴이
 * 다시 진행 중으로 바뀐다.
 */
export function shouldStartStream(
  streamTurnId: string,
  finishedTurnId: string,
  turnId: string | null | undefined,
): boolean {
  if (!turnId) return true
  return streamTurnId !== turnId && finishedTurnId !== turnId
}

/**
 * 전송 직전에 대화 귀속을 잡을지 판단한다.
 *
 * 화면에 아직 반영하지 않은 완료 응답이 남아 있으면(streaming·completed)
 * 건드리지 않는다. 그 답변이 다른 대화에 저장되는 편보다 낫다.
 */
export function shouldBindConversation(status: string): boolean {
  return status === 'idle'
}

/**
 * 첨부 하나의 전달 결과를 찾는다.
 *
 * 이름이 같은 소재가 둘 이상일 수 있으므로 경로로 먼저 맞추고, 경로가 없는
 * 예전 메시지는 이름으로 맞춘다.
 */
export function findDelivery<T extends { path?: string; name?: string }>(
  entries: T[],
  attachment: { path?: string; name?: string },
): T | undefined {
  if (attachment.path) {
    const byPath = entries.find((row) => row.path === attachment.path)
    if (byPath) return byPath
  }
  return entries.find((row) => row.name === attachment.name)
}
