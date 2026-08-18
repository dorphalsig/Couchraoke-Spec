# F21 — Clock Sync (TV-side)

**Platform scope**: TV-side (Android TV only).

Purpose: verify TV-side NTP-lite processing of `ping`/`pong` samples, including RTT calculation, offset calculation, invalid-sample rejection, and best-of-N selection.

## Formulas

```text
rttMs         = (t4 - t1) - (t3 - t2)
clockOffsetMs = ((t1 - t2) + (t4 - t3)) / 2
```

## Files

- `case_normal_5_samples/ping_pong_sequence.json` / `expected.clockSync.json`
- `case_all_invalid_rtt/ping_pong_sequence.json` / `expected.failure.json`
- `case_best_of_n_selection/ping_pong_sequence.json` / `expected.clockSync.json`

## Validation rules covered

- Keep last 5 samples
- Discard samples with `rttMs < 0` or `rttMs > 2000`
- Choose the sample with the smallest valid RTT
- Fail if no valid samples remain

Spec covers: tv_app.md §4.5, tv_app.md Appendix B.2.3–B.2.4
