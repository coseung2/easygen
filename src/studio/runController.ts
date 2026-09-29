// 노드 실행 제어: 실행 시작, 작업 이벤트 반영, 결과 소재 등록.
//
// 실행의 실제 기준은 Rust `studio_runs`/`jobs` 행이다. 이 모듈은 그 기록을
// 화면 상태에 반영하고, 완료된 결과 파일을 프로젝트 문서의 후보 소재로 등록한다.

import type { WorkerEvent } from '../app-config'
import {
  generateColorClip,
  generateSilence,
  generateStillClip,
  getStoragePaths,
  childPath,
  readJsonFile,
  renderSpec,
  writeJsonFile,
  type PipelineEvent,
  type StoragePaths,
} from '../lib/pipeline'
import {
  buildMotionSpec,
  cuesFromCopy,
  normalizeCueTiming,
  parseCues,
  unsupportedForRenderer,
  type MotionShot,
  type TypoCue,
} from '../lib/motion'
import { isTauri } from '../lib/tauri'
import { listWorkflows } from '../lib/workflows'
import { listTemplates, renderTemplate, templateRef } from '../lib/templates'
import { isRunnable, nodeSpec } from './catalog'
import { cancelNodeRun, finishNodeRun, kindFromExtension, listNodeRuns, probePath, retryRunDownload, startLocalRun, startNodeRun } from './lib'
import { callConnectionTool, listConnectionTools } from '../lib/connections'
import { useStudioStore } from './store'
import { checkToolCall } from './toolInput'
import { isActiveRun, isTerminalRun, uid, type PortType, type StudioAsset, type StudioNode, type StudioRunRow } from './types'

function studioArtifactPath(paths: StoragePaths, projectId: string, name: string): string {
  return childPath(paths.studio, projectId, 'artifacts', name)
}

export interface StartResult {
  ok: boolean
  reason?: string
}

function configText(node: StudioNode, key: string): string {
  const value = node.config[key]
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number') return String(value)
  return ''
}

function configNumber(node: StudioNode, key: string): number | null {
  const value = node.config[key]
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
    return Number(value)
  }
  return null
}

/// 포트 자료형에 맞는 소재만 입력으로 쓴다. 다른 종류의 결과가 섞여도
/// 영상 포트에 JSON이 들어가는 식으로 조용히 잘못 전달되지 않게 한다.
const PORT_ASSET_KINDS: Partial<Record<PortType, StudioAsset['kind']>> = {
  Image: 'image',
  Video: 'video',
  Audio: 'audio',
  // 모션 구성은 JSON 파일이다. 영상 결과가 구성 입력으로 새지 않게 한다.
  MotionSpec: 'other',
}

function portTypeFor(node: StudioNode, portId: string): PortType | undefined {
  return nodeSpec(node.kind).inputs.find((port) => port.id === portId)?.type
}

function assetMatchesPort(asset: StudioAsset, portType: PortType | undefined): boolean {
  const expected = portType ? PORT_ASSET_KINDS[portType] : undefined
  if (!expected) return true
  return asset.kind === expected
}

/** 입력 포트에 연결된 소재 노드 또는 상위 노드의 최신 결과를 찾는다. */
export function incomingAsset(nodeId: string, portId: string): StudioAsset | undefined {
  const doc = useStudioStore.getState().doc
  const target = doc.nodes.find((item) => item.id === nodeId)
  const portType = target ? portTypeFor(target, portId) : undefined
  for (const edge of doc.edges.filter((item) => item.target === nodeId && item.targetHandle === portId)) {
    const source = doc.nodes.find((item) => item.id === edge.source)
    if (!source) continue
    for (const asset of sourceAssets(source, doc.assets, portType)) {
      if (assetMatchesPort(asset, portType)) return asset
    }
  }
  return undefined
}

/**
 * 상위 노드가 실제로 내보내는 소재. 후보 선택 노드는 고정한 후보만,
 * 소재 노드는 연결한 소재만, 생성 노드는 최신 결과 하나만 내보낸다.
 * 후보 비교·고정은 후보 선택 노드가 맡는다. 생성 노드의 지난 후보까지
 * 다음 노드로 흘려보내면 컷과 문구가 과거 실행과 뒤섞인다.
 */
function sourceAssets(
  source: StudioNode,
  assets: StudioAsset[],
  portType: PortType | undefined,
): StudioAsset[] {
  if (source.kind === 'asset') {
    const assetId = configText(source, 'assetId')
    return assetId ? assets.filter((item) => item.id === assetId) : []
  }
  if (source.kind === 'select') {
    const selectedId = configText(source, 'selectedAssetId')
    return selectedId ? assets.filter((item) => item.id === selectedId) : []
  }
  // 생성 노드는 포트 자료형에 맞는 최신 결과 하나만 내보낸다. 영상 노드의
  // 결과에는 영상과 구성 JSON이 함께 있으므로 자료형으로 골라야 한다.
  for (const id of source.results) {
    const asset = assets.find((item) => item.id === id)
    if (asset && assetMatchesPort(asset, portType)) return [asset]
  }
  return []
}

export function incomingAssets(nodeId: string, portIds: string[]): StudioAsset[] {
  const found = new Map<string, StudioAsset>()
  const doc = useStudioStore.getState().doc
  const target = doc.nodes.find((item) => item.id === nodeId)
  for (const portId of portIds) {
    const portType = target ? portTypeFor(target, portId) : undefined
    for (const edge of doc.edges.filter((item) => item.target === nodeId && item.targetHandle === portId)) {
      const source = doc.nodes.find((item) => item.id === edge.source)
      if (!source) continue
      for (const asset of sourceAssets(source, doc.assets, portType)) {
        if (assetMatchesPort(asset, portType) && !found.has(asset.id)) found.set(asset.id, asset)
      }
    }
  }
  return [...found.values()]
}

