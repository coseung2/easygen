import React from 'react'
import { listenSafely } from './lib/listen'
import { CheckCircle2, Plus, X, Zap } from 'lucide-react'
import { EditPage } from './EditPage'
import { ConnectionsPage } from './pages/ConnectionsPage'
import { StudioPage } from './studio/StudioPage'
import { UsagePage } from './UsagePage'
import { GeneratePage } from './pages/GeneratePage'
import { JobsPage } from './pages/JobsPage'
import { ResultsPage } from './pages/ResultsPage'
import { SettingsPage } from './pages/SettingsPage'
import { call, isTauri } from './lib/tauri'
import { listRecentJobs, storedJobToJob } from './lib/jobs'
import type { Job, JobStage, JobKind } from './types'
import { navItems, stageLabels, type Draft, type Page, type WorkerEvent } from './app-config'
import { applyWorkerEvent, reconcileJobLists } from './ux/stageOne'

export function App() {
  const [page, setPage] = React.useState<Page>('Studio')
  React.useEffect(() => {
    const openUsage = () => { if (window.location.hash === '#usage') setPage('Usage') }
    window.addEventListener('hashchange', openUsage)
    return () => window.removeEventListener('hashchange', openUsage)
  }, [])
  const [jobs, setJobs] = React.useState<Job[]>([])
  const [notice, setNotice] = React.useState('')
  const [retryDraft, setRetryDraft] = React.useState<Draft | null>(null)

  // The queue screen is otherwise in-memory only, so a restart would hide the
  // jobs the database already knows about (including the ones closed as
  // interrupted). Rows already in memory win, since they are the live ones.
  React.useEffect(() => {
    if (!isTauri) return
    let cancelled = false
    void listRecentJobs(100)
      .then((rows) => {
        if (cancelled || rows.length === 0) return
        setJobs((current) => reconcileJobLists(current, rows.map(storedJobToJob)))
      })
      .catch((error) => setNotice(`작업 기록을 다시 읽지 못했습니다: ${String(error)}`))
    return () => { cancelled = true }
  }, [])

  React.useEffect(() => {
    if (!isTauri) return
    return listenSafely<WorkerEvent>('worker-event', (message) => {
      if (!message.job_id) return
      setJobs((current) => current.map((job) => job.id === message.job_id ? applyWorkerEvent(job, message, stageLabels) : job))
    })
  }, [])

  const submit = async (draft: Draft) => {
    if (!isTauri) {
      setNotice('브라우저 미리보기에서는 작업을 실행하지 않습니다. Tauri 앱에서 여세요.')
      return
    }
    const count = draft.kind === 'music' ? 1 : draft.variants
    const seedBase = draft.seed ?? Math.floor(Math.random() * 900000000)
    const created: Job[] = []
    for (let index = 0; index < count; index += 1) {
      const id = 'job_' + Date.now() + '_' + String(index + 1).padStart(2, '0')
      const payload = {
        id,
        prompt: draft.kind === 'music' ? draft.style : draft.prompt,
        input_path: draft.inputPath,
        duration: draft.kind === 'music' ? 60 : draft.duration,
        resolution: draft.kind === 'music' ? '48 kHz stereo' : draft.width + '×' + draft.height,
        kind: draft.kind,
        width: draft.width,
        height: draft.height,
        seed: seedBase + index,
        style: draft.style,
        lyrics: draft.lyrics,
        profile_id: draft.profileId,
      }
      try {
        const job: Job = {
          id, kind: draft.kind, profileId: draft.profileId, status: 'QUEUED', stage: 'JOB_CREATED',
          prompt: payload.prompt, inputPath: draft.inputPath, duration: payload.duration, resolution: payload.resolution,
          width: draft.width, height: draft.height, seed: payload.seed, style: draft.style, lyrics: draft.lyrics, createdAt: new Date().toISOString(), logs: ['작업이 큐에 등록되었습니다.'],
        }
        await call('create_job', { job: payload })
        setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)])
        await call(draft.kind === 'music' ? 'start_music' : 'start_job', { job: payload })
        created.push(job)
      } catch (error) {
        setNotice(`작업을 등록하지 못했습니다: ${String(error)}`)
      }
    }
    if (created.length === 0) return
    setNotice(created.length > 1 ? `${created.length}개 작업을 큐에 넣었습니다.` : '작업을 큐에 넣었습니다.')
    setPage('Jobs')
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark"><Zap size={18} fill="currentColor" /></div>
          <div>
            <strong>MODAL GUI</strong>
            <span>H3 / YuE2 STUDIO</span>
          </div>
        </div>
        <div className="workspace-chip">{isTauri ? '로컬 작업 공간' : '브라우저 미리보기'}</div>
        <nav className="primary-nav" aria-label="주 메뉴">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button key={id} className={page === id ? 'nav-item active' : 'nav-item'} aria-label={label} onClick={() => setPage(id)}>
              <Icon size={17} strokeWidth={1.8} />
              <span>{label}</span>
              {id === 'Jobs' && jobs.filter((job) => job.status === 'RUNNING' || job.status === 'QUEUED').length > 0 && (
                <em>{jobs.filter((job) => job.status === 'RUNNING' || job.status === 'QUEUED').length}</em>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          {isTauri ? null : <div className="runtime-status"><div><b>읽기 전용 미리보기</b><small>외부 실행과 저장은 Tauri 앱에서 합니다.</small></div></div>}
        </div>
      </aside>

      {page === 'Studio' ? (
        <main className="workspace studio-mode">
          <StudioPage />
        </main>
      ) : (
        <main className="workspace">
          <header className="topbar">
            <div>
              <div className="eyebrow">WORKSPACE / {page.toUpperCase()}</div>
              <h1>{page === 'Generate' ? '새 미디어 만들기' : page === 'Jobs' ? '작업 큐' : page === 'Edit' ? '편집 · 모션그래픽' : page === 'Results' ? '결과물' : page === 'Usage' ? '사용량 리포트' : page === 'Connections' ? '연결 관리' : '설정'}</h1>
            </div>
            <div className="topbar-actions">
              <span className="system-pill">{isTauri ? '로컬 앱' : '미리보기'}</span>
              <button className="icon-button" title="새 작업" aria-label="새 작업" onClick={() => setPage('Generate')}><Plus size={18} /></button>
            </div>
          </header>

          {notice && <div className="toast"><CheckCircle2 size={16} />{notice}<button onClick={() => setNotice('')} aria-label="알림 닫기"><X size={14} /></button></div>}

          {page === 'Generate' && <GeneratePage onSubmit={submit} retryDraft={retryDraft} />}
          {page === 'Jobs' && <JobsPage jobs={jobs} onNew={() => setPage('Generate')} onRetry={(job) => { setRetryDraft({ kind: job.kind || 't2v', prompt: job.kind === 'music' ? '' : job.prompt, inputPath: job.inputPath || '', duration: job.duration, width: job.width || 1344, height: job.height || 768, variants: 1, seed: job.seed, style: job.style || (job.kind === 'music' ? job.prompt : ''), lyrics: job.lyrics || '', profileId: job.profileId || '' }); setNotice('선택한 작업 입력을 생성 화면에 채웠습니다. 새 유료 작업으로만 다시 실행됩니다.'); setPage('Generate') }} />}
          {page === 'Edit' && <EditPage />}
          {page === 'Results' && <ResultsPage />}
          {page === 'Usage' && <UsagePage />}
          {page === 'Connections' && <ConnectionsPage />}
          {page === 'Settings' && <SettingsPage />}
        </main>
      )}
    </div>
  )
}
