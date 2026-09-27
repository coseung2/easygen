// 노드 카탈로그: 제품이 제공하는 노드 종류와 포트·설정 필드 정의.
// 문서 5장의 노드 표를 기준으로 하며, 실행 도구 연결은 단계별로 추가된다.

import {
  Boxes,
  ClipboardList,
  Clapperboard,
  FileImage,
  Film,
  ImagePlus,
  ListChecks,
  Music,
  Palette,
  Scissors,
  Shapes,
  Sparkles,
  TextCursorInput,
  Type,
  Upload,
  Wrench,
} from 'lucide-react'
import type { ComponentType } from 'react'
import type { NodeKind, Port, PortType } from './types'

export type FieldType = 'text' | 'textarea' | 'number' | 'select' | 'checkbox'

/** 앱 데이터에서 채워지는 선택 목록. 정적 options 대신 쓴다. */
export type FieldDynamicSource = 'workflows' | 'connections' | 'profiles'

export interface FieldSpec {
  key: string
  label: string
  type: FieldType
  options?: Array<{ value: string; label: string }>
  dynamic?: FieldDynamicSource
  placeholder?: string
  min?: number
  max?: number
  step?: number
  rows?: number
}

export interface NodeKindSpec {
  kind: NodeKind
  label: string
  group: string
  description: string
  icon: ComponentType<{ size?: number; strokeWidth?: number }>
  inputs: Port[]
  outputs: Port[]
  contextIn: boolean
  contextOut: boolean
  fields: FieldSpec[]
  // 실제 실행 연결이 붙는 구현 단계. null이면 실행 버튼이 없는 기획·구성 노드다.
  executionStage: number | null
}

export const PORT_COLORS: Record<PortType, string> = {
  Text: '#cbd5e2',
  Brief: '#f1c56c',
  StyleGuide: '#e0a3ff',
  Image: '#7ec9ff',
  Video: '#8b9dff',
  Audio: '#6ee7b7',
  Mask: '#ffb86b',
  ShotList: '#f1c56c',
  MotionSpec: '#f0abfc',
  Timeline: '#facc15',
  ProjectFile: '#94a3b8',
  Json: '#9ca3af',
}

export const CONTEXT_COLOR = '#5f7183'

const TOOL_OPTIONS = [
  { value: '', label: '실행 도구 미지정' },
  { value: 'higgsfield', label: 'Higgsfield MCP' },
  { value: 'modal-h3', label: 'Modal H3' },
  { value: 'modal-comfy', label: 'Modal ComfyUI 워크플로' },
  { value: 'gpt-image', label: 'GPT 이미지' },
  { value: 'ae', label: 'After Effects' },
  { value: 'local', label: '로컬 렌더러' },
]

