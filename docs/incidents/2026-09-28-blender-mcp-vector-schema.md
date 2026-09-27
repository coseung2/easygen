# Blender MCP vector schema mismatch

- Date/time: 2026-09-28, Asia/Seoul
- Impact: Initial iron-ball scene construction calls were rejected; no user data was lost or generation credits spent.

## Symptoms and evidence

- Tool declarations exposed location, scale and resolution as arrays of strings, while runtime validation required numbers: `expected number, received string`.
- A dependent camera setup consequently failed because the scene had no camera. Fresh scene inspection confirmed zero objects before recovery.

## Confirmed cause

- Exposed declarations and runtime vector validation disagree. Dependent calls also continued after validation failure.

## Response and recovery verification

- Inspected state, submitted numeric arrays, and successfully constructed the scene.
- Viewed opening, descending and settled renders; verified baked rigid-body motion and saved `F:/modal-gui/lab/2026-09-28-iron-ball-test/iron-ball-test.blend`.

## Follow-up

- Correct connector declarations to numeric arrays. Until corrected, use numeric vectors and stop dependent operations when a prerequisite fails.
