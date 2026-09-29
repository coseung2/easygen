# Controlled H3 A/B benchmark duplicate submission

- Date/timezone: 2026-09-29, Asia/Seoul.
- Symptoms: A preliminary baseline call was submitted twice after the first command returned no visible output. The two downloaded files have identical SHA-256 and the same remote output path.
- Impact: The preliminary run is excluded from the controlled benchmark. It may have added an unseparable production-app charge. The controlled benchmark itself used separate apps with persisted call IDs and no duplicate submissions.
- Evidence: Preliminary files `baseline.mp4` and `baseline-2.mp4` share SHA-256 `7f5fe9e57b648288417c9fe0a8aac1b8f8acbbc5a3f74cd324ecd659cb10c4d6`. Controlled apps: baseline `ap-3dDf6E4Bngwh8MqnVB5PYf`, Kitchen `ap-9ddPadPx2sJNxFTFLuYLz6`.
- Response: Added persisted submission locks and ran the controlled baseline/Kitchen apps independently. Results are recorded under `F:\modal-gui\lab\2026-09-29-h3-controlled-ab\production.json`.
- Follow-up: Treat preliminary app charges as unattributed; use only controlled app costs for the decision.
