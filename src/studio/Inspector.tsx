// 우측 검사 패널: 선택한 노드·샷·소재의 설정과 프로젝트 요약.

import React from 'react'
import { Copy, FolderOpen, Link2, Link2Off, Trash2 } from 'lucide-react'
import { formatBytes } from '../lib/pipeline'
import { isRunnable, nodeSpec, type FieldSpec } from './catalog'
import { inputsOf, referencedAssetOf } from './graph'
import {
  assetDisplayUrl,
  deleteTemplate,
  listTemplates,
  projectUsageSummary,
  saveTemplate,
  type ProjectUsageSummary,
  type TemplateRow,
} from './lib'
import { insertTemplate, templateFromSelection } from './templates'
import { isTauri } from '../lib/tauri'
import { activeRunFor, cancelStudioRun, retryStudioDownload, startStudioRun } from './runController'
import { generatedAssetFor } from './runController'
import { ChatPanel } from './ChatPanel'
import { useStudioStore } from './store'
import { browserCapability, confirmProtectedAction } from '../ux/stageOne'
import { WORKFLOW_STATUS_LABELS, listWorkflows, type WorkflowRow } from '../lib/workflows'
import { listModalProfiles, type ModalProfile } from '../lib/usage'
import { checkToolCall } from './toolInput'
import {
  listConnectionTools,
  listConnections,
  type ConnectionRow,
  type ConnectionToolRow,
} from '../lib/connections'
import { REFERENCE_ROLES, SHOT_ROLES, assetPortType, runStatusLabel, type ConfigValue, type StudioAsset, type StudioEdge, type StudioNode } from './types'

interface InspectorProps {
  onImportAssets: () => void
  onExpandShot: (shotId: string) => void
  onReveal: (path: string) => void
  onNotice: (message: string) => void
}

export function Inspector({ onImportAssets, onExpandShot, onReveal, onNotice }: InspectorProps) {
  const selection = useStudioStore((state) => state.selection)
  const [tab, setTab] = React.useState<'settings' | 'chat'>('settings')

  const settings = (() => {
    if (!selection) return <ProjectInspector onImportAssets={onImportAssets} onNotice={onNotice} />
    if (selection.type === 'node') {
      return <NodeInspector id={selection.id} onReveal={onReveal} onNotice={onNotice} />
    }
    if (selection.type === 'shot') return <ShotInspector id={selection.id} onExpandShot={onExpandShot} />
    return <AssetInspector id={selection.id} onReveal={onReveal} />
  })()

  return (
    <div className="inspector-shell">
      <div className="seg studio-tabs inspector-tabs">
        <button className={tab === 'settings' ? 'active' : ''} onClick={() => setTab('settings')}>설정</button>
        <button className={tab === 'chat' ? 'active' : ''} onClick={() => setTab('chat')}>대화</button>
      </div>
      {tab === 'chat' ? <ChatPanel onNotice={onNotice} /> : settings}
    </div>
  )
}

function FieldControl({ field, value, onChange }: { field: FieldSpec; value: ConfigValue; onChange: (value: ConfigValue) => void }) {
  if (field.type === 'checkbox') {
    return (
      <label className="checkbox-field">
        <input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} />
        {field.label}
      </label>
    )
  }
  if (field.type === 'textarea') {
    return (
      <label className="field-label">
        {field.label}
        <textarea
          rows={field.rows ?? 4}
          value={typeof value === 'string' ? value : ''}
          placeholder={field.placeholder}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
    )
  }
  if (field.type === 'select') {
    if (field.dynamic === 'workflows') {
      return <WorkflowSelect field={field} value={value} onChange={onChange} />
    }
    if (field.dynamic === 'profiles') {
      return <ProfileSelect field={field} value={value} onChange={onChange} />
    }
    return (
      <label className="field-label">
        {field.label}
        <select value={typeof value === 'string' ? value : ''} onChange={(event) => onChange(event.target.value)}>
          {field.options?.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    )
  }
  if (field.type === 'number') {
    return (
      <label className="field-label">
        {field.label}
        <input
          value={value === null || value === undefined ? '' : String(value)}
          inputMode="numeric"
          placeholder={field.placeholder}
          onChange={(event) => {
            const raw = event.target.value.replace(/[^0-9.-]/g, '')
            onChange(raw === '' ? null : Number(raw))
          }}
        />
      </label>
    )
  }
  return (
    <label className="field-label">
      {field.label}
      <input value={typeof value === 'string' ? value : ''} placeholder={field.placeholder} onChange={(event) => onChange(event.target.value)} />
    </label>
  )
}

