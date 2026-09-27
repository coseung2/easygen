// 하단 타임라인: 선택한 타이포·모션·편집 노드의 배경 컷, 정확한 문구,
// 오디오 구간을 초 단위로 편집하고 최신 결과를 확인한다(문서 8장).

import React from 'react'
import { Film, FolderOpen, Music, Play, Square, Trash2, Type as TypeIcon } from 'lucide-react'
import { cuesFromCopy, cuesTotalSeconds, normalizeCueTiming, parseCues, serializeCues, type TypoCue } from '../lib/motion'
import { nodeSpec } from './catalog'
import { assetDisplayUrl } from './lib'
import { activeRunFor, cancelStudioRun, cuesFromSpecAssets, incomingAsset, incomingAssets, latestRunFor, startStudioRun } from './runController'
import { useStudioStore } from './store'
import { runStatusLabel, type StudioAsset, type StudioNode } from './types'

const TIMELINE_KINDS = new Set(['typo', 'motion', 'edit'])

function planSeconds(node: StudioNode, clips: StudioAsset[]): number {
  const configured = Number(node.config.seconds)
  if (Number.isFinite(configured) && configured > 0) return configured
  if (node.kind === 'edit') {
    const perShot = Number(node.config.shotSeconds)
    const shotSeconds = Number.isFinite(perShot) && perShot > 0 ? perShot : 5
    return Math.max(1, clips.length * shotSeconds)
  }
  return node.kind === 'typo' ? 6 : 8
}

function backgroundClips(node: StudioNode): StudioAsset[] {
  const video = incomingAsset(node.id, 'video')
  if (video) return [video]
  if (node.kind === 'typo') return incomingAssets(node.id, ['image'])
  if (node.kind === 'motion') return incomingAssets(node.id, ['source'])
  return incomingAssets(node.id, ['video'])
}

function rulerTicks(duration: number): number[] {
  const step = duration <= 12 ? 1 : duration <= 30 ? 2 : 5
  const ticks: number[] = []
  for (let value = 0; value <= duration + 0.001; value += step) ticks.push(Number(value.toFixed(2)))
  return ticks
}

