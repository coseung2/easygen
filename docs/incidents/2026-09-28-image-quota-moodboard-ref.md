# 이미지 생성 한도로 무드보드 레퍼 재생성 실패

- Date/time: 2026-09-28 12:19, Asia/Seoul
- Symptoms: 무드보드 2번 시안(먹선 민화) 승인 후 풀프레임 레퍼 재생성(`boards/ref-2.png`)이 HTTP 429 `usage_limit_reached`로 거절됐다.
- Impact: 승인된 레퍼 이미지가 아직 없다. 이미지 생성이 필요한 다음 단계(스토리보드 보드)도 같은 한도에 막혀 리셋 전에는 진행할 수 없다.
- Timeline: 무드보드 보드 한 장 생성(성공) → 사용자 2번 시안 승인 → 레퍼 재생성 1회 시도 → 429, 리셋 예정 16:24:05 KST. 재시도하지 않았다.
- Evidence: 생성 도구 응답 `usage_limit_reached`, `plan_type: plus`, `resets_in_seconds 14768`. 완료분: `F:\modal-gui\lab\2026-09-28-geobukseon-moodboard\boards\moodboard-grid.png`.
- Confirmed cause: 이미지 생성 사용량 한도. Modal 청구 한도와는 별개다(제4조 §5의 3단계 미연결 문제와도 별개).
- Response: 무한 재시도 금지 규칙(제4조 §3)에 따라 1회 실패 후 중단했다. 승인 기록만 남기고 레퍼 생성은 리셋 후로 보류했다. 보드에서 잘라 쓰는 대체안은 쓰지 않았다(2026-09-27 편집 보드 드리프트 후속 규칙).
- Recovery verification: 아직 없음. 리셋 후 `boards/ref-2.png`를 재생성하고 경로와 크기를 확인하면 해소된다.
- Follow-up: 리셋(16:24 KST) 후 레퍼 재생성 1회. 그전까지 스토리보드 보드 생성도 보류한다.
