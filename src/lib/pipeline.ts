import { call } from './tauri'

export type MediaEntry = {
  name: string
  path: string
  size_bytes: number
  modified?: string | null
}

export type PipelineInputs = {
  clips_root: string
  clips: MediaEntry[]
  audio: MediaEntry[]
  renders: MediaEntry[]
  markers: MediaEntry[]
  edits: MediaEntry[]
}

export type StoryboardShot = {
  clip: string
  in: number
  out: number
}

export type Storyboard = {
  name: string
  audio: string
  duration: number
  fps: number
  width: number
  height: number
  shots: StoryboardShot[]
  cues: TextCue[]
  beats: number[]
}

export type TextCue = {
  start: number
  end: number
  text: string
  size: number
}

export type Markers = {
  audio: string
  audio_duration_seconds?: number
  analyzed_seconds?: number
  sensitivity?: number
  min_gap_seconds?: number
  beats: number[]
  waveform: number[]
  waveform_bin_seconds?: number
}

export type PipelineEvent = {
  type: string
  run_id?: string
  plugin?: string
  message?: string
  detail?: string
  level?: string
  markers?: string
  output?: string
  metadata?: string | null
  beat_count?: number
  waveform_bins?: number
  analyzed_seconds?: number
  percent?: number
  seconds?: number
  shots?: number
  snap_cuts?: boolean
  duration_seconds?: number
  success?: boolean
  renderer?: string
  script?: string
  payload?: string
  installed_script?: string | null
  executable?: string
  artifact?: string
  /** 글꼴 대체 안내(font_missing)와 도구 미설치 안내(tool_missing)에 쓴다. */
  font?: string
  requested?: string
  substituted?: string
  tool?: string
}

export type RendererCapability = {
  kinetic_typography: boolean
  beat_reactive_cuts: boolean
  beat_reactive_effects: boolean
  audio_mux: boolean
  expressions: boolean
  max_resolution: string | null
  watermark: boolean
}

export type RendererInfo = {
  id: string
  name: string
  execution: 'batch' | 'project_handoff'
  available: boolean
  capabilities: RendererCapability
  executable: string | null
  version: string | null
  unavailable_reason: string | null
  notes: string | null
}

export type StoragePaths = {
  clips: string
  music: string
  deliverables: string
  thumbs: string
  edits: string
  studio: string
}

/** Only the native backend decides the local storage location. */
export const getStoragePaths = () => call<StoragePaths>('storage_paths')

export function childPath(root: string, ...parts: string[]): string {
  const separator = root.includes('\\') ? '\\' : '/'
  return [root.replace(/[\\/]+$/, ''), ...parts].join(separator)
}

export const listPipelineInputs = (clipsRoot?: string) =>
  call<PipelineInputs>('list_pipeline_inputs', { clipsRoot: clipsRoot || null })

export const readJsonFile = <T>(path: string) => call<T>('read_json_file', { path })

export const writeJsonFile = (path: string, value: unknown) =>
  call<void>('write_json_file', { path, value })

export const makeThumbnail = (path: string, time = 1.5) =>
  call<string>('make_thumbnail', { path, time })

/** 무음 트랙. 오디오 입력 없이 타이포·모션만 렌더할 때 쓴다. */
export const generateSilence = (path: string, seconds: number) =>
  call<string>('generate_silence', { path, seconds })

/** 단색 배경 클립. 배경 소재가 없을 때 쓴다. */
export const generateColorClip = (
  path: string,
  seconds: number,
  width: number,
  height: number,
  color?: string,
) => call<string>('generate_color_clip', { path, seconds, width, height, color: color ?? null })

/** 이미지 한 장을 지정 길이의 클립으로 만든다. */
export const generateStillClip = (
  path: string,
  source: string,
  seconds: number,
  width: number,
  height: number,
) => call<string>('generate_still_clip', { path, source, seconds, width, height })

export const revealInExplorer = (path: string) => call<void>('reveal_in_explorer', { path })

export const openWithDefault = (path: string) => call<void>('open_with_default', { path })

export const listRenderers = () =>
  call<{ renderers: RendererInfo[] }>('list_renderers').then((value) => value.renderers)

export const analyzeAudio = (request: {
  run_id: string
  audio: string
  output: string
  duration: number
  sensitivity: number
  min_gap: number
  max_beats: number
  bins: number
}) => call<void>('analyze_audio', { request })

export const renderTrailer = (request: {
  run_id: string
  mode: 'base' | 'graphics'
  audio: string
  clips_root: string
  markers?: string | null
  cues?: string | null
  output: string
  metadata?: string | null
  duration: number
  shot_seconds: number
  snap_cuts: boolean
  renderer: string
  renderer_options?: string[]
}) => call<void>('render_trailer', { request })

export const buildStoryboard = (request: {
  audio: string
  output: string
  clips_root?: string | null
  markers?: string | null
  duration?: number
  shot_seconds?: number
  snap_cuts?: boolean
}) => call<Storyboard>('build_storyboard', { request })

export const renderSpec = (request: {
  run_id: string
  spec: string
  output: string
  metadata?: string | null
  mode?: 'base' | 'graphics'
  renderer?: string
}) => call<void>('render_spec', { request })

export function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)))
  return (bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1) + ' ' + units[index]
}

export function slug(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'run'
}
