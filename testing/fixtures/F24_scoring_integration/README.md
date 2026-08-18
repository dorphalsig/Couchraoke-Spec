# F24 — Scoring integration (frames → score)

**Platform scope**: TV-side (Android TV only).

Purpose: verify end-to-end scoring integration from chart + accepted pitch frames through note finalization and final score output.

## Files

- `chart.txt`
- `pitch_frames_perfect.json`
- `pitch_frames_partial.json`
- `pitch_frames_silence.json`
- `expected.score_perfect.json`
- `expected.score_partial.json`
- `expected.score_silence.json`

## Scenarios

- `perfect`: every note window gets fully matching voiced frames → `scoreTotalInt = 10000`
- `partial`: mixed hits/misses and unvoiced samples → partial score
- `silence`: all frames unvoiced → `scoreTotalInt = 0`

Spec covers: tv_app.md §2.2, tv_app.md §4.3–§4.4, tv_app.md Appendix C
