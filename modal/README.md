# Modal 워크플로우

각자 자신의 Modal 계정에 독립 워크플로우를 만듭니다. **앱과 After Effects 없이 실행**하며 [직접 실행 안내](../docs/modal-workflows.md)를 따릅니다. H3 이용자는 라이선스를 이미 확보했으므로 다시 묻지 않습니다.

## 외부 사용자용 독립 경로

| 파일 | 기본 배포 이름 | 역할 |
| --- | --- | --- |
| `workflow_h3.py` | `my-workflow-h3` | H3 영상 |
| `workflow_image.py` | `my-workflow-image` | Krea·Ideogram 이미지 |
| `workflow_music.py` | `my-workflow-music` | YuE2 Python 음악 |
| `bootstrap.py` | 임시 CPU 작업 | 사용자 볼륨 생성·모델 다운로드·해시 검사 |
| `check_environment.py` | 임시 CPU 작업 | 공개 이미지 빌드·노드 등록 검사 |

`python tools/setup_modal.py h3 --apply`가 준비와 배포를 순서대로 수행합니다. 모델·소스 목록은 `easygen_runtime/`에 있으며 사용자 이름은 `EASYGEN_WORKFLOW_PREFIX`로 지정합니다. 개인 Modal 이미지 ID·모델 볼륨은 사용하지 않습니다.

## 유지보수자 개인 앱 경로

`easygen_h3.py`, `easygen_image.py`, `yue2_music.py`, `app.py`와 이미지 평가 코드는 개인 앱·기존 실행 호환용입니다. 외부 환경 구축 시 이 파일들을 배포하지 않습니다. 새 구축을 위해 개인 앱의 기존 배포·볼륨을 변경하지 않습니다.
