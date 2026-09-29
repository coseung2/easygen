# Modal GUI 헌법

제정: 2026-09-27 (Asia/Seoul)

이 폴더는 Modal GUI의 정체성과 운영 규칙을 정한다. 설계 문서, 작업 계획, 코드가 이 문서와 어긋나면 이 문서가 우선한다.

| 조 | 문서 | 정하는 것 |
| --- | --- | --- |
| 1 | [앱 정체성](01-app-identity.md) | Modal GUI가 무엇이고 무엇이 아닌지, 제품 원칙, 데이터가 어디에 사는지 |
| 2 | [레퍼런스 관리](02-reference-library.md) | 레퍼런스 영상의 수집·분석·보관·인용 규칙 |
| 3 | [파이프라인 버전 관리](03-pipeline-versioning.md) | 앱이 실행하는 생성·렌더 파이프라인의 식별, 버전, 출시, 폐기 규칙 |
| 4 | [실행 경로 선택](04-execution-routing.md) | 샷마다 로컬 코드, 모션 도구, 외부 API, Modal 중 무엇으로 만들지와 유료 승인 |
| 5 | [두 트랙과 승격](05-two-tracks.md) | 제작 실험(Lab)과 앱 개발(App)의 경계, 노드 프롬프트 버전, Lab → App 승격 절차 |

## 우선순위

```text
헌법 (docs/constitution/)
  ↓ 따른다
아키텍처·설계 (README.md, docs/creative-studio-architecture.md, docs/renderer-plugins.md)
  ↓ 따른다
작업 계획·조사 (docs/next-work-plan.md, docs/research/)
  ↓ 따른다
코드
```

## 개정 절차

1. 바꿀 조항과 이유를 이 폴더의 해당 문서에 먼저 반영한다.
2. 문서 하단 "개정 이력"에 날짜, 바뀐 조항, 이유를 한 줄로 남긴다.
3. 그다음 코드와 하위 문서를 맞춘다.

코드가 헌법과 조용히 어긋나게 두지 않는다. 당장 맞출 수 없으면 해당 문서의 "현재 미준수 사항"에 적는다.
