# F15 — Session lifecycle: hello/assignSinger + disconnect/reconnect

Updated in spec v4.19: `assignPlayer` removed; `hello` now includes `httpPort`;
`sessionState` (carrying `connectionId`) replaces `assignPlayer` as the TV's response
to `hello`; `requestSongList` is sent immediately after each `sessionState`;
`assignSinger` now uses `songInstanceSeq` (uint32), `endTimeTvMs`, and `udpPort`;
`connectionId` is NOT present in `assignSinger`.

## Files and conventions

- `transcript.jsonl` / `expected.session.json`: current schema (spec v4.19)
- `transcript.legacy.jsonl` / `expected.outcome.legacy.json`: kept for backward compatibility
  with the pre-v4.19 schema (contains `assignPlayer`, old `assignSinger` fields).
  Legacy files MUST NOT be updated.

## Subcases

- `case_reconnect_reclaim/` — disconnected client reclaims its singer slot via stable
  `clientId`; receives a new `connectionId` on reconnect; `assignSinger` is re-sent with
  recomputed `endTimeTvMs` and incremented `songInstanceSeq`; third client is rejected.
- `case_slot_taken/` — TV kicks the disconnected client (`tv_internal`); a third client
  joins and takes the free slot; original client is rejected as session full.

## connectionId semantics

Each new WebSocket connection receives a fresh `connectionId` in the `sessionState`
response. The value is monotonically increasing per session but MUST NOT be assumed
to be sequential. PitchFrames carrying a stale `connectionId` are silently dropped (§8.3).

Spec covers: §7, §8.2, §7.4, Appendix B
