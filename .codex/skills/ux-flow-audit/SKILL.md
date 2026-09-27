---
name: ux-flow-audit
description: Use when measuring the interaction cost of a Modal GUI flow before or after a change — counts KLM mental operators and excise steps with a reproducible script, so "이 동작은 두 단계다" becomes ΔM and seconds instead of taste. Not for visual design review or bug hunting.
---

# Modal GUI UX Flow Audit — interaction cost

Measures **what a user goal actually costs** in a Modal GUI flow: how many decisions and actions it takes, and which of those steps are *excise* — work the product forces on the user to satisfy its own implementation rather than the user's goal.

Scope boundaries:

- **Not a visual review.** Colour, spacing, typography, and hierarchy are covered by `.codex/skills/ux-audit/SKILL.md` and the actual rendered screen.
- **Not a lifecycle/state-truth review.** Missing states, stale rows, orphaned runs, and event-propagation defects are a different audit — see `.codex/skills/ux-audit/SKILL.md`, then come back here for the measurement.
- **Not a bug hunt.** A wrong value or a failing test is debugging.

What this skill adds is the **number**. It makes claims such as "이 동작은 두 단계야", "이 버튼을 왜 눌러야 하지", "한 화면에서 안 되네" reproducible: the same flow scored twice gives the same ΔM and the same seconds.

## When to use

- A flow is reported as costing too many steps, or a step feels forced.
- A background or long-running process (worker run, render, download, billing sync, project save) appears as a button the user must press to make something current.
- Before/after comparison for a flow change — is the goal cheaper than it was?
- An audit finding needs a defensible severity: is this repeated friction on a core path (P1) or polish (P2)?

**Don't use for:** visual design changes, missing features, or a specific wrong result.

## Core model — three rules

**1. A button is an action; a background job is a state.**

```
run:  idle ──(event)──> running ──> ready
```

State is *presented*; the user does nothing. The moment it becomes a button you have invented a transition that exists only so the user can time it. That is excise by construction — the system's scheduling leaked into the interface.

This app already owns several real fast paths: the worker event stream (`worker-event`), the startup `listRecentJobs` hydration, and per-domain loaders. A manual refresh next to one of them is the canonical excise case; the legitimate place for a button is a provider that cannot push (Modal 청구/사용량 sync) or a transition that is genuinely the user's call.

**2. Cost is the number of mental operators (M), not the number of clicks.**

A press is 0.10 s. Preparing for one is 1.35 s. Each added step adds an M, so "one more button" costs ~2.5 s *and* breaks flow — not 0.1 s. Table and worked examples: `references/klm-operators.md`.

**3. Excise is judged against a goal, not by counting steps.**

This is a single-operator desktop tool, so there is no teacher/student split to lean on. The same step can be goal-directed in one mode and excise in another: a 계정 동기화 click is 운영 work and legitimate, the same click appearing in 창작 flow is excise. **Always name the goal mode (창작 / 운영 / 검토) and the surface (Tauri desktop or `npm run dev` browser preview) before labelling a step.** Taxonomy and the forced/discretion test: `references/excise-taxonomy.md`.

## Prerequisites

- `python` — stdlib only, for `scripts/klm_score.py`.
- A running app when a flow is *walked* (not required for scoring a path already traced through the code):
  - Browser preview: `npm run dev` (Vite). Tauri-gated behavior is inert here — say so in the report.
  - Full app: `npm run tauri dev` (needs the Rust toolchain and the Python worker).
  - Live generation needs a Modal profile and worker credentials; a walk that would spend real GPU credit needs the user's go-ahead first.
- Reference environment variable **names** in reports — never paste values, tokens, workspace ids, or connection strings.
- Screen inventory for this app: `references/surfaces.md` (routes, studio panels, command domains, durable tables).

## How to run

1. Write the goal the way the user says it — "레퍼런스 영상 뽑아서 결과물에서 확인하기", not `studio_start_node_run`.
2. Derive the shortest conceivable path: which transitions could the *system* perform unasked (worker event, startup hydration, automatic download, optimistic asset registration)?
3. Walk the real flow and log every step actually taken; then score both paths.
4. Classify each step, and apply Core Model rule 1 to any step that only triggers background work.

## Quick reference

| Operator | Meaning | Seconds |
|---|---|---:|
| `M` | mental preparation (decide) | **1.35** |
| `P` | point (move to target) | 1.10 |
| `H` | hand move (keyboard ↔ mouse) | 0.40 |
| `K` | keystroke | 0.20 |
| `B` | button press | 0.10 |

