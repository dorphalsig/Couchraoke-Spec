# F13 — Jitter-buffer selection + staleness

Purpose: verify §5.2.3 receiver-side pitch selection:
- select the most recent frame where `tvTimeMs <= detectionTimeTvMs`
- if the newest qualifying frame is stale by >120ms, treat pitch as `toneValid=false`

**Note (spec v4.19)**: field was renamed from `tCaptureMs` / `tvCaptureMs` → `tvTimeMs`
throughout this fixture to match §8.3 and §5.2.2 normative naming.

**Platform scope**: TV-side (Android only). iOS companion does not run jitter-buffer logic.

Assumes `clockOffsetMs=0` so `tvTimeMs` values map directly to TV time.

## Files
- `pitchFrames.jsonl` — 3 frames used as the jitter buffer seed
- `expected.selection.json` — expected selection result per `tvNowMs` sample

Spec covers: §5.2.3, §9.1
