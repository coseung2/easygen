# Modal GUI

**Modal GUI is a local-first Windows video-production studio in development.** 이 저장소는 제품 앱(App)과 제작 실험(Lab)을 함께 다룹니다. App은 레퍼런스·스토리보드·생성·편집 흐름을 한곳에 모으는 데스크톱 앱이며, Lab은 영상과 제작 방식을 실험하고 반복 검증하는 트랙입니다. Lab에서 검증·승인된 절차만 버전이 있는 파이프라인과 노드 프롬프트로 승격합니다.

Modal GPU 실행은 사용자가 접근 권한을 가진 워크스페이스를 대상으로 합니다. Modal GUI는 MiniMax 상용 API 클라이언트가 아니며, 계정 제한이나 과금 정책 우회를 목적으로 하지 않습니다.

## Repository and local data

Git에는 앱·실험 코드, 문서, 가벼운 파이프라인 정의와 프롬프트를 둡니다. 파이프라인과 프롬프트는 각각 `pipelines/`와 `prompts/`에서 `id@version` 및 상태로 관리합니다. 출시된 정의는 덮어쓰지 않고 새 버전을 만듭니다.

원본 영상·이미지, 실험 중간물과 생성 결과, 골든 입력 및 출시 판정 결과는 로컬 작업 데이터로 보관하며 Git에 넣지 않습니다. 앱 데이터와 자격 증명도 코드와 분리합니다. 자격 증명은 OS 보안 저장소를 사용하고 저장소·로그에 기록하지 않습니다. 세부 경계와 예외는 [제1조](docs/constitution/01-app-identity.md) 및 [제2조](docs/constitution/02-reference-library.md)를 따릅니다.

## Getting started

Windows 개발 환경에서 저장소를 받은 뒤 Node.js/npm, Rust 및 Tauri의 Windows 개발 요건을 준비합니다. 의존성을 설치하고 Vite 개발 화면은 `npm run dev`, 데스크톱 개발 실행은 `npm run tauri dev`로 시작할 수 있습니다.

```powershell
npm ci
npm run dev
# Desktop app:
npm run tauri dev
```

Modal 작업이 필요한 경우 별도로 Modal Python SDK와 사용자 인증이 필요합니다. 기능별 추가 전제는 관련 문서와 코드에 따르세요. 비밀값을 명령행이나 문서에 붙여넣지 마세요.

## Status and verification

프로젝트는 개발 중이며, 문서에 그려진 전체 제품 흐름이 모두 구현되었거나 실제 서비스에서 검증되었다는 뜻은 아닙니다. UI 존재, 자동 테스트 통과, 외부 서비스·GPU에서의 실제 실행은 서로 다른 검증 수준입니다. 특히 pipeline registry와 프롬프트 버전 체계의 존재만으로 각 항목이 출시 승인되었다고 볼 수 없습니다. 현재 파이프라인 상태는 [`pipelines/README.md`](pipelines/README.md)와 registry를 확인하세요.

사용 가능한 검사는 다음과 같습니다.

```powershell
npm run build
npm run check:worker
npm run check:renderers
npm run check:ux-contract
```

각 검사는 해당 로컬 코드 범위만 확인합니다. 통과만으로 Modal 배포, 유료 GPU 작업, 자격 증명 연동 또는 전체 사용자 흐름이 검증되지는 않습니다.

## Project rules

헌법은 설계 문서와 코드보다 우선합니다. 먼저 요청이 Lab인지 App인지 판단하고, 실행 경로와 유료 단계는 승인 규칙을 따르세요.

- [헌법 목차](docs/constitution/README.md)
- [제1조 — 앱 정체성과 데이터 위치](docs/constitution/01-app-identity.md)
- [제2조 — 레퍼런스 관리](docs/constitution/02-reference-library.md)
- [제3조 — 파이프라인 버전 관리](docs/constitution/03-pipeline-versioning.md)
- [제4조 — 실행 경로와 유료 승인](docs/constitution/04-execution-routing.md)
- [제5조 — Lab·App 경계와 승격](docs/constitution/05-two-tracks.md)
