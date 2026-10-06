# 독립 워크플로우 준비 검증

2026-10-06 (Asia/Seoul).

## 확인한 범위

- `modal/check_environment.py`를 실행하여 공개 CUDA registry부터 컨테이너를 새로 빌드했다. 기존 개인 이미지 ID·모델 볼륨을 사용하지 않았다.
- ComfyUI `73c9bad4d21e7addbe1d13bc92eee0f1431b017d`와 `easygen_runtime/sources.json`의 5개 custom node commit을 설치했다. `pip check` 통과.
- CPU ComfyUI 서버를 실행하고 `/object_info`에서 H3·이미지 필수 노드 14개를 확인했다. 검사 반환값은 `status: ready`, `gpu_tested: false`다.
- Hugging Face 모델 메타데이터에서 H3 7개, 이미지 7개, YuE2 19개의 실제 경로·revision·크기·SHA-256을 확보했다. 작은 일반 파일은 해당 revision에서 내려받아 해시를 계산했다. 큰 모델은 서버 메타데이터를 사용했으며 전체 다운로드는 하지 않았다.
- 로컬 테스트는 이름 분리, 다운로드·재개, 기존 파일 해시 불일치 시 보존, verify-only, 호출 중복 방지·조회·회수를 검사한다.

## 별도 검증이 필요한 범위

- 새 사용자 계정의 인증·쿼터·모델 접근은 그 사용자 환경에서 확인한다.
- 전체 모델 다운로드·볼륨 해시 검사는 `bootstrap.py` 실행 결과로 확인한다.
- 실제 GPU 추론·결과 디코드는 승인된 최소 생성으로 확인한다. CPU 노드 등록을 GPU 생성 성공으로 표현하지 않는다.
- YuE2의 독립 이미지·모델·GPU를 결합한 전체 실행은 이번 검증에 포함하지 않았다.

개인 앱 배포 파일과 원격 앱은 변경하지 않았다. 독립 배포는 `workflow_*.py`, 기본 리소스 이름은 `my-workflow-*`다.
