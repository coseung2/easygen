// 제작 스튜디오: 프로젝트 목록, 캔버스, 스토리보드, 검사 패널, 저장/복원.

import React from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Connection,
  type Edge,
  type EdgeChange,
  type FinalConnectionState,
  type NodeChange,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Download, PanelLeft, PanelRight, Redo2, Save, Timer, Undo2 } from 'lucide-react'
import type { WorkerEvent } from '../app-config'
import { listenSafely, registerSafely } from '../lib/listen'
import { isTauri } from '../lib/tauri'
import { revealInExplorer } from '../lib/pipeline'
import type { PipelineEvent } from '../lib/pipeline'
import { Inspector } from './Inspector'
import { LeftPanel } from './LeftPanel'
import { NodeCard, type StudioFlowNode } from './NodeCard'
import { StoryboardBar } from './StoryboardBar'
import { StudioHome } from './StudioHome'
import { TimelinePanel } from './TimelinePanel'
import {
  browserAssetInput,
  createProject,
  deleteProject,
  exportProject,
  importPathAsset,
  importProject,
  listProjects,
  loadProject,
  pickDirectory,
  pickAssetPaths,
  saveProject,
  watchFileDrops,
} from './lib'
import { evaluateConnection } from './graph'
import { applyPipelineEvent, applyWorkerEvent, reconcileRuns } from './runController'
import { useStudioStore, type AssetInput } from './store'
import { browserCapability, confirmProtectedAction } from '../ux/stageOne'
import { emptyDocument, normalizeDocument, type ConnectionKind, type NodeKind, type StudioProjectRecord, type StudioProjectSummary } from './types'

const LAST_PROJECT_KEY = 'modal-gui.studio.lastProject'
const nodeTypes = { studio: NodeCard }

