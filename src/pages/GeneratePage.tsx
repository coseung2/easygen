import React from 'react'
import { AudioLines, ImagePlus, Play, Video } from 'lucide-react'
import { isTauri } from '../lib/tauri'
import { listModalProfiles } from '../lib/usage'
import { formatStamp, formatUsd } from '../lib/usage'
import type { ModalProfile } from '../lib/usage'
import type { JobKind } from '../types'
import { defaultLyrics, defaultStyle, modeLabels, type Draft } from '../app-config'
import { browserCapability } from '../ux/stageOne'

export function GeneratePage({ onSubmit, retryDraft }: { onSubmit: (draft: Draft) => Promise<void>; retryDraft?: Draft | null }) {
  const [kind, setKind] = React.useState<JobKind>('fl2v')
  const [prompt, setPrompt] = React.useState('A cinematic supply crate ignites in a volcanic battlefield, red flare smoke, sparks and dust, dynamic tracking camera, realistic game trailer lighting, no logo, no text.')
  const [inputPath, setInputPath] = React.useState('')
  const [inputName, setInputName] = React.useState('')
  const [style, setStyle] = React.useState(defaultStyle)
  const [lyrics, setLyrics] = React.useState(defaultLyrics)
  const [duration, setDuration] = React.useState(5)
  const [resolution, setResolution] = React.useState('1344x768')
  const [variants, setVariants] = React.useState(1)
  const [seedText, setSeedText] = React.useState('')
  const [profiles, setProfiles] = React.useState<ModalProfile[]>([])
  const [profileId, setProfileId] = React.useState('')

  React.useEffect(() => {
    if (!retryDraft) return
    setKind(retryDraft.kind)
    setPrompt(retryDraft.prompt)
    setInputPath(retryDraft.inputPath)
    setDuration(retryDraft.duration)
    setResolution(`${retryDraft.width}x${retryDraft.height}`)
    setVariants(retryDraft.variants)
    setSeedText(retryDraft.seed === undefined ? '' : String(retryDraft.seed))
    setStyle(retryDraft.style)
    setLyrics(retryDraft.lyrics)
    setProfileId(retryDraft.profileId)
  }, [retryDraft])
  React.useEffect(() => {
    if (!isTauri) return
    void listModalProfiles()
      .then((value) => {
        setProfiles(value)
        setProfileId((current) => current || (value.find((item) => item.enabled)?.id ?? ''))
      })
      .catch(() => undefined)
  }, [])

  const [width, height] = resolution.split('x').map(Number)
  const isMusic = kind === 'music'
  // A stopped account is rejected by the backend, so the form only offers
  // accounts that are actually usable.
  const activeProfiles = profiles.filter((profile) => profile.enabled)
  const selectedProfile = activeProfiles.find((profile) => profile.id === profileId)
  const canSubmit = (isMusic ? style.trim().length > 0 && lyrics.trim().length > 0 : prompt.trim().length > 0 && (kind === 't2v' || inputPath.trim().length > 0)) && (!isTauri || Boolean(selectedProfile))
  const previewBlock = browserCapability('callExternalService')

  const chooseFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] as (File & { path?: string }) | undefined
    if (!file) return
    setInputName(file.name)
    setInputPath(file.path || file.name)
  }

  return (
    <div className="page-stack">
      <div className="mode-switch" role="tablist" aria-label="생성 모드">
        {(['t2v', 'fl2v', 'ref2v', 'music'] as JobKind[]).map((item) => (
          <button key={item} className={kind === item ? 'mode-tab active' : 'mode-tab'} onClick={() => setKind(item)} role="tab" aria-selected={kind === item}>
            {item === 'music' ? <AudioLines size={15} /> : <Video size={15} />}
            {modeLabels[item]}
          </button>
        ))}
      </div>

      <form className="studio-form" onSubmit={(event) => {
        event.preventDefault()
        void onSubmit({
          kind,
          prompt,
          inputPath,
          duration,
          width,
          height,
          variants,
          seed: seedText.trim() ? Number(seedText) : undefined,
          style,
          lyrics,
          profileId,
        })
      }}>
        {!isMusic && (
          <div className="field-row">
            <label className="field-label">참조 이미지
              <input
                value={inputPath}
                onChange={(event) => { setInputPath(event.target.value); setInputName('') }}
                placeholder="C:\assets\reference.png"
              />
            </label>
            <label className="file-button">
              <ImagePlus size={15} />{inputName || '파일 선택'}
              <input type="file" accept="image/*" onChange={chooseFile} />
            </label>
          </div>
        )}

        {isMusic
          ? <>
              <label className="field-label">스타일<textarea value={style} onChange={(event) => setStyle(event.target.value)} rows={3} /></label>
              <label className="field-label">가사<textarea value={lyrics} onChange={(event) => setLyrics(event.target.value)} rows={8} /></label>
            </>
          : <textarea className="prompt-area" value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="장면 프롬프트" />}

        <div className="control-grid">
          {!isMusic && <label className="field-label">길이<select value={duration} onChange={(event) => setDuration(Number(event.target.value))}><option value={5}>5초</option><option value={10}>10초</option><option value={15}>15초</option></select></label>}
          {!isMusic && <label className="field-label">해상도<select value={resolution} onChange={(event) => setResolution(event.target.value)}><option value="1344x768">1344 × 768</option><option value="1152x640">1152 × 640</option><option value="896x512">896 × 512</option></select></label>}
          <label className="field-label">변주 수<select value={variants} onChange={(event) => setVariants(Number(event.target.value))}><option value={1}>1개</option><option value={2}>2개</option><option value={4}>4개</option><option value={8}>8개</option></select></label>
          <label className="field-label">Seed<input value={seedText} onChange={(event) => setSeedText(event.target.value.replace(/[^0-9]/g, ''))} placeholder="자동" inputMode="numeric" /></label>
            <label className="field-label">실행 계정 {selectedProfile ? `${selectedProfile.workspace_label || 'workspace 미확인'} · ${selectedProfile.enabled ? '사용 가능' : '사용 불가'} · 마지막 동기화 ${formatStamp(selectedProfile.last_synced_at)} · ${selectedProfile.last_synced_at ? selectedProfile.budget_limit === null ? `실제 계량 ${formatUsd(selectedProfile.month_cost)}` : `예산 잔여 추정 ${formatUsd(selectedProfile.budget_limit - selectedProfile.month_cost)}` : '비용 미확인'}` : '계정 정보 없음'}
            <select value={profileId} onChange={(event) => setProfileId(event.target.value)}>
              {activeProfiles.length === 0 && <option value="">사용 중인 계정 없음</option>}
              {activeProfiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
            </select>
          </label>
        </div>

        <div className="form-footer">
          {!isTauri || !selectedProfile ? <span className="target-note">{!isTauri ? previewBlock.reason : '사용 가능한 계정 없음'}</span> : null}
          <button className="primary-action" disabled={!isTauri || !canSubmit} title={isTauri ? undefined : previewBlock.nextAction}>
            <Play size={16} fill="currentColor" />
            {isMusic ? '음악 생성' : variants > 1 ? variants + '개 생성' : '영상 생성'}
          </button>
        </div>
      </form>
    </div>
  )
}
