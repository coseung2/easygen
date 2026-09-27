// 하단 스토리보드 패널: 샷 순서·역할·예상 길이·카피 편집.

import React from 'react'
import { ChevronDown, ChevronLeft, ChevronRight, Clapperboard, Trash2 } from 'lucide-react'
import { useStudioStore } from './store'
import { confirmProtectedAction } from '../ux/stageOne'
import { SHOT_ROLES } from './types'

export function StoryboardBar({ onExpandShot }: { onExpandShot: (shotId: string) => void }) {
  const shots = useStudioStore((state) => state.doc.shots)
  const selection = useStudioStore((state) => state.selection)
  const addShot = useStudioStore((state) => state.addShot)
  const updateShot = useStudioStore((state) => state.updateShot)
  const removeShot = useStudioStore((state) => state.removeShot)
  const moveShot = useStudioStore((state) => state.moveShot)
  const setSelection = useStudioStore((state) => state.setSelection)
  const [collapsed, setCollapsed] = React.useState(false)

  const ordered = [...shots].sort((left, right) => left.order - right.order)
  const total = ordered.reduce((sum, shot) => sum + (Number(shot.expectedSeconds) || 0), 0)

  const add = () => {
    const id = addShot()
    setSelection({ type: 'shot', id })
  }

  return (
    <section className={collapsed ? 'storyboard collapsed' : 'storyboard'}>
      <header className="storyboard-head">
        <span className="section-kicker">
          <Clapperboard size={12} />
          스토리보드
        </span>
        <span className="storyboard-meta">샷 {ordered.length}개 · 총 {total.toFixed(1)}초</span>
        <button className="secondary-action small" onClick={add}>샷 추가</button>
        <button
          className="icon-button small"
          onClick={() => setCollapsed((value) => !value)}
          title={collapsed ? '스토리보드 펼치기' : '스토리보드 접기'}
        >
          <ChevronDown size={13} className={collapsed ? 'flip' : ''} />
        </button>
      </header>

      {!collapsed && (
        <div className="storyboard-strip">
          {ordered.length === 0 && (
            <p className="dim">샷 없음</p>
          )}
          {ordered.map((shot, index) => (
            <article
              key={shot.id}
              className={selection?.type === 'shot' && selection.id === shot.id ? 'shot-card selected' : 'shot-card'}
              onClick={() => setSelection({ type: 'shot', id: shot.id })}
            >
              <header className="shot-card-head">
                <span className="shot-index">샷 {index + 1}</span>
                <select
                  value={shot.role}
                  onClick={(event) => event.stopPropagation()}
                  onChange={(event) => updateShot(shot.id, { role: event.target.value })}
                >
                  {SHOT_ROLES.map((role) => (
                    <option key={role} value={role}>{role}</option>
                  ))}
                </select>
                <div className="shot-move">
                  <button
                    className="icon-button small"
                    title="앞으로"
                    disabled={index === 0}
                    onClick={(event) => { event.stopPropagation(); moveShot(shot.id, -1) }}
                  >
                    <ChevronLeft size={12} />
                  </button>
                  <button
                    className="icon-button small"
                    title="뒤로"
                    disabled={index === ordered.length - 1}
                    onClick={(event) => { event.stopPropagation(); moveShot(shot.id, 1) }}
                  >
                    <ChevronRight size={12} />
                  </button>
                </div>
              </header>
              <input
                className="shot-title"
                value={shot.title}
                onClick={(event) => event.stopPropagation()}
                onChange={(event) => updateShot(shot.id, { title: event.target.value })}
              />
              <textarea
                className="shot-desc"
                rows={2}
                placeholder="장면 설명"
                value={shot.description}
                onClick={(event) => event.stopPropagation()}
                onChange={(event) => updateShot(shot.id, { description: event.target.value })}
              />
              <div className="shot-row-meta">
                <label onClick={(event) => event.stopPropagation()}>
                  <input
                    className="shot-seconds"
                    value={String(shot.expectedSeconds)}
                    inputMode="numeric"
                    onChange={(event) => updateShot(shot.id, { expectedSeconds: Math.max(0, Number(event.target.value.replace(/[^0-9.]/g, '')) || 0) })}
                  />
                  초
                </label>
                <span>{shot.nodeIds.length}개 노드</span>
                <button
                  className="icon-button small danger"
                  title="샷 삭제"
                  onClick={(event) => { event.stopPropagation(); if (confirmProtectedAction(`“${shot.title}” 샷을 삭제합니다. 연결된 제작 노드는 캔버스에 남습니다.`)) removeShot(shot.id) }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
              <footer className="shot-card-foot">
                <button
                  className="link-button"
                  onClick={(event) => { event.stopPropagation(); onExpandShot(shot.id) }}
                >
                  캔버스에 펼치기
                </button>
                {shot.selectedAssetId && <em className="shot-flag">소재 선택됨</em>}
              </footer>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
