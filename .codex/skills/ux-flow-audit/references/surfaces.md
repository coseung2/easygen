# Modal GUI surfaces — inventory for flow audits

Everything below is read from the tree, not from memory. Regenerate before trusting an
old line:

```powershell
Get-Content src\app-config.ts            # nav items and their labels
Select-String src-tauri\src\main.rs -Pattern "^\s+\w+::"   # registered Tauri commands
Select-String src-tauri\src\database.rs -Pattern "CREATE TABLE"  # durable tables
```

If an audit report names a surface, match it against this file first. When the tree
changes, update this section in the same change.

## How the app is entered

| Entry | What runs | What is inert |
|---|---|---|
| `npm run dev` | Vite browser preview of the same React app | Everything behind `isTauri` — Tauri commands, file dialog, worker events |
| `npm run tauri dev` | Full desktop app: Rust core, SQLite, Python worker sidecar | — |

Desktop runtime facts: SQLite lives at the app data dir (`database/app.db`), the studio
root comes from `paths::studio_root()`, and ChatGPT secrets live under the app data
dir's `secrets/`. Startup calls `jobs::fail_interrupted_jobs`,
`studio_run::fail_interrupted_runs`, and `workflows::seed_default_workflows`.

## Screens

Sidebar order and labels (`src/app-config.ts` → `navItems`, rendered in `src/App.tsx`):

| Page id | Label | Component |
|---|---|---|
| `Studio` | 제작 스튜디오 (default) | `src/studio/StudioPage.tsx` |
| `Generate` | 새 작업 | `src/pages/GeneratePage.tsx` |
| `Jobs` | 작업 큐 | `src/pages/JobsPage.tsx` |
| `Edit` | 편집 · 모션 | `src/EditPage.tsx` |
| `Results` | 결과물 | `src/pages/ResultsPage.tsx` |
| `Usage` | 사용량 | `src/UsagePage.tsx` |
| `Connections` | 연결 관리 | `src/pages/ConnectionsPage.tsx` |
| `Settings` | 설정 | `src/pages/SettingsPage.tsx` |

`src/Gallery.tsx` exists but is not routed — treat it as dead until proven live, and
report it as an obsolete-surface candidate rather than a working screen.

## Studio panels (`src/studio/`)

`StudioPage.tsx` hosts the canvas; `StudioHome.tsx` is the project list. Panels and
their owners:

| Panel | File | What it shows |
|---|---|---|
| Node palette / projects | `LeftPanel.tsx` | node kinds, creation |
| Inspector | `Inspector.tsx` | node config, results, run controls (largest surface) |
| AI chat | `ChatPanel.tsx` + `chatDelivery.ts` | conversation with the local AI session |
| Timeline | `TimelinePanel.tsx` | time-based assembly |
| Storyboard | `StoryboardBar.tsx` | shot list and selected assets |
| Node rendering | `NodeCard.tsx` | per-node status and ports |

Logic: `store.ts` (projects, document, runs), `runController.ts` (run lifecycle),
`graph.ts` (ports/validation), `catalog.ts` (node/tool catalog), `templates.ts`,
`toolInput.ts`, `lib.ts`, `types.ts`.

## Command domains (`src-tauri/src/`)

| Module | Responsibility |
|---|---|
| `jobs.rs` | create/start/list jobs, mark interrupted jobs failed |
| `accounts.rs` | Modal profiles: list, save, enable, archive |
| `usage.rs` | usage rows, billing sync, studio usage summary |
| `media.rs` | thumbnails, generated clips/silence, JSON read/write, reveal in explorer |
| `pipeline.rs` | audio analysis, trailer/spec render, storyboard build, renderer list |
| `studio.rs` | project list/create/load/save/delete, asset import, path probe |
| `studio_run.rs` | node runs: start, local start, finish, list, retry download, cancel |
| `studio_export.rs` | project export/import |
| `studio_templates.rs` | template list/save/delete |
| `connections.rs` | MCP-style connections, tools, enable toggles, test, call tool |
| `chatgpt_auth.rs` | ChatGPT login flow, accounts, logout, token refresh |
| `ai_chat.rs` | AI session, send/interrupt/status, conversations, messages |
| `workflows.rs` | workflow definitions list/save/delete |

## Durable state (`src-tauri/src/database.rs`)

`modal_profiles`, `jobs`, `job_events`, `usage_records`, `studio_projects`,
`studio_project_revisions`, `studio_assets`, `studio_runs`, `connections`,
`connection_tools`, `provider_accounts`, `conversations`, `messages`,
`workflow_definitions`, `studio_templates`.

## Background owners and the realtime path

- Python worker: `worker/main.py`, `worker/job_runner.py`, `worker/protocol.py`,
  `worker/billing.py`, `worker/profile.py`. It speaks JSONL to the app; its tests are
  `worker/test_*.py` (`npm run check:worker`).
- Canvas runs and generated assets are owned by `studio_run` on the Rust side, not by
  the open panel.
- User-visible updates arrive as a Tauri event: `worker-event`, consumed in
  `src/App.tsx` through `listenSafely` (`src/lib/listen.ts`). Startup and list
  hydration go through the loaders in `src/lib/` (`jobs.ts`, `usage.ts`,
  `connections.ts`, `chat.ts`, `chatgpt.ts`, `motion.ts`, `pipeline.ts`,
  `workflows.ts`, `tauri.ts`).

## State vocabularies (do not paraphrase these in reports)

- `JobStatus`: `QUEUED | ASSIGNING | RUNNING | DOWNLOADING | COMPLETED | FAILED | CANCELLED`
- `JobStage`: `JOB_CREATED | PROFILE_ASSIGNED | INPUT_UPLOADING | CONTAINER_STARTING | GPU_READY | MODEL_LOADING | MODEL_READY | PREPROCESSING | GENERATING | MUSIC_GENERATING | AUDIO_DOWNLOADING | ENCODING | SAVING | RESULT_DOWNLOADING | COMPLETED`
- `JobKind`: `t2v | fl2v | ref2v | music`
- Studio `NodeStatus`: `draft | ready | running | done | stale | failed`
- Run status: `queued | running | downloading | completed | prepared | cancel_requested | failed | cancelled` (labels in `RUN_STATUS_LABELS`; `isTerminalRun` / `isActiveRun`)
- `NodeKind`: `asset | brief | moodboard | storyboard | prompt | image | video | design | comfy | motion | typo | audio | select | edit | export | tool`

## Checks

```powershell
npm run build                                  # tsc -b && vite build
npm run check:worker                           # python -m unittest discover -s worker
npm run check:renderers                        # python -m unittest tools.test_renderers
cargo test --manifest-path src-tauri\Cargo.toml
```

Passing checks are not visual verification. A UI claim needs the actual screen.
