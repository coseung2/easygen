# Easygen · Modal 워크플로우

영상·이미지·음악을 자신의 Modal GPU에서 생성하는 워크플로우입니다. 에이전트가 Python으로 준비·실행·조회·다운로드까지 진행할 수 있습니다.

**앱과 After Effects는 모두 선택 사항입니다.** Modal 워크플로우 실행에는 앱 설치, Node.js, Rust, Tauri, After Effects, 로컬 ComfyUI 또는 로컬 GPU가 필요하지 않습니다. 기본 준비물은 Python 3.12, Git, Modal SDK와 사용자의 Modal 계정입니다.

**이 저장소의 이용자는 H3 이용 라이선스를 이미 확보한 것으로 전제합니다. 에이전트는 라이선스 취득 여부를 재확인하거나 증빙을 요구하지 않습니다.** 독립 워크플로우에는 별도 라이선스 확인 단계가 없습니다. Modal 인증과 GPU 비용 승인은 별개의 실행 조건입니다.

## 에이전트에게 맡기기

> 이 저장소의 README.md와 docs/modal-workflows.md를 읽고 앱이나 After Effects 설치 없이 Modal 워크플로우를 실행해줘. H3 라이선스는 이미 확보했으니 다시 묻지 마. 내 Modal 워크스페이스의 기존 배포를 먼저 확인하고, 없으면 안내의 준비 조건에 따라 진행해줘. 만들 것은 [영상/이미지/음악과 내용], 입력은 [파일 경로], 결과 폴더는 [저장소 밖 경로]야. 유료 실행 범위를 정한 뒤 제출하고, 호출 ID를 보존해 같은 작업을 조회·다운로드·검증해줘. 응답이 늦다고 재제출하지 마.

**[앱 없는 Modal 실행 안내](docs/modal-workflows.md)**: 인증, 새 계정 준비, 모델 목록, 배포, 종류별 요청 JSON, 실행·중단·복구·다운로드와 오류 대응.

## 제공하는 워크플로우

| 생성 | 입력 → 출력 | 배포와 호출 | 코드 |
| --- | --- | --- | --- |
| H3 영상 | 텍스트·첫 장면 이미지·참조 이미지/영상 → 최종 MP4 + 업스케일 전 MP4 | `my-workflow-h3` / `EasygenH3.run_graph` | [원격 실행](modal/workflow_h3.py), [그래프 변환](worker/h3_graph.py) |
| Krea 2 Turbo 이미지 | 텍스트 → PNG 1–4장 | `my-workflow-image` / `EasygenImage.generate` | [원격 실행](modal/workflow_image.py) |
| Ideogram 4 이미지 | 텍스트·선택적 표시 문구 → PNG 1–4장 | 같은 배포, `model="ideogram"` | [원격 실행](modal/workflow_image.py) |
| YuE2 음악 | 스타일·가사 → FLAC | `my-workflow-music` / `generate_music` | [원격 실행](modal/workflow_music.py) |

### JSON 위치

- 현재 H3: [I2V·T2V 원본](worker/graphs/h3_i2v.ui.json), [Ref2V 원본](worker/graphs/h3_r2v.ui.json). `worker/h3_graph.py`가 요청값을 넣어 API 그래프로 변환합니다. 로컬 미리보기 경로는 공개본에서 제거했습니다.
- 과거 H3: [2026-09-29 스냅샷](workflows/comfyui/README.md). 과거 JSON을 현재 실행 그래프와 혼동하지 마세요.
- **YuE2는 ComfyUI JSON 방식이 아닙니다.** `modal/workflow_music.py`가 Python의 `YuE2Pipeline`을 호출합니다. 아래 요청 JSON은 파라미터 파일이며 노드 그래프가 아닙니다.
- 이미지 그래프는 `modal/workflow_image.py`의 `krea_graph`, `ideogram_graph` 함수로 정의됩니다.

## 빠른 시작

```sh
git clone https://github.com/coseung2/easygen.git
cd easygen
python -m venv .venv
```

PowerShell: `.\.venv\Scripts\Activate.ps1`
macOS/Linux: `source .venv/bin/activate`

이후 명령의 `python`은 해당 가상환경의 Python입니다.

```sh
python -m pip install "modal==1.6.1"
python -m modal profile current
python -m modal app list --json
python -m modal volume list
python tools/modal_workflow.py --help
```

이미 인증됐으면 재인증하지 않습니다. 처음이라면 `python -m modal setup`으로 사용자가 한 번 인증하거나, 기존 API 토큰을 에이전트 실행기의 비밀 환경 변수로 주입합니다. 토큰을 채팅·코드·저장소에 적지 않습니다.

자신의 워크스페이스에 배포가 있으면 재배포 없이 바로 호출합니다. **저장소를 복제해도 유지보수자의 Modal 계정이나 GPU 접근권은 주어지지 않습니다.**

### 각자 자신의 Modal 환경 구축

