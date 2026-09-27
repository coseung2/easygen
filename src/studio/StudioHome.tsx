// 스튜디오 진입 화면: 프로젝트 만들기와 최근 프로젝트 목록.

import React from 'react'
import { Download, FolderOpen, Plus, Trash2, Workflow } from 'lucide-react'
import { isTauri } from '../lib/tauri'
import type { StudioProjectSummary } from './types'

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

  return (
    <div className="studio-home">
      <header className="studio-home-head">
        <span className="section-kicker">
          <Workflow size={12} />
          제작 스튜디오
        </span>
        <h2>캔버스에서 제작 흐름을 구성합니다</h2>
        <p>
          프로젝트를 만들고 캔버스에 브리프·무드보드·스토리보드·생성 노드를 배치하세요. 스토리보드에서 샷을 정하고,
          소재를 가져와 노드에 연결하면 제작 문서가 자동으로 저장됩니다.
        </p>
        <button className="secondary-action small" onClick={onImport}>
          <Download size={13} />
          내보낸 프로젝트 가져오기
        </button>
      </header>

      <form
        className="studio-create"
        onSubmit={(event) => {
          event.preventDefault()
          onCreate(name)
          setName('')
        }}
      >
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="새 프로젝트 이름"
          aria-label="새 프로젝트 이름"
        />
        <button className="primary-action" disabled={busy}>
          <Plus size={15} />
          프로젝트 만들기
        </button>
      </form>

      {error && <p className="inline-warn">{error}</p>}

      <div className="project-grid">
        {projects.length === 0 && (
          <p className="dim">
            아직 저장된 프로젝트가 없습니다. 첫 프로젝트를 만들어 캔버스 검토를 시작하세요.
          </p>
        )}
        {projects.map((project) => (
          <article className="project-card" key={project.id}>
            <button className="project-open" onClick={() => onOpen(project.id)}>
              <strong>{project.name}</strong>
              <small>
                노드 {project.nodeCount} · 소재 {project.assetCount} · 리비전 {project.revision}
              </small>
              <span>수정 {project.updatedAt.slice(0, 16).replace('T', ' ')}</span>
            </button>
            <div className="project-actions">
              <button className="icon-button small" title="열기" onClick={() => onOpen(project.id)}>
                <FolderOpen size={13} />
              </button>
              <button className="icon-button small danger" title="삭제" onClick={() => onDelete(project.id)}>
                <Trash2 size={13} />
              </button>
            </div>
          </article>
        ))}
      </div>

      <p className="dim studio-home-note">
        {isTauri
          ? '프로젝트 문서는 앱 데이터베이스에, 가져온 소재 파일은 F:\\modal-gui\\studio 폴더에 복사됩니다.'
          : '브라우저 미리보기에서는 프로젝트가 이 브라우저의 저장소에만 보관되고 소재 파일은 임시로 표시됩니다. 실제 저장은 Tauri 앱에서 확인하세요.'}
      </p>
    </div>
  )
}
