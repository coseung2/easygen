// 스튜디오 진입 화면: 프로젝트 만들기와 최근 프로젝트 목록.

import React from 'react'
import { Clock, Download, FilePlus2, FolderOpen, Plus, Search, Sparkles, Trash2, Workflow } from 'lucide-react'
import { isTauri } from '../lib/tauri'
import type { StudioProjectSummary } from './types'

const TEMPLATE_PRESETS = [
  { name: '트레일러 시퀀스 파이프라인', desc: '인트로 영상 → 메인 컷 → 엔딩 텍스트 노드 자동 구성' },
  { name: '숏폼 릴스 제작 워크플로', desc: '세로 9:16 비디오 생성 및 비트 매칭 컷 편집' },
  { name: 'YuE2 배경음악 + 비디오 합성', desc: '오디오 분석 노드와 영상 컷 결합' },
]

export function StudioHome({
  projects,
  busy,
  error,
  onCreate,
  onOpen,
  onDelete,
  onImport,
}: {
  projects: StudioProjectSummary[]
  busy: boolean
  error: string
  onCreate: (name: string) => void
  onOpen: (id: string) => void
  onDelete: (id: string) => void
  onImport: () => void
}) {
  const [name, setName] = React.useState('')
  const [search, setSearch] = React.useState('')

  const filteredProjects = projects.filter((p) =>
    !search.trim() || p.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="studio-home">
      <header className="studio-home-head">
        <span className="section-kicker">
          <Workflow size={12} />
          STUDIO WORKSPACE
        </span>
        <h2>제작 스튜디오 프로젝트</h2>
        <p>노드 기반 캔버스에서 영상, 음악, 텍스트 모션그래픽, 컷 편집을 유기적으로 연결하여 고품질 미디어를 생성합니다.</p>
        <div style={{ marginTop: 12 }}>
          <button className="secondary-action small" onClick={onImport}>
            <Download size={13} />
            프로젝트 파일 가져오기
          </button>
        </div>
      </header>

      {/* Quick Create Form */}
      <form
        className="studio-create"
        onSubmit={(event) => {
          event.preventDefault()
          if (!name.trim()) return
          onCreate(name)
          setName('')
        }}
      >
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="새 프로젝트 이름 입력 (예: PUBG 43.1 티저 트레일러)..."
          aria-label="새 프로젝트 이름"
        />
        <button className="primary-action" disabled={busy || !name.trim()}>
          <Plus size={15} />
          프로젝트 생성
        </button>
      </form>

      {/* Template Suggestions */}
      <div style={{ display: 'grid', gap: 8, marginTop: 4 }}>
        <span className="section-kicker" style={{ color: '#8fa0b5' }}>
          <Sparkles size={11} /> 빠른 템플릿 제안
        </span>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 10 }}>
          {TEMPLATE_PRESETS.map((t) => (
            <button
              key={t.name}
              type="button"
              className="palette-item"
              onClick={() => {
                onCreate(t.name)
              }}
            >
              <div className="palette-icon"><FilePlus2 size={15} /></div>
              <div className="palette-copy">
                <strong>{t.name}</strong>
                <small>{t.desc}</small>
              </div>
            </button>
          ))}
        </div>
      </div>

      {error && <p className="inline-warn">{error}</p>}

      {/* Projects Search and Grid */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#e2e9f3' }}>
          내 프로젝트 목록 ({projects.length})
        </h3>
        {projects.length > 3 && (
          <input
            className="search-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="프로젝트 검색..."
            style={{ width: 200 }}
          />
        )}
      </div>

      <div className="project-grid">
        {projects.length === 0 ? (
          <p className="dim" style={{ gridColumn: '1 / -1', padding: '32px 0', textAlign: 'center' }}>
            생성된 프로젝트가 없습니다. 위의 생성 폼 또는 템플릿으로 시작하세요.
          </p>
        ) : filteredProjects.length === 0 ? (
          <p className="dim" style={{ gridColumn: '1 / -1', padding: '24px 0', textAlign: 'center' }}>
            검색어와 일치하는 프로젝트가 없습니다.
          </p>
        ) : (
          filteredProjects.map((project) => (
            <article className="project-card" key={project.id}>
              <button className="project-open" onClick={() => onOpen(project.id)}>
                <strong>{project.name}</strong>
                <small>
                  노드 {project.nodeCount}개 · 소재 {project.assetCount}개 · 리비전 #{project.revision}
                </small>
                <span>수정: {project.updatedAt.slice(0, 16).replace('T', ' ')}</span>
              </button>
              <div className="project-actions">
                <button className="icon-button small" title="프로젝트 열기" onClick={() => onOpen(project.id)}>
                  <FolderOpen size={13} />
                </button>
                <button className="icon-button small danger" title="프로젝트 삭제" onClick={() => onDelete(project.id)}>
                  <Trash2 size={13} />
                </button>
              </div>
            </article>
          ))
        )}
      </div>

      {!isTauri && <p className="inline-warn">브라우저 미리보기에서는 임시 인메모리 저장소로 동작합니다.</p>}
    </div>
  )
}