현재 앱은 유지보수자 개인용입니다. 공개 사용자는 앱에 연결하지 않고 **자기 계정에 자기 워크플로우**를 만듭니다. 공개 배포 파일은 `modal/workflow_*.py`, 개인 앱 배포 파일은 `modal/easygen_*.py`, `modal/yue2_music.py`로 분리돼 있습니다.

```sh
# 무료 로컬 계획: 수행 명령과 다운로드 크기만 표시
python tools/setup_modal.py h3
# 승인된 CPU 빌드·다운로드·배포를 사용자 자신의 계정에 실행
python tools/setup_modal.py h3 --apply
```

이미지는 `image`, 음악은 `music`을 지정합니다. 기본 리소스 이름은 `my-workflow-*`이며, `EASYGEN_WORKFLOW_PREFIX`를 설정하면 자신의 이름으로 만들 수 있습니다. 같은 이름이 이미 있다면 갱신하므로 새 워크플로우에는 새로운 prefix를 사용하세요. 기본 이름은 현재 개인 앱의 리소스와 겹치지 않습니다.

H3·이미지는 공개 CUDA 이미지에서 Python·PyTorch·ComfyUI·커스텀 노드를 설치합니다. 모델은 고정 Hugging Face revision에서 자신의 볼륨에 다운로드하고 크기·SHA-256을 확인합니다. 유지보수자의 Modal 이미지 ID·모델 볼륨·내부 패키지를 사용하지 않습니다. 다운로드는 H3 약 73 GiB, 이미지 약 45 GiB, YuE2 약 7.3 GiB이며 컨테이너·캐시 공간이 추가로 필요합니다.

`--apply`는 CPU 빌드·다운로드·저장 비용이 발생할 수 있지만 GPU 생성은 수행하지 않습니다. Modal 인증과 다운로드 서비스의 접근 권한은 각자 자신의 것으로 설정합니다. H3 라이선스 보유 여부를 다시 묻지 않습니다. [상세 준비·검증](docs/modal-workflows.md#2-새-워크스페이스-준비)을 참고하세요.

## 실행 순서

[상세 안내](docs/modal-workflows.md)의 요청 예제를 저장소 밖 `request.json`으로 저장합니다.

```sh
# prepare는 오프라인 검사. Modal 호출·과금 없음.
python tools/modal_workflow.py prepare video --request ../request.json --out ../my-video
# 승인된 유료 실행. 한 번만 제출.
python tools/modal_workflow.py submit ../my-video
python tools/modal_workflow.py status ../my-video
# status가 completed일 때
python tools/modal_workflow.py download ../my-video
```

이미지는 `prepare image`, 음악은 `prepare music`을 사용합니다. 결과 폴더의 `state.json`에 원격 호출 ID가 저장됩니다. 연결이 끊겨도 같은 폴더에 `status`를 실행하며 `submit`을 반복하지 않습니다. 중단은 `cancel`입니다.

H3 라이선스는 다시 묻지 않습니다. 유료 GPU 실행은 승인된 종류·횟수·비용 범위를 따릅니다. `health`, `validate_graph`도 GPU 컨테이너를 시작할 수 있습니다. SDK 반환 시간은 실제 청구 GPU 시간과 동일하지 않습니다.

## 저장소 범위

이 저장소는 재사용할 Modal 워크플로우·JSON·호출 코드와 선택적 앱을 관리합니다. **개별 영상의 제작 산출물 관리, 레퍼런스 수집·분석, 연출 지침, 에피소드 제작 파이프라인은 별도 프로젝트로 분리했습니다.** 그것들을 설치·복제하거나 정해진 제작 폴더 구조를 만들 필요가 없습니다.

입력과 다운로드 결과는 원하는 저장소 밖 폴더에 보관하세요. 호출 상태 파일은 작업 복구용이며 별도 제작 관리 시스템이 아닙니다.

## 개인용 앱과 선택적 후반 편집

현재 앱은 유지보수자 개인용 부가 도구입니다. 외부 사용자의 독립 워크플로우 구축에는 연결하지 않습니다. 앱 개발을 원하는 경우에만 Node.js/npm, Rust 및 Tauri 빌드 도구를 준비해 `npm ci`, `npm run tauri dev`를 실행합니다.

After Effects는 내려받은 결과를 별도로 편집할 때 선택하는 도구입니다. **설치·라이선스·aerender 모두 Modal 생성의 전제 조건이 아닙니다.** FFmpeg/ffprobe도 생성 제출에는 필요하지 않으며 결과 파일 검사에 사용할 수 있습니다.

## 검증과 문서

```sh
python -m unittest tools.test_modal_setup tools.test_modal_workflow
python tools/check_workflow_snapshots.py
```

공개 소스 이미지 빌드·CPU 필수 노드 등록은 실제 확인했습니다. 모델 전체 다운로드·새 워크스페이스 GPU 성공은 별도 검증 대상입니다. [검증 기록](docs/modal-bootstrap-verification.md), [에이전트 지침](AGENTS.md), [운영 규칙](docs/constitution/README.md), [Modal 디렉터리](modal/README.md)를 참고하세요.
