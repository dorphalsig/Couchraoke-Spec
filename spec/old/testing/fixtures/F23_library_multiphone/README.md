# F23 — Library aggregation across multiple phones

**Platform scope**: TV-side (Android TV only).

Purpose: verify manifest aggregation, sorting, disconnect removal, and refresh-replaces semantics for the TV song library.

## Files

- `phone_a_manifest.json`
- `phone_b_manifest.json`
- `case_both_connected/expected.library.json`
- `case_phone_a_disconnects/expected.library.json`
- `case_refresh_replaces/phone_a_manifest_v2.json`
- `case_refresh_replaces/expected.library.json`

## Validation rules covered

- Two connected phones contribute songs to one merged library
- Sort order is Artist → Album → Title
- Disconnect removes all songs for that phone immediately
- Refresh replaces prior songs for that phone instead of appending

Spec covers: §3.1.3, §3.2, §3.3
