# 선택적 앱용 템플릿

이 폴더는 기존 앱이 호출하는 재사용 가능한 로컬 템플릿입니다. **Modal 워크플로우 실행에는 설치하거나 사용할 필요가 없습니다.** 직접 실행은 [Modal 안내](../docs/modal-workflows.md)를 따릅니다.

개별 영상 제작·레퍼런스 관리와 H3 참조 영상 실험은 다른 프로젝트로 분리했습니다. 현재 원격 H3 JSON은 [worker/graphs](../worker/graphs/)에 있습니다.

| 템플릿 | 상태 | 엔진 |
| --- | --- | --- |
| `local-launch-spoof@1.0` | candidate | local-python |
| `local-freeze-cast@1.0` | candidate | local-python |

`registry.json`이 목록이며 각 버전의 `manifest.json`이 입출력과 파일 해시를 정의합니다. 앱은 해시가 다르면 실행하지 않습니다. 공통 `_shared/` 모듈도 앱의 두 템플릿이 사용하므로 유지합니다. candidate 등록은 출시 승인이 아닙니다.

템플릿을 사용하는 경우에만 Python에 `rembg[cpu]==2.0.67`, `numpy<2.3`, `scipy`, `pillow`를 준비합니다. 인물 따내기의 `bria-rmbg`는 비상업용 CC BY-NC 4.0이며 `birefnet-general`은 MIT입니다. 이 의존성은 H3·YuE2 직접 실행과 별개입니다.

```sh
python pipelines/seal.py
python pipelines/seal.py --check
```

해시 갱신은 draft·candidate에만 적용합니다. 출시된 버전을 바꾸려면 새 버전을 만듭니다.
