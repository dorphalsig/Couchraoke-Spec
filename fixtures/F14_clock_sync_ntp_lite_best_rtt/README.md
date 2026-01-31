# F14 — Clock sync NTP-lite (best-of-N by RTT)

Purpose: verify Section 9.1.1:
- compute rttMs and offsetMs per sample
- select the sample with the smallest rttMs as clockOffsetMs

Files:
- clockSync.jsonl: pong samples (t1..t4)
- expected.clockSync.json: per-sample computed values and expected selected clockOffsetMs
