import React from 'react'
import { AudioLines, Dices, ImagePlus, Play, Sparkles, Video, X } from 'lucide-react'
import { isTauri } from '../lib/tauri'
import { listModalProfiles } from '../lib/usage'
import { formatStamp, formatUsd } from '../lib/usage'
import type { ModalProfile } from '../lib/usage'
import type { JobKind } from '../types'
import { defaultLyrics, defaultStyle, modeLabels, type Draft } from '../app-config'
import { browserCapability } from '../ux/stageOne'

const VIDEO_PRESETS = [
  { label: '🔥 화염 속 보급 상자', prompt: 'A cinematic supply crate ignites in a volcanic battlefield, red flare smoke, sparks and dust, dynamic tracking camera, realistic game trailer lighting, no logo, no text.' },
  { label: '⚡ 사이버펑크 네온 시티', prompt: 'Cyberpunk metropolis in heavy rain, holographic billboards reflecting on wet asphalt, flying vehicles streaks, ultra-detailed 8k, cinematic anamorphic lens flare.' },
  { label: '🌊 폭풍우 속 해전', prompt: 'Turbulent ocean storm, massive waves crashing against a combat naval destroyer, lightning strikes illuminating dark thunderclouds, cinematic blockbuster film look.' },
  { label: '🎬 폐허 도시 수색', prompt: 'Post-apocalyptic abandoned urban ruins, overgrown ivy on concrete skyscrapers, dust motes dancing in golden sunbeams, slow dramatic drone sweep.' },
]

const MUSIC_PRESETS = [
  { label: '🎸 하이 에너지 록', style: 'English, high-energy cinematic electronic rock, punchy hybrid drums, dark synth pulses, original composition, 128 BPM', lyrics: '[Verse]\nRed flare rising, night turns gold\nDrop zone calling, nerve takes hold\n\n[Chorus]\nDrop in, take over\nKick, dive, dominate\nUpdate forty-three point one changes the game' },
  { label: '🌌 앰비언트 신스웨이브', style: 'Retro 80s synthwave, pulsating analog bassline, lush pads, shimmering arpeggios, nostalgic cinematic mood, 110 BPM', lyrics: '[Intro]\nNeon lights glow through the midnight mist\n\n[Chorus]\nRun through the wire, endless horizon\nNever look back into the digital night' },
]

