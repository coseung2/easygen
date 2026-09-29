# h3-refvideo

## 1.0 — candidate, 2026-09-28

Separate `h3-refvideo-v1` deployment derived from the legacy H3 worker and current R2V graph.
Connect an explicit reference video to both conditioning stages through `VHS_LoadVideoPath`.
Optional reference images remain independent; video-only mode removes the unused image loader.
Graph preparation checks sealed file hashes, paths, dimensions and explicit `<Video 1>` prompt tagging.
Legacy deployment and mutable volume workflows remain unchanged.

Local tests and deployment are not evidence of generated motion adherence. GPU inference,
comparison against a fixed Blender guide, runtime model hashes, cost recording and user acceptance
remain required before release. Four seconds rounds to 107 generated frames at 24fps (4.458s);
the guide is sampled at 24fps without speed changes, and a delivery trim must be explicit.
