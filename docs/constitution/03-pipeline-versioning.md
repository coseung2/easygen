# 제3조 파이프라인 버전 관리

파이프라인은 Modal GUI가 실행하는 "입력 → 결과" 제작 절차 하나를 말한다. 예를 들면 H3 이미지→영상 ComfyUI 워크플로, YuE2 음악 생성, FFmpeg 키네틱 타이포 렌더, AE 에피소드 스크립트가 있다. 이 조는 파이프라인을 식별하고, 버전을 올리고, 출시하고, 폐기하는 규칙을 정한다.

핵심은 이것이다. **출시된 버전은 절대 고치지 않는다. 바꾸려면 새 버전을 만든다. 모든 결과는 자기를 만든 버전을 기억한다.**

## 1. 현재 상태 (2026-09-27 코드 기준)

- `modal/app.py`는 `kind` 값(`t2v`, `ref2v`, 그 외는 i2v)에 따라 `video_minimax_h3_*.json` 파일 이름을 코드 안에서 고른다. Modal 앱 이름은 `minimax-h3-latest-workflows`다.
- 워크플로 원본은 `F:\modal-gui\workflows\`(예: `Minimax H3 1M 15S FL2V - Fast ver3.0 - Modal L40S.json`), 배포본은 `F:\modal-gui\remote-workflows\`, API 변환본은 `F:\modal-gui\prepared\`에 있다.
- 컨테이너 이미지는 ID로 고정돼 있고, 모델은 Modal Volume `minimax-h3-models`에 있다.
- DB의 `workflow_definitions` 테이블에는 버전 칸이 없다. `studio_runs`와 `jobs`에도 어떤 파이프라인 버전으로 실행했는지 남지 않는다.

따라서 지금은 워크플로 파일을 덮어쓰면 과거 결과가 어떤 설정으로 만들어졌는지 알 수 없다. "latest"라는 앱 이름이 이 문제를 그대로 보여준다.

## 2. 식별자

```text
<파이프라인 ID>@<버전>
예: h3-i2v@3.0   h3-ref2v@3.1   yue2-music@1.0   ffmpeg-kinetic-typo@2.0
```

- 파이프라인 ID는 `<모델 또는 도구>-<작업>` 형태의 소문자 kebab-case다. 한 번 정하면 바꾸지 않는다.
- 버전은 `MAJOR.MINOR` 두 자리다.
- 이미 쓰고 있는 이름은 그대로 이어받는다. "Fast ver3.0"은 `3.0`으로 등록한다.

## 3. 언제 버전을 올리나

| 바뀐 것 | 올릴 자리 | 예 |
| --- | --- | --- |
| 입력·출력 계약 (필수 입력 추가·삭제, 출력 형식, 해상도·길이 범위) | MAJOR | First/Last 두 프레임 입력 추가, MP4 → ProRes |
| 같은 계약 안에서 결과가 달라지는 변경 (모델 가중치, 샘플러, 스텝, 노드 구성, GPU 종류, 컨테이너 이미지) | MINOR | 스텝 20 → 30, L40S → H100 |
| 결과가 바뀌지 않는 변경 (주석, 매니페스트 설명 문구) | 올리지 않음 | 단, 워크플로·코드 파일이 바뀌면 무조건 MINOR 이상 |

판단이 애매하면 MINOR를 올린다. 버전을 아끼느라 기록을 잃는 쪽이 더 비싸다.

## 4. 저장 구조

```text
저장소  pipelines/
├─ registry.json                  전체 파이프라인과 버전별 상태 목록
└─ <pipeline-id>/
   ├─ CHANGELOG.md                버전마다 무엇이 왜 바뀌었는지
   └─ <MAJOR.MINOR>/
      ├─ manifest.json            계약과 고정값 (아래)
      ├─ workflow.ui.json         ComfyUI 원본 (해당 시)
      ├─ workflow.api.json        API 변환본 (해당 시)
      └─ ...                      렌더 스크립트 등 이 버전이 실행하는 파일

