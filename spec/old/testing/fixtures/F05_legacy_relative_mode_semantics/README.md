# F05 — Legacy RELATIVE mode semantics (<1.0.0)

## Scenario

A legacy song (`#VERSION` absent → treated as 0.3.0) enables `#RELATIVE:YES` and uses the legacy RELATIVE body format. MVP rejects this format as unsupported rather than producing a parsed-song fixture.

## Files

- `song_relative_duet_bpm_rel0/song.txt`
- `song_relative_duet_bpm_rel0/audio.mp3` (empty stub)

Spec covers: tv_app.md §2.4 UsdxParser.