export const NODE_SPECS: NodeKindSpec[] = [
  {
    kind: 'asset',
    label: '소재',
    group: '소재',
    description: '이미지·영상·오디오·프로젝트 파일을 프로젝트 소재로 등록합니다.',
    icon: FileImage,
    inputs: [],
    outputs: [],
    contextIn: false,
    contextOut: false,
    fields: [],
    executionStage: null,
  },
  {
    kind: 'brief',
    label: '브리프',
    group: '기획',
    description: '광고 목적, 제품 사실, 타깃, 필수 문구와 길이를 정합니다.',
    icon: ClipboardList,
    inputs: [],
    outputs: [{ id: 'out', label: '제작 조건', type: 'Brief' }],
    contextIn: false,
    contextOut: true,
    fields: [
      { key: 'goal', label: '광고 목적', type: 'text', placeholder: '예: 신규 업데이트 런칭 트레일러' },
      { key: 'facts', label: '확인된 제품 사실', type: 'textarea', rows: 4, placeholder: '화면에 넣어도 되는 사실만 기록합니다.' },
      { key: 'audience', label: '타깃', type: 'text' },
      { key: 'copy', label: '필수 문구', type: 'textarea', rows: 3, placeholder: '정확히 노출해야 하는 문구' },
      { key: 'seconds', label: '목표 길이(초)', type: 'number', min: 1, max: 600 },
    ],
    executionStage: null,
  },
  {
    kind: 'moodboard',
    label: '무드보드',
    group: '기획',
    description: '레퍼런스를 모으고 색감·재질·조명·움직임 기준을 정합니다.',
    icon: Palette,
    inputs: [{ id: 'refs', label: '레퍼런스', type: 'Image', multiple: true }],
    outputs: [{ id: 'out', label: '스타일 기준', type: 'StyleGuide' }],
    contextIn: false,
    contextOut: true,
    fields: [
      { key: 'color', label: '색감', type: 'text', placeholder: '예: 어두운 청록 + 앰버 하이라이트' },
      { key: 'material', label: '재질', type: 'text' },
      { key: 'light', label: '조명', type: 'text' },
      { key: 'motion', label: '움직임', type: 'text' },
      { key: 'notes', label: '참고 메모', type: 'textarea', rows: 3 },
    ],
    executionStage: null,
  },
  {
    kind: 'storyboard',
    label: '스토리보드',
    group: '기획',
    description: '샷 순서·예상 길이·카피·전환을 정합니다. 하단 스토리보드 패널과 같은 샷을 사용합니다.',
    icon: Clapperboard,
    inputs: [
      { id: 'brief', label: '브리프', type: 'Brief' },
      { id: 'style', label: '스타일', type: 'StyleGuide' },
    ],
    outputs: [{ id: 'out', label: '샷 목록', type: 'ShotList' }],
    contextIn: false,
    contextOut: true,
    fields: [
      { key: 'totalSeconds', label: '총 길이(초)', type: 'number', min: 1, max: 600 },
      { key: 'tone', label: '톤 메모', type: 'textarea', rows: 3 },
    ],
    executionStage: null,
  },
  {
    kind: 'prompt',
    label: '프롬프트',
    group: '기획',
    description: '여러 생성 노드가 공유할 프롬프트를 작성하고 버전을 관리합니다.',
    icon: TextCursorInput,
    inputs: [
      { id: 'style', label: '스타일', type: 'StyleGuide' },
      { id: 'shot', label: '샷 의도', type: 'Text' },
    ],
    outputs: [{ id: 'out', label: '프롬프트', type: 'Text' }],
    contextIn: true,
    contextOut: false,
    fields: [
      { key: 'prompt', label: '프롬프트 원문', type: 'textarea', rows: 8 },
      { key: 'version', label: '버전 라벨', type: 'text', placeholder: 'v1' },
    ],
    executionStage: null,
  },
  {
    kind: 'image',
    label: '이미지 생성·수정',
    group: '생성',
    description: '키비주얼·제품 장면·첫/끝 프레임·부분 수정을 만듭니다.',
    icon: ImagePlus,
    inputs: [
      { id: 'prompt', label: '프롬프트', type: 'Text', multiple: true },
      { id: 'refs', label: '참조 이미지', type: 'Image', multiple: true },
      { id: 'mask', label: '마스크', type: 'Mask' },
    ],
    outputs: [{ id: 'out', label: '이미지 후보', type: 'Image', multiple: true }],
    contextIn: true,
    contextOut: false,
    fields: [
      { key: 'prompt', label: '프롬프트', type: 'textarea', rows: 7 },
      { key: 'tool', label: '실행 도구', type: 'select', options: TOOL_OPTIONS },
      { key: 'aspect', label: '화면비', type: 'select', options: [
        { value: '16:9', label: '16:9' },
        { value: '9:16', label: '9:16' },
        { value: '1:1', label: '1:1' },
        { value: '4:5', label: '4:5' },
      ] },
      { key: 'resolution', label: '해상도', type: 'select', options: [
        { value: '1024', label: '1024' },
        { value: '1344', label: '1344' },
        { value: '1536', label: '1536' },
      ] },
      { key: 'candidates', label: '후보 수', type: 'number', min: 1, max: 8 },
      { key: 'seed', label: 'Seed', type: 'text', placeholder: '자동' },
    ],
    executionStage: 3,
  },
  {
    kind: 'video',
    label: '영상 생성',
    group: '생성',
    description: '텍스트·시작/끝 이미지·레퍼런스로 영상을 만듭니다.',
    icon: Film,
    inputs: [
      { id: 'prompt', label: '프롬프트', type: 'Text', multiple: true },
      { id: 'first', label: '시작 프레임', type: 'Image' },
      { id: 'last', label: '끝 프레임', type: 'Image' },
      { id: 'refs', label: '참조 이미지·영상', type: 'Image', multiple: true },
    ],
    outputs: [{ id: 'out', label: '영상 후보', type: 'Video', multiple: true }],
    contextIn: true,
    contextOut: false,
    fields: [
      { key: 'prompt', label: '프롬프트', type: 'textarea', rows: 7 },
      { key: 'tool', label: '실행 도구', type: 'select', options: TOOL_OPTIONS },
      { key: 'profileId', label: '실행 계정 (Modal)', type: 'select', dynamic: 'profiles' },
      { key: 'seconds', label: '길이', type: 'select', options: [
        { value: '5', label: '5초' },
        { value: '10', label: '10초' },
        { value: '15', label: '15초' },
      ] },
      { key: 'aspect', label: '화면비', type: 'select', options: [
        { value: '16:9', label: '16:9' },
        { value: '9:16', label: '9:16' },
        { value: '1:1', label: '1:1' },
      ] },
      { key: 'resolution', label: '해상도', type: 'select', options: [
        { value: '1344x768', label: '1344 × 768' },
        { value: '1152x640', label: '1152 × 640' },
        { value: '896x512', label: '896 × 512' },
      ] },
      { key: 'candidates', label: '후보 수', type: 'number', min: 1, max: 8 },
      { key: 'seed', label: 'Seed', type: 'text', placeholder: '자동' },
    ],
    executionStage: 2,
  },
  {
    kind: 'design',
    label: '디자인 작업',
    group: '생성',
    description: '지원되는 Higgsfield 기능이나 등록한 디자인 도구로 그래픽을 만듭니다.',
    icon: Shapes,
    inputs: [
      { id: 'prompt', label: '작업 지시', type: 'Text' },
      { id: 'refs', label: '소재', type: 'Image', multiple: true },
    ],
    outputs: [
      { id: 'out', label: '디자인 결과', type: 'Image', multiple: true },
      { id: 'raw', label: '원본 결과', type: 'Json' },
    ],
    contextIn: true,
    contextOut: false,
    fields: [
      { key: 'prompt', label: '작업 지시', type: 'textarea', rows: 5 },
      { key: 'tool', label: '실행 도구', type: 'select', options: TOOL_OPTIONS },
      { key: 'format', label: '출력 형식', type: 'select', options: [
        { value: 'png', label: 'PNG' },
        { value: 'svg', label: 'SVG' },
        { value: 'psd', label: 'PSD (지원 시)' },
      ] },
    ],
    executionStage: 3,
  },
  {
    kind: 'comfy',
    label: 'Comfy 워크플로',
    group: '생성',
    description: 'Modal에 배포한 ComfyUI 워크플로를 등록하고 노출된 입력값을 실행합니다.',
    icon: Boxes,
    inputs: [
      { id: 'prompt', label: '프롬프트', type: 'Text', multiple: true },
      { id: 'image', label: '이미지', type: 'Image', multiple: true },
      { id: 'video', label: '영상', type: 'Video' },
      { id: 'mask', label: '마스크', type: 'Mask' },
    ],
    outputs: [
      { id: 'image', label: '이미지 결과', type: 'Image', multiple: true },
      { id: 'video', label: '영상 결과', type: 'Video', multiple: true },
      { id: 'audio', label: '오디오 결과', type: 'Audio', multiple: true },
    ],
    contextIn: true,
    contextOut: false,
    fields: [
      { key: 'workflow', label: '워크플로', type: 'select', dynamic: 'workflows' },
      { key: 'profileId', label: '실행 계정 (Modal)', type: 'select', dynamic: 'profiles' },
      { key: 'prompt', label: '프롬프트', type: 'textarea', rows: 5 },
      { key: 'script', label: '가사·발화 원문', type: 'textarea', rows: 4, placeholder: '음악·음성 워크플로가 요구할 때 사용합니다.' },
      { key: 'seconds', label: '길이', type: 'select', options: [
        { value: '5', label: '5초' },
        { value: '10', label: '10초' },
        { value: '15', label: '15초' },
      ] },
      { key: 'resolution', label: '해상도', type: 'select', options: [
        { value: '1344x768', label: '1344 × 768' },
        { value: '1152x640', label: '1152 × 640' },
        { value: '896x512', label: '896 × 512' },
      ] },
      { key: 'seed', label: 'Seed', type: 'text', placeholder: '자동' },
      { key: 'steps', label: '스텝', type: 'number', min: 1, max: 100 },
    ],
    executionStage: 2,
  },
  {
    kind: 'motion',
    label: '모션그래픽',
    group: '가공',
    description: '로고·도형·제품 그래픽의 움직임과 전환을 설계합니다.',
    icon: Sparkles,
    inputs: [
      { id: 'source', label: '그래픽 소재', type: 'Image', multiple: true },
      { id: 'video', label: '영상', type: 'Video' },
      { id: 'prompt', label: '지시', type: 'Text' },
    ],
    outputs: [
      { id: 'spec', label: '모션 구성', type: 'MotionSpec' },
      { id: 'video', label: '그래픽 영상', type: 'Video' },
    ],
    contextIn: true,
    contextOut: false,
    fields: [
      { key: 'copy', label: '오버레이 문구 (선택)', type: 'text', placeholder: '정확히 표시할 문구' },
      { key: 'font', label: '글꼴 (선택)', type: 'text', placeholder: '예: Malgun Gothic' },
      { key: 'brief', label: '모션 지시', type: 'textarea', rows: 4 },
      { key: 'tool', label: '실행 도구', type: 'select', options: TOOL_OPTIONS },
      { key: 'seconds', label: '구성 길이(초)', type: 'number', min: 1, max: 120 },
      { key: 'resolution', label: '해상도', type: 'select', options: [
        { value: '1920x1080', label: '1920 × 1080' },
        { value: '1344x768', label: '1344 × 768' },
        { value: '1080x1920', label: '1080 × 1920' },
      ] },
      { key: 'fps', label: '프레임레이트', type: 'select', options: [
        { value: '24', label: '24 fps' },
        { value: '30', label: '30 fps' },
        { value: '60', label: '60 fps' },
      ] },
    ],
    executionStage: 4,
  },
  {
    kind: 'typo',
    label: '키네틱 타이포',
    group: '가공',
    description: '정확한 문구와 글꼴, 등장·퇴장·강조 타이밍을 편집합니다.',
    icon: Type,
    inputs: [
      { id: 'video', label: '배경 영상', type: 'Video' },
      { id: 'image', label: '배경 이미지', type: 'Image', multiple: true },
      { id: 'style', label: '스타일', type: 'StyleGuide' },
      { id: 'audio', label: '오디오(비트)', type: 'Audio' },
    ],
    outputs: [
      { id: 'spec', label: '타이포 구성', type: 'MotionSpec' },
      { id: 'video', label: '타이포 영상', type: 'Video' },
    ],
    contextIn: true,
    contextOut: false,
    fields: [
      { key: 'copy', label: '정확한 문구', type: 'textarea', rows: 3, placeholder: '렌더에 그대로 들어갈 문구' },
      { key: 'font', label: '글꼴', type: 'text', placeholder: '예: Pretendard Bold' },
      { key: 'seconds', label: '길이(초)', type: 'number', min: 1, max: 120 },
      { key: 'resolution', label: '해상도', type: 'select', options: [
        { value: '1920x1080', label: '1920 × 1080' },
        { value: '1344x768', label: '1344 × 768' },
        { value: '1080x1920', label: '1080 × 1920' },
      ] },
      { key: 'fps', label: '프레임레이트', type: 'select', options: [
        { value: '24', label: '24 fps' },
        { value: '30', label: '30 fps' },
        { value: '60', label: '60 fps' },
      ] },
      { key: 'entrance', label: '등장 방식', type: 'select', options: [
        { value: 'fade', label: '페이드' },
        { value: 'slide', label: '슬라이드' },
        { value: 'scale', label: '스케일' },
        { value: 'type', label: '타자' },
      ] },
      { key: 'timing', label: '타이밍 메모', type: 'text', placeholder: '예: 0.5s 등장, 비트에 강조' },
      { key: 'tool', label: '실행 도구', type: 'select', options: TOOL_OPTIONS },
    ],
    executionStage: 4,
  },
  {
    kind: 'audio',
    label: '음악·음성',
    group: '생성',
    description: '음악, 나레이션, 효과음을 만들거나 기존 오디오를 사용합니다.',
    icon: Music,
    inputs: [
      { id: 'prompt', label: '설명', type: 'Text' },
      { id: 'style', label: '스타일', type: 'StyleGuide' },
    ],
    outputs: [{ id: 'out', label: '오디오', type: 'Audio', multiple: true }],
    contextIn: true,
    contextOut: false,
    fields: [
      { key: 'kind', label: '종류', type: 'select', options: [
        { value: 'music', label: '음악' },
        { value: 'narration', label: '나레이션' },
        { value: 'sfx', label: '효과음' },
      ] },
      { key: 'profileId', label: '실행 계정 (Modal)', type: 'select', dynamic: 'profiles' },
      { key: 'prompt', label: '설명·스타일', type: 'textarea', rows: 5 },
      { key: 'script', label: '발화 원문', type: 'textarea', rows: 4 },
      { key: 'seconds', label: '길이(초)', type: 'number', min: 1, max: 300 },
    ],
    executionStage: 2,
  },
  {
    kind: 'select',
    label: '후보 선택',
    group: '조립',
    description: '여러 후보를 비교하고 선택을 고정합니다. 선택한 소재가 다음 노드로 전달됩니다.',
    icon: ListChecks,
    inputs: [
      { id: 'image', label: '이미지 후보', type: 'Image', multiple: true },
      { id: 'video', label: '영상 후보', type: 'Video', multiple: true },
      { id: 'audio', label: '오디오 후보', type: 'Audio', multiple: true },
    ],
    outputs: [],
    contextIn: false,
    contextOut: false,
    fields: [{ key: 'reason', label: '선택 이유', type: 'text' }],
    executionStage: null,
  },
  {
    kind: 'edit',
    label: '편집·합성',
    group: '조립',
    description: '컷 순서·길이·레이어·전환·오디오를 결합해 타임라인을 만듭니다.',
    icon: Scissors,
    inputs: [
      { id: 'video', label: '영상', type: 'Video', multiple: true },
      { id: 'audio', label: '오디오', type: 'Audio', multiple: true },
      { id: 'spec', label: '모션 구성', type: 'MotionSpec', multiple: true },
      { id: 'timeline', label: '타임라인', type: 'Timeline' },
    ],
    outputs: [
      { id: 'timeline', label: '타임라인', type: 'Timeline' },
      { id: 'preview', label: '프리뷰 영상', type: 'Video' },
    ],
    contextIn: true,
    contextOut: false,
    fields: [
      { key: 'notes', label: '구성 메모', type: 'textarea', rows: 4 },
      { key: 'shotSeconds', label: '기본 컷 길이(초)', type: 'number', min: 1, max: 30 },
      { key: 'resolution', label: '출력 해상도', type: 'select', options: [
        { value: '1920x1080', label: '1920 × 1080' },
        { value: '1344x768', label: '1344 × 768' },
        { value: '1080x1920', label: '1080 × 1920' },
      ] },
      { key: 'fps', label: '프레임레이트', type: 'select', options: [
        { value: '24', label: '24 fps' },
        { value: '30', label: '30 fps' },
        { value: '60', label: '60 fps' },
      ] },
      { key: 'autofit', label: '비트에 컷 자동 맞춤', type: 'checkbox' },
    ],
    executionStage: 2,
  },
  {
    kind: 'export',
    label: '검토·내보내기',
    group: '출력',
    description: '프리뷰를 확인하고 출력 형식과 최종 파일을 정합니다.',
    icon: Upload,
    inputs: [
      { id: 'timeline', label: '타임라인', type: 'Timeline' },
      { id: 'video', label: '영상', type: 'Video' },
      { id: 'project', label: '편집 프로젝트', type: 'ProjectFile' },
    ],
    outputs: [
      { id: 'file', label: '완성 영상', type: 'Video' },
      { id: 'project', label: '편집 프로젝트', type: 'ProjectFile' },
    ],
    contextIn: false,
    contextOut: false,
    fields: [
      { key: 'format', label: '출력 형식', type: 'select', options: [
        { value: 'mp4', label: 'MP4 (H.264)' },
        { value: 'prores', label: 'ProRes (지원 시)' },
        { value: 'project', label: '편집 프로젝트' },
      ] },
      { key: 'resolution', label: '해상도', type: 'select', options: [
        { value: '1920x1080', label: '1920 × 1080' },
        { value: '1344x768', label: '1344 × 768' },
        { value: '1080x1920', label: '1080 × 1920' },
      ] },
      { key: 'filename', label: '파일명', type: 'text', placeholder: 'final-cut' },
    ],
    executionStage: 4,
  },
  {
    kind: 'tool',
    label: '도구 실행',
    group: '도구',
    description: '전용 화면이 없는 MCP 도구를 구조화된 입력으로 실행합니다.',
    icon: Wrench,
    inputs: [
      { id: 'text', label: '텍스트', type: 'Text' },
      { id: 'image', label: '이미지', type: 'Image', multiple: true },
      { id: 'video', label: '영상', type: 'Video' },
      { id: 'audio', label: '오디오', type: 'Audio' },
    ],
    outputs: [
      { id: 'json', label: '원본 결과', type: 'Json' },
      { id: 'image', label: '이미지', type: 'Image' },
      { id: 'video', label: '영상', type: 'Video' },
    ],
    contextIn: true,
    contextOut: false,
    fields: [
      { key: 'input', label: '입력 JSON', type: 'textarea', rows: 6, placeholder: '{ "prompt": "..." }' },
    ],
    executionStage: 3,
  },
]

export const NODE_SPEC_BY_KIND: Record<NodeKind, NodeKindSpec> = NODE_SPECS.reduce(
  (map, spec) => {
    map[spec.kind] = spec
    return map
  },
  {} as Record<NodeKind, NodeKindSpec>,
)

export const NODE_GROUPS = ['소재', '기획', '생성', '가공', '조립', '출력', '도구']

export function nodeSpec(kind: NodeKind): NodeKindSpec {
  return NODE_SPEC_BY_KIND[kind]
}

// 실행 연결이 실제로 동작하는 노드 종류.
// 영상·Comfy = Modal H3, 음악·음성 = YuE2, 편집·합성 = 로컬 FFmpeg, 도구 실행 = MCP.
const RUNNABLE_KINDS = new Set<NodeKind>(['video', 'comfy', 'audio', 'edit', 'tool', 'typo', 'motion'])

export function isRunnable(kind: NodeKind): boolean {
  return RUNNABLE_KINDS.has(kind)
}

export function portById(ports: Port[], id: string): Port | undefined {
  return ports.find((port) => port.id === id)
}
