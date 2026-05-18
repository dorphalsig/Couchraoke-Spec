# F19_icloud_eviction_ios

## Spec Sections Covered
["phone_app.md §2.2", "phone_app.md §3.2"]

## Purpose
Tests iOS companion behavior when a required playback asset is evicted from local storage but remains in iCloud. The song is invalid and must not be published in `/manifest.json`.
Covers phone_app.md §2.2 iCloud Drive Files and the shared manifest non-null `audioUrl` rule.

## Files
- `bohemian.txt`: Sample song chart.
- `cover.jpg`: Sample cover art.
- `expected.discovery.json`: Expected invalid discovery outcome under eviction scenarios.
