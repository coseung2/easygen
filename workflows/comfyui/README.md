# ComfyUI 워크플로우 스냅샷

[2026-09-29 목록](snapshots/2026-09-29/catalog.json)은 제작에 사용한 로컬 폴더에서 수집한 그래프 12개를 기록한다. 원본 바이트를 유지하며 각 파일에 SHA-256과 크기를 기록했다. 개인 컴퓨터의 저장 위치는 목록에 포함하지 않는다.

| 폴더 | 파일 수 | 의미 |
| --- | --- | --- |
| `ui/` | 4 | FL2V·Ref2V Fast 3.0 원본과 L40S 수정본 |
| `api/` | 4 | 위 계열의 기존 API 변환본. 실행 당시 프롬프트·입력 이름이 들어 있을 수 있음 |
| `deployment-copies/` | 4 | I2V·R2V·T2V 및 deployed-r2v 로컬 사본 |

파일명이 같거나 비슷해도 활성 노드·해상도·입력 연결이 같다고 가정하지 않는다. API 그래프는 특정 입력을 넣어 만든 실행 자료로, 새로운 작업에는 prompt·seed·이미지/영상 입력·출력 prefix를 확인해야 한다. `catalog.json`의 `source`는 원본 분류를 나타내는 상대 이름이다.

## 검증 범위

```powershell
python tools/check_workflow_snapshots.py
```

목록의 경로·파일 크기·해시와 UI/API JSON 구조를 검사한다. 이는 ComfyUI 노드 설치나 GPU 추론 성공을 증명하지 않는다. 이번 공개 작업에서는 원격 Modal Volume을 다시 읽지 않았으며, `live_deployment_verified`는 `false`다.

이 스냅샷들은 [h3-refvideo@1.0](../../pipelines/h3-refvideo/1.0/manifest.json)과 별개다. 해당 파이프라인은 Blender 참조 영상을 받는 전용 변환을 사용한다. 임의의 FL2V·I2V·T2V 그래프를 그 worker에 연결해도 동작한다는 뜻이 아니다.

## 새 클론의 실행 전제

1. 원하는 입력 종류에 맞는 그래프를 선택하고 실제 사용되는 노드·모델 파일을 확인한다.
2. ComfyUI와 custom node의 commit, 모델 repository·revision·파일 해시, GPU·정밀도를 기록한다.
3. 입력 자산을 준비하고 사용자 자신의 실행 환경에 경로를 연결한다.
4. UI 다운로드 메타데이터와 선택된 위젯의 모델 파일명을 대조한다. 일부 그래프는 설명에 있는 모델과 실제 INT8 선택값이 다르다.
5. 입력부터 최종 저장 노드까지 작은 실행으로 확인한 뒤 파이프라인 버전으로 승격한다.

현재 H3 worker의 기반 Modal 이미지와 내부 `h3_service` 빌드가 저장소에 없어, 새 계정에서의 동일 환경 구축은 미완료다. [설치·인증 안내](../../README.md#3-modal-가입과-api-인증)를 참고한다.
