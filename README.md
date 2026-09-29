# Modal GUI · 영상 제작 파이프라인

영상 제작 실험에서 사용한 연출 지침, 프롬프트, ComfyUI 워크플로우, Python·After Effects 제작 도구를 모은 저장소입니다. Lab의 제작 절차를 버전별 파이프라인으로 정리하며, 별도의 데스크톱 앱에서도 활용합니다.

아래는 **에이전트가 클론한 저장소에서 제작 도구와 Modal API를 사용하는 안내**입니다. 데스크톱 앱 설치는 파이프라인 실행의 전제 조건이 아닙니다.

## 1. 클론과 로컬 도구

Windows / PowerShell 7 기준입니다. [Git](https://git-scm.com/downloads), [Python 3.12](https://www.python.org/downloads/windows/), [FFmpeg](https://ffmpeg.org/download.html)를 설치합니다. FFmpeg 다운로드 페이지의 Windows 빌드를 사용하고 `ffmpeg`와 `ffprobe`가 있는 폴더를 PATH에 추가합니다.

```powershell
git clone https://github.com/coseung2/modal-gui.git
cd modal-gui
py -3.12 -m venv .venv
# 활성화 없이 동일 인터프리터 지정
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install pillow "numpy<2.3" scipy modal
ffmpeg -version
ffprobe -version
```

인물 누끼 템플릿에만 다음 패키지를 추가합니다. 모델 가중치와 이용 조건은 별도 확인이 필요합니다.

```powershell
& .\.venv\Scripts\python.exe -m pip install "rembg[cpu]==2.0.67"
```

이는 공통 도구 설치이며 모든 과거 영상의 환경을 고정한 lockfile은 아닙니다. 개별 실험의 추가 의존성도 확인하고, 설치 버전은 `python -m pip freeze`로 로컬 실행 기록에 남깁니다.

## 2. 작업 폴더와 폰트

생성물은 클론 밖에 저장합니다. 환경 변수는 에이전트 시작 전에 설정하거나 실행 도구의 환경 설정으로 전달합니다.

```powershell
$env:MODAL_GUI_DATA_ROOT = Join-Path $env:LOCALAPPDATA 'modal-gui'
$env:MODAL_GUI_FONT_ROOT = Join-Path $env:MODAL_GUI_DATA_ROOT 'fonts'
$env:MODAL_GUI_TEMPLATE_PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path
New-Item -ItemType Directory -Force -Path $env:MODAL_GUI_DATA_ROOT, $env:MODAL_GUI_FONT_ROOT | Out-Null
```

`tools/lab_paths.py`를 사용하는 Lab 도구는 이 설정을 읽습니다. `pipelines/_shared/motionkit.py`의 템플릿은 번들·Windows 설치 폰트 폴더를 읽으므로 해당 폰트는 운영체제에 설치합니다. 모든 과거 Lab 스크립트가 공통 설정으로 이관된 것은 아닙니다.

- Black Han Sans는 [라이선스와 함께 번들](pipelines/_shared/fonts/)되어 있습니다.
- 템플릿은 Gmarket Sans Bold, Pretendard Black·SemiBold를 사용하며 없으면 일부 Windows 폰트로 대체합니다. **같은 화면을 재현하려면 원래 폰트가 필요합니다.**
- AE 제작은 [After Effects](https://www.adobe.com/products/aftereffects.html)와 사용 권한이 필요합니다. 제작 기록에는 AE 2021 / 18.0.1이 있으며 다른 버전의 동일 결과는 미검증입니다. JSX로 프로젝트를 만드는 단계와 `aerender`로 렌더하는 단계는 구분합니다.

## 3. Modal 가입과 API 인증

[Modal 가입](https://modal.com/signup) 후 사용할 Workspace를 선택합니다. 이 저장소의 원격 호출은 Modal **Python SDK**를 사용합니다. [공식 시작 안내](https://modal.com/docs/guide/getting-started)

### 개인 PC: 사용자가 한 번 인증

```powershell
& .\.venv\Scripts\python.exe -m modal setup
& .\.venv\Scripts\python.exe -m modal token info
```

브라우저 인증은 사용자가 완료합니다. 이후 같은 OS 사용자로 실행하는 에이전트는 저장된 CLI 인증을 사용합니다. 기존 인증이 있으면 재발급하지 않습니다.

### 에이전트·CI: API 토큰을 실행 환경에 주입

Modal Dashboard의 Workspace 토큰 설정에서 받은 **Token ID / Token Secret 쌍**을 에이전트 실행기의 비밀 환경 변수로 지정합니다.

| 변수 | 의미 |
| --- | --- |
| `MODAL_TOKEN_ID` | Modal API Token ID |
| `MODAL_TOKEN_SECRET` | 대응하는 Token Secret |
| `MODAL_ENVIRONMENT` | 사용할 Environment 이름. 아래 예시는 `main` |

사용자가 로컬에서 직접 설정한다면 PowerShell 7의 입력 프롬프트를 이용합니다. 실제 값은 명령문·채팅에 붙여넣지 않습니다.

```powershell
$env:MODAL_TOKEN_ID = Read-Host 'Modal Token ID'
$env:MODAL_TOKEN_SECRET = Read-Host 'Modal Token Secret' -MaskInput
$env:MODAL_ENVIRONMENT = 'main'
& .\.venv\Scripts\python.exe -m modal token info
```

토큰 환경 변수는 저장된 `.modal.toml` 인증보다 우선합니다. Workspace는 토큰에 연결되므로 연결 결과가 의도한 Workspace인지 확인합니다. `MODAL_PROFILE`만 바꿔도 주입된 토큰이 바뀌는 것은 아닙니다. `.env` 파일만 만들어서는 자동 로드되지 않으며 **CLI를 실행하는 프로세스**에 환경 변수를 전달해야 합니다. [인증 우선순위](https://modal.com/docs/guide/trigger-deployed-functions), [설정 API](https://modal.com/docs/sdk/py/latest/config)

공유 Workspace의 자동화에는 [Service User](https://modal.com/docs/guide/service-users)를 사용할 수 있습니다. 사용 가능한 플랜과 Environment 권한을 확인합니다. API 토큰을 웹 엔드포인트의 Proxy Token 또는 Hugging Face 토큰과 혼용하지 않습니다.

### 에이전트 연결 확인 — 생성 작업 없음

```powershell
& .\.venv\Scripts\python.exe -m modal --version
& .\.venv\Scripts\python.exe -m modal token info
& .\.venv\Scripts\python.exe -m modal app list --env main --json
& .\.venv\Scripts\python.exe -m modal volume list --env main --json
```

위 명령은 인증과 리소스 목록을 조회합니다. 토큰·계정 정보 출력은 공개 로그나 Git에 저장하지 않습니다. 인증 성공은 모델·워크플로우·배포 준비 완료를 뜻하지 않습니다.

## 4. 모델과 원격 실행 준비

| 경로 | 코드가 참조하는 원격 자원 | 새 Workspace에서 필요한 준비 |
| --- | --- | --- |
| H3 영상 | `minimax-h3-latest-workflows / LatestH3`, `minimax-h3-models`, `minimax-h3-comfyui-data` | ComfyUI·모델·워크플로우 준비 후 배포. **현재 기반 이미지 재현이 미완료** |
| H3 참조 영상 | `h3-refvideo-v1 / RefVideoH3`, 위 두 Volume | [버전별 정의](pipelines/h3-refvideo/1.0/manifest.json)와 참조 영상 입력. 동일한 이미지 의존성 존재 |
| YuE2 음악 | `yue2-music / generate_music`, `yue2-models`, `yue2-outputs` | 자신의 Environment에 Volume 생성, [배포 코드](modal/yue2_music.py) 준비. 최초 모델 다운로드 필요 |
| Qwen 이미지 실험 | `qwen-image-21-research / QwenImage21` | [실험 코드](modal/qwen_image21.py)의 모델 다운로드·배포 단계. H3 필수 의존성은 아님 |

H3의 `Image.from_id(...)`는 기존 Workspace 이미지에 의존하며, 컨테이너의 `/root/h3_service`도 이 저장소에서 빌드되지 않습니다. custom node 버전과 모델 해시도 완전히 고정되지 않았습니다. **가입·토큰 설정만으로 새 계정에서 기존 H3 영상을 재현할 수 있다고 주장하지 않습니다.** 리소스가 없으면 에이전트는 누락 항목을 보고합니다.

실제 코드가 참조하는 모델·도구:

- [Comfy-Org / MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3), [원 모델 카드](https://huggingface.co/MiniMaxAI/MiniMax-H3): FL2VA·Ref2VA INT8 convrot, Qwen3VL 32B 인코더, video/audio VAE. 정확한 파일명은 [모델 매핑](modal/app.py)에 있습니다. 그래프 다운로드 메타데이터와 실제 선택 파일명이 다를 수 있어 대조해야 합니다.
- [H3 Latent Upscaler](https://huggingface.co/LBH-123-AI/Minimax_h3_latent_Upscaler): worker가 지정한 upscaler 가중치.
- [YuE2-3B](https://huggingface.co/m-a-p/YuE2-3B), [YuE2-Vae](https://huggingface.co/m-a-p/YuE2-Vae): 음악 생성. 코드가 revision을 고정하지 않아 과거 모델과 동일한지는 미확인입니다.
- [Qwen-Image-2.1](https://huggingface.co/Comfy-Org/Qwen-Image-2.1): 실험 코드의 revision은 `9a44dbdb47cefd046be9c0a13476192f34c8db8e`입니다.
- [ComfyUI](https://github.com/Comfy-Org/ComfyUI), [VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite), [H3 Upscaler 노드](https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler), [H3 Optimizations](https://github.com/Zironic/H3-Optimizations), [Deno 노드](https://github.com/Deno2026/comfyui-deno-custom-nodes): 코드가 참조하는 custom node입니다. 링크만으로 버전 호환성이 보장되지는 않습니다.

가중치는 Git에 넣지 않습니다. 출처·revision·파일 해시·이용 조건을 확인해 준비합니다. 기존 제작자의 별도 이용 허가는 클론 사용자에게 자동 이전되지 않습니다.

## 5. 에이전트가 먼저 수행할 확인

아래는 생성 요청을 제출하지 않는 로컬 확인입니다.

```powershell
& .\.venv\Scripts\python.exe tools/motion_graphics_pipeline.py --help
& .\.venv\Scripts\python.exe tools/motion_graphics_pipeline.py plugins
& .\.venv\Scripts\python.exe tools/run_h3_job.py --help
& .\.venv\Scripts\python.exe pipelines/seal.py --check
```

에이전트에 다음 지시를 전달할 수 있습니다.

> README와 AGENTS.md, 사용할 파이프라인 manifest를 읽어라. Python·FFmpeg·폰트·입력 파일·모델·custom node·Modal 인증과 배포 목록을 확인해라. 기존 실행 환경의 인증을 사용하고 비밀값을 출력하거나 읽어 모으지 마라. 입력부터 최종 렌더까지 누락된 의존성을 보고해라. 원격 생성은 GPU·호출 수·예상 비용과 사용자 실행 승인이 갖춰진 범위에서 수행해라. setup 확인으로 deploy, download_weights, health.remote, generate, modal run을 자동 실행하지 마라. 결과는 로컬 데이터 루트에 저장하고 버전·입력 해시·실행 기록을 남겨라.

## 자료와 재현 상태

- [파이프라인 목록](pipelines/README.md) · [노드 프롬프트](prompts/) · [ComfyUI 그래프 스냅샷](workflows/comfyui/README.md)
- [제작 지침](.codex/skills/video-production/SKILL.md) · [창작 원칙](docs/creative/README.md)
- [Lab 재현 의존성과 공개 선별표](docs/reproducibility/lab-selection.md)
- [저장소 규칙](docs/constitution/README.md)

공개 선별 기준은 **클론한 사람이 필요한 입력을 준비하고 같은 절차를 실행할 수 있는가**입니다. 실행 코드·프롬프트·워크플로우·설치 정보·입력 계약을 연결하며, 필수 중간 자산은 재배포 가능하면 포함하고 그렇지 않으면 취득·생성 절차와 미해결 상태를 명시합니다. 개인 절대 경로, 자격 증명, 가상환경, 캐시는 공개하지 않습니다. 로컬 단위 테스트와 타 계정의 실제 생성·AE 렌더 검증은 구분합니다.
