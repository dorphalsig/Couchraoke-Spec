# F02 — Header parsing edge cases

This is a discovery/index fixture with a small `songs_root/` tree containing multiple single-song subcases.

A harness should:
1. Recursively discover `song.txt` files under `songs_root/`.
2. Load and validate each song according to the current UsdxParser and LibraryManager rules.
3. Compare deterministic results to `expected.discovery.json`.

## `expected.discovery.json` (repo convention)

In addition to the required fields (`isValid`, `invalidReasonCode`, `invalidLineNumber`), this fixture asserts deterministic header outcomes for valid songs:

- `header.title`
- `header.artist`
- `header.version`
- `header.bpmFile`
- `header.audioResolved`
- `derived.previewStartSec`
- `header.customTagsOrdered` (ordered list of `{name,value}` pairs, matching the current CustomTags representation)

Invalid songs omit `header`/`derived` fields and only assert validity plus diagnostics.
