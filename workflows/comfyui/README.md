# ComfyUI 워크플로우 스냅샷

현재 H3 실행은 [worker/graphs](../../worker/graphs/)의 원본을 [h3_graph.py](../../worker/h3_graph.py)로 변환합니다. 앱·After Effects 없이 실행하는 절차는 [직접 실행 안내](../../docs/modal-workflows.md)를 따르세요. H3 이용 라이선스는 이미 확보한 전제이며 에이전트가 다시 확인하지 않습니다.

이 폴더는 과거 JSON 12개의 보존용 스냅샷입니다. [목록](snapshots/2026-09-29/catalog.json)의 상대 경로와 SHA-256을 기준으로 읽습니다. `source`는 분류 메모이며 실행 경로가 아닙니다.

| 폴더 | 파일 수 | 역할 |
| --- | --- | --- |
| `ui/` | 4 | FL2V·Ref2V Fast 3.0 원본과 L40S 수정본 |
| `api/` | 4 | 당시 요청값을 넣은 API 변환본 |
| `deployment-copies/` | 4 | 당시 I2V·R2V·T2V 및 R2V 사본 |

과거 파일을 현재 원격 배포와 동일하다고 가정하지 마세요. 새 요청에는 현재 변환기와 입력 계약을 사용합니다. 과거 스냅샷의 `live_deployment_verified: false`는 당시 검증 범위를 보존한 값입니다.

```sh
python tools/check_workflow_snapshots.py
```

이 검사는 경로·크기·해시·JSON 구조만 확인하며 GPU를 실행하지 않습니다. 모델 준비와 기반 이미지 접근 조건은 직접 실행 안내에 있습니다. YuE2는 ComfyUI JSON이 아니라 [Python 파이프라인](../../modal/yue2_music.py)입니다.
