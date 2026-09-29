// 좌측 패널: 노드 추가 카탈로그와 프로젝트 소재.

import React from 'react'
import { Plus, Upload } from 'lucide-react'
import { formatBytes } from '../lib/pipeline'
import { NODE_GROUPS, NODE_SPECS } from './catalog'
import { assetDisplayUrl } from './lib'
import { useStudioStore } from './store'
import type { NodeKind } from './types'

export function LeftPanel({ onAddNode, onImportAssets }: { onAddNode: (kind: NodeKind) => void; onImportAssets: () => void }) {
  const [tab, setTab] = React.useState<'nodes' | 'assets'>('nodes')
  const assets = useStudioStore((state) => state.doc.assets)
  const nodes = useStudioStore((state) => state.doc.nodes)
  const setSelection = useStudioStore((state) => state.setSelection)

  const openAsset = (assetId: string) => {
    const node = nodes.find((item) => item.kind === 'asset' && item.config.assetId === assetId)
    if (node) setSelection({ type: 'node', id: node.id })
    else setSelection({ type: 'asset', id: assetId })
  }

  return (
    <aside className="studio-left">
      <div className="seg studio-tabs">
        <button className={tab === 'nodes' ? 'active' : ''} onClick={() => setTab('nodes')}>노드</button>
        <button className={tab === 'assets' ? 'active' : ''} onClick={() => setTab('assets')}>소재 {assets.length > 0 ? assets.length : ''}</button>
      </div>

      {tab === 'nodes' && (
        <div className="studio-scroll">
          {NODE_GROUPS.map((group) => {
            const specs = NODE_SPECS.filter((spec) => spec.group === group)
            if (specs.length === 0) return null
            return (
              <section className="palette-group" key={group}>
                <h4>{group}</h4>
                {specs.map((spec) => {
                  const Icon = spec.icon
                  return (
                    <button key={spec.kind} className="palette-item" onClick={() => onAddNode(spec.kind)} title={spec.description}>
                      <span className="palette-icon"><Icon size={14} /></span>
                      <span className="palette-copy">
                        <strong>{spec.label}</strong>
                        <small>{spec.description}</small>
                      </span>
                      <Plus size={12} className="palette-plus" />
                    </button>
                  )
                })}
              </section>
            )
          })}
        </div>
      )}

      {tab === 'assets' && (
        <div className="studio-scroll">
          <button className="secondary-action small wide" onClick={onImportAssets}>
            <Upload size={13} />
            소재 가져오기
          </button>
          {assets.length === 0 && <p className="dim">소재 없음</p>}
          <div className="asset-list">
            {assets.map((asset) => (
              <button key={asset.id} className="asset-item" onClick={() => openAsset(asset.id)} title={asset.storedPath || asset.name}>
                <span className="asset-thumb">
                  {asset.kind === 'image' && <img src={assetDisplayUrl(asset)} alt="" />}
                  {asset.kind === 'video' && <video src={assetDisplayUrl(asset)} muted />}
                  {asset.kind === 'audio' && <em>♪</em>}
                  {asset.kind === 'other' && <em>?</em>}
                </span>
                <span className="asset-copy">
                  <strong>{asset.name}</strong>
                  <small>
                    {asset.kind}
                    {asset.sizeBytes ? ` · ${formatBytes(asset.sizeBytes)}` : ''}
                    {asset.ephemeral ? ' · 임시' : ''}
                  </small>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </aside>
  )
}
