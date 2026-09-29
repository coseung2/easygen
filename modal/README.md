# H3 worker boundary

`app.py` is the only H3 Modal deployment boundary. The checkpoint and its license/source must be pinned before enabling GPU generation. The desktop app must never call a MiniMax API or scrape the Modal web UI.

`qwen_image21.py` is an independent, private research/evaluation deployment for
Qwen-Image 2.1. It is not connected to the desktop app or a released pipeline.
The Comfy-Org weights retain the Qwen Research License: commercial use needs a
separate license. Run `modal run modal/qwen_image21.py::download_weights` before
`modal deploy modal/qwen_image21.py`. Its GPU function is called only through
the authenticated Modal SDK; no public web endpoint is exposed.
