"""영상과 음악이 공유하는 박자 격자 (128 BPM).

v3: 사용자 "장면전환이 빨라서 정보를 파악하기 힘들다" → 장소당 8박(3.75초) → 12박(5.6초),
실사 3박(1.4초) → 6박(2.8초), 카드 1박 → 1.5박. 전체 30초 → 약 41초.
v5: 사용자 "훅 몽타주가 부자연스럽고 너무 빠름" → 훅 8박 → 12박. 사진이 한 박에 한 장씩 붙는 콜라주.
"""
BPM = 128
B = 60 / BPM                 # 한 박 0.46875초
FPS = 30

HOOK_END = 12 * B            # 5.625
INTRO_END = HOOK_END + B     # 4.21875
STOP_LEN = 12 * B            # 5.625
DRIVE = 3 * B                # 주행 3박
POP = 1.5 * B                # 카드 1.5박 (장소명 읽을 시간)
ZOOM = B / 2                 # 확대 반 박
LIVE = 6 * B                 # 실사 6박 (2.8초)
BACK = B                     # 복귀 1박
N_STOPS = 6
END_START = INTRO_END + STOP_LEN * N_STOPS   # 37.96875
END_LEN = 8 * B              # 엔딩 8박 (라이저 2박 + 히트 후 6박)
DUR = round(END_START + END_LEN, 3)          # 41.719


def stop_times(k):
    t0 = INTRO_END + k * STOP_LEN
    pop = t0 + DRIVE
    zoom = pop + POP
    live = zoom + ZOOM
    back = live + LIVE
    return {"t0": t0, "pop": pop, "zoom": zoom, "live": live, "back": back, "end": t0 + STOP_LEN}