export function StudioPage() {
  const [mode, setMode] = React.useState<'loading' | 'home' | 'workspace'>('loading')
  const [projects, setProjects] = React.useState<StudioProjectSummary[]>([])
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')

  const refresh = React.useCallback(async () => {
    const rows = await listProjects()
    setProjects(rows)
  }, [])

  const openRecord = React.useCallback((record: StudioProjectRecord) => {
    const parsed = normalizeDocument(JSON.parse(record.documentJson) as unknown)
    useStudioStore.getState().openProject({ id: record.id, name: record.name, revision: record.revision, doc: parsed })
    if (isTauri) localStorage.setItem(LAST_PROJECT_KEY, record.id)
    setMode('workspace')
    // 저장된 실행 기록을 읽어 완료된 결과를 후보로 복구한다.
    void reconcileRuns(record.id)
  }, [])

  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const last = localStorage.getItem(LAST_PROJECT_KEY)
      if (last) {
        try {
          const record = await loadProject(last)
          if (!cancelled) {
            openRecord(record)
            return
          }
        } catch {
          if (isTauri) localStorage.removeItem(LAST_PROJECT_KEY)
        }
      }
      try {
        const rows = await listProjects()
        if (!cancelled) setProjects(rows)
      } catch (loadError) {
        if (!cancelled) setError(String(loadError))
      }
      if (!cancelled) setMode((current) => (current === 'loading' ? 'home' : current))
    })()
    return () => { cancelled = true }
  }, [openRecord])

  const create = async (name: string) => {
    if (!isTauri) return setError(browserCapability('persistProject').reason)
    setBusy(true)
    setError('')
    try {
      const record = await createProject(name.trim() || '새 프로젝트', emptyDocument())
      openRecord(record)
    } catch (createError) {
      setError(String(createError))
    } finally {
      setBusy(false)
    }
  }

  const open = async (id: string) => {
    setBusy(true)
    setError('')
    try {
      const record = await loadProject(id)
      openRecord(record)
    } catch (openError) {
      setError(String(openError))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (id: string) => {
    if (!isTauri) return setError(browserCapability('persistProject').reason)
    const project = projects.find((item) => item.id === id)
    const label = project ? `“${project.name}” 프로젝트` : '이 프로젝트'
    if (!confirmProtectedAction(`${label}를 삭제합니다. 노드 ${project?.nodeCount ?? 0}개와 소재 ${project?.assetCount ?? 0}개의 연결이 프로젝트 목록에서 사라집니다.`)) return
    try {
      await deleteProject(id)
      if (localStorage.getItem(LAST_PROJECT_KEY) === id) localStorage.removeItem(LAST_PROJECT_KEY)
      await refresh()
    } catch (removeError) {
      setError(String(removeError))
    }
  }

  const importFromFolder = async () => {
    if (!isTauri) return setError(browserCapability('persistProject').reason)
    setError('')
    try {
      const dir = await pickDirectory('내보낸 프로젝트 폴더 선택')
      if (!dir) return
      const result = await importProject(dir)
      const missing: string[] = []
      if (result.missing.connections.length > 0) missing.push(`연결: ${result.missing.connections.join(', ')}`)
      if (result.missing.workflows.length > 0) missing.push(`워크플로: ${result.missing.workflows.join(', ')}`)
      if (result.missing.fonts.length > 0) missing.push(`글꼴: ${result.missing.fonts.join(', ')}`)
      if (missing.length > 0) setError(`가져왔지만 다시 연결해야 하는 항목이 있습니다 — ${missing.join(' · ')}`)
      const record = await loadProject(result.projectId)
      openRecord(record)
    } catch (importError) {
      setError(String(importError))
    }
  }

  const exitWorkspace = async () => {
    useStudioStore.getState().closeProject()
    setMode('home')
    try {
      await refresh()
    } catch {
      // 목록 갱신 실패는 다음 진입에서 다시 시도한다.
    }
  }

  if (mode === 'workspace') {
    return (
      <ReactFlowProvider>
        <StudioWorkspace onExit={exitWorkspace} onExitError={setError} />
      </ReactFlowProvider>
    )
  }

  if (mode === 'loading') {
    return <div className="studio-home"><p className="dim">프로젝트를 불러오는 중…</p></div>
  }

  return (
    <StudioHome
      projects={projects}
      busy={busy}
      error={error}
      onCreate={(name) => void create(name)}
      onOpen={(id) => void open(id)}
      onDelete={(id) => void remove(id)}
      onImport={() => void importFromFolder()}
    />
  )
}

function StudioWorkspace({ onExit, onExitError }: { onExit: () => Promise<void>; onExitError: (message: string) => void }) {
  const reactFlow = useReactFlow()
  const projectId = useStudioStore((state) => state.projectId)
  const projectName = useStudioStore((state) => state.projectName)
  const doc = useStudioStore((state) => state.doc)
  const dirty = useStudioStore((state) => state.dirty)
  const saveState = useStudioStore((state) => state.saveState)
  const saveError = useStudioStore((state) => state.saveError)
  const lastSavedAt = useStudioStore((state) => state.lastSavedAt)
  const canUndo = useStudioStore((state) => state.past.length > 0)
  const canRedo = useStudioStore((state) => state.future.length > 0)
  const notice = useStudioStore((state) => state.notice)
  const setNotice = React.useCallback((message: string) => useStudioStore.getState().setNotice(message), [])
  const [dropActive, setDropActive] = React.useState(false)
  const panelKey = `modal-gui.studio.panels.${projectId || 'new'}`
  const [panels, setPanels] = React.useState({ left: false, right: false, timeline: false, storyboard: false })
  const fileInputRef = React.useRef<HTMLInputElement | null>(null)
  const canvasRef = React.useRef<HTMLDivElement | null>(null)
  const savingRef = React.useRef(false)
  const pendingRef = React.useRef(false)
  React.useEffect(() => {
    const raw = localStorage.getItem(panelKey)
    if (!raw) return
    try {
      const parsed = JSON.parse(raw) as typeof panels
      if (window.innerWidth < 1180) {
        const opened = (['left', 'right', 'timeline', 'storyboard'] as const).filter((key) => parsed[key])
        for (const key of opened.slice(1)) parsed[key] = false
      }
      setPanels(parsed)
    } catch { localStorage.removeItem(panelKey) }
  }, [panelKey])
  React.useEffect(() => {
    const onResize = () => {
      if (window.innerWidth >= 1180) return
      setPanels((current) => {
        const opened = (['left', 'right', 'timeline', 'storyboard'] as const).filter((key) => current[key])
        if (opened.length <= 1) return current
        const next = { ...current }
        for (const key of opened.slice(1)) next[key] = false
        localStorage.setItem(panelKey, JSON.stringify(next))
        return next
      })
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [panelKey])
  const updatePanels = (patch: Partial<typeof panels>) => {
    setPanels((current) => {
      const next = { ...current, ...patch }
      const narrow = window.innerWidth < 1180
      if (narrow) {
        const opened = (['left', 'right', 'timeline', 'storyboard'] as const).find((key) => patch[key] && next[key])
        if (opened) for (const key of ['left', 'right', 'timeline', 'storyboard'] as const) if (key !== opened) next[key] = false
      }
      localStorage.setItem(panelKey, JSON.stringify(next))
      return next
    })
  }
  const selection = useStudioStore((state) => state.selection)
  React.useEffect(() => {
    if (selection) updatePanels({ right: true })
  }, [selection])
  // 연속 추가할 때 노드가 겹치지 않도록 화면 중앙 기준으로 배치 순서를 센다.
  const placementRef = React.useRef(0)

  const saveNow = React.useCallback(async () => {
    if (!isTauri) return
    if (savingRef.current) {
      pendingRef.current = true
      return
    }
    savingRef.current = true
    try {
      for (;;) {
        const state = useStudioStore.getState()
        if (!state.projectId) break
        state.markSaving()
        const snapshot = state.doc
        try {
          const result = await saveProject(state.projectId, state.projectName, snapshot)
          const latest = useStudioStore.getState()
          if (latest.projectId !== state.projectId) break
          // 저장하는 동안 편집이 있었다면 그 문서는 아직 저장되지 않았다.
          // 완료로 표시하면 아직 저장되지 않은 편집이 조용히 사라진다.
          if (latest.doc === snapshot) latest.markSaved(result.revision, result.updatedAt)
          else pendingRef.current = true
        } catch (saveFailure) {
          useStudioStore.getState().markSaveError(String(saveFailure))
          break
        }
        if (!pendingRef.current) break
        pendingRef.current = false
      }
    } finally {
      savingRef.current = false
    }
  }, [])

  const requestExit = async () => {
    const state = useStudioStore.getState()
    if (state.saveState === 'saving') {
      onExitError('저장이 끝난 뒤 프로젝트 목록으로 돌아갈 수 있습니다. 저장을 다시 시도하세요.')
      return
    }
    if (state.saveState === 'error' || state.dirty) {
      const retry = window.confirm(state.saveState === 'error' ? `저장에 실패했습니다: ${state.saveError}\n다시 저장한 뒤 나갈까요?` : '저장되지 않은 변경이 있습니다. 저장한 뒤 나갈까요?')
      if (retry) {
        await saveNow()
        if (useStudioStore.getState().saveState === 'error' || useStudioStore.getState().dirty) return
      } else if (!confirmProtectedAction('저장하지 않고 프로젝트 목록으로 돌아갑니다. 저장되지 않은 변경은 현재 화면에서 사라집니다.')) {
        return
      }
    }
    await onExit()
  }

  React.useEffect(() => {
    const onLeave = (event: BeforeUnloadEvent) => {
      const state = useStudioStore.getState()
      if (state.dirty || state.saveState === 'saving' || state.saveState === 'error') {
        event.preventDefault()
        event.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', onLeave)
    return () => window.removeEventListener('beforeunload', onLeave)
  }, [])

  // 자동 저장: 편집이 멈추고 2.5초 뒤에 저장한다. 실행 결과 저장과는 별개다.
  React.useEffect(() => {
    if (!dirty) return
    const timer = window.setTimeout(() => { void saveNow() }, 2500)
    return () => window.clearTimeout(timer)
  }, [dirty, doc, saveNow])

  const importAssets = React.useCallback(async (inputs: AssetInput[], origin: { x: number; y: number }) => {
    if (inputs.length === 0) return
    const positions = inputs.map((_, index) => ({
      x: origin.x + (index % 3) * 280,
      y: origin.y + Math.floor(index / 3) * 220,
    }))
    useStudioStore.getState().registerAssets(inputs, positions)
    setNotice(`${inputs.length}개 소재를 등록했습니다.`)
  }, [])

  const importPaths = React.useCallback(async (paths: string[], origin: { x: number; y: number }) => {
    const projectId = useStudioStore.getState().projectId
    if (!projectId) return
    const inputs: AssetInput[] = []
    const failures: string[] = []
    for (const path of paths) {
      try {
        inputs.push(await importPathAsset(projectId, path))
      } catch (importError) {
        failures.push(String(importError))
      }
    }
    await importAssets(inputs, origin)
    if (failures.length > 0) setNotice(failures[0])
  }, [importAssets])

  const importBrowserFiles = React.useCallback(async (files: File[], origin: { x: number; y: number }) => {
    const inputs: AssetInput[] = []
    for (const file of files) inputs.push(await browserAssetInput(file))
    await importAssets(inputs, origin)
  }, [importAssets])

  const viewportCenter = React.useCallback(
    () => {
      const rect = canvasRef.current?.getBoundingClientRect()
      const x = rect ? rect.left + rect.width / 2 : window.innerWidth / 2
      const y = rect ? rect.top + rect.height / 2 : window.innerHeight / 2
      return reactFlow.screenToFlowPosition({ x, y })
    },
    [reactFlow],
  )

  const handleImport = React.useCallback(async () => {
    if (isTauri) {
      try {
        const paths = await pickAssetPaths()
        if (paths.length > 0) await importPaths(paths, viewportCenter())
      } catch (importError) {
        setNotice(String(importError))
      }
      return
    }
    fileInputRef.current?.click()
  }, [importPaths, viewportCenter])

  const addNodeAtCenter = React.useCallback((kind: NodeKind) => {
    const origin = viewportCenter()
    const index = placementRef.current
    placementRef.current += 1
    const column = index % 3
    const row = Math.floor(index / 3) % 4
    const id = useStudioStore.getState().addNode(kind, {
      x: origin.x - 300 + column * 260,
      y: origin.y - 240 + row * 170,
    })
    useStudioStore.getState().setSelection({ type: 'node', id })
    window.setTimeout(() => { void reactFlow.fitView({ padding: 0.22, duration: 320, maxZoom: 1 }) }, 60)
  }, [reactFlow, viewportCenter])

  const expandShot = React.useCallback((shotId: string) => {
    const origin = viewportCenter()
    useStudioStore.getState().expandShot(shotId, { x: origin.x - 420, y: origin.y - 120 })
    setNotice('샷에 필요한 프롬프트·영상·후보 선택 노드를 만들었습니다.')
    window.setTimeout(() => { void reactFlow.fitView({ padding: 0.2, duration: 360, maxZoom: 0.9 }) }, 60)
  }, [reactFlow, viewportCenter])

  // 내보내기: 제작 문서와 선택 소재를 폴더로 복사한다. 인증값은 포함하지 않는다.
  const exportToFolder = React.useCallback(async () => {
    if (!isTauri) return setNotice(browserCapability('persistProject').reason)
    const state = useStudioStore.getState()
    if (!state.projectId) return
    try {
      await saveNow()
      const dir = await pickDirectory('프로젝트를 내보낼 폴더 선택')
      if (!dir) return
      const result = await exportProject(state.projectId, dir)
      const missing = result.missingAssets.length > 0
        ? ` 파일을 찾지 못한 소재 ${result.missingAssets.length}개는 경로만 남겼습니다.`
        : ''
      setNotice(`프로젝트를 내보냈습니다: ${result.dir} (소재 ${result.assetCount}개).${missing}`)
    } catch (error) {
      setNotice(`내보내지 못했습니다: ${String(error)}`)
    }
  }, [saveNow])

  // Tauri 창 드롭: 실제 파일 경로를 받아 프로젝트 소재로 복사한다.
  React.useEffect(() => {
    let stop = () => {}
    void watchFileDrops((paths, position) => {
      setDropActive(false)
      void importPaths(paths, reactFlow.screenToFlowPosition(position))
    }).then((unlisten) => { stop = unlisten })
    return () => stop()
  }, [importPaths, reactFlow])

  // 실행 중인 노드의 진행 상황: 작업 큐와 같은 worker 이벤트를 받아 반영한다.
  React.useEffect(() => {
    if (!isTauri) return
    return listenSafely<WorkerEvent>('worker-event', (payload) => applyWorkerEvent(payload))
  }, [])

  // 로컬 렌더(편집·합성 노드)의 진행 상황.
  React.useEffect(() => {
    if (!isTauri) return
    return listenSafely<PipelineEvent>('pipeline-event', (payload) => applyPipelineEvent(payload))
  }, [])

  // ChatGPT 대화 스트림: 델타와 턴 완료를 화면 상태로 모은다.
  React.useEffect(() => {
    if (!isTauri) return
    return listenSafely<{ method?: string; params?: Record<string, unknown> }>('ai-chat-event', (payload) => {
      payload = payload ?? {}
      const method = payload.method
      const params = payload.params ?? {}
      const threadId = typeof params.threadId === 'string' ? params.threadId : ''
      const turn = params.turn as { id?: string; status?: string } | undefined
      const turnId = typeof params.turnId === 'string' ? params.turnId : turn?.id ?? ''
      if (method === 'item/agentMessage/delta' && typeof params.delta === 'string') {
        useStudioStore.getState().appendChatDelta(threadId, turnId, params.delta)
      } else if (method === 'turn/completed') {
        useStudioStore.getState().finishChatTurn(threadId, turnId, turn?.status ?? 'completed')
      }
    })
  }, [])

  React.useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const meta = event.ctrlKey || event.metaKey
      const target = event.target as HTMLElement | null
      const typing = Boolean(target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable))
      if (meta && event.key.toLowerCase() === 's') {
        event.preventDefault()
        void saveNow()
        return
      }
      if (typing) return
      if (meta && event.key.toLowerCase() === 'z' && !event.shiftKey) {
        event.preventDefault()
        useStudioStore.getState().undo()
      } else if (meta && (event.key.toLowerCase() === 'y' || (event.key.toLowerCase() === 'z' && event.shiftKey))) {
        event.preventDefault()
        useStudioStore.getState().redo()
      } else if (event.key === 'Escape') {
        useStudioStore.getState().setSelection(null)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [saveNow])

  const saveChip = saveState === 'saving'
    ? '저장 중…'
    : saveState === 'error'
      ? `저장 실패: ${saveError}`
      : lastSavedAt
        ? `${lastSavedAt.slice(11, 19)} 저장됨`
        : '저장 대기'

  return (
    <div className="studio-shell">
      <header className="studio-topbar">
        <button className="secondary-action small" onClick={() => void requestExit()}>← 프로젝트 목록</button>
        <input
          className="studio-name"
          value={projectName}
          onChange={(event) => useStudioStore.getState().setProjectName(event.target.value)}
          aria-label="프로젝트 이름"
        />
        <span className={`save-chip ${saveState}`}>{saveChip}</span>
        <div className="studio-topbar-right">
          <button
            className={panels.left ? 'icon-button active' : 'icon-button'}
            title={panels.left ? '왼쪽 패널 접기' : '왼쪽 패널 펼치기'}
            onClick={() => updatePanels({ left: !panels.left })}
          >
            <PanelLeft size={15} />
          </button>
          <button
            className={panels.right ? 'icon-button active' : 'icon-button'}
            title={panels.right ? '오른쪽 패널 접기' : '오른쪽 패널 펼치기'}
            onClick={() => updatePanels({ right: !panels.right })}
          >
            <PanelRight size={15} />
          </button>
          <button
            className={panels.storyboard ? 'icon-button active' : 'icon-button'}
            title={panels.storyboard ? '스토리보드 접기' : '스토리보드 펼치기'}
            onClick={() => updatePanels({ storyboard: !panels.storyboard })}
          >
            <Timer size={15} />
          </button>
          <button className="icon-button" disabled={!canUndo} title="되돌리기 (Ctrl+Z)" onClick={() => useStudioStore.getState().undo()}>
            <Undo2 size={15} />
          </button>
          <button className="icon-button" disabled={!canRedo} title="다시 실행 (Ctrl+Shift+Z)" onClick={() => useStudioStore.getState().redo()}>
            <Redo2 size={15} />
          </button>
          <button className="primary-action small" disabled={saveState === 'saving'} onClick={() => void saveNow()}>
            <Save size={14} />
            저장
          </button>
          <button className="secondary-action small" title="제작 문서와 소재를 폴더로 내보냅니다" onClick={() => void exportToFolder()}>
            <Download size={14} />
            내보내기
          </button>
        </div>
      </header>

      <div className="studio-body">
        {panels.left && <LeftPanel onAddNode={addNodeAtCenter} onImportAssets={() => void handleImport()} />}

        <div
          className="studio-canvas"
          ref={canvasRef}
          onDragOver={(event) => {
            event.preventDefault()
            if (!isTauri) setDropActive(true)
          }}
          onDragLeave={() => setDropActive(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDropActive(false)
            if (isTauri) return
            const files = Array.from(event.dataTransfer?.files ?? [])
            if (files.length > 0) {
              const position = reactFlow.screenToFlowPosition({ x: event.clientX, y: event.clientY })
              void importBrowserFiles(files, position)
            }
          }}
        >
          <StudioCanvas onNotice={setNotice} />
          {doc.nodes.length === 0 && (
            <div className="canvas-empty">
              <strong>빈 캔버스</strong>
              <button className="primary-action" onClick={() => addNodeAtCenter('brief')}>첫 노드 추가</button>
              <button className="secondary-action" onClick={() => void handleImport()}>소재 가져오기</button>
              <button className="secondary-action" onClick={() => useStudioStore.getState().addShot()}>샷 추가</button>
            </div>
          )}
          {dropActive && <div className="drop-overlay">파일을 놓으면 프로젝트 소재로 등록됩니다</div>}
          {notice && (
            <div className="studio-notice">
              <span>{notice}</span>
              <button onClick={() => useStudioStore.getState().clearNotice()} aria-label="알림 닫기">×</button>
            </div>
          )}
        </div>

        {panels.right && (
          <aside className="studio-right">
            <Inspector
              onImportAssets={() => void handleImport()}
              onExpandShot={expandShot}
              onReveal={(path) => { void revealInExplorer(path).catch(() => setNotice('폴더를 열 수 없습니다: ' + path)) }}
              onNotice={setNotice}
            />
          </aside>
        )}
      </div>

      {panels.timeline && (
        <TimelinePanel
          onReveal={(path) => { void revealInExplorer(path).catch(() => setNotice('폴더를 열 수 없습니다: ' + path)) }}
          onNotice={setNotice}
        />
      )}

      {panels.storyboard && <StoryboardBar onExpandShot={expandShot} />}

      <input
        ref={fileInputRef}
        type="file"
        multiple
        hidden
        onChange={(event) => {
          const files = Array.from(event.target.files ?? [])
          if (files.length > 0) void importBrowserFiles(files, viewportCenter())
          event.target.value = ''
        }}
      />
    </div>
  )
}

function StudioCanvas({ onNotice }: { onNotice: (message: string) => void }) {
  const doc = useStudioStore((state) => state.doc)
  const selection = useStudioStore((state) => state.selection)

  const flowNodes = React.useMemo(() => doc.nodes.map((node) => ({
    id: node.id,
    type: 'studio' as const,
    position: node.position,
    data: { nodeId: node.id },
    selected: selection?.type === 'node' && selection.id === node.id,
  })), [doc.nodes, selection])

  const flowEdges = React.useMemo(() => doc.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    sourceHandle: edge.sourceHandle,
    target: edge.target,
    targetHandle: edge.targetHandle,
    type: edge.kind === 'context' ? 'straight' : 'default',
    style: edge.kind === 'context'
      ? { stroke: '#5f7183', strokeDasharray: '5 4' }
      : { stroke: '#46617c' },
    label: edge.role || undefined,
    labelStyle: { fill: '#9fb0c4', fontSize: 9 },
    labelBgStyle: { fill: '#0f151c' },
  })), [doc.edges])

  const onNodesChange = React.useCallback((changes: NodeChange<StudioFlowNode>[]) => {
    const positions: Record<string, { x: number; y: number }> = {}
    const removals: string[] = []
    for (const change of changes) {
      if (change.type === 'position' && change.position) positions[change.id] = change.position
      else if (change.type === 'remove') removals.push(change.id)
      else if (change.type === 'select' && change.selected) useStudioStore.getState().setSelection({ type: 'node', id: change.id })
    }
    if (Object.keys(positions).length > 0) useStudioStore.getState().moveNodes(positions)
    if (removals.length > 0) useStudioStore.getState().removeNodes(removals)
  }, [])

  const onEdgesChange = React.useCallback((changes: EdgeChange<Edge>[]) => {
    const removals = changes.filter((change) => change.type === 'remove').map((change) => change.id)
    if (removals.length > 0) {
      for (const id of removals) useStudioStore.getState().removeEdge(id)
    }
  }, [])

  const onConnect = React.useCallback((connection: Connection) => {
    const kind: ConnectionKind = connection.sourceHandle === 'context' && connection.targetHandle === 'context' ? 'context' : 'data'
    const result = useStudioStore.getState().addEdge({
      source: connection.source,
      sourceHandle: connection.sourceHandle ?? null,
      target: connection.target,
      targetHandle: connection.targetHandle ?? null,
      kind,
    })
    if (!result.ok) onNotice(result.reason)
  }, [onNotice])

  const isValidConnection = React.useCallback((connection: Connection | Edge) => {
    const kind: ConnectionKind = connection.sourceHandle === 'context' && connection.targetHandle === 'context' ? 'context' : 'data'
    return evaluateConnection(useStudioStore.getState().doc, {
      source: connection.source,
      sourceHandle: connection.sourceHandle ?? null,
      target: connection.target,
      targetHandle: connection.targetHandle ?? null,
      kind,
    }).ok
  }, [])

  // React Flow가 유효하지 않은 연결을 막을 때, 왜 만들 수 없는지 화면에 설명한다.
  const onConnectEnd = React.useCallback((_event: MouseEvent | TouchEvent, state: FinalConnectionState) => {
    if (state.isValid === true || !state.fromHandle) return
    const point = 'clientX' in _event
      ? { x: _event.clientX, y: _event.clientY }
      : { x: _event.changedTouches?.[0]?.clientX ?? 0, y: _event.changedTouches?.[0]?.clientY ?? 0 }
    const element = document.elementFromPoint(point.x, point.y)
    const handle = element?.closest('.react-flow__handle')
    const targetHandleId = state.toHandle?.id ?? handle?.getAttribute('data-handleid') ?? null
    const targetNodeId = state.toHandle?.nodeId ?? handle?.getAttribute('data-nodeid') ?? null
    if (!targetHandleId || !targetNodeId) return
    const kind: ConnectionKind = state.fromHandle.id === 'context' && targetHandleId === 'context' ? 'context' : 'data'
    const result = evaluateConnection(useStudioStore.getState().doc, {
      source: state.fromHandle.nodeId,
      sourceHandle: state.fromHandle.id ?? null,
      target: targetNodeId,
      targetHandle: targetHandleId,
      kind,
    })
    if (!result.ok) onNotice(result.reason)
  }, [onNotice])

  return (
    <ReactFlow
      nodes={flowNodes}
      edges={flowEdges}
      nodeTypes={nodeTypes}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      onConnectEnd={onConnectEnd}
      onNodeDragStart={() => useStudioStore.getState().beginGesture()}
      isValidConnection={isValidConnection}
      onPaneClick={() => useStudioStore.getState().setSelection(null)}
      deleteKeyCode={['Delete', 'Backspace']}
      connectionRadius={30}
      fitView
      minZoom={0.15}
      maxZoom={1.75}
      proOptions={{ hideAttribution: false }}
    >
      <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#1d2733" />
      <Controls showInteractive={false} />
      <MiniMap pannable zoomable nodeColor="#2b3b4a" maskColor="rgba(9, 12, 17, .72)" />
    </ReactFlow>
  )
}