export function defaultToolFor(node: StudioNode): string {
  const configured = configText(node, 'tool')
  if (configured) return configured
  if (node.kind === 'video') return 'modal-h3'
  if (node.kind === 'audio') return 'yue2-music'
  return ''
}

export const TOOL_LABELS: Record<string, string> = {
  'modal-h3': 'Modal H3',
  'yue2-music': 'YuE2 음악',
  'local-ffmpeg': '로컬 FFmpeg 렌더',
  ae: 'After Effects 프로젝트',
}

function parseResolution(value: string, fallbackWidth = 1344, fallbackHeight = 768): [number, number] {
  const match = value.match(/(\d+)\s*[x×]\s*(\d+)/i)
  if (!match) return [fallbackWidth, fallbackHeight]
  return [Number(match[1]), Number(match[2])]
}

function generatedAsset(path: string): StudioAsset {
  const name = path.split(/[\\/]/).pop() ?? path
  return {
    id: uid('ast'),
    name,
    kind: kindFromExtension(name),
    storedPath: path,
    url: '',
    sizeBytes: 0,
    hash: '',
    source: 'generated',
    addedAt: new Date().toISOString(),
  }
}

async function startModalVideoRun(node: StudioNode, workflow?: { id: string; tool: string }): Promise<StartResult> {
  const tool = workflow?.tool ?? defaultToolFor(node)
  if (tool !== 'modal-h3') {
    return { ok: false, reason: `이 실행 도구는 아직 연결되지 않았습니다: ${tool}` }
  }
  const prompt = configText(node, 'prompt')
  if (!prompt) return { ok: false, reason: '프롬프트를 입력하세요.' }

  const firstFrame = incomingAsset(node.id, 'first') ?? (node.kind === 'comfy' ? incomingAsset(node.id, 'image') : undefined)
  const refs = incomingAssets(node.id, ['refs', 'image'])
  const input = firstFrame ?? refs[0]
  const kind = firstFrame ? 'fl2v' : input ? 'ref2v' : 't2v'
  const [width, height] = parseResolution(configText(node, 'resolution'))
  const seconds = configNumber(node, 'seconds') ?? 5
  const candidates = Math.min(Math.max(Math.round(configNumber(node, 'candidates') ?? 1), 1), 8)
  // 후보가 여러 개인데 seed가 비어 있으면 후보마다 같은 요청이 되어 중복으로
  // 거부된다. 이때만 기준 seed를 만들어 후보마다 다른 변주로 제출한다.
  const configuredSeed = configNumber(node, 'seed')
  const seedBase = configuredSeed ?? (candidates > 1 ? Math.floor(Math.random() * 1_000_000) : null)
  const state = useStudioStore.getState()
  // 노드에서 고른 Modal 계정으로 실행한다. 비어 있으면 앱의 기본 프로필을 쓴다.
  const profileId = configText(node, 'profileId') || null

  // 실제로 전달되는 입력만 기록한다. 참고만 한 소재를 전달했다고 표시하지 않는다.
  const inputJson = JSON.stringify({
    prompt,
    kind,
    workflow: workflow?.id ?? null,
    profile: profileId,
    resolution: `${width}x${height}`,
    seconds,
    input: input ? { id: input.id, name: input.name, path: input.storedPath, role: firstFrame ? '시작 프레임' : '레퍼런스' } : null,
    references: refs.map((asset) => ({ id: asset.id, name: asset.name })),
  })

  const created: StudioRunRow[] = []
  let submitted = 0
  try {
    for (let index = 0; index < candidates; index += 1) {
      const run = await startNodeRun({
        projectId: state.projectId,
        nodeId: node.id,
        nodeTitle: node.title,
        tool,
        prompt,
        inputPath: input?.storedPath ?? null,
        duration: seconds,
        width,
        height,
        seed: seedBase === null ? null : Math.round(seedBase) + index,
        kind,
        profileId,
        inputJson,
      })
      created.push(run)
      submitted += 1
    }
  } catch (error) {
    // 일부 후보가 이미 제출됐다면 그 사실을 화면과 기록에 남긴다.
    const store = useStudioStore.getState()
    for (const run of created) store.upsertRun(run)
    if (submitted > 0) {
      store.setNodeStatus(node.id, 'running')
      return {
        ok: true,
        reason: `후보 ${submitted}개를 제출한 뒤 중단됐습니다: ${String(error)}`,
      }
    }
    return { ok: false, reason: String(error) }
  }
  const store = useStudioStore.getState()
  for (const run of created) store.upsertRun(run)
  store.setNodeStatus(node.id, 'running')
  return { ok: true, reason: candidates > 1 ? `${candidates}개 후보 실행을 시작했습니다.` : '실행을 시작했습니다.' }
}

async function startMusicRun(node: StudioNode, workflow?: { id: string; tool: string }): Promise<StartResult> {
  const style = configText(node, 'prompt')
  if (!style) return { ok: false, reason: '음악 스타일(설명)을 입력하세요.' }
  const lyrics = configText(node, 'script')
  const seconds = configNumber(node, 'seconds') ?? 60
  const state = useStudioStore.getState()
  const profileId = configText(node, 'profileId') || null
  try {
    const run = await startNodeRun({
      projectId: state.projectId,
      nodeId: node.id,
      nodeTitle: node.title,
      tool: workflow?.tool ?? 'yue2-music',
      prompt: style,
      duration: seconds,
      style,
      lyrics,
      profileId,
      inputJson: JSON.stringify({ style, lyrics, seconds, workflow: workflow?.id ?? null, profile: profileId }),
    })
    useStudioStore.getState().upsertRun(run)
    useStudioStore.getState().setNodeStatus(node.id, 'running')
    return { ok: true, reason: '음악 실행을 시작했습니다.' }
  } catch (error) {
    return { ok: false, reason: String(error) }
  }
}

