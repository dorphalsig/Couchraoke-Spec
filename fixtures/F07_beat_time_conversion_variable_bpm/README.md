# F07 — Beat/time conversion: variable BPM with clamp

Purpose: verify Section 5.2 variable-BPM segment walk and the clamp behavior `tSec <= 0 => MidBeat_internal = 0`.

This fixture is derived from Appendix E.2.

Harness assumptions (repo convention for this fixture):
- `lyricsTimeSec` samples are interpreted as the song timeline in seconds where `lyricsTimeSec=0` is audio start.
- No clock-sync offset is involved (pure timing math).

Files:
- `song.txt`: minimal chart containing a header BPM and a `B` BPM change line.
- `expected.beat_cursors.json`: expected conversion results, including the clamp case.
