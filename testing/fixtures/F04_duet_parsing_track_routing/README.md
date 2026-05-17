# F04 — Duet parsing track routing

Validates duet marker handling and P1/P2 note routing.

## Cases

- `valid_duet_interleaved/` contains an interleaved duet chart and `expected.parsedSong.json` to assert track routing.
- `invalid_duet_marker_p3/` asserts that unsupported player markers are rejected.

Spec covers: tv_app.md §2.4 UsdxParser.
