# F16 — Medley Sequencer

**Scope**: Android TV. iOS OOS.

**Purpose** (§2.6.17 / §4.2): verify medley window computation and segment sequencing.

## Formula

```
timeFromBeat(b) = (b × 15) / bpmFile   [seconds]
medleyStartSec = max(0.0, timeFromBeat(medleyStartBeat) − 8)
medleyEndSec   = timeFromBeat(medleyEndBeat) + 2
```

Clamp: if `timeFromBeat(medleyStartBeat) ≤ 8` → `medleyStartSec = 0.0`.

## Expected output

| Song | start (s) | startSec | end (s) | endSec   |
|------|-----------|----------|---------|----------|
| A    | 12.0      | 4.0      | 24.0    | 26.0     |
| B    | 15.0      | 7.0      | 24.0    | 26.0     |
| C    | 12.0      | 4.0      | 21.4286 | 23.4286  |

Tolerance: ±10 ms.

## Guard conditions (inline, not file-driven)

- `medleyStartBeat >= medleyEndBeat` → assertion error
- `audioUrl` null → reject before playlist/start; no `MedleySegment` is produced
- Scan-time: `#MEDLEYSTARTBEAT >= #MEDLEYENDBEAT` → `canMedley=false`
