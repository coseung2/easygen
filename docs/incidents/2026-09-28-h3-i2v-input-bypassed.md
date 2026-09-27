# H3 i2v 입력 이미지 무시

- 일시: 2026-09-28, Asia/Seoul
- 증상: 조리원 숏폼 시험에서 `tools/run_h3_job.py --kind i2v`로 장면 그림 두 장(01-H, 07-H)을 넣었지만, 두 결과 모두 첫 프레임부터 입력 그림과 무관한 캐릭터·구도로 나왔다. 출력은 입력이 768×768로 지정됐는데도 1344×768이었다.
- 영향: Modal L40S 유료 호출 2회가 쓸 수 없는 결과로 끝났다. 실제 청구액은 로컬에서 확인할 수 없다. 결과는 `F:\modal-gui\lab\2026-09-28-joriwon-vs-home\h3\`에 증거로 남긴다.
- 증거: 배포된 `minimax-h3-comfyui-data/user/default/workflows/video_minimax_h3_i2v.json`은 `F:\modal-gui\remote-workflows\` 사본과 해시가 같다. 이 워크플로의 `LoadImage`(54, 55)와 `ImageResizeKJv2`(52, 53)가 모두 `mode: 4`(bypass)라, `modal/app.py`의 `_convert`가 이 노드들을 건너뛰고 `MiniMaxH3ImageToVideo`의 `first_frame`/`last_frame`이 연결되지 않는다. 결과적으로 i2v가 프롬프트만 쓰는 t2v처럼 동작한다. 폭·높이도 워크플로 기본값이 쓰인 것으로 보인다(원인 미확정).
- 확정 원인: 배포된 i2v 워크플로의 입력 노드가 bypass 상태다.
- 대응: 추가 H3 호출은 하지 않았다. 입력 보존이 확인된 경로는 Ref2V다(2026-09-27 rainbow 사고 기록의 후속 복구 참고).
- 후속: i2v를 쓰려면 워크플로에서 입력 노드를 활성화하거나, `run_h3_job.py`가 bypass된 입력 노드를 만나면 실행 전에 실패하도록 막는다. 그 전까지 그림 기반 생성은 `--kind ref2v`를 쓴다.

- 2026-09-28 복구: 배포된 워크플로를 `F:\modal-gui\remote-workflows\backup\video_minimax_h3_i2v.2026-09-28.bypassed.json`에 백업한 뒤 노드 52·53·54·55를 활성화(mode 4→0)해 볼륨과 로컬 사본에 반영했다(`lab` 폴더의 `fix_h3_i2v_workflow.py`). 워크플로 해상도가 16:9로 고정이라 정사각 장면은 1344×768 종이색 여백에 넣어 입력했다. 재시험 2회(01-H, 07-H) 모두 첫 프레임부터 입력 그림의 캐릭터·색·선을 유지했고, 표본 프레임에서 형태 붕괴는 보이지 않았다. 새 문제로 01-H의 로컬 다운로드가 0바이트에서 멈췄는데, 결과는 볼륨에 이미 있어 `modal volume get`으로 직접 받았다(원인 미확인). 사용자 최종 승인은 아직이다.
