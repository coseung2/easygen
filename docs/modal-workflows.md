# 앱 없는 Modal 실행 안내

이 문서는 에이전트가 저장소를 받은 뒤 실제 코드를 선택하고 실행·복구·다운로드하기 위한 안내다. **앱과 After Effects는 필수가 아니다.** Node.js·Rust·Tauri, 로컬 ComfyUI·GPU, 별도 제작·레퍼런스 관리 프로젝트도 필요 없다.

**H3 이용자는 라이선스를 이미 확보했다.** 에이전트는 취득 여부나 증빙을 다시 묻지 않는다. 독립 런타임은 비공개 라이선스 패키지나 재확인 단계를 사용하지 않는다. 리소스 접근 실패를 라이선스 질문으로 바꾸지 않는다.

## 1. 로컬 준비와 인증

Python 3.12 가상환경을 만들고 활성화한다. 모든 명령은 저장소 루트에서 해당 가상환경의 Python으로 실행한다.

```sh
python -m pip install "modal==1.6.1"
python tools/modal_workflow.py --help
python -m modal profile current
python -m modal app list --json
python -m modal volume list
```

이미 인증돼 있으면 그대로 사용한다. 처음 인증만 사용자가 `python -m modal setup`에서 완료한다. 자동화 환경은 기존 `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`을 실행기의 비밀 환경 변수로 주입한다. 에이전트가 토큰 값을 읽어 출력하거나 요청 파일에 넣지 않는다.

