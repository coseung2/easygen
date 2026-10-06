# 앱 없는 Modal 실행 안내

이 문서는 에이전트가 저장소를 받은 뒤 실제 코드를 선택하고 실행·복구·다운로드하기 위한 안내다. **앱과 After Effects는 필수가 아니다.** Node.js·Rust·Tauri, 로컬 ComfyUI·GPU, 별도 제작·레퍼런스 관리 프로젝트도 필요 없다.

**H3 이용자는 라이선스를 이미 확보했다.** 에이전트는 취득 여부나 증빙을 다시 묻지 않는다. 호출기는 기존 런타임의 attestation 문자열을 자동 전달한다. 리소스 접근 실패를 라이선스 질문으로 바꾸지 않는다.

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

### 준비 여부를 먼저 분류

| 대상 | 배포 코드 | 준비 조건 |
| --- | --- | --- |
| H3 | `modal/easygen_h3.py` | 접근 가능한 기반 이미지, ComfyUI·custom nodes, H3 모델 7개, 데이터·모델 볼륨 |
| Krea·Ideogram | `modal/easygen_image.py` | 접근 가능한 기반 이미지, ComfyUI, 이미지 모델 7개, 모델 볼륨 |
| YuE2 | `modal/yue2_music.py` | 파일 내 이미지 빌드, YuE2 모델 접근, 캐시·출력 볼륨 |

H3와 이미지는 `modal.Image.from_id("im-AYSPVNRooQYXy8IgQlPWOJ")`를 사용한다. **이 ID는 다른 워크스페이스에서 접근 가능하다고 보장하지 않는다.** 기반 이미지 전체 빌드 정의와 H3의 `/root/h3_service` 패키지는 이 저장소에 포함돼 있지 않다. 배포 코드가 덧붙이는 custom node 설치 명령만으로 기반 이미지가 완전히 재현되지는 않는다.

따라서 새 계정에서 준비되지 않았다면:
1. 사용 가능한 동등 이미지·사전 구축 배포가 있는지 확인한다.
2. 없으면 기반 이미지 빌드 정의·패키지 또는 접근 가능한 대체 배포가 필요하다는 사실과 빠진 항목을 보고한다.
3. H3 라이선스를 다시 묻거나, 앱·After Effects 설치로 해결하려 하지 않는다.
4. 임의의 이미지·모델로 바꾸고 기존 워크플로우와 같다고 보고하지 않는다. 현재 공개 코드만으로 새 H3 계정의 완전한 부트스트랩이 완료됐다고 주장하지 않는다.

H3·이미지의 ComfyUI 추가 단계는 v0.37.0 / `73c9bad4d21e7addbe1d13bc92eee0f1431b017d`를 확인한다. 일부 custom node는 고정 commit 없이 clone하므로 모든 의존성이 완전히 고정된 구성은 아니다.

### 볼륨과 모델

`python -m modal volume list`에서 없는 볼륨만 만든다. 아래는 각 대상에 필요한 이름이다.

```sh
# H3만 사용할 때
python -m modal volume create minimax-h3-models
python -m modal volume create minimax-h3-comfyui-data
# 이미지만 사용할 때
python -m modal volume create local-image-gen-models-v1
# 음악만 사용할 때
python -m modal volume create yue2-models
python -m modal volume create yue2-outputs
```

빈 볼륨 생성은 모델 준비 완료가 아니다. 기존 볼륨을 지우거나 덮어쓰지 않는다.

H3의 `minimax-h3-models`에 필요한 상대 경로:

```text
diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors
diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors
text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors
vae/minimax_h3_video_vae_int8_convrot.safetensors
vae/minimax_h3_audio_vae_fp32.safetensors
latent_upscale_models/minimax_h3_latent_upscaler_3d_conv_v1_fp32.pth
loras/lightx2v_hybrid-4to8step-full-fusion_Turbo_pruned.safetensors
```

볼륨의 LoRA 경로에는 `H3/`가 없으며, 런타임이 ComfyUI의 `models/loras/H3/`로 연결한다. 정확한 연결은 `modal/easygen_h3.py:MODEL_LINKS`가 기준이다. 모델은 저장소에 포함돼 있지 않다.

H3 JSON의 설명에는 다음 출처가 기록돼 있다. 이는 출처 안내이며 다운로드 availability·revision·해시 검증 완료를 뜻하지 않는다. 에이전트는 실제 요청 파일명을 사용하고 다운로드 기록에 revision·SHA-256을 남긴다. H3 라이선스 확인 질문을 추가하지 않는다.

