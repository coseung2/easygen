import React from 'react'
import { AlertCircle, AudioLines, CheckCircle2, ChevronRight, Clock, Copy, ListTodo, Plus, RotateCcw, Search, Sparkles, Video } from 'lucide-react'
import type { Job } from '../types'
import { modeLabels, stageLabels } from '../app-config'

const STAGE_KEYS = Object.keys(stageLabels)

export function JobsPage({ jobs, onNew, onRetry }: { jobs: Job[]; onNew: () => void; onRetry: (job: Job) => void }) {
  const [selected, setSelected] = React.useState<string>('')
  const [filter, setFilter] = React.useState<'ALL' | 'RUNNING' | 'COMPLETED' | 'FAILED'>('ALL')
  const [search, setSearch] = React.useState('')
  const [copiedId, setCopiedId] = React.useState('')

  const job = jobs.find((item) => item.id === selected)
  const running = jobs.filter((j) => j.status === 'RUNNING' || j.status === 'QUEUED').length
  const complete = jobs.filter((j) => j.status === 'COMPLETED').length
  const failed = jobs.filter((j) => j.status === 'FAILED' || j.status === 'CANCELLED').length

  const filteredJobs = jobs.filter((item) => {
    if (filter === 'RUNNING' && item.status !== 'RUNNING' && item.status !== 'QUEUED') return false
    if (filter === 'COMPLETED' && item.status !== 'COMPLETED') return false
    if (filter === 'FAILED' && item.status !== 'FAILED' && item.status !== 'CANCELLED') return false
    if (search.trim()) {
      const q = search.toLowerCase()
      return item.id.toLowerCase().includes(q) || item.prompt.toLowerCase().includes(q) || (item.profileId && item.profileId.toLowerCase().includes(q))
    }
    return true
  })

  const copyText = (text: string, id: string) => {
    void navigator.clipboard?.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(''), 2000)
  }

  return (
    <div className="page-stack">
      {/* KPI Stats Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-icon running"><Clock size={18} /></div>
          <div className="kpi-info">
            <span className="kpi-label">진행 중 (대기/실행)</span>
            <span className="kpi-value">{running}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon completed"><CheckCircle2 size={18} /></div>
          <div className="kpi-info">
            <span className="kpi-label">완료된 작업</span>
            <span className="kpi-value">{complete}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon failed"><AlertCircle size={18} /></div>
          <div className="kpi-info">
            <span className="kpi-label">실패 / 취소</span>
            <span className="kpi-value">{failed}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon total"><ListTodo size={18} /></div>
          <div className="kpi-info">
            <span className="kpi-label">전체 기록</span>
            <span className="kpi-value">{jobs.length}</span>
          </div>
        </div>
      </div>

      {/* Toolbar with Search and Filter */}
      <div className="table-toolbar">
        <div className="seg" role="tablist" aria-label="작업 필터">
          <button className={filter === 'ALL' ? 'active' : ''} onClick={() => setFilter('ALL')}>전체 ({jobs.length})</button>
          <button className={filter === 'RUNNING' ? 'active' : ''} onClick={() => setFilter('RUNNING')}>진행 중 ({running})</button>
          <button className={filter === 'COMPLETED' ? 'active' : ''} onClick={() => setFilter('COMPLETED')}>완료 ({complete})</button>
          <button className={filter === 'FAILED' ? 'active' : ''} onClick={() => setFilter('FAILED')}>실패 ({failed})</button>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            className="search-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="프롬프트 또는 작업 ID 검색..."
          />
          <button className="primary-action small" onClick={onNew}>
            <Plus size={14} />새 작업
          </button>
        </div>
      </div>

      {/* Main Table */}
      <section className="panel table-panel">
        {jobs.length === 0 ? (
          <EmptyState icon={<ListTodo size={24} />} title="등록된 작업이 없습니다" detail="새 작업을 생성하면 큐에 등록되고 실시간 상태를 추적합니다." />
        ) : filteredJobs.length === 0 ? (
          <EmptyState icon={<Search size={24} />} title="검색 결과가 없습니다" detail="검색어나 필터 조건을 변경해 보세요." />
        ) : (
          <div className="job-table">
            {filteredJobs.map((item) => (
              <JobRow
                key={item.id}
                job={item}
                isSelected={item.id === selected}
                onOpen={() => setSelected(item.id === selected ? '' : item.id)}
                onRetry={() => onRetry(item)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Selected Job Detail Panel */}
      {job && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="section-kicker">JOB INSPECTOR</span>
              <h2>작업 상세 정보</h2>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="secondary-action small" onClick={() => copyText(job.prompt, 'prompt')}>
                <Copy size={13} />
                {copiedId === 'prompt' ? '복사됨!' : '프롬프트 복사'}
              </button>
              {(job.status === 'FAILED' || job.status === 'CANCELLED') && (
                <button className="primary-action small" onClick={() => onRetry(job)}>
                  <RotateCcw size={13} />
                  같은 입력으로 새 작업 실행
                </button>
              )}
            </div>
          </div>

          <div style={{ display: 'grid', gap: 12 }}>
            <div className="setting-row">
              <span>작업 ID</span>
              <code>{job.id}</code>
            </div>
            <div className="setting-row">
              <span>프롬프트</span>
              <p style={{ margin: 0, color: '#e2e9f3', fontSize: 12, lineHeight: 1.6 }}>{job.prompt}</p>
            </div>
            <div className="setting-row">
              <span>Modal 계정</span>
              <span>{job.profileId || '미선택 (기본 계정)'}</span>
            </div>
            <div className="setting-row">
              <span>원격 함수 실행</span>
              <code>{job.functionCallId || '아직 연결 전'}</code>
            </div>
            <div className="setting-row">
              <span>진행 단계</span>
              <span className="status-pill running">{stageLabels[job.stage] || job.stage}</span>
            </div>
            {job.outputPath && (
              <div className="setting-row">
                <span>결과 파일</span>
                <code>{job.outputPath}</code>
              </div>
            )}
            {job.error && (
              <div className="setting-row" style={{ color: '#ff9da0' }}>
                <span>실패 원인</span>
                <p style={{ margin: 0, color: '#ff9da0', fontSize: 11 }}>{job.error}</p>
              </div>
            )}
            {job.logs && job.logs.length > 0 && (
              <div>
                <span className="inspector-label" style={{ marginBottom: 6, display: 'block' }}>작업 실행 로그</span>
                <pre className="advanced-log">{job.logs.join('\n')}</pre>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  )
}

function JobRow({ job, isSelected, onOpen, onRetry }: { job: Job; isSelected: boolean; onOpen: () => void; onRetry: () => void }) {
  const statusClass = job.status.toLowerCase()
  const stageIndex = STAGE_KEYS.indexOf(job.stage)
  const progressPercent = stageIndex >= 0 ? Math.round(((stageIndex + 1) / STAGE_KEYS.length) * 100) : (job.status === 'COMPLETED' ? 100 : 15)

  return (
    <div className={`job-row ${isSelected ? 'active' : ''}`} style={{ cursor: 'pointer' }} onClick={onOpen}>
      <div className="job-kind">
        {job.kind === 'music' ? <AudioLines size={16} /> : <Video size={16} />}
      </div>
      <div className="job-copy">
        <strong>{job.prompt ? job.prompt.slice(0, 80) : '설정된 프롬프트 없음'}</strong>
        <small>
          {job.id} · {job.kind ? modeLabels[job.kind] : 'H3'} · {new Date(job.createdAt).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </small>
        {job.status === 'FAILED' && job.error ? <small className="bad">{job.error}</small> : null}
      </div>

      {job.status === 'RUNNING' && (
        <div className="job-progress-wrap" title={`${progressPercent}% 진행 중`}>
          <div className="job-progress-bar">
            <div className="job-progress-fill" style={{ width: `${progressPercent}%` }} />
          </div>
        </div>
      )}

      <span className={'status-pill ' + statusClass}>
        {job.status === 'COMPLETED' ? '완료' : job.status === 'FAILED' ? '실패' : job.status === 'QUEUED' ? '대기' : '실행 중'}
      </span>
      <span className="job-stage">{stageLabels[job.stage] || job.stage}</span>
      <ChevronRight size={16} className="row-arrow" style={{ transform: isSelected ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s ease' }} />
    </div>
  )
}

function EmptyState({ icon, title, detail }: { icon: React.ReactNode; title: string; detail: string }) {
  return (
    <div className="empty-state">
      <span>{icon}</span>
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  )
}
