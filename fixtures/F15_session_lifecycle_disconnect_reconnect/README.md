# F15 — Session lifecycle: hello/assignSinger + disconnect/reconnect

This fixture is split into deterministic subcases (Appendix F.5.15).

## Files and conventions

- `transcript.jsonl` / `expected.session.json`: **current repo convention** (Appendix F.4.4)
- `transcript.legacy.jsonl` / `expected.outcome.legacy.json`: kept for backward compatibility with an earlier transcript schema

## Subcases

- `case_reconnect_reclaim/` — disconnected client reclaims its singer slot by stable `clientId`; third client is rejected.
- `case_slot_taken/` — host kicks the disconnected client (`tv_internal` event); a third client joins and takes the free slot; original client is rejected.