F 드라이브  F:\modal-gui\pipelines\<pipeline-id>\<MAJOR.MINOR>\
├─ golden-inputs\                 출시 판정용 고정 입력
└─ release-check\                 판정 때 만든 결과, 비용·시간 기록
```

정의 파일은 작은 텍스트라 git으로 관리한다. 워크플로 JSON은 파일당 약 40–70KB다. 무거운 샘플과 결과만 F 드라이브에 둔다.

### manifest.json 필수 항목

```json
{
  "id": "h3-i2v",
  "version": "3.0",
  "status": "released",
  "kind": "video",
  "engine": "modal-comfyui",
  "summary": "이미지 1장 + 프롬프트 → 최대 15초 영상",
  "inputs": { "image": "required", "prompt": "required", "seconds": "1-15", "seed": "optional" },
  "outputs": { "video": "mp4" },
  "runtime": {
    "modal_app": "h3-i2v-v3",
    "gpu": "L40S",
    "container_image": "im-...",
    "model_volume": "minimax-h3-models",
    "model_files": [{ "name": "...", "sha256": "..." }]
  },
  "files": { "workflow.api.json": "sha256:..." },
  "released_at": "YYYY-MM-DD",
  "supersedes": "2.x",
  "notes": ""
}
```

`files`에는 이 버전 폴더에 있는 모든 실행 파일의 해시를 적는다. 앱은 실행 전에 해시를 확인하고, 일치하지 않으면 실행하지 않는다.

`engine` 값은 제4조 §1 표에 있는 것만 쓴다. 새 엔진이 필요하면 제4조를 먼저 개정한다.

파이프라인 안에 LLM 판단 단계가 있으면 매니페스트에 `"prompts": { "<단계>": "<node-kind>@<version>" }`로 노드 프롬프트 버전을 적는다(제5조 §3). 참조한 노드 프롬프트 버전이 바뀌면 파이프라인도 MINOR를 올린다.

## 5. 상태와 수명

```text
draft → candidate → released → deprecated → retired
```

| 상태 | 의미 | 앱에서 |
| --- | --- | --- |
| draft | 만드는 중. 파일이 자주 바뀐다 | 개발자 설정에서만 보인다 |
| candidate | 파일 고정, 출시 판정 중 | "시험" 표시와 함께 선택 가능 |
| released | 판정 통과. 이때부터 파일 변경 금지 | 기본 선택지 |
| deprecated | 새 버전으로 대체됨 | 새 작업에서 선택할 수 없고, 기존 프로젝트 재실행만 가능 |
| retired | 더 이상 실행하지 않음 | 이력 조회만 가능. 정의 파일은 지우지 않는다 |

- 한 파이프라인 ID에서 released는 MAJOR마다 최대 하나만 기본값으로 둔다.
- candidate 단계에서 파일을 바꾸면 draft로 돌아간다.
- retired가 되어도 `pipelines/`의 정의 파일은 남긴다. 과거 결과를 설명하는 근거이기 때문이다.

## 6. 출시 판정

candidate를 released로 올리려면 아래를 모두 충족해야 한다.

1. `golden-inputs\`의 고정 입력으로 실제 Modal에서 실행해 결과를 `release-check\`에 남긴다. 목(mock)이나 로컬 시뮬레이션은 인정하지 않는다.
2. 직전 released 버전과 같은 입력의 결과를 나란히 비교한다.
3. 실행 시간, GPU 종류, 비용을 기록한다. 실제 청구액과 추정치를 구분한다.
4. `CHANGELOG.md`에 바뀐 점, 이유, 비교 결과를 적는다.
5. 사용자가 승인한다.

판정 결과가 이전보다 나쁘면 출시하지 않는다. 이전 버전을 기본값으로 유지한다.

## 7. 실행 기록과 되돌리기

- 모든 실행은 `pipeline_id`, `pipeline_version`, `manifest` 해시를 `jobs`와 `studio_runs`에 남긴다. 결과 폴더의 `metadata.json`에도 같은 값을 쓴다.
- 프로젝트는 노드마다 사용할 파이프라인 버전을 고정해서 저장한다. 새 버전이 출시돼도 기존 프로젝트는 자동으로 바뀌지 않는다. 업그레이드는 사용자가 노드별로 선택한다.
- Modal 배포 이름에는 MAJOR를 넣는다(`h3-i2v-v3`). `latest` 같은 움직이는 이름은 쓰지 않는다. MINOR까지 공존해야 하면 `h3-i2v-v3-1`처럼 붙인다.
- 되돌리기는 기본값을 직전 released 버전으로 바꾸는 것으로 한다. 파일을 되돌리거나 덮어쓰지 않는다.
- 원격 배포를 지우거나 retired로 바꾸기 전에는 그 버전을 쓰는 프로젝트가 있는지 확인하고 사용자에게 알린다.

## 8. 이관 계획 (미실행)

지금 흩어져 있는 워크플로를 이 규칙으로 옮기는 순서다. 코드 변경이 필요해서 이번 제정에서는 실행하지 않았다.

1. `F:\modal-gui\workflows`, `remote-workflows`, `prepared`의 파일을 대조해 `h3-i2v@3.0`, `h3-ref2v@3.0`, `h3-t2v@3.0`, `h3-fl2v@3.0`을 정한다. 어느 파일이 실제 배포본인지 해시로 확인한다.
2. `pipelines/`에 매니페스트와 워크플로를 넣고 `registry.json`을 만든다. 원래 F 드라이브 파일은 옮기지 않고 그대로 둔다.
3. `workflow_definitions`에 `version`, `status`, `manifest_hash`를 추가하고, `jobs`와 `studio_runs`에 `pipeline_id`, `pipeline_version`을 추가한다.
4. `modal/app.py`가 파일 이름 대신 `pipeline_id@version`을 받아 해당 매니페스트를 읽게 바꾼다. Modal 앱 이름을 `minimax-h3-latest-workflows`에서 버전이 들어간 이름으로 바꾼다.
5. YuE2, FFmpeg 렌더러, AE 스크립트를 같은 방식으로 등록한다. AE 스크립트(`tools/*_episode_ae.jsx`)는 에피소드 전용과 재사용 파이프라인을 먼저 구분한다.

## 개정 이력

- 2026-09-27 제정.
