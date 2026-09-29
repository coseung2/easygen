# H3 세로 출력 무시 (업스케일러 목표 링크 고정 · 볼륨 리로드 누락)

- 일시: 2026-09-28 14:40–15:00, Asia/Seoul
- 증상 1: 거북선 Lab에서 `tools/run_h3_job.py --kind ref2v --width 768 --height 1344`로 제출한 clip-01 결과가 768×1344가 아니라 1344×768(가로)로 나왔다.
- 증상 2: clip-03 첫 제출이 `DenoMiniMaxH3ReferenceImageLoader` 입력 검증 실패로 추론 전에 멈췄다("Selected image file(s) are missing or unreadable before execution: gui/geobukseon-c3/clip-03-h3.png"). 같은 업로드 방식으로 넣은 clip-01·02는 성공했다.
- 영향: 승인된 H3 호출 4회 중 1회(clip-01)가 사용할 수 없는 가로 결과로 소모됐다. 실제 청구액은 로컬에서 확인할 수 없다. clip-03 검증 실패 1회는 추론 전 실패로 GPU 과금이 발생하지 않은 것으로 본다(미확정).
- 증거: `F:\modal-gui\lab\2026-09-28-geobukseon-moodboard\h3\clips\clip-01-h3.mp4`(1344×768), `h3\manifest.jsonl`, 실패 스택트레이스(세션 로그), Modal 앱 버전 기록 v17→v18→v19, 로컬 `_convert` 변환 비교.
- 확정 원인 1: r2v 워크플로에서 샘플러(노드 313·315)의 width/height는 `ResolutionSelector 16:9`에서 `a/2`로, 최종 해상도를 정하는 latent 업스케일러(노드 206 `MinimaxH3LatentUpscaler3D`)의 `mode.width/mode.height`는 같은 `ResolutionSelector`의 16:9 출력에 **링크**되어 있다. `modal/app.py`의 기존 크기 오버라이드(커밋 a729de7)는 샘플러만 바꾸고 있어, 샘플러를 세로로 돌려도 업스케일러가 최종 출력을 16:9로 되돌린다. 로컬 변환 비교로 확인: 수정 전 206 `mode.width/height = ["177",0]/["177",1]`(링크), 수정 후 요청 크기 리터럴.
- 확정 원인 2: `generate()`가 실행 전 `data.reload()`를 호출하지 않아, 방금 업로드된 입력을 웜 컨테이너가 못 본다. 신규 컨테이너(clip-01·02)에서는 통과하고, 직전 호출 후 살아 있는 컨테이너(clip-03)에서 실패하는 패턴과 일치한다. `pipelines/h3-refvideo/1.0`의 워커에는 이미 `data.reload()`가 있었다.
- 대응: `modal/app.py` 수정 — (1) 샘플러 크기가 링크면 요청 크기의 절반을 32px 버킷으로 내림, 업스케일러 목표를 요청 크기로 오버라이드. (2) `generate()` 시작에 `data.reload()` 추가. v18(태그 `size-override-20260928`), v19(태그 `size-override-plus-reload-20260928`) 배포. 가로 기본값(1344×768)은 로컬 변환 비교에서 수정 전후 동일한 샘플러(672×384)·목표(1344×768) 조합으로 확인.
- 복구 검증: clip-02·03·04 ref2v 재시험이 모두 768×1344·124프레임으로 생성됐고, 표본 프레임에서 입력 구도·화풍 유지와 무자막을 확인했다. clip-01은 가로 결과라 재생성 1회가 필요하다(사용자 승인 대기).
- 후속: (1) `modal/app.py` 변경은 아직 커밋하지 않았다. (2) t2v 워크플로 파일은 노드 6개짜리 스텁이라 이번 수정 대상이 아니다. (3) i2v 워크플로도 같은 링크 구조라 수정 효과가 함께 적용된다(재시험은 하지 않음).
- 관련: `2026-09-28-h3-i2v-input-bypassed.md`(이 문서의 "폭·높이도 워크플로 기본값" 미확정 원인을 여기서 확정).

## 추가 증상 (clip-01 재시도 중)

- 2026-09-28 15:2x, `geobukseon-c1b` 실행이 컨테이너 **안에서** `_wait`의 `/history` 폴링 urlopen 30초 타임아웃으로 실패했다. 볼륨에 출력이 남지 않았고(최신 출력은 ref2v_00048에서 멈춤), 컨테이너는 이후 종료됐다.
- 같은 파라미터로 즉시 재시도(`geobukseon-c1c`)는 성공(ref2v_00049, 768×1344). 확정 원인 없음 — 일시적 행으로 본다. 해당 실행의 GPU 과금 여부는 미확인.
- 후속: 같은 조건에서 재발하면 컨테이너 로그(`modal container logs`)와 ComfyUI 큐 상태를 남긴다. 현재 `generate()`는 ComfyUI stdout을 DEVNULL로 버리고 있어 컨테이너 로그에 남는 것이 없다(개선 후보).
