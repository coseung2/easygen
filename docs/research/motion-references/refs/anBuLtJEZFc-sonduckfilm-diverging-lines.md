# Diverging Line 모션 — SonduckFilm

| 항목 | 값 |
| --- | --- |
| 출처 | [YouTube](https://www.youtube.com/watch?v=anBuLtJEZFc) · SonduckFilm · 2026-09-23 |
| 길이·비율·fps | 1:20 · 9:16 (1080×1920) · 23.98fps |
| 성격 | 튜토리얼 쇼츠 (AE 라인 모션 기법 + 무료 프로젝트 배포) |
| AI 제작 여부 | 해당 없음 (인물 촬영 + AE 화면 녹화) |
| 태그 | `9x16` `diverging-lines` `trim-paths` `path-animation` `word-sync-captions` `ae-native-vector` `free-ae-project` |
| 분석 방법 | 메타데이터 · 2fps 프레임 160장 · 컨택트시트 4종 · 화면 캡션 판독 · 설명란·배포 페이지 대조 |
| 분석일 | 2026-09-28 |

## 한 줄 요약

펜으로 그린 곡선 하나를 여러 Shape 레이어에 복사해 붙이고, Trim Paths로 선이 그려지게 하고, Null 오브젝트를 기준으로 갈라지게 배치한다. 같은 프로젝트 파일을 설명란에서 무료로 받게 해 튜토리얼 자체가 배포 채널이 된다.

## 구간표

| 구간 | 화면 | 역할 |
| --- | --- | --- |
| 0:00–0:02 | 인물 클로즈업 + 캡션 "THIS IS" | 훅 |
| 0:01–0:04 | 검정 타이틀 카드 "Diverging Paths" + 흰·파랑 곡선과 원형 노드, Ae 아이콘, TWILIGHT / GLOW / SERENITY 라벨 | 결과 예고 |
| 0:04–0:06 | 인물 + 캡션 "GRAPHICS / IN AFTER" | 주제 선언 |
| 0:06–0:12 | AE 인터페이스 + 캡션 "YOU CAN GET / FOR FREE" | 무료 프로젝트 안내 |
| 0:12–1:05경 | AE 화면 녹화 본편. 펜으로 곡선 Path 그리기 → Shape Layer 1(Stroke·Fill·Trim Paths) → 새 컴포지션·뷰어 클릭 → Path 복사/붙여넣기("PASTE IT / YOUR PATH") → Null Object 추가·배치("THE NULL") → 원형 요소를 경로에 정렬("CIRCLE / ALIGNED / POSITIONED") → Trim Paths End 키프레임 | 기법 본편 |
| 1:05경–1:12경 | 결과 포스터 "Diverging Paths" 재등장 | 결과 정리 |
| 1:12경–1:20 | MGPP / MotionDuck 패널 확대, "DRAG & DROP PRESETS", "FREE TEMPLATES GO TO: sonduckfilm.com/100" | 배포·판매 유도 |

계층 패널에서 확인된 구조: Shape Layer 1~3 + Background. Shape Layer 1은 Path 1 · Stroke 1 · Fill 1 · Trim Paths 1(Start 0.0% / End 0.0%, End에 키프레임)로 구성되어 있다. 캡션은 내레이션 단어 단위로 교체되고, 화면 하단 1/3에 흰 굵은 글자로 뜬다.

## 가져올 것

- 경로 복사 → 붙여넣기: 곡선 Path 하나를 여러 Shape 레이어가 공유하면 수정이 한 곳에서 끝난다.
- Trim Paths End 0% → 100%로 선이 그려지는 등장.
- Null 오브젝트를 분기 기준점으로 두고 회전·이동을 한 노드에서 제어.
- 검정 바탕 + 흰 선 + 강조색 한 색(파랑)의 색 체계. 색만 바꿔 브랜드에 맞출 수 있다.
- 실선·점선·원형 노드의 대비로 만드는 "경로·네트워크" 인상.
- 단어 동기화 캡션: 내레이션 단어 단위로 교체되며 하단을 차지해도 AE UI 판독을 방해하지 않는다.
- 튜토리얼 = 배포물: 기법을 보여주는 영상과 같은 파일을 함께 주는 형식. 우리 Lab 기록의 `steps/`·`production.json`과 같은 역할을 영상 밖에서 한다.

## 피할 것

- 마지막 10여 초는 템플릿 프로모가 결과 화면을 대체한다. 결과를 길게 보여주는 구간이 짧다.
- 화면 캡션을 단어 단위로 끊으면 문장이 조각나 보인다. 우리 자막을 만들 때는 호흡 단위로 묶는다.
- 소형 UI 텍스트(패널명·수치)는 모바일에서 판독이 어렵다. 기법은 수치가 아니라 형태 변화로 보여준다.

## 확인 못 한 것

- YouTube 자동 자막 확보 실패(HTTP 429, timedtext). 캡션 문구는 프레임 판독으로만 얻어 일부 구간이 빠졌다.
- 프레임 단위 타임코드, 키프레임 수치, 커브 값, 사용 폰트.
- 무료 프로젝트(`https://www.sonduckfilm.com/download/diverging-line-ae-project/`)의 파일 구성과 라이선스. 다운로드에 SonduckFilm 계정 로그인이 필요해 받지 않았다.
- 조회수·좋아요는 분석일(2026-09-28) 값: 8,473 / 325.

## 증거 위치

- 컨택트시트: [assets/anBuLtJEZFc-sonduckfilm-diverging-lines.sheet.jpg](../assets/anBuLtJEZFc-sonduckfilm-diverging-lines.sheet.jpg)
- 원본: `F:\modal-gui\references\anBuLtJEZFc-sonduckfilm-diverging-lines\` — `anBuLtJEZFc.mp4`(1080×1920 H.264) · `anBuLtJEZFc.info.json` · `frames\` 2fps 160장 · `anBuLtJEZFc.metadata.json` · 배포 페이지 HTML 2개
- 채널 카탈로그: [sonduckfilm-shorts.md](sonduckfilm-shorts.md)