export function TimelinePanel({
  onReveal,
  onNotice,
}: {
  onReveal: (path: string) => void
  onNotice: (message: string) => void
}) {
  const node = useStudioStore((state) => {
    if (state.selection?.type !== 'node') return undefined
    return state.doc.nodes.find((item) => item.id === state.selection?.id)
  })
  const nodes = useStudioStore((state) => state.doc.nodes)
  const assets = useStudioStore((state) => state.doc.assets)
  const runs = useStudioStore((state) => state.runs)
  const setNodeConfig = useStudioStore((state) => state.setNodeConfig)
  const [busy, setBusy] = React.useState(false)
  // 편집·합성 노드는 구성 입력(MotionSpec)의 문구를 그대로 렌더한다.
  const [specCues, setSpecCues] = React.useState<TypoCue[]>([])

  const candidates = React.useMemo(
    () => nodes.filter((item) => TIMELINE_KINDS.has(item.kind)),
    [nodes],
  )

  const nodeId = node?.id ?? ''
  const nodeKind = node?.kind ?? ''
  React.useEffect(() => {
    if (!nodeId || nodeKind !== 'edit') {
      setSpecCues([])
      return
    }
    let cancelled = false
    void cuesFromSpecAssets(incomingAssets(nodeId, ['spec'])).then((list) => {
      if (!cancelled) setSpecCues(list)
    })
    return () => { cancelled = true }
  }, [nodeId, nodeKind, assets, runs.length])

  if (!node || !TIMELINE_KINDS.has(node.kind)) {
    return (
      <div className="timeline-panel empty">
        <span className="timeline-title">타임라인</span>
        {candidates.length === 0 ? (
          <p className="dim">타임라인으로 편집할 타이포·모션·편집 노드가 아직 없습니다. 왼쪽 패널에서 추가하세요.</p>
        ) : (
          <div className="timeline-picker">
            <span className="dim">편집할 노드를 선택하세요:</span>
            {candidates.map((item) => (
              <button
                key={item.id}
                className="row-action"
                onClick={() => useStudioStore.getState().setSelection({ type: 'node', id: item.id })}
              >
                {nodeSpec(item.kind).label} · {item.title}
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  const spec = nodeSpec(node.kind)
  const clips = backgroundClips(node)
  const audio = incomingAsset(node.id, 'audio')
  const duration = planSeconds(node, clips)
  const storedCues = parseCues(node.config.cues)
  const copy = typeof node.config.copy === 'string' ? node.config.copy : ''
  const fromSpec = node.kind === 'edit'
  const cues = fromSpec
    ? specCues
    : storedCues.length > 0
      ? storedCues
      : normalizeCueTiming(
        copy
          ? cuesFromCopy({
            copy,
            durationSeconds: duration,
            entrance: typeof node.config.entrance === 'string' ? node.config.entrance : 'fade',
            timing: typeof node.config.timing === 'string' ? node.config.timing : undefined,
            font: typeof node.config.font === 'string' && node.config.font.trim() ? node.config.font : undefined,
          })
          : [],
        duration,
      )
  const activeRun = activeRunFor(runs, node.id)
  const latestRun = latestRunFor(runs, node.id)
  const resultAsset = node.results[0] ? assets.find((asset) => asset.id === node.results[0]) : undefined
  const renderer = typeof node.config.tool === 'string' && node.config.tool === 'ae' ? 'ae' : 'ffmpeg'

  const commitCues = (next: TypoCue[]) => {
    setNodeConfig(node.id, 'cues', serializeCues(normalizeCueTiming(next, duration)))
  }

  const updateCue = (index: number, patch: Partial<TypoCue>) => {
    commitCues(cues.map((cue, position) => (position === index ? { ...cue, ...patch } : cue)))
  }

  const addCue = () => {
    const start = Math.min(cuesTotalSeconds(cues), Math.max(0, duration - 0.5))
    commitCues([...cues, { start: Number(start.toFixed(3)), end: Number(Math.min(duration, start + 2).toFixed(3)), text: '새 문구', size: 64 }])
  }

  const rebuildFromCopy = () => {
    if (!copy.trim()) {
      onNotice('노드 설정의 정확한 문구를 먼저 입력하세요.')
      return
    }
    commitCues(cuesFromCopy({
      copy,
      durationSeconds: duration,
      entrance: typeof node.config.entrance === 'string' ? node.config.entrance : 'fade',
      timing: typeof node.config.timing === 'string' ? node.config.timing : undefined,
      font: typeof node.config.font === 'string' && node.config.font.trim() ? node.config.font : undefined,
    }))
  }

  const run = async () => {
    setBusy(true)
    try {
      const result = await startStudioRun(node.id)
      if (!result.ok) onNotice(result.reason ?? '실행을 시작하지 못했습니다.')
      else if (result.reason) onNotice(result.reason)
    } finally {
      setBusy(false)
    }
  }

  const stop = async () => {
    if (!activeRun) return
    const result = await cancelStudioRun(activeRun.id)
    onNotice(result.reason ?? '중단 요청을 보냈습니다.')
  }

  const ticks = rulerTicks(duration)
  const percent = (value: number) => `${Math.min(100, Math.max(0, (value / duration) * 100))}%`

  return (
    <div className="timeline-panel">
      <header className="timeline-head">
        <span className="timeline-title">
          <Film size={13} />
          타임라인 · {spec.label}
        </span>
        <span className="timeline-node">{node.title}</span>
        <span className="timeline-meta">
          {duration.toFixed(1)}초 · {String(node.config.resolution ?? '1920x1080')} · {String(node.config.fps ?? 24)}fps · {renderer === 'ae' ? 'After Effects 프로젝트' : 'FFmpeg 렌더'}
        </span>
        <div className="timeline-actions">
          {activeRun ? (
            <>
              <span className="snode-run-state">{runStatusLabel(activeRun.status)}{activeRun.stage ? ` · ${activeRun.stage}` : ''}</span>
              <button className="row-action danger" onClick={() => void stop()}>
                <Square size={11} />
                중단 요청
              </button>
            </>
          ) : (
            <button className="primary-action small" disabled={busy} onClick={() => void run()}>
              <Play size={12} fill="currentColor" />
              실행
            </button>
          )}
        </div>
      </header>

      <div className="timeline-body">
        <div className="timeline-lanes">
          <div className="timeline-ruler">
            {ticks.map((tick) => (
              <span key={tick} className="timeline-tick" style={{ left: percent(tick) }}>{tick}s</span>
            ))}
          </div>

          <div className="timeline-lane">
            <span className="timeline-lane-label"><Film size={12} /> 컷</span>
            <div className="timeline-track">
              {clips.length === 0 && <span className="timeline-empty">단색 배경으로 렌더합니다</span>}
              {clips.map((clip, index) => {
                const per = duration / Math.max(1, clips.length)
                return (
                  <span
                    key={clip.id}
                    className="timeline-bar clip"
                    style={{ left: percent(index * per), width: percent(per) }}
                    title={clip.storedPath || clip.name}
                  >
                    {clip.name}
                  </span>
                )
              })}
            </div>
          </div>

          <div className="timeline-lane">
            <span className="timeline-lane-label"><TypeIcon size={12} /> 문구</span>
            <div className="timeline-track">
              {cues.length === 0 && <span className="timeline-empty">문구 큐가 없습니다</span>}
              {cues.map((cue, index) => (
                <span
                  key={`${cue.text}-${index}`}
                  className="timeline-bar text"
                  style={{ left: percent(cue.start), width: percent(Math.max(0.2, cue.end - cue.start)) }}
                  title={`${cue.start}s–${cue.end}s ${cue.text}`}
                >
                  {cue.text}
                </span>
              ))}
            </div>
          </div>

          <div className="timeline-lane">
            <span className="timeline-lane-label"><Music size={12} /> 오디오</span>
            <div className="timeline-track">
              {audio ? (
                <span className="timeline-bar audio" style={{ left: '0%', width: '100%' }} title={audio.storedPath || audio.name}>
                  {audio.name}
                </span>
              ) : (
                <span className="timeline-bar audio muted" style={{ left: '0%', width: '100%' }}>무음 트랙</span>
              )}
            </div>
          </div>
        </div>

        <div className="timeline-editor">
          <div className="timeline-editor-head">
            <strong>정확한 문구 {cues.length}</strong>
            {!fromSpec && (
              <div className="timeline-editor-actions">
                <button className="row-action" onClick={addCue}>+ 문구 추가</button>
                <button className="row-action" onClick={rebuildFromCopy}>문구에서 다시 만들기</button>
              </div>
            )}
          </div>
          {fromSpec && (
            <p className="dim">
              편집·합성 노드는 구성 입력(MotionSpec)의 문구를 그대로 렌더합니다. 문구는 타이포·모션 노드에서 편집하고 이 노드의 구성 입력에 연결하세요.
            </p>
          )}
          {cues.length === 0 && (
            <p className="dim">
              {fromSpec
                ? '구성 입력이 연결되지 않았거나 문구가 없습니다.'
                : node.kind === 'motion'
                  ? '오버레이 문구가 없으면 모션만 렌더합니다.'
                  : '노드 설정의 정확한 문구를 입력하거나 아래에서 문구를 추가하세요.'}
            </p>
          )}
          <div className="cue-list">
            {cues.map((cue, index) => (
              fromSpec ? (
                <div className="cue-row readonly" key={`${cue.text}-${index}`}>
                  <span className="cue-static">{cue.start}s–{cue.end}s</span>
                  <span className="cue-static wide" title={cue.text}>{cue.text}</span>
                </div>
              ) : (
              <div className="cue-row" key={`${cue.text}-${index}`}>
                <label className="cue-field">
                  시작
                  <input
                    type="number"
                    step={0.1}
                    min={0}
                    max={duration}
                    value={cue.start}
                    onChange={(event) => updateCue(index, { start: Number(event.target.value) })}
                  />
                </label>
                <label className="cue-field">
                  끝
                  <input
                    type="number"
                    step={0.1}
                    min={0}
                    max={duration}
                    value={cue.end}
                    onChange={(event) => updateCue(index, { end: Number(event.target.value) })}
                  />
                </label>
                <label className="cue-field wide">
                  문구
                  <input
                    value={cue.text}
                    onChange={(event) => updateCue(index, { text: event.target.value })}
                  />
                </label>
                <label className="cue-field">
                  크기
                  <input
                    type="number"
                    step={2}
                    min={12}
                    max={240}
                    value={cue.size}
                    onChange={(event) => updateCue(index, { size: Number(event.target.value) })}
                  />
                </label>
                <button
                  className="icon-button small danger"
                  title="문구 삭제"
                  onClick={() => commitCues(cues.filter((_, position) => position !== index))}
                >
                  <Trash2 size={12} />
                </button>
              </div>
              )
            ))}
          </div>
          {!fromSpec && (
            <p className="dim timeline-note">
              문구는 그대로 렌더에 들어갑니다. 한글 문구는 한국어 글꼴로 렌더하고, 글꼴 파일이 없으면 대체 사실을 알립니다.
            </p>
          )}
        </div>

        <div className="timeline-preview">
          <strong>최신 결과</strong>
          {!resultAsset && <p className="dim">아직 결과가 없습니다. 실행하면 이곳에서 바로 확인할 수 있습니다.</p>}
          {resultAsset && (
            <>
              {resultAsset.kind === 'video' && <video src={assetDisplayUrl(resultAsset)} controls preload="metadata" />}
              {resultAsset.kind === 'image' && <img src={assetDisplayUrl(resultAsset)} alt="" />}
              {resultAsset.kind === 'audio' && <audio src={assetDisplayUrl(resultAsset)} controls />}
              {resultAsset.kind === 'other' && (
                <p className="dim">프로젝트 파일: {resultAsset.name}</p>
              )}
              <small title={resultAsset.storedPath || resultAsset.name}>{resultAsset.name}</small>
              {resultAsset.storedPath && (
                <button className="link-button" onClick={() => onReveal(resultAsset.storedPath)}>
                  <FolderOpen size={12} /> 폴더에서 보기
                </button>
              )}
            </>
          )}
          {latestRun && (
            <small className="dim">
              {runStatusLabel(latestRun.status)} · {latestRun.createdAt.slice(5, 16).replace('T', ' ')}
              {latestRun.errorMessage ? ` · ${latestRun.errorMessage}` : ''}
            </small>
          )}
        </div>
      </div>
    </div>
  )
}
