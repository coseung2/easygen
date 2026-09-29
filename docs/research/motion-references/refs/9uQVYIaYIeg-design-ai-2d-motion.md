# 이런 2D 모션그래픽, 이제 AI로 직접 만드세요 — 디자인하는AI

| 항목 | 값 |
| --- | --- |
| 출처 | [YouTube](https://www.youtube.com/watch?v=9uQVYIaYIeg) · 디자인하는AI · 2026-09-25 |
| 길이 | 15:10 |
| 성격 | 튜토리얼 (AI 영상 생성) |
| AI 제작 여부 | 확인됨 (Newtake 캔버스, 화면상 MiniMax H3) |
| 태그 | `pipeline-video-gen` `prompt-spec` `reference-analysis` `text-trail` `kinetic-typo` `flat-character` |
| 분석 방법 | 메타데이터 · 한국어 자동자막 · 컨택트시트 |
| 분석일 | 2026-09-27 |

## 한 줄 요약

짧은 요청 뒤에 샷 길이·타이포·컬러·전환·카메라·사운드·금지 요소를 담은 상세 연출 지시서를 두고, 레퍼런스를 샷·모션으로 분석해 영상 모델에 넣는 흐름.

## 구간표

| 구간 | 내용 |
| --- | --- |
| [01:35–04:11](https://www.youtube.com/watch?v=9uQVYIaYIeg&t=95s) | 상세 연출 지시서 구성 |
| [04:15–05:54](https://www.youtube.com/watch?v=9uQVYIaYIeg&t=255s) | 텍스트 노드 → 영상 생성 노드 연결 |
| [06:16–10:09](https://www.youtube.com/watch?v=9uQVYIaYIeg&t=376s) | 레퍼런스 분석 → 프롬프트 재사용, 텍스트 트레일 |
| [10:17–12:28](https://www.youtube.com/watch?v=9uQVYIaYIeg&t=617s) | 캐릭터 참조를 기획·생성 단계 모두에 입력 |
| [12:29–14:40](https://www.youtube.com/watch?v=9uQVYIaYIeg&t=749s) | 제품 이미지 + 지시서, 25칸 스토리보드 |

## 가져올 것

- 참조 역할(스타일·정체성·제품·동작)을 분리하고 전달 경로를 명시한다. 기획 모델이 본 이미지가 영상 모델에 자동 전달되지 않는다.

## 피할 것

- 25칸 스토리보드를 필수 샷 수로 오해하거나 스토리보드 이미지를 타임라인으로 취급하는 것.

## 확인 못 한 것

- 생성 비용·성공률. 발표자 사례 기준이다.

## 증거 위치

상세: [AI 모션그래픽 트렌드 분석 §2-A](../../2026-09-27-ai-motion-graphics-trends.md) · 원자료는 로컬 데이터 루트의 `references/`에 보관한다.
