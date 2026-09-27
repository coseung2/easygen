# KLM — Keystroke-Level Model

Card, Moran & Newell (1980, Xerox PARC). A task is decomposed into operators; each
operator has a measured duration; summing them predicts execution time. Deterministic
arithmetic — no aesthetics, no judgement.

## Operator table

| Operator | Meaning | Seconds |
|---|---|---:|
| `M` | mental preparation — deciding the next action | **1.35** |
| `P` | pointing — moving the cursor to a target | 1.10 |
| `H` | homing — moving the hand between keyboard and mouse | 0.40 |
| `K` | keystroke / button press on keyboard | 0.20 |
| `B` | pressing a mouse button | 0.10 |

## Where the M operators go

The whole model turns on M placement. The standard heuristic: **insert an M before
every P that selects a command.** A click is cheap; *deciding to click* is 13.5× the
press. This is why an extra confirm step is far more expensive than it looks.

## Worked example — saving a file

```
Keyboard shortcut:   M K K                              = 1.35 + 0.20 + 0.20 = 1.75 s
Menu path:           M H P B  M P B                     = 1.35+0.40+1.10+0.10
                                                        + 1.35+1.10+0.10      = 5.50 s
```

3× the time for the same outcome, and the difference is almost entirely the **second
M** (1.35 s) plus the extra pointing (1.10 s). `scripts/klm_score.py selftest` asserts
these two numbers.

## Reading the numbers correctly

- **Use ratios, not absolutes.** Individual and device differences are large; "경로 B는
  경로 A보다 약 3배" is defensible, "사용자는 5.5초를 쓴다" is not.
- **ΔM is the headline metric.** Report added mental operators first, seconds second.
- **KLM models expert, error-free performance.** It under-counts first-time use and
  ignores recovery from mistakes (a failed Modal run, a dropped download, an expired
  login), so the measured cost of this app's flows is a lower bound.
- **The model says what a step costs, not whether it should exist.** Legitimacy comes
  from the goal mode — see `excise-taxonomy.md`.

## Why this matters for background work

Adding a "동기화" or "새로고침" button adds a full cycle: `M P B` (2.55 s) *plus* the
cognitive load of deciding *when* — a judgement the user has no information to make
well. The worker and the database already know when state changed; the user does not.
That is why the state/action split in `SKILL.md` rule 1 removes the cost entirely
rather than shaving it.

## Field evidence

A KLM analysis of computerised physician order entry found that safety-motivated
verification dialogs and excess confirm steps **roughly doubled** order-entry time,
and drove clinicians to build **workarounds** that bypassed the very checks the
dialogs existed to enforce. Adding a step to make a system safer can make it less
safe. The same mechanism applies to forced sync/publish steps and to duplicated
confirm dialogs around destructive studio actions.

## Sources

- Card, Moran & Newell, *The keystroke-level model for user performance time with
  interactive systems* (CACM, 1980)
- *Textbook of Usability*, GOMS and Keystroke-Level Model chapter
- Krug, *Don't Make Me Think* — "클릭 수는 문제가 아니다, 단 각 클릭이 생각 없는
  명확한 선택이라면" (rule 2). This is the same claim stated from the other side.