/**
 * Comfy 노드는 등록된 워크플로를 실행한다. 워크플로의 도구가 실행 경로를
 * 정하므로, 같은 캔버스에서 서로 다른 워크플로를 쓸 수 있다.
 */
async function startComfyRun(node: StudioNode): Promise<StartResult> {
  const workflowId = configText(node, 'workflow')
  if (!workflowId) {
    return { ok: false, reason: '실행할 워크플로를 선택하세요. 연결 관리 화면의 워크플로에서 등록할 수 있습니다.' }
  }
  let workflow: { id: string; tool: string; name: string } | undefined
  try {
    const rows = await listWorkflows()
    workflow = rows.find((row) => row.id === workflowId)
  } catch (error) {
    return { ok: false, reason: String(error) }
  }
  if (!workflow) {
    return { ok: false, reason: '등록된 워크플로를 찾을 수 없습니다. 연결 관리 화면에서 다시 등록하세요.' }
  }
  if (workflow.tool === 'yue2-music') return startMusicRun(node, workflow)
  if (workflow.tool === 'modal-h3') return startModalVideoRun(node, workflow)
  return { ok: false, reason: `이 워크플로 도구에는 아직 실행 경로가 없습니다: ${workflow.tool}` }
}

/// 로컬 렌더는 앱이 직접 파이프라인을 돌리므로, 진행 상황을 이어받을 수 있도록
/// 실행 id → 출력 경로를 세션 동안 기억한다.
const localRuns = new Map<string, { nodeId: string; outputPath: string; specPath?: string }>()

export function localOutputPath(runId: string): string | undefined {
  return localRuns.get(runId)?.outputPath
}

export function localSpecPath(runId: string): string | undefined {
  return localRuns.get(runId)?.specPath
}

function durationForAsset(assetId: string, fallback: number): number {
  const doc = useStudioStore.getState().doc
  const owner = doc.nodes.find((item) => item.results.includes(assetId))
  const seconds = owner ? configNumber(owner, 'seconds') : null
  return seconds && seconds > 0 ? seconds : fallback
}

/** 모션 구성(MotionSpec) 소재에서 정확한 문구 큐를 읽는다. */
export async function cuesFromSpecAssets(assets: StudioAsset[]): Promise<TypoCue[]> {
  const cues: TypoCue[] = []
  // 구성 JSON만 대상으로 최신 것 하나를 쓴다. 이전 실행의 문구까지 함께
  // 렌더되면 안 되고, 영상 결과가 구성으로 잘못 들어와도 무시해야 한다.
  const specs = assets
    .filter((asset) => asset.storedPath && /\.json$/i.test(asset.storedPath))
    .sort((left, right) => right.addedAt.localeCompare(left.addedAt))
  for (const asset of specs.slice(0, 1)) {
    try {
      const spec = await readJsonFile<{
        cues?: Array<Record<string, unknown>>
        layers?: Array<Record<string, unknown>>
      }>(asset.storedPath)
      // 렌더러가 쓰는 큐 목록을 우선 읽는다. 크기·글꼴이 그대로 들어 있다.
      for (const cue of spec.cues ?? []) {
        if (typeof cue.text !== 'string' || !cue.text.trim()) continue
        const start = Number(cue.start)
        const end = Number(cue.end)
        const size = Number(cue.size)
        cues.push({
          start: Number.isFinite(start) ? Math.max(0, start) : 0,
          end: Number.isFinite(end) ? Math.max(0, end) : 0,
          text: cue.text,
          size: Number.isFinite(size) && size > 0 ? Math.round(size) : 64,
          ...(typeof cue.font === 'string' && cue.font.trim() ? { font: cue.font.trim() } : {}),
        })
      }
      if (cues.length > 0) continue
      for (const layer of spec.layers ?? []) {
        if (layer.kind !== 'text' || typeof layer.text !== 'string' || !layer.text.trim()) continue
        const startTick = Number(layer.startTick ?? 0)
        const endTick = Number(layer.endTick ?? 0)
        cues.push({
          start: Number((startTick / 24000).toFixed(3)),
          end: Number((endTick / 24000).toFixed(3)),
          text: layer.text,
          size: 64,
          ...(typeof layer.font === 'string' && layer.font.trim() ? { font: layer.font.trim() } : {}),
        })
      }
    } catch {
      // 읽지 못한 구성은 건너뛴다. 다른 입력으로 렌더는 계속한다.
    }
  }
  return cues.sort((left, right) => left.start - right.start)
}

