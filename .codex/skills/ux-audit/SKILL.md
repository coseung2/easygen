---
name: ux-audit
description: Audit any Modal GUI user-facing surface for missing required states, lifecycle cleanup defects, stale or misleading status, unnecessary steps, redundant controls/copy/containers, leaked implementation state, slow synchronization, and cost/account truthfulness before implementation. Use for UX/UI 전수조사, 기능별 UX 정리, 리팩터링 전 검토, 제작 스튜디오·작업 큐·결과물·편집·사용량·연결 관리·설정 화면 점검, or desktop app experience review.
---

# Modal GUI UX Audit

Use this skill for any user-facing Modal GUI surface: the canvas studio, job queue, results, edit/motion, usage and accounts, connections, settings, or a cross-screen workflow. It is not a visual-only review — follow the user's task through the actual implementation and check whether the UI represents product state, cost/account boundaries, and recovery behavior truthfully.

When a finding is specifically about how many decisions or actions a flow costs, use `.codex/skills/ux-flow-audit/SKILL.md` as the measurement companion. This skill owns lifecycle/state-truth/stale-state/missing-or-redundant UX review; `ux-flow-audit` supplies reproducible KLM/excise cost for before/after comparisons.

## Source-of-truth order

Read only the documents relevant to the target, then compare them with current code.

1. `README.md` for product intent. Verify its stack and behavior claims against `package.json` and the code — the README lists Tailwind/shadcn, while the current UI is plain class-based CSS in `src/styles.css` (no tailwind dependency in `package.json`). Treat stated stack as intent, not fact.
2. `docs/creative-studio-architecture.md`, `docs/next-work-plan.md`, `docs/renderer-plugins.md`, `docs/autograph-template.md`.
3. `docs/incidents/` — evidence of an intentional boundary or a past regression, not a desired UX by itself.
4. Rendered component code: `src/App.tsx`, `src/app-config.ts`, `src/pages/**`, `src/studio/**`, `src/UsagePage.tsx`, `src/EditPage.tsx`.
5. The Tauri command behind each action: the `invoke_handler` list in `src-tauri/src/main.rs`, then the owning module (`jobs.rs`, `accounts.rs`, `usage.rs`, `studio.rs`, `studio_run.rs`, `studio_export.rs`, `studio_templates.rs`, `connections.rs`, `chatgpt_auth.rs`, `ai_chat.rs`, `media.rs`, `pipeline.rs`, `workflows.rs`).
6. Authoritative state: the SQLite schema in `src-tauri/src/database.rs` (`jobs`, `job_events`, `studio_runs`, `usage_records`, `modal_profiles`, `provider_accounts`, `connections`, `connection_tools`, `studio_projects`, …) plus the event path that tells the UI about it.
7. Tests that encode an intentional boundary: `src-tauri/src/tests.rs`, `worker/test_*.py`, `tools/test_renderers.py`.

Do not promote an observation from a fixture, incident, current DB row, or current asset into a product rule. Examples in this codebase:

- 비용은 실제 값과 추정/예산 값을 구분한다 (`docs/next-work-plan.md`). 잔여 크레딧을 직접 조회할 수 없을 때 임의 계산을 실제 값처럼 표시하지 않는다.
- 미디어 길이는 소재/실행 메타데이터에서 온다. 현재 파일 몇 개의 길이를 상수처럼 굳히지 않는다.
- `stale` 노드 상태처럼 코드에 이미 존재하는 상태를 "버그"로 단정하기 전에, 그 상태가 어떤 제품 결정을 표현하는지 확인한다.

## Start with the user journey

For every target, identify the shortest real user journey before reviewing individual controls.

Record:

- goal mode — this is a single-operator tool, so the discipline is naming the goal you measure against: 창작(제작), 운영(계정·비용·연결), 검토(결과 확인·편집·내보내기)
- entry point and surface actually measured — Tauri desktop window, or the `npm run dev` browser preview where `isTauri` gates behavior
- required user decisions
- system-owned preparation or validation
- active/task state
- completion state
- exit/retirement/cleanup state
- error/recovery state
- cross-process propagation the user can observe (worker → app, app → Modal, remote result → local asset)

Then ask for every visible step:

> Is this a real user decision, or did an implementation detail become a screen/button?

If a step exists only because the system performs two operations (job 생성 → 프로필 할당, 렌더 → 다운로드, 실행 → 소재 등록), it should normally remain one user action. Preserve separate steps only when the user must inspect, approve, compare, schedule, or deliberately defer something between them.

## Audit dimensions

### 1. Missing required states, actions, and lifecycle cleanup

