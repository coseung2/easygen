// 캔버스 노드 카드: 이름, 실행 도구 요약, 결과 썸네일, 포트, 상태, 실행 버튼.

import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { Play } from 'lucide-react'
import { CONTEXT_COLOR, isRunnable, nodeSpec, PORT_COLORS } from './catalog'
import { configSummary, inputsOf, outputPortsFor, specContextIn, specContextOut } from './graph'
import { assetDisplayUrl } from './lib'
import { activeRunFor, latestRunFor, startStudioRun } from './runController'
import { useStudioStore } from './store'
import { runStatusLabel, type NodeStatus, type StudioAsset, type StudioNode } from './types'

export type StudioFlowNode = Node<{ nodeId: string }, 'studio'>

export const STATUS_LABELS: Record<NodeStatus, string> = {
  draft: '편집 중',
  ready: '준비됨',
  running: '실행 중',
  done: '완료',
  stale: '입력 변경됨',
  failed: '실패',
}

function referencedAssetOf(node: StudioNode, assets: StudioAsset[]): StudioAsset | undefined {
  const key = node.kind === 'asset' ? 'assetId' : node.kind === 'select' ? 'selectedAssetId' : ''
  if (!key) return undefined
  const value = node.config[key]
  if (typeof value !== 'string' || !value) return undefined
  return assets.find((asset) => asset.id === value)
}

export function NodeCard({ data, selected }: NodeProps<StudioFlowNode>) {
  const node = useStudioStore((state) => state.doc.nodes.find((item) => item.id === data.nodeId))
  const referenced = useStudioStore((state) => {
    const current = state.doc.nodes.find((item) => item.id === data.nodeId)
    return current ? referencedAssetOf(current, state.doc.assets) : undefined
  })
  const resultAsset = useStudioStore((state) => {
    const current = state.doc.nodes.find((item) => item.id === data.nodeId)
    const latest = current?.results[0]
    if (!latest) return undefined
    return state.doc.assets.find((asset) => asset.id === latest)
  })
  const activeRun = useStudioStore((state) => activeRunFor(state.runs, data.nodeId))
  const latestRun = useStudioStore((state) => latestRunFor(state.runs, data.nodeId))

  if (!node) return null

  const spec = nodeSpec(node.kind)
  const Icon = spec.icon
  const inputs = inputsOf(node)
  const outputs = outputPortsFor(node, referenced)
  const rows = Math.max(inputs.length, outputs.length)
  const preview = resultAsset ?? (node.kind === 'asset' ? referenced : undefined)
  const previewUrl = preview ? assetDisplayUrl(preview) : ''
  const contextOut = specContextOut(node)
  const contextIn = specContextIn(node)

  return (
    <div className={selected ? 'snode selected' : 'snode'} data-kind={node.kind}>
      {contextOut && (
        <Handle
          type="source"
          id="context"
          position={Position.Top}
          className="snode-handle"
          style={{ background: CONTEXT_COLOR, borderStyle: 'dashed' }}
          title="맥락 출력"
        />
      )}
      {contextIn && (
        <Handle
          type="target"
          id="context"
          position={Position.Top}
          className="snode-handle"
          style={{ background: CONTEXT_COLOR, borderStyle: 'dashed' }}
          title="맥락 입력 (브리프·무드보드 참고)"
        />
      )}

      <header className="snode-head">
        <span className="snode-kind">
          <Icon size={12} strokeWidth={2} />
          {spec.label}
        </span>
        <strong title={node.title}>{node.title}</strong>
      </header>

      <p className="snode-summary">{configSummary(node)}</p>

      {previewUrl && (
        <div className="snode-thumb">
          {preview?.kind === 'video' ? (
            <video src={previewUrl} muted playsInline />
          ) : (
            <img src={previewUrl} alt="" />
          )}
        </div>
      )}

      <div className="snode-ports">
        {Array.from({ length: rows }).map((_, index) => {
          const input = inputs[index]
          const output = outputs[index]
          return (
            <div className="snode-port-row" key={`${input?.id ?? 'i'}${output?.id ?? 'o'}-${index}`}>
              {input && (
                <>
                  <Handle
                    type="target"
                    id={input.id}
                    position={Position.Left}
                    className="snode-handle"
                    style={{ background: PORT_COLORS[input.type] }}
                    title={`${input.label} · ${input.type}${input.multiple ? ' · 복수' : ''}`}
                  />
                  <span className="snode-port in" title={input.type}>
                    {input.label}
                  </span>
                </>
              )}
              {output && (
                <>
                  <span className="snode-port out" title={output.type}>
                    {output.label}
                  </span>
                  <Handle
                    type="source"
                    id={output.id}
                    position={Position.Right}
                    className="snode-handle"
                    style={{ background: PORT_COLORS[output.type] }}
                    title={`${output.label} · ${output.type}`}
                  />
                </>
              )}
            </div>
          )
        })}
      </div>

      <footer className="snode-foot">
        <span className={`snode-status ${node.status}`}>{STATUS_LABELS[node.status]}</span>
        {activeRun && <span className="snode-run-state">{activeRun.status === 'cancel_requested' ? '중단 확인 대기' : runStatusLabel(activeRun.status)}</span>}
        {!activeRun && <span className="snode-run-state">{node.status === 'ready' ? '입력 확인됨' : node.status === 'draft' ? '입력 필요' : '상태 확인'}</span>}
        {!activeRun && latestRun?.status === 'failed' && <span className="snode-run-state bad">실행 실패</span>}
        {node.results.length > 0 && <span className="snode-run-state ok">후보 {node.results.length}</span>}
        {spec.executionStage !== null && node.status !== 'done' ? (
          <button
            className="snode-run"
            disabled={!isRunnable(node.kind) || Boolean(activeRun) || node.status === 'draft'}
            title={!isRunnable(node.kind) ? '연결된 실행 도구가 없습니다.' : activeRun ? '이미 실행 중입니다.' : node.status === 'draft' ? '필수 입력을 먼저 작성하세요.' : node.status === 'failed' ? latestRun?.errorMessage || '실패 원인을 확인한 뒤 다시 실행하세요.' : '입력과 계정 상태를 확인해 실행합니다.'}
            onClick={(event) => {
              event.stopPropagation()
              void startStudioRun(node.id).then((result) => {
                const store = useStudioStore.getState()
                if (!result.ok) store.setNotice(result.reason ?? '실행을 시작하지 못했습니다.')
                else if (result.reason) store.setNotice(result.reason)
              })
            }}
          >
            <Play size={10} fill="currentColor" />
            {activeRun ? '실행 중' : node.status === 'stale' || node.status === 'failed' ? '다시 실행' : '실행'}
          </button>
        ) : (
          <span className="snode-note">{node.status === 'done' ? '후보 확인' : '구성 노드'}</span>
        )}
      </footer>
    </div>
  )
}
