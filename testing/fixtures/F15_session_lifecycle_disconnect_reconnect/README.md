# F15 — Session lifecycle: hello/sessionState + assignSinger + disconnect/reconnect

Tests the full TV-side session lifecycle using the current wire protocol (tv_app.md v1.9).

## Current protocol summary

- `hello` (phone→TV) includes: `type`, `protocolVersion`, `clientId`, `deviceName`, `appVersion`, `httpPort`.
- TV responds with `sessionState` carrying `connectionId` (assigned per connection, incrementing).
- After `sessionState`, TV fetches `GET /manifest.json` from the phone immediately (during Open/Results only).
- When a song is selected, TV sends `assignSinger` with: `sessionId`, `songInstanceSeq`, `playerId`, `difficulty`, `startMode`, `stopAtLyricsTimeMs`, `udpPort`, `songTitle`, `songArtist`. `connectionId` is NOT present in `assignSinger`.
- TV broadcasts `playbackState` on phase transitions: `state` ∈ {`countdown`, `playing`, `paused`, `stopped`}, includes `revision`, `lyricsTimeMs`, `stopAtLyricsTimeMs`, `countdownRemainingMs` (only during countdown), `reason`.
- Reconnect: TV assigns a new `connectionId`. If phone was an active singer, TV re-sends `assignSinger` with the same `songInstanceSeq` and a recomputed `stopAtLyricsTimeMs`.
- Manifest fetch is deferred during Countdown/Live/Paused/DisconnectPaused; catalog marked stale until Results/Open.
- Error codes: `session_full`, `session_locked`, `protocol_mismatch`, `invalid_token`.

## Files

- `transcript.jsonl` / `expected.session.json`: full session flow (2 phones join, song assigned, third rejected, protocol mismatch rejected)
- `case_reconnect_reclaim/`: phone reconnects mid-song, reclaims singer slot via same `clientId`, receives new `connectionId`
- `case_slot_taken/`: roster already has 10 connected devices; an 11th unknown `clientId` is rejected with `session_full`

## connectionId semantics

Each new WebSocket connection receives a fresh `connectionId` in `sessionState`. Value increments per session. PitchFrames carrying a stale `connectionId` are silently dropped.

Spec covers: tv_app.md §2.3 NetworkController (T8.3, T8.5)
