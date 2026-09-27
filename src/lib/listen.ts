// 이벤트 리스너 등록 도우미.
//
// React StrictMode는 개발 모드에서 effect를 두 번 실행한다. 비동기 등록이 끝나기
// 전에 정리 함수가 불리면 리스너가 하나 더 남아 이벤트가 두 번 전달되므로,
// 등록이 늦게 끝나도 새지 않게 정리한다.
import { listen } from '@tauri-apps/api/event'

export function listenSafely<T>(event: string, handler: (payload: T) => void): () => void {
  let cancelled = false
  let stop: (() => void) | null = null
  void listen<T>(event, (message) => handler(message.payload)).then((unlisten) => {
    if (cancelled) unlisten()
    else stop = unlisten
  })
  return () => {
    cancelled = true
    if (stop) stop()
  }
}

export function registerSafely(register: () => Promise<() => void>): () => void {
  let cancelled = false
  let stop: (() => void) | null = null
  void register().then((unlisten) => {
    if (cancelled) unlisten()
    else stop = unlisten
  })
  return () => {
    cancelled = true
    if (stop) stop()
  }
}
