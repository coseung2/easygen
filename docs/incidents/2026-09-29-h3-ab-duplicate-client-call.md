# H3 A/B baseline client call duplicated

- Date/timezone: 2026-09-29, Asia/Seoul.
- Symptoms: The first `run_h3_job.py` command returned no visible output while the remote job was still in progress. The same command was submitted again. Two local files and two manifest entries were created.
- Impact: The approved one-call baseline scope was exceeded at the client-call level. Both files have the same SHA-256 and refer to the same remote output `PUBG/ref2v_00057-audio.mp4`; whether Modal deduplicated generation or another invocation incurred usage cannot be established from these records alone. Kitchen was not rerun. No production code or prior clips were changed.
- Timeline: A baseline request was submitted using Turing `r2-rotors` input, 5 seconds, 768×1344, seed 21702. Without confirming its session state, an identical request was submitted. Both returned success and wrote `baseline.mp4` and `baseline-2.mp4`. The duplicate was discovered from the manifest and hashes, and further GPU calls were stopped.
- Evidence: Both manifest records have the same job ID, remote output path, prompt and seed. Both local MP4 hashes are `7f5fe9e57b648288417c9fe0a8aac1b8f8acbbc5a3f74cd324ecd659cb10c4d6`. Modal's 17:00 hourly billing bucket for the shared production H3 app totals $0.12546921 across CPU, memory and L40S, but is not per-call attribution.
- Confirmed cause: The agent resubmitted before resolving the status of the first command. Exact remote invocation count remains unconfirmed.
- Response/recovery: No Kitchen call was made under this approval. Both copies and their manifest were preserved. The experiment App was not changed; no comparison win or per-clip cost is claimed.
- Prevention/follow-up: Retain and poll the returned command session before deciding a call is lost; use a unique idempotency key or exact remote result check before any retry. A fresh bounded A/B approval and isolated cost tagging would be needed for an operational cost decision.
