# F08 — Scoring deadline/window evaluation

**Purpose**: verify ScoringEngine finalizes a simple note using the current deadline-driven, range-query scoring model.

## Scenario

- Single Normal note from beat 0 with duration 2; active window is `[0, 2)`.
- Pitch frames are timestamped in TV monotonic time and selected by the jitter buffer with `noteStartTvMs <= tvTimeMs < noteEndTvMs`.
- The note is finalized once the scoring coroutine reaches `noteEndTvMs + 450ms`; all qualifying frames are evaluated once.

## Files

- `song.txt` — one Normal note followed by sentence break.
- `pitchFrames.jsonl` — two qualifying voiced frames for P1.
- `expected.score.json` — deterministic score breakdown for a perfect hit on the single note.

Spec covers: tv_app.md §2.2 ScoringEngine, §4.3 Scoring Coroutine, §4.4 Jitter Buffer.