Do not audit only for things to remove. Check what must exist for the flow to remain truthful.

For every entity shown in a list or canvas, identify its visibility predicate explicitly:

`created → visible/eligible → active → terminal/expired → removed or archived`

Entities to trace and where their truth lives:

- 작업 (`jobs` + `job_events`): `QUEUED → ASSIGNING → RUNNING → DOWNLOADING → COMPLETED | FAILED | CANCELLED`. Startup calls `jobs::fail_interrupted_jobs` — a job left mid-flight by the previous process can never finish, so it must never stay `RUNNING`.
- 캔버스 실행 (`studio_runs`): uses `isTerminalRun` / `isActiveRun`; startup calls `studio_run::fail_interrupted_runs`. Check `cancel_requested` never lingers as an active row after the worker is gone.
- 프로젝트·소재 (`studio_projects`, `studio_project_revisions`, `studio_assets`): imported vs `source: 'browser'` ephemeral assets; a node's `results` candidate list where the newest result is first — confirm the UI selects a candidate that still exists.
- 노드 상태 (`draft | ready | running | done | stale | failed`): `stale` after an upstream change must be visible or actionable, not silently rendered as `done`.
- 연결 (`connections`, `connection_tools`) and provider accounts (`provider_accounts`, ChatGPT login states): enabled/disabled, login expired, tool disabled, unreachable.
- 사용량 (`usage_records`): 실제 / 추정 / 미확인 / 반영 대기 must be distinguishable; a failed read must preserve the last good value with its timestamp rather than showing 0.

Look for lifecycle defects such as:

- terminal rows that remain in a queue/list as active (`참여 중`-style labels that do not match authoritative state)
- cleanup that depends only on client unmount instead of an authoritative terminal transition
- counters (`runningJobs` per profile, job counts, asset counts) that a terminal transition does not invalidate in the parent list
- missing empty, cancelled, disconnected, permission-denied, expired-login, and recovery states
- a required retry/cancel/continue action that the state model allows but the UI does not offer (see `studio_retry_download`, `studio_cancel_run`)
- orphaned rows a delete did not clean: run rows whose node was removed, assets left by a failed import, revisions after a project delete

Do not solve a lifecycle defect by hiding a stale row in one component while the durable state still affects counts, cost attribution, or later runs. Trace who owns cleanup and whether it is idempotent and recoverable after a crash.

Before accepting any count, badge, or status label, name its exact source and keep these apart: 실행 중 작업 수 (live), 이력 (durable), 대기 행 (queue), 결과 후보 (asset list), 예산 잔여 (user-set budget), 실제 크레딧 (provider-reported). A label must match its source.

### 2. Unnecessary actions and duplicated stages

Look for:

- explicit refresh buttons while the worker event stream already owns the update
- prepare → save → export → import chains that can safely be one primary action
- duplicate submit/confirm controls for the same decision
- secondary actions competing visually with the one action needed to continue
- separate screens for server-owned preparation or validation
- confirmation dialogs for low-risk reversible actions, and missing confirmation on destructive ones (`studio_delete_project`, `connection_delete`, `studio_template_delete`)

Do not remove a boundary solely to reduce clicks. Keep it if it protects a destructive, financial (GPU time and Modal credit), privacy-sensitive, or rule-changing action, or if it is a genuine review/approval decision.

Provider-side data is a legitimate exception: 청구/사용량(`usage::sync_modal_billing`) cannot be pushed by Modal, so an explicit sync may be the user's decision rather than excise. Judge it with the forced/discretion test and present last-synced time and state instead of a permanently pulsing button.

### 3. Redundant copy and explanatory noise

Flag copy when the same fact is repeated by combinations of eyebrow/kicker, page title, section title, explanatory paragraph, empty-state paragraph, badge/status label, or button label.

In this app the recurring smell is canvas chrome narrating itself: panel headers that repeat the sidebar label, helper text explaining that a run is running, notes that restate the node title, and empty states that describe the obvious. Prefer showing the current decision or state over narrating interface behavior. Help text earns its place when it explains consequences, constraints, unfamiliar rules, or recovery — not when it restates the label above it.

### 4. Meaningless visual containers

Inspect card/panel/wrapper nesting in the studio inspector, timeline, chat panel, and the list screens. Remove or flatten containers that provide no grouping, interaction boundary, scrolling boundary, hierarchy, or responsive purpose.

Common smells: a single sentence inside its own bordered card; a button wrapped in a standalone panel for decoration; cards inside cards repeating the same heading; full-page shells that add padding/background but no layout responsibility; permanent status boxes for states that should be exceptional.

