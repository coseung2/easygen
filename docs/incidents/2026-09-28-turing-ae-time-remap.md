# Turing 쇼츠 AE time-remap 빌드 중단

- 날짜·시간대: 2026-09-28 21:55 Asia/Seoul.
- 증상: v3 스크립트의 루프용 freeze-frame 설정 중 AE가 비활성 속성의 setValue를 거부, 최종 master 저장 전 빌드 중단.
- 영향: 이 실행에서 생성한 미저장 프로젝트에만 영향. 기존 v2는 저장 후 닫았으며 보존됨. GPU 호출 없음.
- 확인 원인: Time Remapping의 모든 키를 지워 속성이 비활성화된 뒤 setValue 실행.
- 대응: 이 실행의 15 / LOOP 컴포지션이 있는 미저장 프로젝트만 확인해 build-interrupted.aep로 보존. 기본 time-remap 키를 유지하고 상수 표현식으로 freeze를 구현하도록 변경.
- 증거: F:/modal-gui/lab/2026-09-28-turing-enigma/v3/build.log, build.jsx.
- 복구 확인: 수정 후 AE 18.0.1x1에서 15개 장면·60초 프로젝트 저장 성공. 1080×1920 30fps 1800프레임 렌더·전체 디코딩 성공, 전환 20프레임과 1fps 60프레임 육안 확인. 사용자 기존 작업이나 공유 런타임 변경 없음.