const RESOLUTION_OPTIONS = [
  { value: '1344x768', label: '16:9 와이드', sub: '1344 × 768' },
  { value: '1152x640', label: '16:9 표준', sub: '1152 × 640' },
  { value: '896x512', label: '16:9 경량', sub: '896 × 512' },
]

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

  const randomizeSeed = () => {
    setSeedText(String(Math.floor(Math.random() * 900000000) + 100000000))
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

      <div className="preset-chips">
        <span className="section-kicker" style={{ marginRight: 4 }}><Sparkles size={11} /> 빠른 추천:</span>
        {(isMusic ? MUSIC_PRESETS : VIDEO_PRESETS).map((preset) => (
          <button
            key={preset.label}
            type="button"
            className="preset-chip"
            onClick={() => {
              if (isMusic && 'style' in preset) {
                setStyle(preset.style)
                setLyrics(preset.lyrics)
              } else if (!isMusic && 'prompt' in preset) {
                setPrompt(preset.prompt)
              }
            }}
          >
            {preset.label}
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
            <label className="field-label">참조 이미지 (시작/기준 프레임)
              <input
                value={inputPath}
                onChange={(event) => { setInputPath(event.target.value); setInputName('') }}
                placeholder="C:\assets\reference.png 또는 파일 선택"
              />
            </label>
            <label className="file-button" title="로컬 이미지 파일 선택">
              <ImagePlus size={15} />{inputName || '파일 탐색'}
              <input type="file" accept="image/*" onChange={chooseFile} />
            </label>
            {inputPath && (
              <button
                type="button"
                className="icon-button"
                title="참조 이미지 초기화"
                onClick={() => { setInputPath(''); setInputName('') }}
              >
                <X size={15} />
              </button>
            )}
          </div>
        )}

        {isMusic ? (
          <>
            <label className="field-label">음악 스타일 및 장르
              <textarea value={style} onChange={(event) => setStyle(event.target.value)} rows={3} placeholder="예: Electronic rock, punchy drums, 128 BPM..." />
            </label>
            <label className="field-label">가사 (섹션 마커 포함)
              <textarea value={lyrics} onChange={(event) => setLyrics(event.target.value)} rows={8} placeholder="[Verse]\n...\n[Chorus]\n..." />
            </label>
          </>
        ) : (
          <div>
            <label className="field-label">장면 프롬프트</label>
            <textarea
              className="prompt-area"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="생성할 영상의 세부 장면, 분위기, 카메라 워크, 조명을 묘사하세요..."
            />
            <div className="prompt-meta-row">
              <span>영문 권장 (최적 결과)</span>
              <span>{prompt.length} 글자</span>
            </div>
          </div>
        )}

        <div className="control-grid">
          {!isMusic && (
            <label className="field-label">길이
              <select value={duration} onChange={(event) => setDuration(Number(event.target.value))}>
                <option value={5}>5초 (표준)</option>
                <option value={10}>10초 (연장)</option>
                <option value={15}>15초 (롱폼)</option>
              </select>
            </label>
          )}

          {!isMusic && (
            <label className="field-label">해상도
              <select value={resolution} onChange={(event) => setResolution(event.target.value)}>
                {RESOLUTION_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label} ({opt.sub})</option>
                ))}
              </select>
            </label>
          )}

          <label className="field-label">생성 수 (변주)
            <select value={variants} onChange={(event) => setVariants(Number(event.target.value))}>
              <option value={1}>1개 (기본)</option>
              <option value={2}>2개 (비교)</option>
              <option value={4}>4개 (배치)</option>
              <option value={8}>8개 (대량)</option>
            </select>
          </label>

          <label className="field-label">Seed
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                value={seedText}
                onChange={(event) => setSeedText(event.target.value.replace(/[^0-9]/g, ''))}
                placeholder="자동 랜덤"
                inputMode="numeric"
              />
              <button type="button" className="icon-button" title="랜덤 시드 생성" onClick={randomizeSeed}>
                <Dices size={15} />
              </button>
            </div>
          </label>

          <label className="field-label" style={{ gridColumn: isMusic ? 'span 2' : 'span 4' }}>
            실행 Modal 계정 {selectedProfile ? `[${selectedProfile.workspace_label || 'workspace'} · ${selectedProfile.last_synced_at ? (selectedProfile.budget_limit === null ? `사용액 ${formatUsd(selectedProfile.month_cost)}` : `예산 잔여 ${formatUsd(selectedProfile.budget_limit - selectedProfile.month_cost)}`) : '동기화 전'}]` : ''}
            <select value={profileId} onChange={(event) => setProfileId(event.target.value)}>
              {activeProfiles.length === 0 && <option value="">사용 가능한 계정 없음</option>}
              {activeProfiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name} ({profile.workspace_label || 'workspace'} · {profile.modal_profile_name || 'default'})
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="form-footer">
          {!isTauri || !selectedProfile ? (
            <span className="target-note">{!isTauri ? previewBlock.reason : '사용 가능한 활성 Modal 계정이 필요합니다.'}</span>
          ) : (
            <span className="target-note">
              {isMusic ? 'YuE2 런타임' : `H3 L40S 런타임 · ${duration}초 · ${width}×${height}`}
            </span>
          )}
          <button className="primary-action" disabled={!isTauri || !canSubmit} title={isTauri ? undefined : previewBlock.nextAction}>
            <Play size={16} fill="currentColor" />
            {isMusic ? '음악 생성 시작' : variants > 1 ? `${variants}개 영상 일괄 생성` : '영상 생성 시작'}
          </button>
        </div>
      </form>
    </div>
  )
}