async function startEditRun(node: StudioNode, paths: StoragePaths): Promise<StartResult> {
  const doc = useStudioStore.getState().doc
  const videos = incomingAssets(node.id, ['video'])
  const audio = incomingAssets(node.id, ['audio'])[0]
  if (videos.length === 0) return { ok: false, reason: '편집할 영상 소재를 노드의 영상 입력에 연결하세요.' }
  if (!audio) return { ok: false, reason: '오디오 소재를 연결하세요. 음악·음성 노드나 오디오 소재가 필요합니다.' }
  if (!audio.storedPath) {
    return { ok: false, reason: '오디오 소재의 실제 파일 경로가 없습니다. Tauri 앱에서 가져온 소재만 렌더할 수 있습니다.' }
  }

  const fallbackSeconds = configNumber(node, 'shotSeconds') ?? 5
  const shots = videos.map((asset) => ({
    clip: asset.storedPath,
    in: 0,
    out: Math.max(0.5, durationForAsset(asset.id, fallbackSeconds)),
  }))
  const missing = shots.filter((shot) => !shot.clip)
  if (missing.length > 0) {
    return { ok: false, reason: '경로가 없는 소재가 있습니다. 생성 결과나 가져온 소재만 렌더할 수 있습니다.' }
  }

  const [width, height] = parseResolution(configText(node, 'resolution') || '1920x1080', 1920, 1080)
  const fps = Math.round(configNumber(node, 'fps') ?? 24)
  const total = shots.reduce((sum, shot) => sum + shot.out, 0)
  // 모션·타이포 노드의 구성을 연결했다면 정확한 문구를 함께 렌더한다.
  const specs = incomingAssets(node.id, ['spec'])
  const cues = normalizeCueTiming(await cuesFromSpecAssets(specs), total)
  const mode = cues.length > 0 ? 'graphics' : 'base'
  const state = useStudioStore.getState()

  let run: StudioRunRow
  try {
    run = await startLocalRun({
      projectId: state.projectId,
      nodeId: node.id,
      nodeTitle: node.title,
      tool: 'local-ffmpeg',
      inputJson: JSON.stringify({
        shots: shots.map((shot) => shot.clip),
        total,
        audio: audio.name,
        fps,
        resolution: `${width}x${height}`,
        specs: specs.map((asset) => asset.name),
        cues: cues.length,
      }),
    })
  } catch (error) {
    return { ok: false, reason: String(error) }
  }

  const specPath = childPath(paths.edits, `${run.id}-spec.json`)
  const outputPath = childPath(paths.edits, `${run.id}.mp4`)
  const spec = {
    name: run.id,
    audio: audio.storedPath,
    duration: Number(total.toFixed(3)),
    fps,
    width,
    height,
    shots,
    cues,
    beats: [],
  }
  try {
    await writeJsonFile(specPath, spec)
    localRuns.set(run.id, { nodeId: node.id, outputPath })
    await renderSpec({ run_id: run.id, spec: specPath, output: outputPath, mode, renderer: 'ffmpeg' })
  } catch (error) {
    localRuns.delete(run.id)
    void finishNodeRun(run.id, 'failed', null, String(error)).catch(() => undefined)
    useStudioStore.getState().upsertRun({ ...run, status: 'failed', errorMessage: String(error) })
    useStudioStore.getState().setNodeStatus(node.id, 'failed')
    return { ok: false, reason: String(error) }
  }

  const store = useStudioStore.getState()
  store.upsertRun(run)
  store.setNodeStatus(node.id, 'running')
  return { ok: true, reason: `로컬 렌더를 시작했습니다. 컷 ${shots.length}개 · ${total.toFixed(1)}초` }
}

/**
 * 타이포·모션 노드 실행(문서 8장). 정확한 문구는 편집 가능한 텍스트 레이어로
 * 렌더하고, 구성(MotionSpec)을 프로젝트 폴더에 남겨 다음 노드가 다시 쓴다.
 */
