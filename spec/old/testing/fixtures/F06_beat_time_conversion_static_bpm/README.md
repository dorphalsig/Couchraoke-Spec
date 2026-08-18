# F06 — Beat/time conversion: static BPM

Purpose: verify Section 5.1–5.2 static-BPM formulas for `CurrentBeat` (highlight) and `CurrentBeatD` (scoring).

Harness assumptions (repo convention for this fixture):
- `lyricsTimeSec` samples below are interpreted as the song timeline in seconds where `lyricsTimeSec=0` is audio start.
- No clock-sync offset is involved (pure timing math).

Files:
- `song.txt`: minimal chart providing BPM/GAP.
- `expected.beat_cursors.json`: deterministic expected cursor values at selected `lyricsTimeSec` samples.
