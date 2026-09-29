# local-launch-spoof

## 1.0 — candidate (2026-09-28)

- Lab `2026-09-28-junyoung-intro`의 `render_launch.py`(junyoung-launch-v5, 합격)를 입력 JSON 기반 템플릿으로 옮김.
  이름, 날짜, 장면별 소재·문구·수치, 팔레트, 인물 따내기 모델이 모두 입력이다.
- 콧날 위치: 옆모습 윤곽에서 첫 번째로 튀어나온 점(코 → 인중)을 자동 탐지. v5 수동값 (634, 787) 대비 (635, 785).
- 회귀 비교(golden `junyoung.json` vs v5): 프레임 평균 차이 0.54/255, 최대 3.66, 음량 −15.4 LUFS·최고 −1.4 dBFS 동일.
  남은 차이는 2–4초 대표 컷 등장 구간의 스티커 크기 반올림.
- Lab 합격 1회라 candidate. 두 번째 인물·제품으로 합격하면 released 판정.
