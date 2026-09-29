# H3 Sage attention kernel failure on L40S

- Date/timezone: 2026-09-29, Asia/Seoul.
- Symptoms: The Sage+Sol branch reached H3 sampling, then failed at step 0/4 with `CUDA error: no kernel image is available for execution on the device`.
- Impact: No Sage comparison clip was produced, so relative speed and visual quality versus Kitchen cannot be measured. The separately approved Kitchen+Sol branch produced one 5.17-second MP4. Production H3 deployment was unchanged. Actual attributed cost is unknown.
- Timeline: In isolated Modal run `ap-rCKcxYozhPnigd0iIr3Mix`, ComfyUI 0.37.0 registered the nodes and applied the MiniMax H3 Sage patch. The Sage sampler failed; the next and final approved call with Kitchen+Sol completed. Both calls were on an L40S, same prompt, input, seed and workflow except for the dense attention node.
- Evidence: The Sage traceback passes through `sageattention/quant.py` and reports `cudaErrorNoKernelImageForDevice`. Lab manifest records the failure and Kitchen success. Kitchen MP4 passed ffprobe and a full decode check.
- Confirmed cause: The installed SageAttention path could not launch its CUDA kernel on this L40S run. The exact wheel/build architecture mismatch is not yet confirmed.
- Response/recovery: No retry or production switch was made. The experiment App stopped with zero tasks; the Kitchen output was retained for review.
- Prevention/follow-up: Pin and verify SageAttention wheel architecture before another Sage benchmark, or compare Kitchen against a known working dense baseline under a newly approved plan. Do not claim Kitchen is faster or visually superior based on this asymmetric result.
