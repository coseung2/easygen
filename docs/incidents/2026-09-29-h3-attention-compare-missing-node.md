# H3 attention comparison missing core node

- Date/timezone: 2026-09-29, Asia/Seoul.
- Symptoms: Both approved A/B attempts stopped before sampling with `Missing node: BlockSparseAttention`.
- Impact: No new rotor video was produced and Sage+Sol versus Kitchen+Sol remains unverified. GPU startup time may have been metered; actual attributed cost is unknown. The production H3 app and Turing v6/v7 outputs were unchanged.
- Timeline: The isolated run `ap-8Zdf1oFHZU8qeDuT3nr715` started ComfyUI 0.31.0 on an L40S. Sage reported the missing node after approximately 28 seconds of local wall time; Kitchen immediately reported the same missing node on the warm container. The run completed without a video. No further GPU generation was attempted.
- Evidence: Modal logs report ComfyUI 0.31.0 and the missing node. The Lab manifest records both failed variants and contains no output path.
- Confirmed cause: The experiment reused the older H3 base image, while the saved workflow's native `BlockSparseAttention` node requires a newer ComfyUI.
- Response/recovery: Only the isolated Lab image was changed to pinned ComfyUI v0.37.0; a CPU-only ComfyUI registration check confirmed `BlockSparseAttention`, `ModelAttentionBackend`, and the Sage patch node. A separately approved GPU run reached sampling in both variants, and Kitchen+Sol produced a decodable MP4. The missing-node condition is resolved for this isolated image; Sage's subsequent CUDA failure is recorded separately. The Lab runner now stops early if a shared native node is missing.
- Prevention/follow-up: Run CPU-only node registration checks before paid A/B calls. Verify actual billing separately; a registered node does not prove its GPU kernel is compatible.
