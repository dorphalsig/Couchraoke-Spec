# F14v2 — Clock Sync (NTP-lite, Phone-side)

Replaces: `F14_clock_sync_ntp_lite_best_rtt` (retired in spec v4.19).

**Why replaced**: F14 used verbose field names (`tTvSendMs`, `tPhoneRecvMs`, etc.) matching
an older pong schema. F14v2 uses the compact `t1`–`t4` / `pingId` naming aligned with
phone_app.md §2.5 and tv_app.md Appendix B.2.3–B.2.4 message schema.

The numeric values are identical to F14; only field names changed.

**Platform scope**: shared — both Android and iOS companion apps compute `clockOffsetMs`.

## Field mapping (TV initiates ping)

| Field | Clock    | Meaning                        |
|-------|----------|--------------------------------|
| t1    | TV       | TV sends ping                  |
| t2    | Phone    | Phone receives ping            |
| t3    | Phone    | Phone sends pong               |
| t4    | TV       | TV receives pong / sends clockAck |

## Formulas (phone_app.md §2.5 / tv_app.md §4.5)

```
rttMs         = (t4 - t1) - (t3 - t2)
clockOffsetMs = ((t1 - t2) + (t4 - t3)) / 2
```

`clockOffsetMs` is TV monotonic time minus phone monotonic time.
A positive value means the phone clock is behind the TV clock.

## Files
- `clockSync.jsonl` — 3 ping/pong tuples
- `expected.clockSync.json` — per-sample RTT + offset, and the chosen (lowest-RTT) sample

## Worked values

| pingId | rttMs | clockOffsetMs |
|--------|-------|---------------|
| a1     | 40    | 500.0         |
| a2     | 180   | 490.0         |
| a3     | 30    | 500.0 ← chosen |

Spec covers: phone_app.md §2.5, tv_app.md Appendix B.2.3–B.2.4