/** 등록된 워크플로를 앱 데이터에서 읽어 채우는 선택 필드. */
/** Modal 계정 선택. 노드에서 고른 계정으로 실행되고, 비어 있으면 기본 프로필을 쓴다. */
function ProfileSelect({ field, value, onChange }: { field: FieldSpec; value: ConfigValue; onChange: (value: ConfigValue) => void }) {
  const [rows, setRows] = React.useState<ModalProfile[]>([])
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    let cancelled = false
    void listModalProfiles()
      .then((list) => { if (!cancelled) setRows(list) })
      .catch((loadError) => { if (!cancelled) setError(String(loadError)) })
    return () => { cancelled = true }
  }, [])

  const current = typeof value === 'string' ? value : ''
  const enabled = rows.filter((row) => row.enabled)
  const selected = rows.find((row) => row.id === current)
  const archived = Boolean(current) && !selected
  return (
    <label className="field-label">
      {field.label}
      <select value={current} onChange={(event) => onChange(event.target.value)}>
        <option value="">기본 프로필 (앱 설정)</option>
        {enabled.map((row) => (
          <option key={row.id} value={row.id}>
            {row.name}{row.modal_profile_name ? ` · ${row.modal_profile_name}` : ''}
          </option>
        ))}
      </select>
      {selected && (
        <small className="dim">
          이번 달 사용료 ${selected.month_cost.toFixed(2)}
          {selected.budget_limit !== null ? ` · 설정 예산 ${selected.budget_limit}` : ''}
        </small>
      )}
      {archived && <small className="bad">선택한 계정을 찾을 수 없습니다. 다른 계정을 고르세요.</small>}
      {rows.length === 0 && !error && (
        <small className="dim">등록된 Modal 계정이 없습니다. 사용량 화면에서 계정을 등록하세요.</small>
      )}
      {error && <small className="bad">{error}</small>}
    </label>
  )
}

function WorkflowSelect({ field, value, onChange }: { field: FieldSpec; value: ConfigValue; onChange: (value: ConfigValue) => void }) {
  const [rows, setRows] = React.useState<WorkflowRow[]>([])
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    let cancelled = false
    void listWorkflows()
      .then((list) => { if (!cancelled) setRows(list) })
      .catch((loadError) => { if (!cancelled) setError(String(loadError)) })
    return () => { cancelled = true }
  }, [])

  const current = typeof value === 'string' ? value : ''
  const selected = rows.find((row) => row.id === current)
  const describe = (mapping: Record<string, unknown>): string =>
    Object.entries(mapping)
      .map(([key, type]) => `${key}(${String(type)})`)
      .join(', ') || '선언 없음'
  return (
    <label className="field-label">
      {field.label}
      <select value={current} onChange={(event) => onChange(event.target.value)}>
        <option value="">워크플로 선택…</option>
        {rows.map((row) => (
          <option key={row.id} value={row.id}>
            {row.name} · {row.tool} · {WORKFLOW_STATUS_LABELS[row.status] ?? row.status}
          </option>
        ))}
      </select>
      {rows.length === 0 && !error && (
        <small className="dim">등록된 워크플로가 없습니다. 연결 관리 화면의 워크플로에서 등록하세요.</small>
      )}
      {selected && (
        <small className="dim">
          입력 {describe(selected.inputs)} · 출력 {describe(selected.outputs)}
          {selected.location ? ` · ${selected.location}` : ''}
        </small>
      )}
      {error && <small className="bad">{error}</small>}
    </label>
  )
}