```bash
# explicit operator sequences, one per argument
python scripts/klm_score.py score "M K K" "M H P B M P B"
# labelled steps — each step is assumed to be M P B
python scripts/klm_score.py steps "스튜디오 열기" "노드 실행" "결과물에서 확인"
# prove the operator table against the textbook examples
python scripts/klm_score.py selftest
```

## Procedure

1. **Pick the flow; state the goal in the user's words.** Criterion: the operator would recognise the sentence as something they wanted to do.
2. **Derive the shortest conceivable path.** Name each transition the system could perform unasked **with its trigger and its real latency** — a run that only reports every stage when the worker flushes is not live for someone watching a canvas. Criterion 2: the shortest path names an event source, not a button.
3. **Walk the real path** and log every step, including the ones the UI forces that a shortcut would skip. Criterion: the log replays to the same end state.
4. **Score both paths** and report the delta (ΔM, Δseconds). Criterion: every number comes from `klm_score.py`, never from estimation.
5. **Classify each actual step** as goal-directed or excise, and name the forced labour (cognitive / memory / visual / physical) and the goal mode it serves or fails.
6. **For every background-trigger step, propose the state.** Convert `idle→(click)→running` into `idle→(event)→running`. Criterion: the proposal names a concrete event source and leaves no user action behind.
7. **Report only what was measured**; mark the rest as hypotheses. Criterion: every claim traces to a logged step, or is explicitly flagged as unverified.

If the app cannot be booted (no Modal credentials, no worker, the flow would spend real credit, or the port is taken), audit from the code path and **say so in the report**. A deterministic read of the component tree plus the Tauri command it calls is legitimate evidence; a fabricated walk is not.

## Report format

```
목표: <사용자 말투의 목표>            (goal mode: 창작 / 운영 / 검토, surface: Tauri 데스크톱 / 브라우저 프리뷰)
실측 경로: <step> → <step> → …      (n steps, M=m, ~T s)
최단 경로: <step> → <step>           (n steps, M=m, ~T s)
Δ: M +x / +y s
excise: <step 라벨> — 강제된 노동: <인지/기억/시각/물리>, 그 모드의 목표가 아님
제안: <step> 버튼 → <event> 트리거 상태
검증 필요(가설): <unmeasured claims>
```

## Pitfalls

1. **Judging by click count.** Fewer clicks is not the goal; fewer *decisions* is. A two-click path through visible options can beat one click that needs a mode switch.
2. **"Optimising" a step that is genuinely the user's call.** 실행 요청(GPU 비용 발생), 삭제, 내보내기/가져오기, 프로필 선택은 사용자 결정이다; 강제된 새로고침은 보통 excise다. Forced vs discretion is the deciding test.
3. **Auto-refreshing stable content.** On the canvas, silent refresh adds its own excise (flicker, lost viewport, lost selection, interrupted typing). Offer "새 결과 3개" instead of shifting the graph under the user.
4. **Counting a modal as one step.** Open + confirm is two M, and the second is where the excise hides.
5. **Treating browser preview and Tauri desktop as one cost model.** Code gated by `isTauri` behaves differently, and the browser preview cannot run real jobs. Score them separately, even when the flow is "the same".
6. **Proposing a UI fix for a provider constraint.** When a manual button exists to compensate for something the *provider* made slow (Modal billing API latency, container cold start, a long download), the excise is real but the fix is not in the UI. Removing the button without fixing the trigger makes the flow worse. Report the constraint as the root cause; gate the removal behind it.
7. **Trusting intended confirm coverage.** Read the handlers, not the design intent. Asymmetric guarding — a confirm on the reversible action, none on the one that writes — is common and invisible in review.
8. **Believing the page's own copy.** "자동으로 반영됩니다" next to a manual button is the product admitting the automatic path is too slow. Treat the copy as evidence, then measure the path it describes.

## Verification

- `python scripts/klm_score.py selftest` prints `OK` (Ctrl+S = 1.75 s, menu = 5.50 s)
- Every screen/panel named in a report exists in `references/surfaces.md` (or is added to it in the same change)
- Every reported number traces to a `klm_score.py` invocation shown in the report
- Every removed step/button has a proposed trigger naming a concrete event source
- The report names the goal mode and the surface it was measured on
- `npm run build` (plus whichever of `npm run check:worker`, `npm run check:renderers`, `cargo test --manifest-path src-tauri/Cargo.toml` the change can affect) still passes when the audit also changes code
- UI claims are verified on the actual screen; a build or test result is not visual verification

## Maintenance

This skill is the repo's own copy at `.codex/skills/ux-flow-audit/`. It was adapted from the aura-board skill of the same name (2026-09-16) for a desktop, single-operator app; keep that repository's copy separate and edit this one for Modal GUI needs. Keep machine-local absolute paths, secret values, and environment-specific identifiers out of this directory.
