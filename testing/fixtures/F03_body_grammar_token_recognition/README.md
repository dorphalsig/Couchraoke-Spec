# F03 — Body grammar: token recognition + invalidation rules

## Purpose

Validates parser handling for supported body tokens, unknown-token warnings, malformed numeric fields, and Freestyle scoring behavior.

## Discovery/index cases

A harness should recursively discover `song.txt` files under `songs_root/`, validate them with the current UsdxParser rules, and compare deterministic results to `expected.discovery.json`.

For valid songs, this fixture asserts a minimal deterministic body summary:
- `bodySummary.track0.noteTypeCounts`

## Scoring subcases

- `scoring/mixed_normal_freestyle/` asserts that Normal notes score normally while Freestyle notes contribute 0.
- `scoring/all_freestyle/` asserts that a chart with only Freestyle notes yields `scoreTotalInt == 0`.

Each scoring subcase is self-contained with `song.txt`, `pitchFrames.jsonl`, and `expected.score.json`. `mixed_normal_freestyle` also includes `expected.parsedSong.json` to lock the parsed model projection used by the scoring tests.

Spec covers: tv_app.md §2.4 UsdxParser and §2.2 ScoringEngine.