async function startGraphicsRun(node: StudioNode, kind: 'typo' | 'motion', paths: StoragePaths): Promise<StartResult> {
  const state = useStudioStore.getState()
  const projectId = state.projectId
  const duration = Math.max(0.5, configNumber(node, 'seconds') ?? (kind === 'typo' ? 6 : 8))
  const [width, height] = parseResolution(configText(node, 'resolution') || '1920x1080', 1920, 1080)
  const fps = Math.round(configNumber(node, 'fps') ?? 24)
  const font = configText(node, 'font')
  const copy = configText(node, 'copy')
  const configuredTool = configText(node, 'tool')
  const renderer = configuredTool === 'ae' ? 'ae' : 'ffmpeg'

  // 타임라인에서 손본 큐가 우선이고, 없으면 정확한 문구를 균등 배분한다.
  let cues = parseCues(node.config.cues)
  if (cues.length === 0 && copy) {
    cues = cuesFromCopy({
      copy,
      durationSeconds: duration,
      entrance: configText(node, 'entrance') || 'fade',
      timing: configText(node, 'timing'),
      font: font || undefined,
    })
  }
  cues = normalizeCueTiming(cues, duration)
  if (kind === 'typo' && cues.length === 0) {
    return { ok: false, reason: '렌더에 넣을 정확한 문구를 입력하세요. 문구는 그대로 화면에 들어갑니다.' }
  }

  const video = incomingAsset(node.id, 'video')
  const images = incomingAssets(node.id, kind === 'typo' ? ['image'] : ['source'])
  const audio = incomingAsset(node.id, 'audio')
  const backgroundCount = video ? 1 : images.length

  let run: StudioRunRow
  try {
    run = await startLocalRun({
      projectId,
      nodeId: node.id,
      nodeTitle: node.title,
      tool: renderer === 'ae' ? 'ae' : 'local-ffmpeg',
      inputJson: JSON.stringify({
        kind,
        renderer,
        // 문구 내용뿐 아니라 타이밍·크기·글꼴까지 제출 기록에 남긴다.
        // 그래야 시간만 바꾼 재실행이 중복으로 거부되지 않는다.
        cues: cues.map((cue) => ({
          start: cue.start,
          end: cue.end,
          size: cue.size,
          text: cue.text,
          font: cue.font ?? null,
        })),
        cueCount: cues.length,
        background: video ? video.name : images.map((asset) => asset.name),
        audio: audio?.name ?? '무음',
        duration,
        fps,
        resolution: `${width}x${height}`,
        font: font || null,
      }),
    })
  } catch (error) {
    return { ok: false, reason: String(error) }
  }

  const specPath = studioArtifactPath(paths, projectId, `${run.id}.motion.json`)
  const outputPath = childPath(paths.edits, `${run.id}.mp4`)
  try {
    const shots: MotionShot[] = []
    if (video?.storedPath) {
      shots.push({ clip: video.storedPath, in: 0, out: durationForAsset(video.id, duration) })
    } else {
      const usable = images.filter((asset) => asset.storedPath)
      if (usable.length > 0) {
        const per = Number((duration / usable.length).toFixed(3))
        for (const [index, asset] of usable.entries()) {
          const clip = studioArtifactPath(paths, projectId, `${run.id}-still-${index + 1}.mp4`)
          await generateStillClip(clip, asset.storedPath, per, width, height)
          shots.push({ clip, in: 0, out: per })
        }
      } else {
        const clip = studioArtifactPath(paths, projectId, `${run.id}-background.mp4`)
        await generateColorClip(clip, duration, width, height, '#101418')
        shots.push({ clip, in: 0, out: Number(duration.toFixed(3)) })
      }
    }
    const audioPath = audio?.storedPath
      ? audio.storedPath
      : await generateSilence(studioArtifactPath(paths, projectId, `${run.id}-silence.wav`), duration)
    const motion = buildMotionSpec({
      name: run.id,
      width,
      height,
      fps,
      durationSeconds: duration,
      shots,
      cues,
      audio: audioPath,
      renderer,
      unsupported: [],
    })
    motion.unsupported = unsupportedForRenderer(motion, renderer)
    // 같은 파일을 렌더러(샷·큐)와 다음 노드(레이어 구성)가 함께 읽는다.
    const spec = {
      name: run.id,
      audio: audioPath,
      duration: Number(duration.toFixed(3)),
      fps,
      width,
      height,
      shots: shots.map((shot) => ({ clip: shot.clip, in: shot.in, out: shot.out })),
      cues: cues.map((cue) => ({
        start: cue.start,
        end: cue.end,
        text: cue.text,
        size: cue.size,
        ...(cue.font ? { font: cue.font } : {}),
      })),
      beats: [],
      version: motion.version,
      durationTicks: motion.durationTicks,
      layers: motion.layers,
      unsupported: motion.unsupported,
    }
    await writeJsonFile(specPath, spec)
    localRuns.set(run.id, { nodeId: node.id, outputPath, specPath })
    await renderSpec({ run_id: run.id, spec: specPath, output: outputPath, mode: 'graphics', renderer })
  } catch (error) {
    localRuns.delete(run.id)
    void finishNodeRun(run.id, 'failed', null, String(error)).catch(() => undefined)
    useStudioStore.getState().upsertRun({ ...run, status: 'failed', errorMessage: String(error) })
    useStudioStore.getState().setNodeStatus(node.id, 'failed')
    return { ok: false, reason: String(error) }
  }

  const store = useStudioStore.getState()
  store.upsertRun(run)
  store.setNodeStatus(node.id, 'running')
  const label = renderer === 'ae' ? 'After Effects 프로젝트' : '렌더'
  return {
    ok: true,
    reason: `${label}를 시작했습니다. 문구 ${cues.length}개 · 배경 ${backgroundCount || '단색'} · ${duration.toFixed(1)}초`,
  }
}

/// 로컬 렌더 파이프라인 이벤트를 실행 기록에 반영한다.
export function applyPipelineEvent(event: PipelineEvent): void {
  const runId = event.run_id
  if (!runId) return
  const local = localRuns.get(runId)
  if (!local) return
  const store = useStudioStore.getState()
  const run = store.runs.find((item) => item.id === runId)

  if (event.type === 'render_completed' || event.type === 'prepare_completed') {
    const output = event.output ?? event.artifact ?? local.outputPath
    const prepared = event.type === 'prepare_completed'
    const specPath = local.specPath
    localRuns.delete(runId)
    void finishNodeRun(runId, prepared ? 'prepared' : 'completed', output, null, null)
      .then((updated) => {
        useStudioStore.getState().upsertRun(updated)
        registerRunOutput(runId, output)
        if (specPath) registerSpecAsset(local.nodeId, specPath)
        if (prepared) {
          useStudioStore.getState().setNotice('편집 프로젝트를 준비했습니다. 생성된 파일을 열어 이어서 작업하세요.')
        }
      })
      .catch((error) => useStudioStore.getState().setNotice(String(error)))
    return
  }
  if (event.type === 'font_missing') {
    const requested = typeof event.font === 'string' ? event.font : '요청한 글꼴'
    useStudioStore.getState().setNotice(`${requested} 파일을 찾지 못해 대체 글꼴로 렌더합니다.`)
    return
  }
  if (event.type === 'tool_missing') {
    const reason = typeof event.detail === 'string' ? event.detail : '설치를 확인하지 못했습니다.'
    useStudioStore.getState().setNotice(`외부 도구를 찾지 못했습니다: ${reason}`)
    return
  }
  if (event.type === 'failed' || (event.type === 'process_exit' && event.success === false)) {
    const message = event.message ?? (event.detail ? `파이프라인 오류: ${event.detail.slice(0, 180)}` : '로컬 렌더가 실패했습니다.')
    localRuns.delete(runId)
    void finishNodeRun(runId, 'failed', null, message).catch(() => undefined)
    if (run) useStudioStore.getState().upsertRun({ ...run, status: 'failed', errorMessage: message })
    useStudioStore.getState().setNodeStatus(local.nodeId, 'failed')
    useStudioStore.getState().setNotice(message)
    return
  }
  if (run && (event.type === 'render_progress' || event.type === 'stage' || event.type === 'log')) {
    const stage = event.percent !== undefined ? `렌더 ${Math.round(event.percent)}%` : event.type
    useStudioStore.getState().upsertRun({ ...run, status: 'running', stage })
  }
}

