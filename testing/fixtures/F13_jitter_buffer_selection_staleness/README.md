# F13 — Jitter buffer insert validation and range query

**Spec refs**: §4.4 (JitterBuffer), §2.2 T5.2.3.4–7

Tests that the jitter buffer correctly enforces the three insert-time drop
conditions and that `getFramesInWindow` returns exactly the surviving frames
whose `tvTimeMs` falls within the requested note window.

## Model

Frames are inserted one at a time in the order listed in `input.frames.jsonl`.
Each insert evaluates three drop conditions (§4.4):

1. **Lateness**: `latenessMs = arrivalTvMs − tvTimeMs > 450` → drop silently
2. **Decreasing seq**: `frame.seq ≤ lastAcceptedSeq` (per-player) → drop
3. **tvTimeMs regression**: `lastAcceptedTvTimeMs − frame.tvTimeMs > 200` → drop

After all inserts, call `getFramesInWindow(playerId, startTvMs, endTvMs)`.
The query additionally filters: `frame.tvTimeMs ∈ [startTvMs, endTvMs)` AND
`arrivalTvMs − tvTimeMs ≤ 450`. Expected output is in
`expected.window_query.json` as a set of `seq` values (order is unspecified).

## Sub-cases

| Sub-case | Covers | Spec test |
|---|---|---|
| `case_lateness_drop` | Frame with latenessMs > 450 excluded at insert | T5.2.3.4 |
| `case_seq_drop` | Frame with seq ≤ lastAcceptedSeq dropped | T5.2.3.5 |
| `case_regression_large_drop` | tvTimeMs regression > 200 ms dropped | T5.2.3.6 |
| `case_regression_small_accept` | tvTimeMs regression ≤ 200 ms accepted | T5.2.3.7 |

## Fields (all frames)

- `seq` — uint32 sequence counter
- `tvTimeMs` — TV-side capture timestamp (ms)
- `arrivalTvMs` — TV-side arrival timestamp (ms); `latenessMs = arrivalTvMs − tvTimeMs`
- `midiNote` — 0–127 voiced; 255 unvoiced
- `playerId` — 0 = P1, 1 = P2
- `songInstanceSeq` — matches active song (1 throughout this fixture)
- `connectionId` — uint16; matches expected connection (1 throughout)

Assumes `clockOffsetMs = 0` so `tvTimeMs` values are directly comparable to TV time.
