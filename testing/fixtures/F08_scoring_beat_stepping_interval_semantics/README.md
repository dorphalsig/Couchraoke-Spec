# F08 — Scoring beat window evaluation (deadline-driven model)

**Purpose**: verify ScoringEngine correctly evaluates note active windows in deadline-driven model (§4.3).

**Scenario**:
- Single Normal note from beat 0 with duration 2 (active for beats in `[0, 2)`)
- Pitch frames arrive with monotonically increasing `deadlineBeatsD` values (0, 1, 2)
- Verify note is scored only when its deadline window overlaps the pitch frame's reported beat range

**Model** (§4.3):
- Each pitch frame reports `deadlineBeatsD` = beat position of the current playback deadline
- A note is in-window if its active beat range `[startBeat, endBeat)` overlaps with the deadline's observation window
- Notes are scored once per frame; duplicate scoring is prevented by frame staleness checks (§2.2 T5.2.3)

**Test coverage** (§2.2 T6.1.1):
- `case_perfect`: note active, pitch valid → full score
- Frame sequence: deadline at 0.5, 1.5, 2.5 beats — verify note transitions from in-window → out-of-window

**Files**:
- `song.txt` — single Normal note (beat 0, duration 2)
- `pitchFrames.jsonl` — three frames with increasing deadlineBeatsD
- `expected.score.json` — scoreTotalInt (perfect score on this single note)
