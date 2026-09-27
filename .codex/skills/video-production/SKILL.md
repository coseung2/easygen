---
name: video-production
description: Plan and produce Modal GUI videos — shortform, ads, motion graphics, kinetic typography, promo clips — by grounding the concept in the reference library, choosing a local/AE/external/Modal route per shot, getting approval before paid generation, and recording what made each result. Use for 영상·숏폼·광고·모션그래픽 제작 요청. Not for reference-only analysis or app UX review.
---

# Modal GUI 영상 제작

요청을 레퍼런스에 근거한 샷 계획으로 바꾸고, 샷마다 가장 싼 실행 경로로 만든 다음, 무엇으로 만들었는지 남긴다. 규칙의 원문은 `docs/constitution/`이다. 여기에는 제작 순서와 판단 기준만 둔다.

이 스킬은 Lab 트랙이다(제5조). 영상 자체와 함께, 나중에 앱 노드로 승격할 수 있도록 각 단계의 지시와 입출력을 남기는 것이 목적이다.

## 1. 먼저 읽을 것

- `docs/constitution/02-reference-library.md` §5 인용 규칙
- `docs/constitution/04-execution-routing.md` 전체
- `docs/constitution/05-two-tracks.md` §4 Lab 기록 규칙
- `docs/research/motion-references/README.md` 전체 목록과 태그표

`prompts/`에 해당 단계의 released 노드 프롬프트가 있으면 그 `system.md`를 따르고 버전을 기록한다. 없으면 이 스킬의 기준으로 진행한다.

요청에 맞는 카드만 `refs/`에서 열고, 조합할 규칙은 `synthesis/styles.md`, `synthesis/techniques.md`에서 필요한 표만 본다. 카드를 전부 읽지 않는다.

## 2. 요청 해석

요청에 없는 것은 합리적인 기본값으로 채우고 계획에 가정으로 적는다. 묻는 것은 결과를 크게 바꾸는 한두 가지뿐이다.

| 항목 | 요청에 없을 때 기본값 |
| --- | --- |
| 비율·길이 | 숏폼이면 9:16, 15–20초 |
| fps | 30 |
| 언어 | 한국어 문구 |
| 주제·브랜드 | 요청 문맥에서 추론. "너의 디자이너 면모"처럼 자기소개형이면 에이전트 자신의 디자인 판단(타이포, 색, 리듬)을 보여주는 작품으로 해석 |
| 음악 | 작품에 맞춘 새 음악(4단계, 승인 필요). 기존 곡을 기본값으로 쓰지 않는다 (제4조 §2 음악) |

## 3. 콘셉트

- 태그로 카드 2–4장을 고른다. 훅, 스타일, 리듬, 마무리를 서로 다른 카드에서 가져와도 된다.
- 한 작품을 통째로 따라 하지 않는다. 카드의 "가져올 것"에서 규칙을 뽑고, "피할 것"을 계획에 반영한다.
- 타 브랜드의 로고, 캐릭터, 문구를 그대로 쓰지 않는다. 구조와 기법만 가져온다.
- 방향이 둘 이상 가능하면 한 줄짜리 대안 1–2개를 함께 제시한다.

## 4. 샷 계획을 보여주고 멈춘다

제작 전에 아래를 한 번에 보여준다.

- 한 줄 콘셉트와 근거 카드 ID
- 형식 (비율, 길이, fps)
- 샷표: `시간 · 화면 · 역할 · 근거 카드 · 실행 단계(1–4) · 도구 · 예상 비용`
- 폰트, 팔레트, 음악 선택
- 가정한 것

3·4단계 샷이 하나라도 있으면 승인을 받기 전에 유료 실행을 하지 않는다. 모든 샷이 1·2단계면 계획을 보여준 뒤 바로 제작에 들어가도 된다. 단, 사용자가 계획만 원한다고 했으면 멈춘다.

## 5. 제작

- 작업 폴더: `F:\modal-gui\lab\<YYYY-MM-DD>-<짧은-이름>\`. 소재, 중간 결과, 최종본을 여기에 둔다. 재사용할 만한 스크립트는 저장소 `lab/<같은-이름>/`에 두고, 일회성 스크립트는 작업 폴더에 둔다.
- 1단계: 기존 도구를 먼저 쓴다. `tools/renderers/ffmpeg_renderer.py`, `tools/motion_graphics_pipeline.py`. FFmpeg 함정은 `docs/renderer-plugins.md`에 있다 (`fontsize` 표현식과 `blend all_expr` 금지).
- 2단계: AE 스크립트는 `tools/*_ae.jsx` 선례를 참고하되, 에피소드 전용 코드를 그대로 복사하지 않는다.
- 4단계: `tools/run_modal_h3_clip.py`, `tools/run_yue2_music.py`. 승인된 호출 수를 넘기지 않는다.
- 한글 폰트는 설치 여부를 먼저 확인한다. 없는 폰트를 전제로 계획하지 않는다.

## 6. 검수

내보내기 전에 직접 확인한다.

- ffprobe로 비율, 길이, fps, 오디오 스트림 확인
- 1fps 컨택트시트를 뽑아 모든 샷을 눈으로 확인: 글자 잘림, 폰트 대체, 오탈자, 판독성
- 루프 설계라면 마지막 프레임과 첫 프레임 비교
- 문구와 숫자가 계획과 일치하는지

## 7. 기록과 보고

작업 폴더에 `production.json`, `steps/`, 그리고 사용자 평가를 받으면 `verdict.md`를 남긴다.

`steps/<단계>.md`에는 각 판단 단계(brief, reference-pick, storyboard, routing, prompt-writing 등)마다 다음을 적는다. 이것이 노드 프롬프트의 초안이 된다.

- 이 단계에서 따른 지시: 역할, 판단 기준, 출력 형식을 시스템 프롬프트처럼 재사용 가능한 문장으로
- 실제 입력 (요청, 카드 ID, 앞 단계 출력)
- 실제 출력 (구조화된 형태)
- 사용자가 고친 부분이 있으면 무엇을 왜 고쳤는지

```json
{
  "request": "원 요청 문장",
  "refs": ["nepda-neop", "qaYO4A8Zf5E-seven-sunbeam"],
  "format": { "aspect": "9:16", "seconds": 20, "fps": 30 },
  "shots": [
    { "t": "0-2.5", "stage": 1, "tool": "local-ffmpeg", "pipeline": null, "cost": 0 }
  ],
  "fonts": [], "music": "",
  "paid": { "calls": 0, "actual": null, "estimated": null },
  "output": "final.mp4"
}
```

`pipeline`에는 `id@version`을 적는다. `pipelines/` 레지스트리가 아직 없으면 `null`로 두고 보고에 "버전 기록 없음"을 적는다 (제3조 §8).

보고에는 결과 파일 경로, 근거 카드, 샷별 실행 단계, 실제로 쓴 비용, 확인한 것과 확인하지 못한 것을 적는다.