Do not flatten structural containers required for focus management, semantic grouping, responsive layout, sticky regions, virtualization, measurement, or canvas viewport clipping.

### 5. Implementation-state leakage

Healthy internal state should usually be invisible.

Flag user-facing items such as:

- job id, `function_call_id`, run id, revision number, asset hash, submission id
- JSONL/sidecar/worker protocol vocabulary, `stage` enum names, `job_events` rows
- `동기화됨`, `실시간 연결`, `온라인` indicators while nothing is degraded
- routine "최신 상태 확인" prompts, cache/reconciliation terminology
- Modal container/GPU preparation phases that require no user action

Show connection or process state only when the user must understand or act on degradation: reconnecting, offline, failed confirmation, stale conflict, retry required, expired login, or read-only fallback. Version numbers belong in an about/debug surface, not the primary chrome (`sidebar-version` is the current case to weigh).

### 6. Realtime and stale-state UX

When the complaint is "늦게 반영된다", do not stop at the component. Trace the complete path:

`user action → Tauri command → SQLite commit → emitted event → React state → render`

In this codebase the fast path is the Tauri event listener (`listenSafely('worker-event', …)` in `src/App.tsx`) fed by the Python worker over the JSONL sidecar, with `listRecentJobs` hydration on startup and per-domain loaders (`src/lib/*.ts`) filling lists. Verify:

- every user-observable transition emits the event that peers and lists need (create, stage change, complete, fail, cancel, download retry)
- terminal transitions invalidate derived labels and parent lists, not just the open detail view
- restart/reconnect reconciliation covers missed events and never leaves an active-looking ghost row
- a background refresh does not visibly replace a usable screen with a loading state
- routine refresh preserves input focus, draft prompt text, scroll position, and canvas viewport
- status text appearing/disappearing does not push primary content (canvas, tables) around during ordinary updates

Durable row wins over optimistic UI. Pending vs committed state must be visually distinguishable, with a defined rollback/reconcile path.

### 7. Truthfulness of shown values (cost, credit, duration, progress)

Check whether the UI shows an estimate as if it were measured, or a stale value as if it were live:

- 실제 크레딧/청구 값 vs 사용자 설정 예산 잔여 vs 추정 사용액 — never merged into one number
- per-job 사용료 before billing reflects it (반영 대기 is a real state, not 0)
- progress/percent or stage labels for a run the process no longer owns
- 클립/샷 길이 from asset metadata rather than an assumed constant

Where a value cannot be known, the honest UI shows the last good value with its timestamp, or an explicit unknown state. Never invent a plausible number.

### 8. Capability- and state-appropriate actions

For each CTA, verify that the current user and state both allow it, and that the reason is visible when it does not.

- actions requiring a selected profile/workspace (`profileId`), a logged-in ChatGPT account, a connected tool, or a downloaded asset must be disabled with a stated reason rather than failing silently
- read-only or preview surfaces (browser dev mode without Tauri, assets with empty `storedPath`) must not offer mutations that cannot work there
- destructive actions need appropriate visual weight and, where the state allows recovery, an undo or retry path
- an action that is technically permitted but contextually nonsensical in the current phase (run a node while another run of that node is active) is a finding

The UI should be derived from capability plus current state, not from route identity alone.

### 9. Content, template, and suggestion quality

For generated or preset content — 템플릿, 스토리보드 자동 분할, 샷 역할, 프롬프트/스타일 프리셋, 모델·렌더러 목록, 채팅 제안 — correctness is not enough. Review whether the produced alternatives preserve the intended context and difficulty.

- storyboard/shot splits should respect the stated role and expected duration instead of drifting
- presets and templates should not silently escape the chosen category or style
- preserve source identity metadata (`kind`, `role`, `expectedSeconds`, `source`, `storedPath`) through preparation and persistence so later stages can make quality decisions; do not discard metadata and approximate it from labels later

### 10. Media and time-based interactions

Do not hardcode media duration or timer behavior from current assets unless an explicit contract fixes it.

Trace: authoritative duration/deadline metadata; autoplay/unlock requirements; background/visibility handling (tab/window hidden during a long run or render); repeat/stop behavior in 결과물; timeline and storyboard synchronization with real clip lengths; what happens when a clip is shorter or longer than its shot's `expectedSeconds`; what the export/render actually uses.

Prefer one coherent task timeline over independent controls when the user does not need to control them separately.

### 11. Loading, recovery, and optimistic state

Distinguish: first load, routine background reconciliation, pending mutation, committed optimistic feedback awaiting acknowledgement, reconnecting, offline, recoverable error, terminal error.

