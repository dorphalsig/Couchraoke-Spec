# ADR-003: Phone HTTP file server for song delivery

**Status:** Accepted
**Date:** 2026-03-01 (recorded retroactively 2026-04-24)
**Deciders:** Product/spec author, Claude Code

## Context

An earlier spec revision required the phone to:

1. ZIP the entire song folder (`.txt`, audio, optional video, cover, background) on demand.
2. Stream the ZIP to the TV as chunked WebSocket binary frames.
3. The TV would extract the package to a session-scoped temporary directory before playback.

Two problems surfaced:

- **Startup latency.** A representative 30 MB audio+video package over 2.4 GHz home Wi-Fi (effective ~25 Mbps) takes ~9.6 s to transfer. The dominant bottleneck is Wi-Fi throughput, not eMMC disk I/O — mid-tier 2022 Android TVs have sequential eMMC reads of ~100–250 MB/s, so ZIP decompression is noise on top. The player had a hard wall before any audio began.
- **ZIP is the wrong codec on already-compressed media.** DEFLATE on MP3 and H.264/AAC typically saves <1–3% while burning CPU on both ends.

The TV does not need the audio/video files resident on disk to score. It only needs to stream them into the TV playback backend and feed UDP pitch frames into the scoring engine. The phone already has the files.

## Decision

The phone runs a read-only HTTP file server for session duration. The TV streams song assets directly from the phone, using standard HTTP `Range` support through its playback backend, with no intermediate storage.

**Transport channels (final):**

- **WebSocket** on the phone's TV-client connection carries control messages only (`hello`, `sessionState`, `assignSinger`, `playbackState`, `ping/pong/clockAck`, `error`).
- **HTTP** on the phone's server provides `/manifest.json` and `/songs/<percent-encoded-relative-path>` with full `Range` support, `Accept-Ranges: bytes`, `Content-Length`, and `Cache-Control: no-cache` on the manifest.
- **UDP** carries pitch frames from phone to TV ([ADR-004](ADR-004-udp-pitch-frame-wire-protocol.md)).

**Libraries (pinned):**

- Android companion HTTP server: `io.ktor:ktor-server-cio:3.4.3` with `io.ktor:ktor-server-partial-content:3.4.3` (handles `Range`/`206` automatically).
- iOS companion HTTP server: Hummingbird 2.22.0 (Swift HTTP/1.1 server; manual `Range` parsing via `FileHandle.seek(toFileOffset:)`).
- TV HTTP client/playback backend: LibVLC consumes the phone's HTTP URLs directly.

## Options Considered

### Option A: ZIP-over-WebSocket (status quo at the time)

| Dimension | Assessment |
|-----------|------------|
| Complexity | High (packaging, chunking, extraction, temp storage) |
| Cost | ~10 s startup stall per song |
| Scalability | Poor (full download before play) |
| Team familiarity | Medium |

**Pros:** Single transport channel. No HTTP server on the phone.
**Cons:** Hard startup wall. Wastes CPU DEFLATE-ing pre-compressed media. Requires TV-side temp storage and cleanup. Cannot start playback before full transfer completes.

### Option B: Chunked WebSocket with speculative playback

| Dimension | Assessment |
|-----------|------------|
| Complexity | High (custom stream protocol, seek support, error recovery) |
| Cost | Medium |
| Scalability | Medium |
| Team familiarity | Low |

**Pros:** Could begin playback before full transfer. No HTTP server needed.
**Cons:** Reinvents HTTP `Range`. The playback backend does not consume bespoke WebSocket byte streams directly — a custom stream adapter would be required. Seek on the stream requires server-side byte-offset semantics we would have to design from scratch.

### Option C: Phone HTTP server (adopted)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low (standard HTTP semantics, battle-tested libraries) |
| Cost | <500 ms time-to-first-byte; playback begins after backend buffering |
| Scalability | Excellent (any number of assets, no bespoke protocol) |
| Team familiarity | High |

**Pros:** Zero intermediate storage. Standard HTTP `Range` support handles seek. HTTP range is universal and debuggable with curl. `/manifest.json` is a trivial in-memory JSON byte array rebuilt on scan. No temp files; no cleanup lifecycle.
**Cons:** Phone runs an HTTP server on a configurable port (default 34 781). Requires `cleartext-permitted` network config on the TV. iOS backgrounding suspends the HTTP socket ~30 s after foreground exit; users must keep the app open.

## Trade-off Analysis

Option A was already broken: the 5–15 s load wall is user-visible and unfixable without changing the transport.

Option B was briefly considered but required us to reinvent range-based streaming with custom playback-backend stream adapter code. Every line written there is a line we do not write against well-understood HTTP semantics.

Option C trades "phone runs a server" for "zero bespoke code." The iOS backgrounding limitation is real but narrow: the companion is designed to be used in the foreground anyway (mic capture + QR scan + pitch display), and a "Keep app in foreground" banner is the correct mitigation.

## Consequences

- The phone MUST serve `/manifest.json` from an in-memory JSON byte array rebuilt on each scan, never from disk on each HTTP request.
- The TV MUST include `android:networkSecurityConfig` permitting cleartext traffic for LAN addresses; without it, `http://` requests fail with `CLEARTEXT_NOT_PERMITTED` on API 28+.
- Android 17+ requires the local-network permission before the HTTP fetcher is used against phone peers.
- The TV playback backend relies on the server honouring `Range` correctly (`206 Partial Content`, `Content-Range`, `Accept-Ranges: bytes`); test fixtures F18 (range) and F19 (iCloud evicted) cover this.
- iOS file reads go through `NSFileCoordinator` to avoid conflicts with the iCloud sync daemon; iCloud-evicted required playback files make the song invalid, so no manifest entry is published. Optional evicted assets are omitted with a `null` optional URL.
- LibVLC is the TV-side playback backend under this transport. Video codec support is governed by ADR-007 and `tv_app.md`.
- Removing ZIP packaging removed ~200 lines of TV-side extract/cleanup code and the entire concept of session-scoped temp directories.

## Action Items

1. [x] Rewrote `§3.1 Storage Access` / `§2.2 HttpFileServer` to specify the HTTP server contract (Range, cache-control, internal URI map).
2. [x] Added HTTP contract requirements to `tv_app.md §8` as TV-side normative dependencies on the phone server.
3. [x] Added iOS iCloud ubiquity check (`ubiquitousItemDownloadingStatusKey == .current`) before a file URL is included in `SongEntry`.
4. [x] Added test fixtures F18 (HTTP range smoke test) and F19 (iCloud evicted).
5. [ ] Confirm whether Ktor CIO needs an explicit worker cap on low-memory Android companion devices under 10 concurrent range fetches.
