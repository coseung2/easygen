# pipelines

제3조(파이프라인 버전 관리)에 따른 실행 절차 모음. `registry.json`이 전체 목록이고, 버전 폴더의
`manifest.json`이 계약과 파일 해시를 가진다. 앱은 해시가 맞지 않으면 실행하지 않는다.

| id@version | 상태 | 이름 | 엔진 |
| --- | --- | --- | --- |
| `local-launch-spoof@1.0` | candidate | 제품 런칭 패러디 | local-python |
| `local-freeze-cast@1.0` | candidate | 프리즈 프레임 캐릭터 인트로 | local-python |

## local-python 템플릿

- `render.py <job.json> [--cutout-python <python>] [stills]`. 입력은 `job.schema.json`, 출력은 MP4와
  `<output>.metadata.json`(파이프라인 id·버전, 인물 따내기 모델과 라이선스). stdout에 JSON 줄 이벤트
  (`render_started` · `render_progress` · `render_completed` · `failed`)를 쓴다.
- 공통 모듈은 `_shared/`: `motionkit.py`(그리기·이징·인코딩), `cutout.py`(BRIA/BiRefNet 스티커, 이미지마다
  별도 프로세스), `sfx.py`, `music_bouncy.py`(120BPM), `music_chiptune.py`(150BPM), `compare.py`(회귀 비교).
- 실행 Python에는 `rembg[cpu]==2.0.67`, `numpy<2.3`, `scipy`, `pillow`가 필요하다. 앱은
  `MODAL_GUI_TEMPLATE_PYTHON` 또는 기본 lab venv를 쓴다.
- 인물 따내기 `bria-rmbg`는 CC BY-NC 4.0(비상업)이다. 상업 영상은 `cutout_model: "birefnet-general"`(MIT).

## 파일을 바꾼 뒤

```powershell
python pipelines/seal.py          # 해시와 registry.json 갱신 (released는 거부)
python pipelines/seal.py --check  # CI/검수용
```

released 버전은 고치지 않는다. 바꾸려면 새 버전 폴더를 만든다.

## 출시 판정 (제3조 §6, 제5조 §5)

- golden 입력과 결과는 `$MODAL_GUI_DATA_ROOT/pipelines/<id>/<ver>/golden-inputs/`, `release-check/`.
- 회귀: `python pipelines/_shared/compare.py <approved.mp4> <template.mp4> <report.json>`.
- 두 템플릿 모두 Lab 합격이 1회라 candidate다. 다른 인물·제품으로 한 번 더 합격하면 released로 올린다.