여러 계정이면 `python -m modal profile list`로 이름을 확인하고 `python -m modal profile activate PROFILE`로 사용자가 지정한 계정을 선택한다. 환경 변수가 설정된 경우 SDK 인증이 프로필보다 우선할 수 있다. 명령 간 동일한 계정과 `MODAL_ENVIRONMENT`를 유지한다. [Modal 인증과 배포 조회](https://modal.com/docs/guide/trigger-deployed-functions)

기존 배포가 있으면 앱을 설치하거나 재배포하지 않고 4절로 진행한다. 없으면 2절을 따른다. 공개 GitHub 저장소는 유지보수자의 Modal 워크스페이스를 공유하는 서비스가 아니다.

## 2. 새 워크스페이스 준비

현재 앱은 유지보수자 개인용이다. 외부 사용자는 앱 계정이나 서버에 연결하지 않고 자신의 Modal 계정에 독립 워크플로우를 만든다. `modal/workflow_h3.py`, `workflow_image.py`, `workflow_music.py`가 공개 배포 경로다. 개인 앱의 `easygen_h3.py`, `easygen_image.py`, `yue2_music.py`, `easygen_team.py`는 배포하지 않는다.

### 이름과 계정 선택

기본 이름은 `my-workflow-h3`, `my-workflow-image`, `my-workflow-music`이다. 필요하면 준비 전에 이름을 정한다:

```powershell
$env:EASYGEN_WORKFLOW_PREFIX = 'my-studio'
```

macOS/Linux: `export EASYGEN_WORKFLOW_PREFIX=my-studio`. 1–40자의 영문 소문자·숫자·하이픈을 사용하고 영문으로 시작한다. 모델 준비·배포·요청 prepare 동안 같은 값을 유지한다. 다른 계정의 같은 이름은 다른 리소스다. 기존 워크플로우를 보존하려면 새 prefix를 사용한다. `state.json`에는 prepare 당시 배포·볼륨 이름이 저장된다.

### 에이전트가 수행할 명령

```sh
python tools/setup_modal.py h3
python tools/setup_modal.py h3 --apply
```

`--apply` 없는 명령은 로컬 계획만 출력한다. `--apply`는 현재 인증된 워크스페이스에서 다음을 순서대로 수행하며 오류 시 멈춘다:

1. Modal 접근 확인.
2. H3·이미지: 공개 이미지 빌드 및 CPU ComfyUI 노드 등록 검사. 모델·GPU 없이 검사한다.
3. CPU 다운로드 작업: 자신의 모델 볼륨 생성, 고정 revision의 모델 다운로드, 크기·SHA-256 검증. YuE2도 생성 전에 내려받는다.
4. 해당 독립 워크플로우 배포. GPU 생성은 실행하지 않는다.

이미지는 `image`, 음악은 `music`을 지정한다. 한 종류만 필요하면 그 종류만 준비한다. CPU 작업이 각 대상의 빈 모델 볼륨을 만들어도 다른 종류의 모델을 다운로드하지는 않는다. CPU 실행·스토리지 비용은 생길 수 있다.

| 종류 | 모델 파일 | 다운로드 합계 | 기본 볼륨 |
| --- | --- | --- | --- |
| H3 | 7개 | 약 72.96 GiB | `my-workflow-h3-models` |
| 이미지 | 7개 | 약 44.82 GiB | `my-workflow-image-models` |
| 음악 | 19개 | 약 7.26 GiB | `my-workflow-music-models` |

실제 파일별 repository·revision·원격 파일명·볼륨 상대 경로·크기·해시는 `easygen_runtime/models.json`이 기준이다. H3에는 FL2VA·Ref2VA, text encoder, 두 VAE, LoRA, upscaler가 포함된다. 이미지 런타임은 Krea·Ideogram 두 모델 세트 모두 필요하다. 데이터 볼륨은 H3 입력·결과용 `my-workflow-h3-data`, 음악 결과용 `my-workflow-music-outputs`다.

`easygen_runtime/sources.json`은 ComfyUI v0.37.0 및 custom node Git commit을 고정한다. 공개 CUDA 이미지와 Python 3.12, PyTorch 2.10.0으로 직접 빌드한다. 운영자의 `im-*` ID와 비공개 `h3_service`가 필요 없다. 전체 전이 pip 의존성·OS 패키지까지 완전히 고정된 lockfile은 아니므로 빌드 검사 결과도 확인한다.

### 다운로드 인증과 재개

공개 파일은 토큰 없이 다운로드한다. 게이트·비공개 접근 때문에 HF 토큰이 필요한 경우 사용자 자신의 권한 있는 토큰을 `HF_TOKEN` 키가 있는 Modal Secret으로 준비한다. `EASYGEN_HF_SECRET`에 그 **Secret 이름**을 지정하면 CPU 다운로드 함수에만 전달한다. 토큰 값을 명령 인자·로그·Git에 적지 않는다. 이것은 접근 인증이며 H3 라이선스 재확인 절차가 아니다.

H3 모델 라이선스는 확보된 전제다. 다른 모델의 이용 조건은 각각 적용되며 유지보수자의 추가 권한이 자동 양도되는 것은 아니다.

끊긴 다운로드는 완료 파일과 `.download-cache`를 같은 볼륨에 보존한다. 이전 준비 작업이 종료됐는지 확인한 뒤 동일 명령을 명시적으로 재실행하면 정상 파일은 검증 후 건너뛴다. 같은 볼륨에 다운로드 작업을 중복 실행하지 않는다. 기존 파일의 해시가 다르면 덮어쓰지 않고 오류를 낸다. 이를 무시하거나 파일을 자동 삭제하지 않는다.

```sh
python -m modal run modal/bootstrap.py --target h3 --verify-only
```

`--verify-only`는 이미 있는 모델의 크기·해시만 검사한다. CPU 실행·볼륨 읽기 비용은 있을 수 있다. 모델을 Git이나 컨테이너 이미지에 넣지 않는다.

## 3. 개별 준비·배포·검증

일괄 도구 대신 필요한 단계만 실행할 수도 있다:

```sh
python -m modal run modal/check_environment.py
python -m modal run modal/bootstrap.py --target h3
python -m modal deploy modal/workflow_h3.py
python -m modal app info my-workflow-h3 --json
python -m modal app history my-workflow-h3 --json
```

이미지 배포는 `modal/workflow_image.py`, 음악은 `modal/workflow_music.py`를 사용한다. 별도 이미지 ID 입력·앱 설치·After Effects 설치는 필요 없다. 배포는 같은 이름의 기존 워크플로우를 갱신하므로 진행 중 작업을 먼저 확인한다.

CPU 노드 등록·파일 해시·배포 성공은 실제 GPU 추론 성공과 별개다. 마지막으로 승인된 최소 생성 1건을 4절대로 실행하고 결과를 디코드해 확인한다. GPU 검증을 하지 않았으면 하지 않았다고 보고한다. H3 `health`·`validate_graph`도 GPU 컨테이너를 시작할 수 있으므로 무료 검사로 무조건 호출하지 않는다.

## 4. 앱 없이 직접 실행

`tools/modal_workflow.py`가 Python SDK를 호출한다. 준비·제출·조회·회수를 별도 명령으로 나눠 에이전트 세션이 바뀌어도 이어서 처리할 수 있다.

### H3 요청 JSON

저장소 밖 `video-request.json`으로 저장:

```json
{
  "mode": "text",
  "prompt": "A small sailboat crossing a calm blue lake, slow camera pan.",
  "seconds": 2,
  "width": 1344,
  "height": 768,
  "seed": 42
}
```

| 모드 | 추가 입력 | 의미 |
| --- | --- | --- |
| `text` | 없음 | 텍스트 → 영상 |
| `image` | `image_path` | 첫 프레임 이미지 → 영상 |
| `reference` | `image_path` 또는 `video_path`, 둘 다 가능 | 참조 이미지·영상 → 영상 |

경로는 절대 경로나 **요청 JSON 파일 기준 상대 경로**다. 이미지 확장자는 PNG/JPG/JPEG/WEBP/BMP, 영상은 MP4/MOV/WEBM/MKV/M4V다. 참조 영상은 프롬프트에서 `<Video 1>`로 가리킬 수 있다. 카메라 전용 인자는 없으므로 지시를 프롬프트에 쓴다. `image` 모드는 같은 이미지를 마지막 프레임에 고정하지 않는다.

길이는 1–15초로 제한되고 24fps의 `17k+5` 프레임 수로 올림한다. 예를 들어 2초는 56프레임이므로 약 2.33초다. 가로·세로는 32 배수로 내림하며 256 미만이면 거절한다. 요청값과 실제 결과 길이·해상도를 구분한다. 원본 UI JSON을 그대로 `run_graph`에 보내지 않는다. 준비 단계가 API JSON으로 변환한다.

```sh
python tools/modal_workflow.py prepare video --request ../video-request.json --out ../video-run
```

이 단계는 로컬 작업만 하며 `graph.json`을 확인할 수 있다. 생성 범위가 승인됐으면:

```sh
python tools/modal_workflow.py submit ../video-run
python tools/modal_workflow.py status ../video-run
```

`submit`은 입력 업로드 후 원격 호출을 한 번 제출하고 ID를 저장한다. `status`는 한 번 조회하고 종료한다. 아직 `submitted`면 30–60초 뒤 같은 폴더를 다시 조회한다. 매번 새 작업을 제출하지 않는다.

### 이미지 요청 JSON

```json
{
  "model": "krea",
  "prompt": "A ceramic cup on a wooden table in soft morning light.",
  "width": 1024,
  "height": 1024,
  "seed": 1,
  "count": 1
}
```

Ideogram은 `"model": "ideogram"`으로 바꾸고 선택적으로 `"text": "HELLO"`를 추가한다. 일반 프롬프트는 코드가 구조화된 caption으로 확장한다. 이 API에는 참조 이미지·이미지 편집 인자가 없다. `count`는 1–4다. 런타임은 크기를 16 배수로 내림한다.

```sh
python tools/modal_workflow.py prepare image --request ../image-request.json --out ../image-run
python tools/modal_workflow.py submit ../image-run
python tools/modal_workflow.py status ../image-run
```

이미지는 회색 빈 결과를 일부 제외할 수 있어 실제 저장 개수가 요청보다 적을 수 있다. 전부 제외되면 오류다.

### YuE2 요청 JSON

```json
{
  "style": "Gentle acoustic folk, warm guitar and a calm vocal.",
  "lyrics": "[Verse]\nMorning light across the sea\nA quiet road ahead of me",
  "seed": 4301
}
```

```sh
python tools/modal_workflow.py prepare music --request ../music-request.json --out ../music-run
python tools/modal_workflow.py submit ../music-run
python tools/modal_workflow.py status ../music-run
```

YuE2는 `style`, `lyrics`, `seed`만 받는다. 길이 지정 인자는 없고, 무가사 입력만으로 보컬 없는 음악을 보장하지 않는다. 워크플로우 JSON을 찾아 설치할 필요가 없다.

### 결과 회수·검증

`status`가 `completed`를 반환하면:

```sh
python tools/modal_workflow.py download ../video-run
# 이미지·음악은 해당 run 폴더를 지정한다.
```

| 파일 | 역할 |
| --- | --- |
| `request.json` | 입력 요청 |
| `graph.json` | H3 API 그래프. 영상에만 있음 |
| `state.json` | 종류·배포·호출 ID·상태·Git commit·참조 파일 해시 |
| `submit.lock` | 중복 제출 방지. 실패했다고 자동 삭제하지 않음 |
| `remote-result.json` | 원격 응답. 이미지에서는 base64 데이터 포함 |
| `final.mp4`, `preview.mp4` | H3 최종·업스케일 전 영상 |
| `image-N.png` 또는 `audio.flac` | 이미지·음악 결과 |
| `outputs.json` | 결과 크기·SHA-256 |

입력 프롬프트나 경로를 다른 사람에게 보내지 않는다. 이 파일들은 개인 실행 폴더에만 저장한다. `downloaded`는 다운로드·빈 파일 검사 완료이며 미디어 전체 디코드나 품질 검증 완료를 뜻하지 않는다.

영상·음악 검증에 FFmpeg가 있다면:

```sh
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height -of json ../video-run/final.mp4
ffmpeg -v error -i ../video-run/final.mp4 -f null -
ffmpeg -v error -i ../music-run/audio.flac -f null -
```

이미지는 기본 이미지 뷰어나 Pillow 등으로 열기·디코드를 확인한다. After Effects는 필요 없다. 결과를 회수한 뒤 승인 없이 원격 볼륨의 입력·출력을 일괄 삭제하지 않는다.

## 5. 중단·복구·오류

```sh
python tools/modal_workflow.py cancel ../video-run
```

취소는 같은 호출 ID에 요청한다. `cancel_requested`는 원격 정지·과금 종료 확인이 아니다. 상태나 컨테이너를 별도로 확인한다. 취소 후 새 생성이 필요하면 새 폴더를 사용하며 승인된 실행 범위를 넘지 않는다.

| 상황 | 에이전트가 할 일 |
| --- | --- |
| 연결 단절, 대기 timeout | `state.json`의 같은 호출 ID로 `status` 수행 |
| `submitting`이고 호출 ID 없음 | 제출 접수가 불확실할 수 있음. Modal 호출 이력에서 접수 확인. lock 제거·재제출 금지 |
| 두 에이전트가 같은 폴더 제출 | 하나만 `submit.lock`을 생성할 수 있음. 다른 쪽은 재제출하지 않음 |
| 호출 ID를 이력에서 확인함 | 작업을 대조한 뒤 `state.json`에 `call_id`와 `status: submitted`를 복구하고 조회 |
| app/function not found | 계정·환경·배포 이름 확인. 타인의 계정으로 바꾸지 않음 |
| image not found / 권한 오류 | 공개 registry·소스 네트워크 접근과 빌드 로그 확인. 개인 앱용 배포 파일을 잘못 선택했는지 확인 |
| 모델 파일·노드 누락 | 모델 경로와 기반 이미지·custom node 구성 확인 |
| 원격 FunctionTimeoutError | 종료된 실행 제한 오류. 일반 대기 timeout과 구분 |
| `get`에서 다른 오류 | 실패 또는 전송 오류일 수 있음. 메시지·원격 이력 확인 후 판단. 자동 재제출하지 않음 |
| prepare 이후 참조 파일 변경 | 입력 해시 불일치. 원격 접수 여부를 확인하고 변경된 입력으로 새 준비 |
| 로컬 폴더 유실·SDK 결과 보존 기간 경과 | 호출 기록과 H3/YuE2 볼륨 경로로 복구. 이미지 base64 응답은 이 코드가 별도 영구 볼륨에 저장하지 않으므로 조기에 회수 |

SDK 직접 호출은 [Modal Function lookup·spawn](https://modal.com/docs/guide/trigger-deployed-functions), 볼륨 회수는 [Volumes](https://modal.com/docs/guide/volumes)를 따른다. 계정·환경을 바꾸면 같은 이름도 다른 리소스이므로 작업 중 변경하지 않는다.

## 6. 검증 범위

```sh
python -m unittest tools.test_modal_workflow
python tools/check_workflow_snapshots.py
```

호출기 로컬 테스트와 H3 그래프 연결·메타데이터 정리는 GPU를 사용하지 않는다. 공개 소스만으로 새 컨테이너를 빌드하고 CPU에서 H3·이미지 필수 노드 14개 등록을 실제 확인했다. 새 계정 전체 모델 다운로드와 GPU 추론 검증은 이번 작업에서 수행하지 않았다. GPU 모델 파일은 Git에 포함하지 않으며 각자 자신의 볼륨에 준비한다. 새 계정의 GPU 추론 성공은 실제 생성으로 별도 검증한다.
