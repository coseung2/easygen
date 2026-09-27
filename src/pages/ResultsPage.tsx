import React from 'react'
import { Check, CircleAlert, Copy, ExternalLink, Film, FolderOpen, RefreshCw } from 'lucide-react'
import { convertFileSrc } from '@tauri-apps/api/core'
import { ThumbGrid } from '../Gallery'
import { listPipelineInputs, revealInExplorer } from '../lib/pipeline'
import type { PipelineInputs } from '../lib/pipeline'
import { isTauri } from '../lib/tauri'

export function ResultsPage() {
  const [inputs, setInputs] = React.useState<PipelineInputs | null>(null)
  const [preview, setPreview] = React.useState('')
  const [error, setError] = React.useState('')
  const [tab, setTab] = React.useState<'ALL' | 'RENDERS' | 'CLIPS' | 'AUDIO'>('ALL')
  const [copied, setCopied] = React.useState(false)

  const loadData = React.useCallback(() => {
    if (!isTauri) {
      setError('Tauri 앱에서 실행하면 F:\\modal-gui\\deliverables의 실제 파일을 읽어옵니다.')
      return
    }
    void listPipelineInputs()
      .then((value) => {
        setInputs(value)
        setPreview((current) => current || value.renders[0]?.path || value.clips[0]?.path || '')
      })
      .catch((cause) => setError(String(cause)))
  }, [])

  React.useEffect(() => {
    loadData()
  }, [loadData])

  const copyPath = () => {
    if (!preview) return
    void navigator.clipboard?.writeText(preview)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const allEntries = React.useMemo(() => {
    if (!inputs) return []
    if (tab === 'RENDERS') return inputs.renders
    if (tab === 'CLIPS') return inputs.clips
    if (tab === 'AUDIO') return inputs.audio
    return [...inputs.renders, ...inputs.clips, ...inputs.audio]
  }, [inputs, tab])

  const filename = preview.split(/[\\/]/).pop() || ''
  const isVideo = ['.mp4', '.mov', '.webm'].some(ext => preview.toLowerCase().endsWith(ext))
  const isAudio = ['.wav', '.mp3', '.ogg', '.flac'].some(ext => preview.toLowerCase().endsWith(ext))

  return (
    <div className="page-stack">
      {error && <div className="inline-warn"><CircleAlert size={14} />{error}</div>}

      {preview && (
        <div className="preview-wrap">
          {isVideo ? (
            <video
              className="preview-video"
              src={isTauri ? convertFileSrc(preview) : undefined}
              controls
              autoPlay
              playsInline
            />
          ) : isAudio ? (
            <div style={{ padding: '32px 20px', background: '#0a0e14', display: 'grid', placeItems: 'center', gap: 12 }}>
              <audio src={isTauri ? convertFileSrc(preview) : undefined} controls style={{ width: '100%', maxWidth: 500 }} />
            </div>
          ) : null}

          <div className="preview-meta">
            <div>
              <strong>{filename}</strong>
              <div style={{ color: '#6f7d91', fontSize: 10, fontFamily: 'DM Mono', marginTop: 4 }}>
                <code>{preview}</code>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <button className="secondary-action small" onClick={copyPath}>
                {copied ? <Check size={13} style={{ color: '#a7ef75' }} /> : <Copy size={13} />}
                {copied ? '복사 완료' : '경로 복사'}
              </button>
              <button className="secondary-action small" onClick={() => void revealInExplorer(preview)}>
                <FolderOpen size={13} />
                탐색기에서 열기
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="table-toolbar">
        <div className="seg" role="tablist" aria-label="결과물 필터">
          <button className={tab === 'ALL' ? 'active' : ''} onClick={() => setTab('ALL')}>전체 ({allEntries.length})</button>
          <button className={tab === 'RENDERS' ? 'active' : ''} onClick={() => setTab('RENDERS')}>최종 렌더 ({inputs?.renders.length || 0})</button>
          <button className={tab === 'CLIPS' ? 'active' : ''} onClick={() => setTab('CLIPS')}>생성 클립 ({inputs?.clips.length || 0})</button>
          <button className={tab === 'AUDIO' ? 'active' : ''} onClick={() => setTab('AUDIO')}>오디오 ({inputs?.audio.length || 0})</button>
        </div>

        <button className="secondary-action small" onClick={loadData} title="새로고침">
          <RefreshCw size={13} />
          목록 갱신
        </button>
      </div>

      <ThumbGrid entries={allEntries} selected={preview} onSelect={setPreview} />
    </div>
  )
}
