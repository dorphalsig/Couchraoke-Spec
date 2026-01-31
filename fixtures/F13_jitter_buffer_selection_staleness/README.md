# F13 — Jitter-buffer selection + staleness

Purpose: verify Section 9.1 receiver-side pitch selection behavior:
- select the most recent pitch frame with `tvCaptureMs <= tvNowMs`
- if the newest eligible frame is stale by more than 200 ms, treat pitch as missing (`toneValid=false`) for that beat

This fixture assumes `clockOffsetMs=0` so `tvCaptureMs = tCaptureMs`.

Files:
- pitchFrames.jsonl
- expected.selection.json
