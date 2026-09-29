# H3 attention comparison startup failure

- Date/timezone: 2026-09-29, Asia/Seoul.
- Symptoms: The isolated Alan Turing rotor A/B Modal run failed while starting ComfyUI. `main.py` rejected `--user-directory /tmp/h3-compare-user` because that directory did not exist. The Modal class lifecycle raised `RuntimeError: ComfyUI stopped during startup`.
- Impact: No comparison video was generated; the intended Sage+Sol and Kitchen+Sol results remain unverified. GPU startup time may have been metered; actual attributed cost has not been verified. Production H3 deployment and source clips were unchanged.
- Timeline: After static graph checks, the approved two-variant run was submitted once. ComfyUI exited before accepting a prompt. The run was interrupted to avoid further paid work, then the missing-directory setup was corrected locally.
- Evidence: Modal run `ap-l7znTY1mZ4AwYiI2E0MVGk` showed the `--user-directory` argument error and lifecycle failure. No comparison manifest or output clips were created.
- Confirmed cause: The Lab startup script created temporary input/output directories but not its ComfyUI user directory.
- Response/recovery: The script now creates the user directory before launch. Python compilation and both static graph checks pass, but GPU startup and generation have **not** been reverified. The experiment App was stopped with zero tasks. No automatic retry is authorized.
- Prevention/follow-up: Check all ComfyUI path preconditions before a paid call; request a new bounded authorization before rerunning the comparison, then inspect video outputs and metered usage separately.
