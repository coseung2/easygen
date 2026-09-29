# Modal GUI 에이전트 안내

이 저장소의 규칙은 [docs/constitution/](docs/constitution/README.md)에 있다. 헌법은 설계 문서와 코드보다 우선한다.

- 앱이 무엇인지, 데이터를 어디에 두는지: [제1조](docs/constitution/01-app-identity.md)
- 레퍼런스 영상 관리: [제2조](docs/constitution/02-reference-library.md)
- 파이프라인 버전: [제3조](docs/constitution/03-pipeline-versioning.md)
- 실행 경로와 유료 승인: [제4조](docs/constitution/04-execution-routing.md)
- 제작 실험(Lab)과 앱 개발(App)의 구분, 노드 프롬프트: [제5조](docs/constitution/05-two-tracks.md)

요청마다 먼저 트랙을 정한다 (제5조 §1).

- Lab: 영상, 숏폼, 광고, 모션그래픽을 만들어 달라는 요청. `.codex/skills/video-production/SKILL.md`를 따른다. 결과는 설정된 로컬 데이터 루트의 `lab/`, 스크립트는 저장소 `lab/`.
- App: 앱 기능·화면·노드 개발. `src/`, `src-tauri/`, `worker/`, `modal/`. UX 점검은 `.codex/skills/ux-audit/`.
- 승격: Lab에서 검증된 방식을 노드나 파이프라인으로 옮기는 요청. 제5조 §5와 제3조를 따른다.

App 코드는 `lab/`을 import하지 않는다. 생성 결과, 원자료, 납품물은 저장소 밖 로컬 데이터 루트에 두고 커밋하지 않는다. 자격 증명은 읽거나 출력하지 않는다. 개인의 절대 경로도 공개 저장소에 기록하지 않는다.
