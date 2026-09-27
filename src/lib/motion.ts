// 모션·타이포 공통 표현(문서 8장).
//
// 내부 편집 시간은 정수 tick(1/24000초)으로 다룬다. 초 단위 표시와 별개로
// 프레임 반올림 오차를 제한하기 위해서다.

export const TICKS_PER_SECOND = 24000

export function secondsToTicks(seconds: number): number {
  return Math.round(seconds * TICKS_PER_SECOND)
}

export function ticksToSeconds(ticks: number): number {
  return ticks / TICKS_PER_SECOND
}

export type MotionLayerKind = 'video' | 'image' | 'text' | 'shape' | 'audio'

export type MotionKeyframe = {
  /** 시작 tick (정수) */
  tick: number
  x?: number
  y?: number
  scale?: number
  rotation?: number
  opacity?: number
  easing?: 'linear' | 'ease-in' | 'ease-out' | 'ease-in-out'
}

export type MotionLayer = {
  id: string
  kind: MotionLayerKind
  name: string
  /** 연결된 소재 경로(있는 경우). 렌더러가 읽을 수 있는 실제 파일 */
  source?: string
  /** 정확한 텍스트 레이어 문구. AI 생성 영상의 글자는 정확성 확인 대상이 아니다 */
  text?: string
  font?: string
  color?: string
  align?: 'left' | 'center' | 'right'
  startTick: number
  endTick: number
  keyframes: MotionKeyframe[]
}

export type MotionSpec = {
  version: 1
  name: string
  width: number
  height: number
  fps: number
  durationTicks: number
  /** 렌더러가 실제로 처리할 수 있는 기능만 담는다 */
  layers: MotionLayer[]
  /** 이 표현에는 있지만 선택한 렌더러가 지원하지 않는 항목 */
  unsupported: string[]
}

export type TypoCue = { start: number; end: number; text: string; size: number; font?: string }

/** 렌더에 들어갈 컷 하나. 배경 클립의 사용 구간을 초 단위로 기록한다. */
export type MotionShot = { clip: string; in: number; out: number }

/** 타이포 노드 설정에서 정확한 문구 큐를 만든다. 문구는 그대로 렌더에 들어간다. */
export function cuesFromCopy(options: {
  copy: string
  durationSeconds: number
  entrance: string
  timing?: string
  fontSize?: number
  font?: string
}): TypoCue[] {
  const lines = options.copy
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
  if (lines.length === 0) return []
  const total = Math.max(0.5, options.durationSeconds)
  const perLine = total / lines.length
  return lines.map((text, index) => ({
    start: Number((index * perLine).toFixed(3)),
    end: Number(((index + 1) * perLine).toFixed(3)),
    text,
    size: options.fontSize ?? (lines.length === 1 ? 72 : 56),
    ...(options.font ? { font: options.font } : {}),
  }))
}

/**
 * 편집된 큐 JSON을 읽는다. 타임라인에서 손댄 값이 기준이고,
 * 잘못된 항목은 버려서 화면이 멈추지 않게 한다.
 */
export function parseCues(raw: unknown): TypoCue[] {
  if (typeof raw !== 'string' || raw.trim() === '') return []
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return []
  }
  if (!Array.isArray(parsed)) return []
  const cues: TypoCue[] = []
  for (const item of parsed) {
    if (!item || typeof item !== 'object') continue
    const record = item as Record<string, unknown>
    const text = typeof record.text === 'string' ? record.text : ''
    if (text.trim() === '') continue
    const start = Number(record.start)
    const end = Number(record.end)
    const size = Number(record.size)
    const cue: TypoCue = {
      start: Number.isFinite(start) ? Math.max(0, start) : 0,
      end: Number.isFinite(end) ? Math.max(0, end) : 0,
      text,
      size: Number.isFinite(size) && size > 0 ? Math.round(size) : 64,
    }
    if (typeof record.font === 'string' && record.font.trim() !== '') cue.font = record.font.trim()
    cues.push(cue)
  }
  return cues.sort((left, right) => left.start - right.start)
}

export function serializeCues(cues: TypoCue[]): string {
  return JSON.stringify(cues)
}