const FILE_EXTENSIONS = /\.(png|jpg|jpeg|webp|gif|bmp|tif|tiff|avif|mp4|mov|webm|mkv|avi|m4v|wav|mp3|flac|m4a|aac|ogg|json|txt|md|svg|psd|aep|agp|zip)$/i

/** 결과 JSON에서 파일처럼 보이는 문자열을 모은다. 존재 확인은 별도로 한다. */
export function fileCandidates(value: unknown, found: Set<string> = new Set<string>()): Set<string> {
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (FILE_EXTENSIONS.test(trimmed) && /^[A-Za-z]:[\\/]/.test(trimmed)) found.add(trimmed)
    return found
  }
  if (Array.isArray(value)) {
    for (const item of value) fileCandidates(item, found)
    return found
  }
  if (value && typeof value === 'object') {
    for (const item of Object.values(value as Record<string, unknown>)) fileCandidates(item, found)
  }
  return found
}

async function startToolRun(node: StudioNode, paths: StoragePaths): Promise<StartResult> {
  const connectionId = configText(node, 'connection')
  const tool = configText(node, 'tool')
  if (!connectionId) {
    return { ok: false, reason: '연결 관리에서 MCP 연결을 등록하고 이 노드에서 선택하세요.' }
  }
  if (!tool) return { ok: false, reason: '실행할 도구를 선택하세요.' }
  const rawInput = configText(node, 'input')
  let args: unknown = {}
  if (rawInput) {
    try {
      args = JSON.parse(rawInput)
    } catch {
      return { ok: false, reason: '입력 JSON을 해석하지 못했습니다. JSON 형식으로 입력하세요.' }
    }
  }
  // 도구가 사라졌거나 필수 입력이 빠진 채로 호출하지 않는다.
  try {
    const tools = await listConnectionTools(connectionId)
    const compatible = checkToolCall(tools, tool, args)
    if (!compatible.ok) return compatible
  } catch (error) {
    return { ok: false, reason: `연결의 도구 목록을 읽지 못했습니다: ${String(error)}` }
  }
  const state = useStudioStore.getState()
  let run: StudioRunRow
  try {
    run = await startLocalRun({
      projectId: state.projectId,
      nodeId: node.id,
      nodeTitle: node.title,
      tool: `mcp:${tool}`,
      inputJson: JSON.stringify({ connectionId, tool, arguments: args }),
    })
  } catch (error) {
    return { ok: false, reason: String(error) }
  }
  useStudioStore.getState().upsertRun(run)
  useStudioStore.getState().setNodeStatus(node.id, 'running')

  try {
    const result = await callConnectionTool(connectionId, tool, args)
    const resultPath = studioArtifactPath(paths, state.projectId, `${run.id}.json`)
    await writeJsonFile(resultPath, { connectionId, tool, arguments: args, result })

    // 도구가 오류를 돌려줬으면 성공으로 기록하지 않는다.
    const toolError = toolErrorMessage(result)
    if (toolError) {
      const failed = await finishNodeRun(run.id, 'failed', resultPath, toolError)
      useStudioStore.getState().upsertRun(failed)
      useStudioStore.getState().setNodeStatus(node.id, 'failed')
      return { ok: false, reason: `도구 실행이 실패했습니다: ${toolError}` }
    }

    // 결과가 가리키는 실제 파일만 소재 등록 후보로 남긴다.
    const detected: string[] = []
    for (const candidate of fileCandidates(result)) {
      try {
        const probe = await probePath(candidate)
        if (probe.exists && probe.isFile && probe.kind !== 'other') detected.push(candidate)
      } catch {
        // 확인 실패는 후보에서 제외한다.
      }
    }

    const updated = await finishNodeRun(run.id, 'completed', resultPath, null, null)
    useStudioStore.getState().upsertRun(updated)
    registerRunOutput(run.id, resultPath)
    if (configText(node, 'detectedFiles') !== JSON.stringify(detected)) {
      useStudioStore.getState().updateNode(node.id, { config: { detectedFiles: JSON.stringify(detected) } })
    }
    useStudioStore.getState().setNotice(
      detected.length > 0
        ? `도구 실행 완료. 결과에서 파일 ${detected.length}개를 찾았습니다. 검사 패널에서 소재로 등록할 수 있습니다.`
        : '도구 실행을 마치고 원본 결과를 저장했습니다.',
    )
    return { ok: true, reason: '도구를 실행했습니다.' }
  } catch (error) {
    void finishNodeRun(run.id, 'failed', null, String(error)).catch(() => undefined)
    useStudioStore.getState().upsertRun({ ...run, status: 'failed', errorMessage: String(error) })
    useStudioStore.getState().setNodeStatus(node.id, 'failed')
    return { ok: false, reason: String(error) }
  }
}

