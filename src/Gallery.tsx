import React from 'react'
import { convertFileSrc } from '@tauri-apps/api/core'
import { AudioLines, FileText, Film, Video } from 'lucide-react'
import { formatBytes, makeThumbnail } from './lib/pipeline'
import type { MediaEntry } from './lib/pipeline'
import { isTauri } from './lib/tauri'

/** Result grid: clicking a card previews that file directly */
export function ThumbGrid({ entries, selected, onSelect }: {
  entries: MediaEntry[]
  selected: string
  onSelect: (path: string) => void
}) {
  if (entries.length === 0) {
    return <p className="dim" style={{ textAlign: 'center', padding: '32px 0' }}>표시할 결과물 파일이 없습니다.</p>
  }
  return (
    <div className="thumb-grid">
      {entries.map((entry) => (
        <ThumbCard
          key={entry.path}
          entry={entry}
          active={entry.path === selected}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}

function ThumbCard({ entry, active, onSelect }: {
  entry: MediaEntry
  active: boolean
  onSelect: (path: string) => void
}) {
  const [thumb, setThumb] = React.useState('')
  const [fallback, setFallback] = React.useState(false)
  const [broken, setBroken] = React.useState(false)

  React.useEffect(() => {
    if (!isTauri) return
    let alive = true
    void makeThumbnail(entry.path)
      .then((path) => { if (alive) setThumb(path) })
      .catch(() => { if (alive) setFallback(true) })
    return () => { alive = false }
  }, [entry.path])

  const ext = entry.name.split('.').pop()?.toUpperCase() || 'FILE'
  const isAudio = ['WAV', 'MP3', 'OGG', 'FLAC', 'AAC'].includes(ext)
  const isVideo = ['MP4', 'MOV', 'WEBM', 'MKV', 'AVI'].includes(ext)

  return (
    <button type="button" className={'thumb-card' + (active ? ' active' : '')} onClick={() => onSelect(entry.path)}>
      <span className="thumb-frame">
        {thumb ? (
          <img src={convertFileSrc(thumb)} alt="" loading="lazy" />
        ) : fallback && isTauri && !broken ? (
          <video
            src={convertFileSrc(entry.path) + '#t=1.5'}
            preload="metadata"
            muted
            playsInline
            onError={() => setBroken(true)}
          />
        ) : isAudio ? (
          <AudioLines size={22} style={{ color: '#7ec9ff' }} />
        ) : isVideo ? (
          <Film size={22} style={{ color: '#a7ef75' }} />
        ) : (
          <FileText size={22} style={{ color: '#f1c56c' }} />
        )}
      </span>
      <span className="thumb-name" title={entry.path}>{entry.name}</span>
      <span className="thumb-meta" style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span>{formatBytes(entry.size_bytes)}</span>
        <span style={{ color: isVideo ? '#a7ef75' : isAudio ? '#7ec9ff' : '#9aa8ba', fontWeight: 700 }}>{ext}</span>
      </span>
    </button>
  )
}
