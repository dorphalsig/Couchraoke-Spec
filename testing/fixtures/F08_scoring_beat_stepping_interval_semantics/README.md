# F08 — Scoring beat stepping correctness (interval semantics)

Purpose: verify:
- beats are evaluated in `(oldBeatD, currentBeatD]` (Section 6.1; Appendix E.1)
- note active window uses `startBeat <= b < endBeat` (Section 5.2 boundary convention; Appendix E.3)

Scenario:
- single Normal note from beat 0 with duration 2 (active at beats 0 and 1; not active at beat 2).
- scoring timeline advances so that beats 0, 1, then 2 are evaluated.

Files:
- `song.txt`
- `pitchFrames.jsonl`
- `expected.score.json`
