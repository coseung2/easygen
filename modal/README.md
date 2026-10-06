# Modal 워크플로우

**앱과 After Effects 없이 실행**합니다. [직접 실행 안내](../docs/modal-workflows.md)를 따르세요. H3 이용자는 라이선스를 이미 확보했으므로 에이전트가 다시 묻지 않습니다.

| 파일 | 배포 | 역할 |
| --- | --- | --- |
| `easygen_h3.py` | `easygen-h3-v1` | H3 API 그래프 실행 |
| `easygen_image.py` | `easygen-image-v1` | Krea 2 Turbo·Ideogram 4 이미지 |
| `yue2_music.py` | `yue2-music` | Python YuE2Pipeline 음악 생성. ComfyUI JSON 없음 |
| `app.py` | `minimax-h3-latest-workflows` | 기존 클라이언트 호환 경로 |
| `local_image_gen.py` | `local-image-gen-modal-test` | 모델 다운로드·이미지 평가 도구 |

현재 H3 원본은 [worker/graphs](../worker/graphs/), 변환기는 [h3_graph.py](../worker/h3_graph.py), 앱 없는 호출기는 [modal_workflow.py](../tools/modal_workflow.py)입니다.

H3·이미지의 기존 기반 이미지 및 모델 볼륨 접근은 별도 준비 조건입니다. 공개 저장소를 받았다고 유지보수자의 Modal 리소스가 공유되지는 않습니다. `local_image_gen.py`의 기본 진입점은 평가 생성까지 수행하므로 다운로드 목적으로 통째로 실행하지 않습니다.
