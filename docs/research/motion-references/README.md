# 모션·광고 레퍼런스 라이브러리

운영 규칙은 [헌법 제2조 레퍼런스 관리](../../constitution/02-reference-library.md)를 따른다.

영상 레퍼런스를 한 편당 카드 하나로 정리하고, 여러 카드를 가로지른 결론은 `synthesis/`에 모은다.

- `refs/` 영상 카드. 새 영상은 [_TEMPLATE.md](refs/_TEMPLATE.md)를 복사해 추가하고 아래 표에 한 줄을 넣는다.
- `synthesis/` [스타일 분류](synthesis/styles.md) · [제작 파이프라인](synthesis/pipelines.md) · [재사용 기법](synthesis/techniques.md)
- `assets/` 컨택트시트 등 가벼운 증거 이미지.
- 원본 영상·자막·프레임 등 무거운 원자료는 저장소 밖 `F:\modal-gui\references\`에 둔다. 카드마다 폴더 하나, 일괄 분석은 `batch-<날짜>-<주제>\`로 묶는다.

원래 분석 문서(2026-09-27 스냅샷)는 그대로 둔다. 카드의 "상세" 링크가 해당 절을 가리킨다.

- [AI 모션그래픽 제작 흐름과 스타일 분석](../2026-09-27-ai-motion-graphics-trends.md)
- [구글 광고 감성·SaaS 제품 런칭 모션](../2026-09-27-product-launch-motion-references.md)
- [Modal GUI 홍보영상 트리트먼트](../2026-09-27-modal-gui-promo-treatment.md)

## 전체 레퍼런스

| 카드 | 성격 | 길이·비율 | 게시 | 대표 태그 |
| --- | --- | --- | --- | --- |
| [신한카드 Simple Plan+](refs/shinhan-simple-plan.md) | 금융 광고 | 0:30 · 16:9 | 2026-03 | `2d-line-drawing` `character-skit` `pun-naming` |
| [NEPDA 넾 읽을 줄 아세요?](refs/nepda-neop.md) | 세로 쇼츠 광고 | 0:20 · 9:16 | 미확인 | `kinetic-typo` `quiz-hook` `loop` |
| [디자인하는AI 2D 모션](refs/9uQVYIaYIeg-design-ai-2d-motion.md) | 튜토리얼 | 15:10 | 2026-09 | `pipeline-video-gen` `prompt-spec` |
| [원카AI Vox 스타일](refs/a3HPd9wsROU-wonka-vox-paper.md) | 튜토리얼 | 19:16 | 2026-09 | `pipeline-image-code` `paper-cutout` |
| [쌩초 코드 모션](refs/Y7l9svE-ymQ-ssaengcho-code-motion.md) | 튜토리얼 | 11:52 | 2026-09 | `timecode-edit` `kinetic-typo` |
| [seven Sunbeam](refs/qaYO4A8Zf5E-seven-sunbeam.md) | 스타일 레퍼런스 | 0:30 · 16:9 · 12fps | 2023-03 | `y2k-pop` `motif-callback` |
| [코드깎는노인 바이브 AE](refs/kc5WFHtChdc-codeoldman-vibe-ae.md) | 튜토리얼 | 8:47 | 2026-09 | `pipeline-ai-ae` `editable-layers` |
| [Google Fake 2D](refs/VQ2scsSPZN4-google-fake-2d.md) | 포트폴리오 | 0:35 | 2024-04 | `minimal-product-launch` `icon-gather` |
| [LangEase](refs/SgmuplXU2iY-langease.md) | SaaS 런칭 | 0:33 | 2025-06 | `3d-ui-card` `progress-to-done` |
| [Numtera](refs/awUYikrGsKk-numtera.md) | SaaS 설명 | 1:35 | 2026-01 | `workflow-explainer` |
| [Lovable 2.0](refs/xDwR1_vrIg8-lovable-2.md) | 제품 출시 | 1:20 | 2025-04 | `gradient-brand-launch` `named-cursors` |

## 태그로 찾기

| 찾는 것 | 태그 | 카드 |
| --- | --- | --- |
| 글자로 훅 거는 쇼츠 | `quiz-hook` `kinetic-typo` `loop` | NEPDA, 쌩초, 디자인하는AI |
| 브랜드명 말장난 | `pun-naming` | 신한, NEPDA |
| 제품 UI 시연 | `input-to-result` `3d-ui-card` `named-cursors` | Google Fake, LangEase, Lovable |
| 설명형·단계형 | `workflow-explainer` `map-infographic` | Numtera, 원카AI |
| 종이·깊이감 | `paper-cutout` `diorama-2.5d` | 원카AI |
| 강한 팝 그래픽 | `y2k-pop` `3d-lettering` | Sunbeam |
| AI 제작 파이프라인 | `pipeline-video-gen` `pipeline-image-code` `pipeline-ai-ae` | 디자인하는AI, 원카AI, 쌩초, 코드깎는노인 |

## 카드 작성 규칙

- 분석 방법 칸에는 실제로 수행한 것만 적는다 (자막·프레임·OCR·오디오 등).
- AI 제작 여부는 확인된 경우에만 "확인됨"으로 적는다. AI 제품 광고와 AI로 만든 광고를 구분한다.
- 광고 속 성능·수치 주장은 검증된 사실로 옮기지 않는다.
- 확인하지 못한 것은 "확인 못 한 것"에 남긴다.
