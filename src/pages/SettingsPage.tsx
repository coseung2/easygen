import React from 'react'
import { Check, Copy, Cpu, FolderOpen, HardDrive, Info, Layers } from 'lucide-react'
import { getStoragePaths, revealInExplorer, type StoragePaths } from '../lib/pipeline'
import { isTauri } from '../lib/tauri'

export function SettingsPage() {
  const [copiedKey, setCopiedKey] = React.useState('')
  const [paths, setPaths] = React.useState<StoragePaths | null>(null)
  const [pathError, setPathError] = React.useState('')

  React.useEffect(() => {
    if (!isTauri) return
    let active = true
    void getStoragePaths()
      .then((value) => { if (active) setPaths(value) })
      .catch((error) => { if (active) setPathError(String(error)) })
    return () => { active = false }
  }, [])

  const copyText = (text: string, key: string) => {
    void navigator.clipboard?.writeText(text)
    setCopiedKey(key)
    setTimeout(() => setCopiedKey(''), 2000)
  }

  return (
    <div className="page-stack">
      <section className="panel settings-panel">
        <div className="settings-section-title">
          <HardDrive size={16} style={{ color: '#a7ef75' }} />
          로컬 스토리지 및 산출물 디렉터리
        </div>
        {pathError && <div className="inline-warn">저장 경로를 읽지 못했습니다: {pathError}</div>}
        <SettingRow
          label="H3 클립 소재"
          value={paths?.clips ?? (isTauri ? '불러오는 중…' : '데스크톱 앱에서 확인 가능')}
          copied={copiedKey === 'clips'}
          onCopy={paths ? () => copyText(paths.clips, 'clips') : undefined}
          onOpen={paths ? () => void revealInExplorer(paths.clips) : undefined}
        />
        <SettingRow
          label="음악 출력 루트"
          value={paths?.music ?? (isTauri ? '불러오는 중…' : '데스크톱 앱에서 확인 가능')}
          copied={copiedKey === 'music'}
          onCopy={paths ? () => copyText(paths.music, 'music') : undefined}
          onOpen={paths ? () => void revealInExplorer(paths.music) : undefined}
        />
        <SettingRow
          label="최종 산출물"
          value={paths?.deliverables ?? (isTauri ? '불러오는 중…' : '데스크톱 앱에서 확인 가능')}
          copied={copiedKey === 'deliverables'}
          onCopy={paths ? () => copyText(paths.deliverables, 'deliverables') : undefined}
          onOpen={paths ? () => void revealInExplorer(paths.deliverables) : undefined}
        />

        <div className="settings-section-title" style={{ marginTop: 24 }}>
          <Cpu size={16} style={{ color: '#5ec4ff' }} />
          원격 GPU 런타임 & AI 모델
        </div>
        <SettingRow label="H3 영상 런타임" value="Modal L40S · v17 dense fallback" />
        <SettingRow label="YuE2 음악 런타임" value="Modal L40S · YuE2-3B + YuE2-Vae" />
        <SettingRow label="패치 타깃 콘텐츠" value="PUBG Update 43.1 · 2026-09-09" />

        <div className="settings-section-title" style={{ marginTop: 24 }}>
          <Info size={16} style={{ color: '#f1c56c' }} />
          시스템 & 환경 정보
        </div>
        <SettingRow label="클라이언트 환경" value={isTauri ? 'Tauri Desktop (Windows)' : 'Web Browser Preview'} />
        <SettingRow label="앱 버전" value="Modal GUI v0.1.0-alpha" />
      </section>
    </div>
  )
}

function SettingRow({
  label,
  value,
  copied,
  onCopy,
  onOpen,
}: {
  label: string
  value: string
  copied?: boolean
  onCopy?: () => void
  onOpen?: () => void
}) {
  return (
    <div className="setting-row">
      <span>{label}</span>
      <code>{value}</code>
      <div style={{ display: 'flex', gap: 6 }}>
        {onCopy && (
          <button className="icon-button small" title="경로 복사" onClick={onCopy}>
            {copied ? <Check size={12} style={{ color: '#a7ef75' }} /> : <Copy size={12} />}
          </button>
        )}
        {onOpen && (
          <button className="icon-button small" title="탐색기에서 열기" onClick={onOpen}>
            <FolderOpen size={12} />
          </button>
        )}
      </div>
    </div>
  )
}