Modal container cold start, model loading, and download time are long real latencies — they need honest stage states with elapsed information, not a fake determinate progress bar and not a spinner that never explains itself. Do not reuse a large first-load skeleton for an ordinary background refresh. Do not claim success before the authoritative confirmation when correctness matters (asset written, row committed, cost attributed).

### 12. Information hierarchy and task focus

Identify the one current task the user should see first. In the canvas studio the node graph is the work; chrome (topbar, navigation, inspector, chat, timeline, storyboard) competes with it. Check whether decorative status, help text, secondary management actions, or permanent panels steal viewport from the active work, and whether the active node/run is visually dominant.

For task-heavy/full-screen flows, navigation may need to collapse or move to overflow when it increases accidental exits or steals space.

### 13. Responsive, input, and accessibility behavior

One desktop surface, but still verify at the sizes the app runs at (default and minimum window, maximized) and between the Tauri window and the Vite browser preview.

Check: clipping and unreachable controls after window resize; keyboard navigation and focus order; focus trapping in dialogs; screen-reader labels on icon-only buttons; long Korean labels; color-only state communication (status dots, node status colors); reduced-motion handling for timeline animation, pulsing indicators, and canvas transitions; contrast of muted metadata text.

Do not mechanically require a specific pixel size on dense domain surfaces where the interaction model intentionally uses a larger composite hit target; inspect the real accessible interaction.

## State-transition review

For stateful features, make a compact transition map before recommending deletions.

Examples of the shapes to write down:

`노드 편집 → 준비(ready) → 실행 요청(queued) → running → downloading → 완료(done) | 실패(failed)`
`작업 생성 → 프로필 할당 → 실행 → 결과 수신 → 결과물 목록 → 편집/내보내기`

Mark each transition with: actor who triggers it, visible CTA, Tauri command, authoritative write, event propagation, what other surfaces show, whether the entity should remain visible in parent lists, and the cleanup/expiry owner plus recovery if the initiating client disappears.

Then list the impossible states the current UI can still render and treat each as a finding:

- 실행 중인데 취소 버튼이 없음
- 완료된 작업이 진행 표시를 유지
- 프로필/계정 미선택 상태에서 실행 가능
- 실패 후 재시도 경로 없음
- 삭제된 노드의 실행 행이 큐에 남음

## Severity

- **P0** — wrong result, cost or account value shown as if measured when it is not, action/state mismatch, terminal or orphaned state presented as active, stale state that breaks the task, data-loss risk, unrecoverable flow, or a misleading confirmation.
- **P1** — repeated friction on a core path, unnecessary required step, confusing competing CTA, frequent layout shift or canvas jump, slow propagation with a manual workaround, or a major hierarchy problem.
- **P2** — redundant explanation, decorative wrapper, minor hierarchy issue, wording duplication, non-blocking polish.

Severity is about user impact, not implementation difficulty.

## Output format

Report findings before editing unless the user explicitly asked for implementation.

For each finding include:

- severity
- screen/state and goal mode measured (창작 / 운영 / 검토) plus surface (Tauri desktop or browser preview)
- concrete UI symptom
- code/component/command/table evidence
- root cause (UI-only, state model, event propagation, contract, persistence, cost attribution)
- recommended user-facing behavior
- whether the fix is local or cross-cutting

Then separate:

1. cross-cutting/platform fixes
2. feature-specific fixes
3. missing essentials / lifecycle integrity fixes
4. safe removals
5. product-rule decisions that must not be guessed

Keep the finding list stable across sessions so later reviews use the same standard; for feature-by-feature cleanup, finish one bounded feature at a time.

## Implementation guardrails

When moving from audit to code:

- preserve authoritative/idempotency boundaries; fix lifecycle ownership at the DB/command layer when stale UI is only the symptom
- do not replace realtime correctness with cosmetic hiding
- do not invent constants from current data (durations, limits, counts, credit values)
- do not silently change cost/account or generation rules without a product decision
- remove obsolete UI and its tests rather than leaving dead alternate flows (check for unrouted leftovers such as `src/Gallery.tsx` before assuming a component is live)
- add regression tests for the user-visible failure that motivated the change
- verify with the project's real checks: `npm run build`, `npm run check:worker`, `npm run check:renderers`, `cargo test --manifest-path src-tauri/Cargo.toml`
- never claim UI verification from a build or test alone; open the actual screen (Vite dev or the Tauri window) and look at it

The goal is not "fewer elements" in isolation. The goal is the smallest interface that accurately exposes the decisions, state, and recovery actions the user actually needs.