| 파일 | JSON에 기록된 출처 |
| --- | --- |
| FL2VA·Ref2VA, Qwen3VL text encoder, audio VAE | `Comfy-Org/MiniMax-H3`의 해당 모델 하위 폴더 |
| INT8 video VAE | `Kijai/MiniMax-H3-experimental`의 같은 파일명 |
| Turbo LoRA | `TenStrip/MinimaxH3-Turbo_Shenanigans`의 같은 파일명 |
| Latent upscaler | `LBH-123-AI/Minimax_h3_latent_Upscaler`의 `minimax_h3_latent_upscaler_3d_conv_v1/` |

권한 있는 로컬 파일을 준비한 뒤 개별 파일을 올리는 예:

```sh
python -m modal volume put minimax-h3-models /absolute/path/to/model.safetensors /diffusion_models/model.safetensors
python -m modal volume ls minimax-h3-models /diffusion_models
```

위 파일명은 형식 예시다. 실제 업로드에는 앞의 정확한 모델 파일명을 사용한다. `--force`로 기존 가중치를 임의 덮어쓰지 않는다. 입력·결과는 `minimax-h3-comfyui-data`의 `input/`, `output/` 아래에 저장된다.

이미지의 `local-image-gen-models-v1` 파일은 다음과 같다. 런타임은 모델 하나만 호출해도 아래 전체 목록을 검사한다.

```text
diffusion_models/krea2_turbo_fp8_scaled.safetensors
text_encoders/qwen3vl_4b_fp8_scaled.safetensors
vae/qwen_image_vae.safetensors
diffusion_models/ideogram4_fp8_scaled.safetensors
diffusion_models/ideogram4_unconditional_fp8_scaled.safetensors
text_encoders/qwen3vl_8b_fp8_scaled.safetensors
split_files/vae/flux2-vae.safetensors
```

`modal/local_image_gen.py:MODEL_FILES`에 Hugging Face repository·파일 경로가 있다. `download_models`는 다운로드 전용 함수지만 파일의 기본 진입점은 평가 생성을 수행한다. 다운로드 목적으로 `modal run modal/local_image_gen.py`를 통째로 실행하지 않는다. 사용하려면 해당 함수만 명시한다:

```sh
python -m modal run modal/local_image_gen.py::download_models
```

CPU 다운로드·저장 비용도 생길 수 있으며, 이 명령이 H3 기반 이미지 접근 문제를 해결하지는 않는다.

YuE2는 `m-a-p/YuE2-3B`, `m-a-p/YuE2-Vae`를 사용한다. 첫 생성에서 `/models/huggingface`에 모델을 캐시하므로 첫 호출에 다운로드·기동 시간이 포함된다. H3 라이선스 전제는 다른 모델의 이용 조건을 바꾸지 않는다. YuE2 코드의 메타데이터에 적힌 추가 제작자 허가는 외부 이용자에게 자동 양도되는 권한이 아니다.

## 3. 필요한 배포만 생성 또는 갱신

준비 조건을 충족한 대상만 배포한다. 생성 중인 기존 앱을 무턱대고 재배포하지 않는다.

```sh
python -m modal app list --json
python -m modal deploy modal/easygen_h3.py
python -m modal deploy modal/easygen_image.py
python -m modal deploy modal/yue2_music.py
```

세 명령을 모두 실행할 필요는 없다. 원하는 종류의 명령만 고른다. 앱 화면·협업 서버는 배포하지 않는다. 배포 후 메타데이터와 이력을 확인한다.

```sh
python -m modal app info easygen-h3-v1 --json
python -m modal app history easygen-h3-v1 --json
```

배포 성공은 GPU 생성 성공을 뜻하지 않는다. H3의 `health`·`validate_graph`는 GPU 컨테이너를 시작하므로 무료 사전 검사로 무조건 호출하지 않는다. `run_graph` 자체가 생성 전에 그래프 검사를 수행한다. [Modal 배포 관리](https://modal.com/docs/cli/latest/app)

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
| image not found / 권한 오류 | 기반 이미지 접근·빌드 자산 부족. H3 라이선스 재질문이나 앱 설치로 대체하지 않음 |
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

호출기 로컬 테스트와 H3 그래프 연결·메타데이터 정리는 GPU를 사용하지 않는다. 이 안내 작성 과정에서 새 계정의 전체 이미지 재구축이나 새 유료 생성을 수행한 것은 아니다. GPU 모델 파일은 Git에 포함하지 않으며 기반 이미지 의존성의 공개 재현 제한은 2절을 따른다.