/** MCP 결과가 오류를 담고 있으면 사유를 돌려준다. 성공으로 기록하지 않기 위해서다. */
export function toolErrorMessage(result: unknown): string {
  if (!result || typeof result !== 'object') return ''
  const record = result as Record<string, unknown>
  if (record.isError === true) {
    const content = Array.isArray(record.content) ? record.content : []
    const text = content
      .map((item) => (
        item && typeof item === 'object' && typeof (item as { text?: unknown }).text === 'string'
          ? String((item as { text: string }).text)
          : ''
      ))
      .filter(Boolean)
      .join(' ')
    return text.trim() || '도구가 오류 결과를 반환했습니다.'
  }
  if (typeof record.error === 'string' && record.error.trim()) return record.error.trim()
  return ''
}

/**
 * 영상 템플릿 노드 실행. 템플릿(pipelines/<id>/<ver>)은 입력 JSON만 받아 이 컴퓨터에서
 * 렌더하고, 진행 이벤트는 다른 로컬 렌더와 같은 pipeline-event로 들어온다.
 */
async function startTemplateRun(node: StudioNode, paths: StoragePaths): Promise<StartResult> {
  const ref = configText(node, 'template')
  if (!ref) return { ok: false, reason: '템플릿을 고르세요.' }
  const templates = await listTemplates()
  const template = templates.find((item) => templateRef(item) === ref)
  if (!template) return { ok: false, reason: `템플릿을 찾을 수 없습니다: ${ref}` }
  if (!template.runnable) return { ok: false, reason: template.unavailableReason ?? '이 템플릿은 지금 실행할 수 없습니다.' }

  let job: Record<string, unknown>
  try {
    const parsed: unknown = JSON.parse(configText(node, 'job') || '{}')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('not an object')
    job = parsed as Record<string, unknown>
  } catch {
    return { ok: false, reason: '템플릿 입력을 JSON 객체로 해석하지 못했습니다.' }
  }
  const missing = missingMedia(job)
  if (missing.length > 0) {
    return { ok: false, reason: `소재 경로를 채우세요: ${missing.slice(0, 3).join(', ')}${missing.length > 3 ? ' 외' : ''}` }
  }

  const state = useStudioStore.getState()
  let run: StudioRunRow
  try {
    run = await startLocalRun({
      projectId: state.projectId,
      nodeId: node.id,
      nodeTitle: node.title,
      tool: `template:${ref}`,
      inputJson: JSON.stringify({ template: ref, job }),
    })
  } catch (error) {
    return { ok: false, reason: String(error) }
  }
  const outputPath = studioArtifactPath(paths, state.projectId, `${run.id}.mp4`)
  try {
    localRuns.set(run.id, { nodeId: node.id, outputPath })
    await renderTemplate({ run_id: run.id, template: ref, job, output: outputPath })
  } catch (error) {
    localRuns.delete(run.id)
    void finishNodeRun(run.id, 'failed', null, String(error)).catch(() => undefined)
    useStudioStore.getState().upsertRun({ ...run, status: 'failed', errorMessage: String(error) })
    useStudioStore.getState().setNodeStatus(node.id, 'failed')
    return { ok: false, reason: String(error) }
  }
  const store = useStudioStore.getState()
  store.upsertRun(run)
  store.setNodeStatus(node.id, 'running')
  return { ok: true, reason: `${template.label} 렌더를 시작했습니다. 인물 따내기 때문에 첫 실행은 몇 분 걸릴 수 있습니다.` }
}

/** 입력 JSON에서 비어 있는 media 경로를 찾는다. 빈 경로로 렌더를 시작하지 않기 위해서다. */
export function missingMedia(value: unknown, path = ''): string[] {
  if (Array.isArray(value)) return value.flatMap((item, index) => missingMedia(item, `${path}[${index}]`))
  if (!value || typeof value !== 'object') return []
  const found: string[] = []
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    const here = path ? `${path}.${key}` : key
    if (key === 'media' && (typeof item !== 'string' || item.trim() === '')) found.push(here)
    else found.push(...missingMedia(item, here))
  }
  return found
}

export async function startStudioRun(nodeId: string): Promise<StartResult> {
  const node = useStudioStore.getState().doc.nodes.find((item) => item.id === nodeId)
  if (!node) return { ok: false, reason: '노드를 찾을 수 없습니다.' }
  const spec = nodeSpec(node.kind)
  if (!isTauri) {
    return {
      ok: false,
      reason: '실행은 Tauri 앱에서 동작합니다. 브라우저 미리보기에서는 편집과 저장만 확인할 수 있습니다.',
    }
  }
  if (!isRunnable(node.kind)) {
    return {
      ok: false,
      reason: spec.executionStage === null
        ? '기획·구성 노드는 실행 대신 다른 노드의 입력으로 쓰입니다.'
        : `${spec.label} 노드의 실행은 ${spec.executionStage}단계에서 연결됩니다.`,
    }
  }
  if (node.kind === 'video') return startModalVideoRun(node)
  if (node.kind === 'comfy') return startComfyRun(node)
  if (node.kind === 'audio') return startMusicRun(node)
  if (['edit', 'typo', 'motion', 'tool', 'template'].includes(node.kind)) {
    let paths: StoragePaths
    try {
      paths = await getStoragePaths()
    } catch (error) {
      return { ok: false, reason: `저장 경로를 읽지 못했습니다: ${String(error)}` }
    }
    if (node.kind === 'edit') return startEditRun(node, paths)
    if (node.kind === 'typo') return startGraphicsRun(node, 'typo', paths)
    if (node.kind === 'motion') return startGraphicsRun(node, 'motion', paths)
    if (node.kind === 'tool') return startToolRun(node, paths)
    if (node.kind === 'template') return startTemplateRun(node, paths)
  }
  return { ok: false, reason: `${spec.label} 노드의 실행은 아직 연결되지 않았습니다.` }
}

