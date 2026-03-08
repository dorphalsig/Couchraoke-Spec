# F10 — Rap scoring: presence-only gated by toneValid

Purpose: verify:
- Rap (`R`) ignores pitch difference (presence-only) but STILL requires `toneValid=true` to score (Section 6.2, Section 9.1).

Scenario:
- One Rap note (duration 4 beats) active for beats 0..3.
- Beats 0–1 have `toneValid=true` => score.
- Beats 2–3 have `toneValid=false` => no score.
