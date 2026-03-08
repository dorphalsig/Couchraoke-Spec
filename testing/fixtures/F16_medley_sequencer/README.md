# F16 — Medley Sequencer

**Platform scope**: Android TV only. iOS does not implement the medley sequencer.

Purpose: verify §12 medley window computation and segment sequencing.

## Beat-to-time formula

```
timeFromBeat(b) = (b × 15) / bpmFile   [seconds]
```

(Derivation: USDX internal beat = 1/4 of a quarter note at bpmFile BPM,
so period = 60 / (bpmFile × 4) s; timeFromBeat = b × period.)

## Window formula

```
medleyStartSec = max(0.0, timeFromBeat(medleyStartBeat) − 8)   // 8s pre-roll
medleyEndSec   = timeFromBeat(medleyEndBeat) + 2               // 2s tail
```

Clamp rule: if `timeFromBeat(medleyStartBeat) ≤ 8` → `medleyStartSec = 0.0`.

## Files

- `medley_queue.json` — 3-song queue (input)
- `expected.medleySegments.json` — expected `medleyStartSec` / `medleyEndSec` per song

## Expected values

| Song | timeFromBeat(start) | medleyStartSec | timeFromBeat(end) | medleyEndSec |
|------|---------------------|----------------|-------------------|--------------|
| A    | 12.0 s              | 4.0 s          | 24.0 s            | 26.0 s       |
| B    | 15.0 s              | 7.0 s          | 24.0 s            | 26.0 s       |
| C    | 12.0 s              | 4.0 s          | 21.4286 s         | 23.4286 s    |

Assertion tolerance: ±10 ms.

## Guard conditions tested (inline, not file-driven)

- `medleyStartBeat >= medleyEndBeat` → `IllegalStateException`
- `audioUrl` null at playback → skip segment, continue
- Scan-time: `#MEDLEYSTARTBEAT >= #MEDLEYENDBEAT` → `canMedley=false`

Spec covers: §12, §3.3