/** 큐가 화면과 렌더에서 같은 순서로 보이도록 시작·끝을 정리한다. */
export function normalizeCueTiming(cues: TypoCue[], durationSeconds: number): TypoCue[] {
  const limit = Math.max(0.5, durationSeconds)
  return cues
    .map((cue) => {
      const start = Math.min(Math.max(0, cue.start), Math.max(0, limit - 0.2))
      const end = Math.min(Math.max(start + 0.2, cue.end), limit)
      return { ...cue, start: Number(start.toFixed(3)), end: Number(end.toFixed(3)) }
    })
    .sort((left, right) => left.start - right.start)
}

export function cuesTotalSeconds(cues: TypoCue[]): number {
  return cues.reduce((max, cue) => Math.max(max, cue.end), 0)
}

/** 타이포/모션 노드의 실행 결과를 문서 8장 표현으로 남긴다. */
export function buildMotionSpec(options: {
  name: string
  width: number
  height: number
  fps: number
  durationSeconds: number
  shots?: MotionShot[]
  cues: TypoCue[]
  audio?: string
  renderer: string
  unsupported: string[]
}): MotionSpec {
  const durationTicks = secondsToTicks(options.durationSeconds)
  const layers: MotionLayer[] = []
  for (const [index, shot] of (options.shots ?? []).entries()) {
    layers.push({
      id: `layer_video_${index + 1}`,
      kind: 'video',
      name: `컷 ${index + 1}`,
      source: shot.clip,
      startTick: secondsToTicks(Math.max(0, shot.in)),
      endTick: secondsToTicks(Math.max(shot.in, shot.out)),
      keyframes: [],
    })
  }
  for (const [index, cue] of options.cues.entries()) {
    layers.push({
      id: `layer_text_${index + 1}`,
      kind: 'text',
      name: cue.text.slice(0, 24),
      text: cue.text,
      ...(cue.font ? { font: cue.font } : {}),
      align: 'center',
      startTick: secondsToTicks(cue.start),
      endTick: secondsToTicks(cue.end),
      keyframes: [
        { tick: secondsToTicks(cue.start), opacity: 0, easing: 'ease-out' },
        { tick: secondsToTicks(cue.start + 0.25), opacity: 1 },
        { tick: secondsToTicks(Math.max(cue.end - 0.25, cue.start + 0.3)), opacity: 1 },
        { tick: secondsToTicks(cue.end), opacity: 0, easing: 'ease-in' },
      ],
    })
  }
  if (options.audio) {
    layers.push({
      id: 'layer_audio',
      kind: 'audio',
      name: '오디오',
      source: options.audio,
      startTick: 0,
      endTick: durationTicks,
      keyframes: [],
    })
  }
  return {
    version: 1,
    name: options.name,
    width: options.width,
    height: options.height,
    fps: options.fps,
    durationTicks,
    layers,
    unsupported: options.unsupported,
  }
}

/** 정확한 한국어 문구는 편집 가능한 텍스트 레이어로 렌더한다(문서 8장). */
export function specTextLayers(spec: MotionSpec): MotionLayer[] {
  return spec.layers.filter((layer) => layer.kind === 'text')
}

/** 한글이 들어간 문구인지 확인한다. 글꼴 대체 여부를 판단할 때 쓴다. */
export function hasHangul(text: string): boolean {
  return /[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]/.test(text)
}

/** ffmpeg 렌더러가 처리할 수 있는 범위 밖 항목을 알려준다. */
export function unsupportedForRenderer(spec: MotionSpec, renderer: string): string[] {
  if (renderer !== 'ffmpeg') return []
  const unsupported: string[] = []
  if (spec.layers.some((layer) => layer.kind === 'shape')) unsupported.push('도형 레이어')
  if (spec.layers.some((layer) => layer.keyframes.some((frame) => frame.rotation !== undefined))) {
    unsupported.push('회전 키프레임')
  }
  if (spec.layers.some((layer) => layer.keyframes.some((frame) => frame.scale !== undefined))) {
    unsupported.push('스케일 키프레임(글자 크기)')
  }
  return unsupported
}