function NodeInspector({ id, onReveal, onNotice }: { id: string; onReveal: (path: string) => void; onNotice: (message: string) => void }) {
  const node = useStudioStore((state) => state.doc.nodes.find((item) => item.id === id))
  const nodes = useStudioStore((state) => state.doc.nodes)
  const edges = useStudioStore((state) => state.doc.edges)
  const assets = useStudioStore((state) => state.doc.assets)
  const runs = useStudioStore((state) => state.runs)
  const updateNode = useStudioStore((state) => state.updateNode)
  const setNodeConfig = useStudioStore((state) => state.setNodeConfig)
  const updateShot = useStudioStore((state) => state.updateShot)
  const shots = useStudioStore((state) => state.doc.shots)
  const removeNodes = useStudioStore((state) => state.removeNodes)
  const duplicateNode = useStudioStore((state) => state.duplicateNode)
  const removeEdge = useStudioStore((state) => state.removeEdge)
  const setEdgeRole = useStudioStore((state) => state.setEdgeRole)
  const addNode = useStudioStore((state) => state.addNode)
  const addEdge = useStudioStore((state) => state.addEdge)

  if (!node) return <div className="inspector-empty">선택한 노드를 찾을 수 없습니다.</div>

  const spec = nodeSpec(node.kind)
  const nodeById = new Map(nodes.map((item) => [item.id, item]))
  const incoming = edges.filter((edge) => edge.target === id)
  const assetRefs = incoming.filter((edge) => edge.kind === 'data' && nodeById.get(edge.source)?.kind === 'asset')
  const otherRefs = incoming.filter((edge) => edge.kind === 'data' && nodeById.get(edge.source)?.kind !== 'asset')
  const contextRefs = incoming.filter((edge) => edge.kind === 'context')
  const asset = referencedAssetOf(assets, node)
  const selectedAsset = node.kind === 'select' ? asset : undefined
  const activeRun = activeRunFor(runs, node.id)

  // 후보: 이 노드로 들어오는 상위 결과 소재.
  const candidates = collectCandidates(node.id, incoming, nodeById, assets)

  const attachReference = (assetId: string) => {
    const target = assets.find((item) => item.id === assetId)
    if (!target) return
    const port = inputsOf(node).find((item) => item.type === assetPortType(target.kind))
    if (!port) {
      onNotice(`${spec.label} 노드는 ${assetPortType(target.kind)} 자료형 입력이 없습니다.`)
      return
    }
    let sourceNode = nodes.find((item) => item.kind === 'asset' && item.config.assetId === assetId)
    if (!sourceNode) {
      const createdId = addNode('asset', { x: node.position.x - 320, y: node.position.y + 60 })
      updateNode(createdId, { title: target.name, config: { assetId: target.id, assetName: target.name } })
      sourceNode = useStudioStore.getState().doc.nodes.find((item) => item.id === createdId)
    }
    if (!sourceNode) return
    const check = addEdge({
      source: sourceNode.id,
      sourceHandle: 'out',
      target: node.id,
      targetHandle: port.id,
      kind: 'data',
    })
    if (!check.ok) onNotice(check.reason)
  }

  return (
    <div className="inspector-body">
      <div className="inspector-head">
        <span className="section-kicker">{spec.group} · {spec.label}</span>
        <div className="inspector-actions">
          <button className="icon-button" title="노드 복제" onClick={() => duplicateNode(node.id)}>
            <Copy size={14} />
          </button>
          <button className="icon-button danger" title="노드 삭제" onClick={() => confirmProtectedAction(`“${node.title}” 노드와 연결된 입력을 삭제합니다. 실행 기록은 남습니다.`) && removeNodes([node.id])}>
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      <label className="field-label">
        노드 이름
        <input value={node.title} onChange={(event) => updateNode(node.id, { title: event.target.value })} />
      </label>

      {node.kind === 'asset' && asset && (
        <div className="inspector-asset">
          <div className="inspector-thumb">
            {asset.kind === 'image' && <img src={assetDisplayUrl(asset)} alt="" />}
            {asset.kind === 'video' && <video src={assetDisplayUrl(asset)} muted controls />}
            {asset.kind === 'audio' && <audio src={assetDisplayUrl(asset)} controls />}
            {asset.kind === 'other' && <span className="dim">미리보기 없음</span>}
          </div>
          <dl className="meta-list">
            <div><dt>파일</dt><dd title={asset.storedPath || asset.name}>{asset.name}</dd></div>
            <div><dt>크기</dt><dd>{asset.sizeBytes ? formatBytes(asset.sizeBytes) : '알 수 없음'}</dd></div>
            <div><dt>hash</dt><dd>{asset.hash || '브라우저 미리보기'}</dd></div>
          </dl>
          {asset.ephemeral && <p className="inline-note">브라우저 미리보기 임시 소재입니다. Tauri 앱에서 가져오면 프로젝트 폴더에 복사됩니다.</p>}
          {asset.storedPath && (
            <button className="secondary-action small" onClick={() => onReveal(asset.storedPath)}>
              <FolderOpen size={13} />
              폴더에서 보기
            </button>
          )}
        </div>
      )}

      {spec.fields.map((field) => (
        <FieldControl
          key={field.key}
          field={field}
          value={node.config[field.key] ?? null}
          onChange={(value) => setNodeConfig(node.id, field.key, value)}
        />
      ))}

      {node.kind === 'tool' && <ToolNodeSection node={node} onNotice={onNotice} />}

      {node.kind === 'select' && (
        <section className="inspector-section">
          <h3 className="inspector-title">후보 {candidates.length}</h3>
          {candidates.length === 0 && <p className="dim">상위 노드의 결과 소재가 아직 없습니다. 생성 노드를 연결하고 실행하면 후보가 쌓입니다.</p>}
          <div className="candidate-list">
            {candidates.map((candidate) => (
              <button
                key={candidate.id}
                className={selectedAsset?.id === candidate.id ? 'candidate-card active' : 'candidate-card'}
                onClick={() => {
                  setNodeConfig(node.id, 'selectedAssetId', candidate.id)
                  for (const shot of shots.filter((item) => item.nodeIds.includes(node.id))) updateShot(shot.id, { selectedAssetId: candidate.id })
                }}
                title={candidate.name}
              >
                <span className="candidate-thumb">
                  {candidate.kind === 'image' && <img src={assetDisplayUrl(candidate)} alt="" />}
                  {candidate.kind === 'video' && <video src={assetDisplayUrl(candidate)} muted />}
                  {candidate.kind !== 'image' && candidate.kind !== 'video' && <em>{candidate.kind}</em>}
                </span>
                <span className="candidate-name">{candidate.name}</span>
              </button>
            ))}
          </div>
          {selectedAsset && <p className="dim">선택 고정: {selectedAsset.name}</p>}
        </section>
      )}

      <section className="inspector-section">
        <h3 className="inspector-title">
          <Link2 size={13} /> 참조 입력 {incoming.length > 0 ? `(${incoming.length})` : ''}
        </h3>
        {incoming.length === 0 && <p className="dim">연결된 입력이 없습니다. 캔버스에서 포트를 끌어 연결하세요.</p>}
        <div className="ref-list">
          {[...assetRefs, ...otherRefs].map((edge) => {
            const sourceNode = nodeById.get(edge.source)
            const port = inputsOf(node).find((item) => item.id === edge.targetHandle)
            return (
              <div className="ref-row" key={edge.id}>
                <div className="ref-copy">
                  <strong>{sourceNode?.title ?? '알 수 없는 노드'}</strong>
                  <small>{port?.label ?? edge.targetHandle} · {port?.type ?? '자료형 미확인'}</small>
                </div>
                {sourceNode?.kind === 'asset' && (
                  <select
                    className="ref-role"
                    value={edge.role}
                    onChange={(event) => setEdgeRole(edge.id, event.target.value)}
                    title="참조 역할"
                  >
                    <option value="">역할 미지정</option>
                    {REFERENCE_ROLES.map((role) => (
                      <option key={role} value={role}>{role}</option>
                    ))}
                  </select>
                )}
                <button className="icon-button small" title="연결 해제" onClick={() => removeEdge(edge.id)}>
                  <Link2Off size={13} />
                </button>
              </div>
            )
          })}
        </div>
        {contextRefs.length > 0 && (
          <div className="ref-list context">
            {contextRefs.map((edge) => (
              <div className="ref-row" key={edge.id}>
                <div className="ref-copy">
                  <strong>{nodeById.get(edge.source)?.title ?? '알 수 없는 노드'}</strong>
                  <small>맥락 참고</small>
                </div>
                <button className="icon-button small" title="맥락 연결 해제" onClick={() => removeEdge(edge.id)}>
                  <Link2Off size={13} />
                </button>
              </div>
            ))}
          </div>
        )}
        {assetRefs.length === 0 && assets.length > 0 && (
          <select className="ref-add" value="" onChange={(event) => event.target.value && attachReference(event.target.value)}>
            <option value="">소재 참조 추가…</option>
            {assets.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
        )}
      </section>

      <section className="inspector-section">
        <h3 className="inspector-title">결과 후보 {node.results.length > 0 ? `(${node.results.length})` : ''}</h3>
        {node.results.length === 0 && (
          <p className="dim">
            {spec.executionStage === null
              ? '기획·구성 노드는 실행 대신 다른 노드의 입력으로 쓰입니다.'
              : `아직 결과가 없습니다. 실행하면 결과가 이 노드의 후보로 등록됩니다.`}
          </p>
        )}
        <div className="result-strip">
          {node.results.map((assetId) => {
            const asset = assets.find((item) => item.id === assetId)
            if (!asset) return null
            return (
              <div className="result-item" key={assetId}>
                {asset.kind === 'image' && <img src={assetDisplayUrl(asset)} alt="" />}
                {asset.kind === 'video' && <video src={assetDisplayUrl(asset)} muted controls preload="metadata" />}
                {asset.kind === 'audio' && <audio src={assetDisplayUrl(asset)} controls />}
                <small title={asset.storedPath || asset.name}>{asset.name}</small>
                {asset.storedPath && (
                  <button className="link-button" onClick={() => onReveal(asset.storedPath)}>폴더에서 보기</button>
                )}
              </div>
            )
          })}
        </div>
      </section>

      <section className="inspector-section">
        <h3 className="inspector-title">실행 기록 {runs.filter((run) => run.nodeId === node.id).length > 0 ? `(${runs.filter((run) => run.nodeId === node.id).length})` : ''}</h3>
        {runs.filter((run) => run.nodeId === node.id).length === 0 && (
          <p className="dim">
            {spec.executionStage === null
              ? '이 노드는 실행되지 않습니다.'
              : isRunnable(node.kind)
                ? '아직 실행 기록이 없습니다. 노드 카드의 실행 버튼만 사용하세요.'
                : `실행 연결은 ${spec.executionStage}단계에서 추가됩니다.`}
          </p>
        )}
        <div className="run-list">
          {runs.filter((run) => run.nodeId === node.id).slice(0, 6).map((run) => (
            <div className={`run-row ${run.status}`} key={run.id}>
              <span className="run-status">{runStatusLabel(run.status)}</span>
              <span className="run-stage">{run.stage ?? run.tool}</span>
              <small>{run.createdAt.slice(5, 16).replace('T', ' ')}</small>
              {run.errorMessage && <small className="bad" title={run.errorMessage}>{run.errorMessage}</small>}
              {run.remotePath && (run.status === 'failed' || run.status === 'cancelled') && (
                <button
                  className="row-action"
                  title={`원격 경로: ${run.remotePath}`}
                  onClick={() => {
                    void retryStudioDownload(run.id).then((result) => onNotice(result.reason ?? '다시 받기를 시작했습니다.'))
                  }}
                >
                  원격 결과 다시 받기
                </button>
              )}
            </div>
          ))}
        </div>
        {isRunnable(node.kind) && (
          <div className="run-actions">
            {activeRun && (
              <button
                className="row-action danger"
                onClick={() => {
                  void cancelStudioRun(activeRun.id).then((result) => onNotice(result.reason ?? '중단 요청을 보냈습니다.'))
                }}
              >
                중단
              </button>
            )}
            {!activeRun && <p className="dim">{node.status === 'stale' ? '입력이 바뀌었습니다. 노드의 다시 실행을 사용하거나 이전 결과를 확인하세요.' : node.status === 'failed' ? '실패 원인을 확인한 뒤 노드에서 다시 실행하세요.' : '실행은 노드 카드의 버튼 하나만 사용합니다.'}</p>}
            {runs.some((run) => run.nodeId === node.id && run.status === 'prepared' && (run.outputPath || run.remotePath)) && <button className="secondary-action small" onClick={() => {
              const prepared = runs.find((run) => run.nodeId === node.id && run.status === 'prepared' && (run.outputPath || run.remotePath))
              if (prepared) onReveal(prepared.outputPath || prepared.remotePath || '')
            }}>준비한 프로젝트 열기</button>}
            {activeRun?.status === 'cancel_requested' && <p className="dim">중단 확인을 기다리는 중입니다. 확인 전에는 다시 실행할 수 없습니다.</p>}
          </div>
        )}
      </section>

      <label className="field-label">
        메모
        <textarea rows={2} value={node.note} onChange={(event) => updateNode(node.id, { note: event.target.value })} />
      </label>
    </div>
  )
}

function ToolNodeSection({ node, onNotice }: { node: StudioNode; onNotice: (message: string) => void }) {
  const [connections, setConnections] = React.useState<ConnectionRow[]>([])
  const [tools, setTools] = React.useState<ConnectionToolRow[]>([])
  const setNodeConfig = useStudioStore((state) => state.setNodeConfig)
  const addResultAsset = useStudioStore((state) => state.addResultAsset)
  const connectionId = typeof node.config.connection === 'string' ? node.config.connection : ''
  const toolName = typeof node.config.tool === 'string' ? node.config.tool : ''

  React.useEffect(() => {
    let cancelled = false
    void listConnections()
      .then((rows) => {
        if (!cancelled) setConnections(rows.filter((row) => row.enabled))
      })
      .catch(() => undefined)
    return () => { cancelled = true }
  }, [])

  React.useEffect(() => {
    if (!connectionId) {
      setTools([])
      return
    }
    let cancelled = false
    void listConnectionTools(connectionId)
      .then((rows) => {
        if (!cancelled) setTools(rows.filter((row) => row.enabled))
      })
      .catch(() => undefined)
    return () => { cancelled = true }
  }, [connectionId])

  const detected = React.useMemo(() => {
    const raw = typeof node.config.detectedFiles === 'string' ? node.config.detectedFiles : ''
    if (!raw) return []
    try {
      const parsed: unknown = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === 'string') : []
    } catch {
      return []
    }
  }, [node.config.detectedFiles])

  // 서버에서 도구가 사라졌거나 필수 입력이 빠졌으면 실행 전에 알린다.
  const compatibility = React.useMemo(() => {
    if (!connectionId || !toolName || tools.length === 0) return null
    const raw = typeof node.config.input === 'string' ? node.config.input : ''
    let args: unknown = {}
    if (raw.trim()) {
      try {
        args = JSON.parse(raw)
      } catch {
        return { ok: false as const, reason: '입력 JSON을 해석하지 못했습니다. JSON 형식으로 입력하세요.' }
      }
    }
    return checkToolCall(tools, toolName, args)
  }, [connectionId, toolName, tools, node.config.input])

  return (
    <section className="inspector-section">
      <h3 className="inspector-title">MCP 도구</h3>
      <label className="field-label">
        연결
        <select
          value={connectionId}
          onChange={(event) => {
            setNodeConfig(node.id, 'connection', event.target.value)
            setNodeConfig(node.id, 'tool', '')
          }}
        >
          <option value="">연결 선택…</option>
          {connections.map((row) => (
            <option key={row.id} value={row.id}>{row.name} ({row.toolCount}개 도구)</option>
          ))}
        </select>
      </label>
      <label className="field-label">
        도구
        <select value={toolName} disabled={!connectionId} onChange={(event) => setNodeConfig(node.id, 'tool', event.target.value)}>
          <option value="">{connectionId ? '도구 선택…' : '연결을 먼저 고르세요'}</option>
          {tools.map((tool) => (
            <option key={tool.name} value={tool.name}>{tool.name}</option>
          ))}
        </select>
      </label>
      {connections.length === 0 && (
        <p className="dim">사이드바의 연결 관리 화면에서 MCP 서버를 등록하고 연결 테스트를 실행하세요.</p>
      )}
      {connectionId && tools.length === 0 && (
        <p className="dim">이 연결에서 확인된 도구가 없습니다. 연결 관리에서 연결 테스트를 다시 실행하세요.</p>
      )}
      {compatibility && !compatibility.ok && <p className="inline-warn">{compatibility.reason}</p>}
      {detected.length > 0 && (
        <div className="detected-files">
          <h4>결과에서 찾은 파일</h4>
          {detected.map((path) => (
            <div className="detected-row" key={path}>
              <small title={path}>{path.split(/[\\/]/).pop()}</small>
              <button
                className="secondary-action small"
                onClick={() => {
                  addResultAsset(node.id, generatedAssetFor(path))
                  onNotice(`소재로 등록했습니다: ${path}`)
                }}
              >
                소재로 등록
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function collectCandidates(
  nodeId: string,
  incoming: StudioEdge[],
  nodeById: Map<string, StudioNode>,
  assets: StudioAsset[],
): StudioAsset[] {
  void nodeId
  const found = new Map<string, StudioAsset>()
  for (const edge of incoming) {
    if (edge.kind !== 'data') continue
    const sourceNode = nodeById.get(edge.source)
    if (!sourceNode) continue
    const assetIds = sourceNode.kind === 'asset'
      ? [typeof sourceNode.config.assetId === 'string' ? sourceNode.config.assetId : '']
      : sourceNode.results
    for (const assetId of assetIds) {
      if (!assetId) continue
      const asset = assets.find((item) => item.id === assetId)
      if (asset) found.set(asset.id, asset)
    }
  }
  return [...found.values()]
}

function ShotInspector({ id, onExpandShot }: { id: string; onExpandShot: (shotId: string) => void }) {
  const shot = useStudioStore((state) => state.doc.shots.find((item) => item.id === id))
  const nodes = useStudioStore((state) => state.doc.nodes)
  const assets = useStudioStore((state) => state.doc.assets)
  const updateShot = useStudioStore((state) => state.updateShot)
  const removeShot = useStudioStore((state) => state.removeShot)
  const setSelection = useStudioStore((state) => state.setSelection)

  if (!shot) return <div className="inspector-empty">선택한 샷을 찾을 수 없습니다.</div>
  const shotNodes = nodes.filter((node) => shot.nodeIds.includes(node.id))

  return (
    <div className="inspector-body">
      <div className="inspector-head">
        <span className="section-kicker">샷 {shot.order + 1}</span>
        <div className="inspector-actions">
          <button className="icon-button danger" title="샷 삭제" onClick={() => confirmProtectedAction(`“${shot.title}” 샷을 삭제합니다. 연결된 제작 노드는 캔버스에 남습니다.`) && removeShot(shot.id)}>
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      <label className="field-label">
        역할
        <select value={shot.role} onChange={(event) => updateShot(shot.id, { role: event.target.value })}>
          {SHOT_ROLES.map((role) => (
            <option key={role} value={role}>{role}</option>
          ))}
        </select>
      </label>
      <label className="field-label">
        제목
        <input value={shot.title} onChange={(event) => updateShot(shot.id, { title: event.target.value })} />
      </label>
      <label className="field-label">
        장면 설명
        <textarea rows={4} value={shot.description} onChange={(event) => updateShot(shot.id, { description: event.target.value })} />
      </label>
      <label className="field-label">
        예상 길이(초)
        <input
          value={String(shot.expectedSeconds)}
          inputMode="numeric"
          onChange={(event) => updateShot(shot.id, { expectedSeconds: Math.max(0, Number(event.target.value.replace(/[^0-9.]/g, '')) || 0) })}
        />
      </label>
      <label className="field-label">
        정확한 화면 문구
        <textarea rows={2} value={shot.copy} onChange={(event) => updateShot(shot.id, { copy: event.target.value })} />
      </label>
      <label className="field-label">
        나레이션
        <textarea rows={2} value={shot.narration} onChange={(event) => updateShot(shot.id, { narration: event.target.value })} />
      </label>

      <section className="inspector-section">
        <h3 className="inspector-title">선택 소재</h3>
        <select value={shot.selectedAssetId ?? ''} onChange={(event) => {
          const assetId = event.target.value || null
          updateShot(shot.id, { selectedAssetId: assetId })
          for (const linked of shotNodes) if (assetId) useStudioStore.getState().setNodeConfig(linked.id, 'selectedAssetId', assetId)
        }}>
          <option value="">선택 없음</option>
          {assets.map((asset) => (
            <option key={asset.id} value={asset.id}>{asset.name}</option>
          ))}
        </select>
      </section>

      <section className="inspector-section">
        <h3 className="inspector-title">연결된 제작 노드 ({shotNodes.length})</h3>
        {shotNodes.length === 0 && <p className="dim">아직 노드가 없습니다. 아래 버튼으로 샷에 필요한 노드를 만드세요.</p>}
        <div className="chip-row">
          {shotNodes.map((node) => (
            <button key={node.id} className="chip" onClick={() => setSelection({ type: 'node', id: node.id })}>
              {node.title}
            </button>
          ))}
        </div>
        <button className="secondary-action small" onClick={() => onExpandShot(shot.id)}>
          캔버스에 펼치기
        </button>
      </section>
    </div>
  )
}

function AssetInspector({ id, onReveal }: { id: string; onReveal: (path: string) => void }) {
  const asset = useStudioStore((state) => state.doc.assets.find((item) => item.id === id))
  const nodes = useStudioStore((state) => state.doc.nodes)
  const removeAsset = useStudioStore((state) => state.removeAsset)
  const addNode = useStudioStore((state) => state.addNode)
  const updateNode = useStudioStore((state) => state.updateNode)
  const setSelection = useStudioStore((state) => state.setSelection)

  if (!asset) return <div className="inspector-empty">선택한 소재를 찾을 수 없습니다.</div>
  const referencing = nodes.filter((node) => node.config.assetId === asset.id)

  return (
    <div className="inspector-body">
      <div className="inspector-head">
        <span className="section-kicker">소재 · {asset.kind}</span>
        <div className="inspector-actions">
          <button className="icon-button danger" title="소재 삭제" onClick={() => confirmProtectedAction(`“${asset.name}” 소재와 이를 참조하는 노드 ${referencing.length}개를 삭제합니다.`) && removeAsset(asset.id)}>
            <Trash2 size={14} />
          </button>
        </div>
      </div>
      <div className="inspector-thumb large">
        {asset.kind === 'image' && <img src={assetDisplayUrl(asset)} alt="" />}
        {asset.kind === 'video' && <video src={assetDisplayUrl(asset)} muted controls />}
        {asset.kind === 'audio' && <audio src={assetDisplayUrl(asset)} controls />}
        {asset.kind === 'other' && <span className="dim">미리보기 없음</span>}
      </div>
      <dl className="meta-list">
        <div><dt>이름</dt><dd>{asset.name}</dd></div>
        <div><dt>경로</dt><dd title={asset.storedPath}>{asset.storedPath || '브라우저 미리보기 임시 소재'}</dd></div>
        <div><dt>크기</dt><dd>{asset.sizeBytes ? formatBytes(asset.sizeBytes) : '알 수 없음'}</dd></div>
        <div><dt>hash</dt><dd>{asset.hash || '-'}</dd></div>
      </dl>
      <div className="button-row">
        {asset.storedPath && (
          <button className="secondary-action small" onClick={() => onReveal(asset.storedPath)}>
            <FolderOpen size={13} />
            폴더에서 보기
          </button>
        )}
        <button
          className="secondary-action small"
          onClick={() => {
            const createdId = addNode('asset', { x: 140, y: 140 })
            updateNode(createdId, { title: asset.name, config: { assetId: asset.id, assetName: asset.name } })
            setSelection({ type: 'node', id: createdId })
          }}
          title="같은 파일을 참조하는 소재 노드를 하나 더 만듭니다."
        >
          노드로 추가
        </button>
      </div>
      <section className="inspector-section">
        <h3 className="inspector-title">참조하는 노드 ({referencing.length})</h3>
        <div className="chip-row">
          {referencing.map((node) => (
            <button key={node.id} className="chip" onClick={() => setSelection({ type: 'node', id: node.id })}>
              {node.title}
            </button>
          ))}
        </div>
      </section>
    </div>
  )
}

function ProjectInspector({ onImportAssets, onNotice }: { onImportAssets: () => void; onNotice: (message: string) => void }) {
  const projectName = useStudioStore((state) => state.projectName)
  const doc = useStudioStore((state) => state.doc)
  const setProjectName = useStudioStore((state) => state.setProjectName)
  const setNotes = useStudioStore((state) => state.setNotes)
  const saveState = useStudioStore((state) => state.saveState)
  const saveError = useStudioStore((state) => state.saveError)
  const lastSavedAt = useStudioStore((state) => state.lastSavedAt)
  const projectId = useStudioStore((state) => state.projectId)
  const [templates, setTemplates] = React.useState<TemplateRow[]>([])
  const [usage, setUsage] = React.useState<ProjectUsageSummary | null>(null)
  const [templateName, setTemplateName] = React.useState('')

  const refresh = React.useCallback(async () => {
    if (!isTauri || !projectId) return
    try {
      setTemplates(await listTemplates())
    } catch {
      // 템플릿 목록을 읽지 못해도 프로젝트 편집은 계속한다.
    }
    try {
      setUsage(await projectUsageSummary(projectId))
    } catch {
      // 비용 요약은 다음 진입에서 다시 시도한다.
    }
  }, [projectId])

  React.useEffect(() => {
    void refresh()
  }, [refresh])

  const saveAsTemplate = async () => {
    if (!isTauri) return onNotice(browserCapability('persistProject').reason)
    const selection = useStudioStore.getState().selection
    const template = templateFromSelection()
    if (template.nodes.length === 0) {
      onNotice('템플릿으로 저장할 노드가 없습니다.')
      return
    }
    const fallback = selection?.type === 'node'
      ? doc.nodes.find((node) => node.id === selection.id)?.title ?? '노드 묶음'
      : projectName
    const name = templateName.trim() || fallback
    try {
      await saveTemplate({ name, description: `노드 ${template.nodes.length}개`, documentJson: JSON.stringify(template) })
      setTemplateName('')
      onNotice(`템플릿을 저장했습니다: ${name}`)
      await refresh()
    } catch (error) {
      onNotice(String(error))
    }
  }

  return (
    <div className="inspector-body">
      <div className="inspector-head">
        <span className="section-kicker">프로젝트</span>
      </div>
      <label className="field-label">
        프로젝트 이름
        <input value={projectName} onChange={(event) => setProjectName(event.target.value)} />
      </label>
      <label className="field-label">
        프로젝트 메모
        <textarea rows={4} value={doc.notes} onChange={(event) => setNotes(event.target.value)} />
      </label>
      <dl className="meta-list">
        <div><dt>노드</dt><dd>{doc.nodes.length}</dd></div>
        <div><dt>연결</dt><dd>{doc.edges.length}</dd></div>
        <div><dt>샷</dt><dd>{doc.shots.length}</dd></div>
        <div><dt>소재</dt><dd>{doc.assets.length}</dd></div>
        <div><dt>저장</dt><dd>{saveState === 'error' ? saveError : lastSavedAt ? lastSavedAt.slice(11, 19) + ' 저장됨' : '저장 전'}</dd></div>
      </dl>
      <button className="secondary-action small" onClick={onImportAssets}>
        소재 가져오기
      </button>

      <section className="inspector-section">
        <h3 className="inspector-title">노드 그룹 템플릿 {templates.length > 0 ? `(${templates.length})` : ''}</h3>
        <p className="dim">선택한 노드와 하위 노드를 템플릿으로 저장하고 다른 프로젝트에서 다시 놓습니다. 소재 경로는 복사하지 않습니다.</p>
        <div className="template-save">
          <input
            value={templateName}
            onChange={(event) => setTemplateName(event.target.value)}
            placeholder="템플릿 이름 (비우면 선택 이름)"
            aria-label="템플릿 이름"
          />
          <button className="secondary-action small" onClick={() => void saveAsTemplate()}>
            프로젝트 전체를 템플릿으로 저장
          </button>
        </div>
        <div className="ref-list">
          {templates.map((template) => (
            <div className="ref-row" key={template.id}>
              <div className="ref-copy">
                <strong>{template.name}</strong>
                <small>노드 {template.nodeCount}개 · {template.description ?? '설명 없음'}</small>
              </div>
              <button
                className="row-action"
                title="캔버스에 놓기"
                onClick={() => {
                  try {
                    const added = insertTemplate(template.documentJson, { x: 80, y: 80 })
                    onNotice(`템플릿에서 노드 ${added}개를 추가했습니다. 소재 연결을 다시 확인하세요.`)
                  } catch (error) {
                    onNotice(String(error))
                  }
                }}
              >
                놓기
              </button>
              <button
                className="icon-button small danger"
                title="템플릿 삭제"
                onClick={() => {
                  if (!isTauri) return onNotice(browserCapability('persistProject').reason)
                  if (!confirmProtectedAction(`“${template.name}” 템플릿을 삭제합니다. 이미 놓인 노드는 남습니다.`)) return
                  void deleteTemplate(template.id).then(() => refresh()).catch((error) => onNotice(String(error)))
                }}
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="inspector-section">
        <h3 className="inspector-title">비용 귀속</h3>
        {usage?.runs.some((run) => run.amountKind === 'pending') && <button className="secondary-action small" onClick={() => { window.location.hash = 'usage'; onNotice('사용량 화면에서 전체 동기화를 실행해 반영 대기 비용을 확인하세요.') }}>사용량에서 비용 동기화</button>}
        {usage && (
          <>
            <dl className="meta-list">
              <div>
                <dt>확인된 비용</dt>
                <dd>{usage.pricedRuns > 0 ? `$${usage.confirmedTotal.toFixed(2)}` : '아직 확인된 비용 없음'}</dd>
              </div>
              <div><dt>비용 확인된 실행</dt><dd>{usage.pricedRuns}</dd></div>
              <div><dt>미확인 실행</dt><dd>{usage.unpricedRuns}</dd></div>
            </dl>
            <div className="run-list">
              {usage.runs.slice(0, 6).map((run) => (
                <div className={`run-row ${run.status}`} key={run.runId}>
                  <span className="run-status">
                    {run.amountKind === 'confirmed' ? `$${run.amount?.toFixed(3) ?? '-'}` : run.amountKind === 'pending' ? '반영 대기' : '미확인'}
                  </span>
                  <span className="run-stage">{run.nodeTitle ?? run.nodeId}</span>
                  <small>{run.tool}</small>
                </div>
              ))}
            </div>
          </>
        )}
      </section>

      <p className="dim">
        캔버스가 비어 있으면 왼쪽 패널에서 노드를 추가하세요. 소재·대화·실행 기록은 이 프로젝트에 함께 저장됩니다.
      </p>
    </div>
  )
}