export function generatedAssetFor(path: string): StudioAsset {
  return generatedAsset(path)
}

/** 완료된 실행의 결과 파일을 프로젝트 문서의 후보 소재로 등록한다. */
export function registerRunOutput(runId: string, outputPath: string): void {
  const state = useStudioStore.getState()
  const run = state.runs.find((item) => item.id === runId)
  if (!run) return
  const existing = state.doc.assets.find((item) => item.storedPath && item.storedPath === outputPath)
  const asset = existing ?? generatedAsset(outputPath)
  useStudioStore.getState().addResultAsset(run.nodeId, asset)
  // 프로젝트 준비(handoff) 결과를 완료로 덮지 않는다. 결과 종류가 다르다.
  const status = run.status === 'prepared' ? 'prepared' : 'completed'
  void finishNodeRun(run.id, status, outputPath, null, asset.id)
    .then((updated) => useStudioStore.getState().upsertRun(updated))
    .catch(() => undefined)
}

/**
 * 모션 구성(MotionSpec) JSON을 노드 결과로 남긴다. 편집·합성 노드의 구성
 * 입력이 이 파일을 읽어 정확한 문구를 이어받는다.
 */
export function registerSpecAsset(nodeId: string, specPath: string): void {
  const state = useStudioStore.getState()
  const existing = state.doc.assets.find((item) => item.storedPath === specPath)
  useStudioStore.getState().addResultAsset(nodeId, existing ?? generatedAsset(specPath))
}

/**
 * 진행 중인 실행에 중단을 요청한다. 실제 취소 확인은 worker 이벤트로만
 * 기록되므로, 여기서는 요청 결과를 그대로 화면에 반영한다.
 */
export async function cancelStudioRun(runId: string): Promise<StartResult> {
  if (!isTauri) return { ok: false, reason: '중단은 Tauri 앱에서 동작합니다.' }
  try {
    const updated = await cancelNodeRun(runId)
    const state = useStudioStore.getState()
    const current = state.runs.find((item) => item.id === runId)
    if (!current || !isTerminalRun(current.status)) state.upsertRun(updated)
    return { ok: true, reason: '중단을 요청했습니다. 원격 실행은 계속될 수 있습니다.' }
  } catch (error) {
    return { ok: false, reason: String(error) }
  }
}

/** 결과 수신만 다시 시도한다. 생성은 다시 하지 않는다. */
export async function retryStudioDownload(runId: string): Promise<StartResult> {
  if (!isTauri) return { ok: false, reason: '다시 받기는 Tauri 앱에서 동작합니다.' }
  try {
    const updated = await retryRunDownload(runId)
    useStudioStore.getState().upsertRun(updated)
    return { ok: true, reason: '원격 결과를 다시 받기 시작했습니다. 생성은 다시 하지 않습니다.' }
  } catch (error) {
    return { ok: false, reason: String(error) }
  }
}

export async function refreshRuns(projectId: string): Promise<void> {
  if (!isTauri) return
  try {
    const rows = await listNodeRuns(projectId)
    useStudioStore.getState().setRuns(rows)
  } catch {
    // 실행 목록을 읽지 못해도 프로젝트 편집은 계속한다.
  }
}

/** 앱을 다시 열었을 때: 저장된 실행 기록을 읽고 아직 등록되지 않은 결과를 복구한다. */
export async function reconcileRuns(projectId: string): Promise<void> {
  if (!isTauri) return
  try {
    const rows = await listNodeRuns(projectId)
    useStudioStore.getState().setRuns(rows)
    for (const run of rows) {
      if (run.status !== 'completed' || !run.outputPath) continue
      const known = useStudioStore.getState().doc.assets.some((asset) => asset.storedPath === run.outputPath)
      if (!known) registerRunOutput(run.id, run.outputPath)
    }
  } catch {
    // 복구 실패는 조용히 넘긴다. 다음 진입에서 다시 시도한다.
  }
}

/** worker 이벤트를 화면 상태에 반영한다. 완료·실패는 저장된 기록을 다시 읽는다. */
export function applyWorkerEvent(event: WorkerEvent): void {
  const jobId = event.job_id
  if (!jobId) return
  const state = useStudioStore.getState()
  const run = state.runs.find((item) => item.jobId === jobId)
  if (!run) return

  if (event.type === 'completed' || event.type === 'failed' || event.type === 'cancelled') {
    void refreshRuns(state.projectId).then(() => {
      if (event.type === 'completed' && event.local_output_path) {
        registerRunOutput(run.id, event.local_output_path)
      }
    })
    if (event.type === 'failed') {
      useStudioStore.getState().setNodeStatus(run.nodeId, 'failed')
      useStudioStore.getState().setNotice(event.message || '실행이 실패했습니다.')
    }
    if (event.type === 'cancelled') {
      useStudioStore.getState().setNodeStatus(run.nodeId, 'draft')
    }
    return
  }

  const status = event.type === 'remote_attached'
    ? 'running'
    : event.stage === 'RESULT_DOWNLOADING' || event.stage === 'AUDIO_DOWNLOADING'
      ? 'downloading'
      : event.stage
        ? 'running'
        : run.status
  useStudioStore.getState().upsertRun({ ...run, status, stage: event.stage ?? run.stage })
}

export function latestRunFor(runs: StudioRunRow[], nodeId: string): StudioRunRow | undefined {
  return runs.find((run) => run.nodeId === nodeId)
}

export function activeRunFor(runs: StudioRunRow[], nodeId: string): StudioRunRow | undefined {
  return runs.find((run) => run.nodeId === nodeId && isActiveRun(run.status))
}

