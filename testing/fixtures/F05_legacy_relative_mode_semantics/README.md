# F05 — Legacy RELATIVE mode semantics (<1.0.0)

Covers Appendix F / F05.

## Scenario

A legacy song (`#VERSION` absent → treated as 0.3.0) that enables `#RELATIVE:YES` and exercises:

- per-track RELATIVE running offsets via `- <startBeat> <delta>` sentence lines
- duet track switching while preserving each track's independent RELATIVE offset state

## Files

- `song_relative_duet_bpm_rel0/song.txt`
- `song_relative_duet_bpm_rel0/expected.parsedSong.json`
- `song_relative_duet_bpm_rel0/audio.mp3` (empty stub)
