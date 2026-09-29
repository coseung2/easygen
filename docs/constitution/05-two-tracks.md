# 제5조 두 트랙과 승격

이 저장소에서는 두 가지 일을 함께 한다.

| 트랙 | 하는 일 | 결과물 |
| --- | --- | --- |
| **제작 실험 (Lab)** | 에이전트와 대화하며 영상을 실제로 만들어 보고, 어떤 절차·프롬프트·도구 조합이 좋은지 찾는다 | 영상, 그리고 검증된 절차와 프롬프트 |
| **앱 개발 (App)** | 검증된 절차를 사용자가 캔버스에서 노드를 클릭해 돌릴 수 있게 만든다 | Modal GUI 앱 |

둘은 한 방향으로 이어진다. **Lab에서 찾고, 검증하고, 승격한 것만 App에 들어간다.** App에서 새 제작 방식을 먼저 발명하지 않는다.

```text
Lab 실험 (여러 번)
  ↓ 좋은 결과가 반복됨
후보 추출: 절차 → 파이프라인 후보, 단계별 지시 → 노드 프롬프트 후보
  ↓ 출시 판정 (제3조 §6, 이 조 §5)
released 파이프라인·노드 프롬프트
  ↓
App 노드가 id@version으로 참조해 실행
```

## 1. 요청을 어느 트랙으로 볼 것인가

| 요청 예 | 트랙 |
| --- | --- |
| "숏폼 만들어줘", "이 광고 스타일로 영상 뽑아봐" | Lab |
| "이 레퍼런스 분석해" | Lab (레퍼런스 관리, 제2조) |
| "스토리보드 노드가 샷 목록을 만들게 해줘", "캔버스 버그 고쳐줘" | App |
| "Lab에서 쓴 방식을 노드로 만들어줘" | 승격 (§5) |

애매하면 결과물이 영상이면 Lab, 앱 코드면 App이다. 한 요청에 둘이 섞이면 Lab을 먼저 끝내고 승격한다.

## 2. 파일 경계

| 트랙 | 저장소 | 로컬 데이터 루트 (`$MODAL_GUI_DATA_ROOT`) |
| --- | --- | --- |
| Lab | `lab/` 실험 스크립트 (작은 코드만) | `$MODAL_GUI_DATA_ROOT/lab/<YYYY-MM-DD>-<이름>/` 소재·중간 결과·최종 영상·실행 기록 |
| App | `src/`, `src-tauri/`, `worker/`, `modal/`, `tools/renderers/` | 앱 데이터 폴더, `studio/`, `exports/` |
| 공유 (승격된 것) | `pipelines/`, `prompts/`, `docs/` | `$MODAL_GUI_DATA_ROOT/pipelines/` 출시 판정 샘플 |

- Lab 스크립트는 App 코드를 import해서 써도 된다. App 코드는 `lab/`을 import하지 않는다.
- Lab 실험은 App의 DB나 프로젝트 파일을 직접 고치지 않는다.
- 에피소드 하나에만 쓰는 스크립트는 `lab/`에 둔다. 여러 실험에서 재사용되기 시작하면 승격을 검토한다.

## 3. 노드 프롬프트

App의 노드 중 LLM이 판단하는 노드(브리프, 무드보드, 스토리보드, 프롬프트 작성, 샷 경로 선택 등)는 **노드 프롬프트**로 동작한다. 노드 프롬프트는 시스템 프롬프트와 입출력 계약을 묶은 것이고, 파이프라인과 똑같이 버전을 관리한다.

### 식별자와 저장 위치

```text
<node-kind>@<MAJOR.MINOR>        예: storyboard@1.0   prompt-writer@2.1

prompts/<node-kind>/
├─ CHANGELOG.md
├─ evals/                       고정 입력과 합격 기준 (§4)
└─ <MAJOR.MINOR>/
   ├─ system.md                 시스템 프롬프트 본문
   └─ meta.json                 계약과 실행 조건
```

### meta.json 필수 항목

```json
{
  "id": "storyboard",
  "version": "1.0",
  "status": "released",
  "inputs": { "brief": "Brief", "style": "StyleGuide", "refs": "ReferenceCard[]" },
  "output": { "type": "ShotList", "schema": "shotlist.schema.json" },
  "model": { "provider": "chatgpt-oauth", "name": "...", "temperature": 0.4 },
  "reads": ["docs/research/motion-references/synthesis/techniques.md"],
  "files": { "system.md": "sha256:..." },
  "origin": "$MODAL_GUI_DATA_ROOT/lab/<experiment-id>",
  "released_at": "YYYY-MM-DD"
}
```

