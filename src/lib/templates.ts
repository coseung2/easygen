// 로컬 영상 템플릿(pipelines/ 레지스트리의 local-python 파이프라인) 래퍼.
import { call, isTauri } from './tauri'

export type TemplateInfo = {
  id: string
  version: string
  status: 'candidate' | 'released' | string
  label: string
  summary: string
  tone: string | null
  schema: Record<string, unknown>
  runnable: boolean
  unavailableReason: string | null
}

type StoredTemplate = Omit<TemplateInfo, 'unavailableReason'> & { unavailable_reason: string | null }

export const templateRef = (template: Pick<TemplateInfo, 'id' | 'version'>) => `${template.id}@${template.version}`

export async function listTemplates(): Promise<TemplateInfo[]> {
  if (!isTauri) return []
  const rows = await call<StoredTemplate[]>('template_list')
  return rows.map(({ unavailable_reason, ...rest }) => ({ ...rest, unavailableReason: unavailable_reason }))
}

export const renderTemplate = (request: { run_id: string; template: string; job: Record<string, unknown>; output: string }) =>
  call<void>('template_render', { request })

/** 템플릿별 빈 입력 예시. 사용자가 경로와 문구를 채운다. 톤은 기본 발랄·웃김이다. */
export const TEMPLATE_STARTERS: Record<string, Record<string, unknown>> = {
  'local-launch-spoof@1.0': {
    name: '이름',
    palette: 'neon',
    cutout_model: 'bria-rmbg',
    scenes: {
      hook: { badge: 'NEW', lines: ['신제품', '출시'], sub: '2026 한정판 · 단 1개' },
      reveal: { media: '', latin: '', specs: ['출시일  YYYY. MM. DD', '특징  ', '구성  '] },
      spec_zoom: { media: '', at: 0, focus: [540, 770], marks: [], title: ['초롱초롱', '눈망울'], tag: 'SPEC 01 · ' },
      spec_loupe: { media: '', point: null, meter_label: '오똑 지수', title: ['오똑한', '콧날'], tag: 'SPEC 02 · ' },
      gag_launch: { media: '', sound_media: '', setup: '천사 같은 얼굴로…', hit: '뿡!', title: '', tag: 'SPEC 03 · ' },
      meter: { media: '', from: 0, to: 1, decimals: 1, unit: '', from_label: '', to_label: '', title: '쑥쑥 성장', tag: 'SPEC 04 · ' },
      burst: { items: [{ media: '', title: '', sub: '' }] },
      endcard: { kicker: '지금 우리 집에서', title: '절찬 육아 중', tag: '한정판 1개 · 평생 소장', footnote: '' },
    },
  },
  'local-freeze-cast@1.0': {
    name: '이름',
    palette: 'neon',
    cutout_model: 'bria-rmbg',
    badge: 'CAST',
    title: ['등장인물', '소개'],
    subtitle: '우리 집 신입 · 이름 편',
    outro_title: '',
    outro_tag: '',
    cast: [{ media: '', freeze_at: 0, label: '이름', role: '', gag: '' }],
  },
}
