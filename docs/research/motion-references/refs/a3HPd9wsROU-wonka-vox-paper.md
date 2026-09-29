# Vox 스타일 모션 그래픽 — 원카AI Wonka

| 항목 | 값 |
| --- | --- |
| 출처 | [YouTube](https://www.youtube.com/watch?v=a3HPd9wsROU) · 원카AI Wonka · 2026-09-25 |
| 길이 | 19:16 |
| 성격 | 튜토리얼 (이미지 생성 + Python 애니메이션) |
| AI 제작 여부 | 확인됨 (Higgsfield 이미지 생성, Python 합성) |
| 태그 | `pipeline-image-code` `paper-cutout` `diorama-2.5d` `map-infographic` `pose-loop` |
| 분석 방법 | 메타데이터 · 한국어 자동자막 · 컨택트시트 |
| 분석일 | 2026-09-27 |

## 한 줄 요약

영상 모델 없이 분리 생성한 이미지(배경·인물·포즈)를 코드로 배치·변형해 종이 콜라주·디오라마 모션을 만든다.

## 구간표

| 구간 | 내용 |
| --- | --- |
| [07:30–10:08](https://www.youtube.com/watch?v=a3HPd9wsROU&t=450s) | 카약 5포즈 생성·순환, 첫 캐릭터를 참조로 사용 |
| [10:55–12:57](https://www.youtube.com/watch?v=a3HPd9wsROU&t=655s) | Remotion이 아닌 이미지 + Python 방식임을 명시 |
| [13:21–14:10](https://www.youtube.com/watch?v=a3HPd9wsROU&t=801s) | 산·바위·케이블카 분리, 거리별 흐림·이동량 |
| [15:26–17:08](https://www.youtube.com/watch?v=a3HPd9wsROU&t=926s) | 지도·경로·배·구름, 투명 소재 교체 |
| [18:05–18:35](https://www.youtube.com/watch?v=a3HPd9wsROU&t=1085s) | 나레이션·배경음악 별도 제작 후 합성 |

## 가져올 것

- 평면 소재를 층으로 쌓아 깊이를 만드는 패럴랙스.
- 포즈 수·포즈 유지 시간·출력 fps를 별개로 관리.

## 피할 것

- 이 영상을 Remotion 튜토리얼로 분류하는 것. 특정 모델의 투명도 지원을 일반화하는 것.

## 확인 못 한 것

- 실제 Python 코드 구조.

## 증거 위치

상세: [AI 모션그래픽 트렌드 분석 §2-B](../../2026-09-27-ai-motion-graphics-trends.md)
