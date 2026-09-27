import React from 'react'
import { AudioLines, ChevronRight, ListTodo, Plus, Video } from 'lucide-react'
import type { Job } from '../types'
import { modeLabels, stageLabels } from '../app-config'

export function JobsPage({ jobs, onNew, onRetry }: { jobs: Job[]; onNew: () => void; onRetry: (job: Job) => void }) {
  const [selected, setSelected] = React.useState<string>('')
  const job = jobs.find((item) => item.id === selected)
  const running = jobs.filter((job) => job.status === 'RUNNING' || job.status === 'QUEUED').length
  const complete = jobs.filter((job) => job.status === 'COMPLETED').length
  const failed = jobs.filter((job) => job.status === 'FAILED').length
  return (
    <div className="page-stack">
      <div className="toolbar">
        <span className="metric-line">
          <span>진행 중 <b>{running}</b></span>
          <span>완료 <b>{complete}</b></span>
          <span>실패 <b>{failed}</b></span>
          <span>전체 <b>{jobs.length}</b></span>
        </span>
        <button className="secondary-action" onClick={onNew}><Plus size={15} />새 작업</button>
      </div>
      <section className="panel table-panel">
        {jobs.length === 0
          ? <EmptyState icon={<ListTodo size={20} />} title="작업 없음" detail="" />
          : <div className="job-table">{jobs.map((item) => <JobRow key={item.id} job={item} onOpen={() => setSelected(item.id)} />)}</div>}
      </section>
      {job && <section className="panel"><h2>작업 상세</h2><p>입력: {job.prompt}</p><p>계정: {job.profileId || '미선택'} · workspace는 사용량 화면의 계정 행에서 확인</p><p>원격 실행: {job.functionCallId || '아직 연결 전'}</p><p>단계: {stageLabels[job.stage] || job.stage}</p><p>결과: {job.outputPath || '결과 대기'}</p><p>비용: 사용량 화면의 청구 근거 확인 전 미확인</p>{job.error && <p>실패 원인: {job.error}</p>}{(job.status === 'FAILED' || job.status === 'CANCELLED') && <div><button className="secondary-action" onClick={() => onRetry(job)}>같은 입력으로 새 작업 준비</button><p>재시도는 기존 작업을 다시 실행하지 않고 새 유료 작업을 만듭니다.</p></div>}</section>}
    </div>
  )
}

function JobRow({ job, onOpen }: { job: Job; onOpen: () => void }) {
  const statusClass = job.status.toLowerCase()
  return <button className="job-row" onClick={onOpen}>
    <div className="job-kind">{job.kind === 'music' ? <AudioLines size={16} /> : <Video size={16} />}</div>
    <div className="job-copy">
      <strong>{job.prompt.slice(0, 76)}</strong>
      <small>{job.id} · {job.kind ? modeLabels[job.kind] : 'H3'} · {new Date(job.createdAt).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}</small>
      {job.status === 'FAILED' && job.error ? <small className="bad">{job.error}</small> : null}
    </div>
    <span className={'status-pill ' + statusClass}>{job.status === 'COMPLETED' ? '완료' : job.status === 'FAILED' ? '실패' : job.status === 'QUEUED' ? '대기' : '실행 중'}</span>
    <span className="job-stage">{stageLabels[job.stage] || job.stage}</span>
    <ChevronRight size={16} className="row-arrow" />
  </button>
}


function EmptyState({ icon, title, detail }: { icon: React.ReactNode; title: string; detail: string }) {
  return <div className="empty-state"><span>{icon}</span><strong>{title}</strong><p>{detail}</p></div>
}