- `inputs`, `output`의 자료형은 앱의 포트 자료형(`src/studio/types.ts`의 `PORT_TYPES`)과 맞춘다. 새 자료형이 필요하면 앱 쪽 타입을 먼저 추가한다.
- 출력은 자유 문장이 아니라 스키마가 있는 구조로 받는다. 다음 노드가 사람 해석 없이 읽을 수 있어야 한다.
- `reads`에는 프롬프트가 실행 시 주입받는 문서를 적는다. 레퍼런스 카드나 종합 문서가 바뀌면 결과가 달라질 수 있으므로 버전 기록에 함께 남긴다.
- `origin`에는 이 프롬프트가 나온 Lab 실험 폴더를 적는다.

### 버전 규칙

제3조 §3을 그대로 따른다. 입출력 계약이 바뀌면 MAJOR, 문구·예시·모델·온도가 바뀌면 MINOR다. released 버전의 `system.md`는 고치지 않는다.

### 쓰는 법

- 시스템 프롬프트에는 역할, 판단 기준, 출력 형식, 금지 사항을 적는다. 헌법 조항을 요약해 넣지 말고 필요한 규칙만 넣는다. 예를 들어 경로 선택 노드에는 제4조 §2의 판단 순서가 들어간다.
- 자격 증명, 사용자 개인정보, 특정 프로젝트의 문구를 넣지 않는다. 프로젝트별 내용은 입력으로 받는다.
- 레퍼런스는 카드 ID로 입력받는다(제2조 §5). 타 브랜드 로고·캐릭터·문구 재현을 지시하지 않는다.

## 4. Lab에서 프롬프트를 남기는 법

Lab 실험은 승격할 재료를 남겨야 한다. 실험 폴더에 다음을 둔다.

- `production.json` 실행 기록 (video-production 스킬 §7)
- `steps/<단계>.md` 각 단계에서 에이전트가 따른 지시와 실제 입력·출력. 예: `steps/brief.md`, `steps/storyboard.md`, `steps/routing.md`
- `verdict.md` 사용자 평가. 무엇이 좋았고 무엇이 아쉬웠는지 한두 줄

`steps/`의 지시문이 노드 프롬프트 초안이 된다. 좋은 결과가 나온 실험의 입력은 `prompts/<node-kind>/evals/`의 고정 입력 후보가 된다.

## 5. 승격 절차

1. **후보 선정.** 같은 방식으로 좋은 평가(`verdict.md`)를 받은 Lab 실험이 2회 이상 있을 때 후보로 올린다. 한 번의 성공은 우연일 수 있다.
2. **추출.** 절차는 `pipelines/<id>/<ver>/`(제3조), 단계별 지시는 `prompts/<node-kind>/<ver>/`로 옮긴다. 상태는 `candidate`다.
3. **평가.** 노드 프롬프트는 `evals/`의 고정 입력 3개 이상으로 돌려 스키마 적합성과 합격 기준을 확인한다. 이전 released 버전이 있으면 같은 입력으로 비교한다. 파이프라인은 제3조 §6을 따른다.
4. **승인.** 사용자가 결과를 보고 승인하면 `released`로 올린다.
5. **연결.** App 노드가 `id@version`으로 참조하게 한다. 노드 설정에 버전을 저장하고, 새 버전이 나와도 기존 프로젝트는 자동으로 바꾸지 않는다.

## 6. 현재 미준수 사항 (2026-09-27 코드 기준)

- 캔버스 노드 16종 중 LLM이 판단해야 할 브리프·무드보드·스토리보드·프롬프트 노드는 실행할 수 없는 상태(`executionStage: null`)이고, 노드별 시스템 프롬프트가 없다. AI 채팅(`src-tauri/src/ai_chat.rs`)은 있지만 노드와 연결된 프롬프트는 없다.
- `lab/`, `prompts/`, `pipelines/`, `$MODAL_GUI_DATA_ROOT/lab/`가 아직 없다.
- 지금까지의 Lab 성격 스크립트가 `tools/`에 섞여 있다. 예: `tools/*_episode_ae.jsx`, `tools/assemble_*_episode.py`, `tools/create_*_plates.py`. 과거 실험 결과는 `$MODAL_GUI_DATA_ROOT/series/`, `$MODAL_GUI_DATA_ROOT/deliverables/`에 있다. 옮기지 않고 그대로 두며, 새 실험부터 이 조를 따른다. 기존 스크립트 정리는 사용자 확인 후 진행한다.

## 개정 이력

- 2026-09-27 제정.
