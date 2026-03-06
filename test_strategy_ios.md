# Karaoke App — Test Strategy (iOS) v4.19

**Spec**: 4.19 | **Coverage target**: 80% overall, ≥60% per file | **Stack**: Kotlin (Android TV host) + Swift (iOS Phone companion)

> **Spec inconsistency on record**: `§5.2.5` lists a different `thresholdTable` from `§8.3`.
> This file uses the **§8.3 values** as authoritative: `[0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.60]`.
> The §5.2.5 table `[0.01, 0.02, 0.04, ...]` should be treated as a spec bug until resolved.

---

## Conventions

- **[U]** = Unit test (XCTest; no device, no network, no system APIs)
- **[I]** = Instrumented test (on-device via XCTest UI or XCTest on simulator where sufficient)
- **Fixture** references use the existing `fixtures/` repo layout
- Mock boundary: `FileManager`/`NSFileCoordinator` (file access), `URLSessionWebSocketTask` (WebSocket), POSIX `sendto`/`recvfrom` (UDP)

### Test framework

- Unit + Integration: **XCTest** (Xcode built-in)
- Mocking: **protocol-based test doubles** (Swift does not have a widely adopted mock library with the maturity of MockK; define lightweight `protocol` facades over system APIs and inject fakes in tests)
- JSON assertions: `JSONDecoder` + `Codable` — decode fixture files and compare field-by-field; do not string-compare JSON.

### Architecture clarifications
- **Phone (iOS)**: header-only scan → produces `songListUpdate` metadata. Uses `FileManager.enumerator` + security-scoped bookmarks for file traversal.
- **TV**: Kotlin only — TV-side modules (2, 3, 4, 6, 10, 11 TV, 12) are not duplicated here. This file covers iOS phone companion modules only.
- **Pitch frames**: 16-byte binary UDP datagrams sent from iOS phone via POSIX socket / `NWConnection`.

---

## Module 1 — Phone-side Song Scanner (iOS)

> Produces `songListUpdate` entries from header-only `.txt` scan via `FileManager.enumerator` + security-scoped bookmarks.

### 1.1 Validation [U]

Mock: inject `FakeFileEnumerator` conforming to a `FileEnumerating` protocol; stubs return pre-seeded URLs and `Data` objects without touching the real filesystem.

| # | What | Fixture | Expected |
|---|---|---|---|
| 1.1.1 | Missing `#ARTIST` | F01/`a/invalid_missing_required_header` | `isValid=false`, code `ERROR_CORRUPT_SONG_MISSING_REQUIRED_HEADER` |
| 1.1.2 | `#AUDIO` missing on disk | F01/`b/invalid_missing_audio` | `isValid=false`, code `ERROR_CORRUPT_SONG_FILE_NOT_FOUND`, `invalidLineNumber=4` |
| 1.1.3 | v1.0.0: `#AUDIO` beats `#MP3` | F01/`c/v1_audio_precedence` | `isValid=true`, `resolvedAudio=audio.ogg` |
| 1.1.4 | Legacy: `#MP3` required, `#AUDIO` ignored | F01/`c/legacy_mp3_preferred` | `isValid=true`, `resolvedAudio=audio.mp3` |
| 1.1.5 | Legacy: no `#MP3` | F01/`c/legacy_missing_mp3_invalid` | `isValid=false`, code `ERROR_CORRUPT_SONG_MISSING_REQUIRED_HEADER` |
| 1.1.6 | Missing optional `#VIDEO` | F01/`c/v1_missing_optional_video` | `isValid=true`, `hasVideo=false` |
| 1.1.7 | `#BPM:0` | S04 | `isValid=false`, code `ERROR_CORRUPT_SONG_MALFORMED_HEADER` |
| 1.1.8 | Non-numeric `#BPM` | F02/`b/invalid_malformed_bpm` | `isValid=false`, code `ERROR_CORRUPT_SONG_MALFORMED_HEADER`, `invalidLineNumber=5` |

### 1.2 Header parsing [U]

| # | What | Fixture | Expected |
|---|---|---|---|
| 1.2.1 | Duplicate tags → last wins | F02/`a/dup_bpm_last_wins` | `bpmFile=120.0` |
| 1.2.2 | Unknown tags preserved | F02/`a/unknown_tags_variants` | `customTags=[{FOO,bar},{EMPTY,""},{"",.JUSTTEXT}]` ordered |
| 1.2.3 | `#VERSION:1.0.0` ignores `#ENCODING` | F02/`c/encoding_utf8_forced` | `title="Tést ✓ UTF8"` |
| 1.2.4 | `previewStartSec` from `#PREVIEWSTART` | F02/`d/preview_from_previewstart` | `previewStartSec=12.5` |
| 1.2.5 | `previewStartSec` medley fallback | F02/`d/preview_from_medley` — `canMedley=true` (tags), no `#PREVIEWSTART`, `BPM=120`, `GAP=0`, `medleyStartBeat=16` | `previewStartSec=2.0` (`timeFromBeat(16)=2.0s`) |
| 1.2.6 | `previewStartSec` → 0 when no medley, no previewstart | F02/`d/preview_from_start` | `previewStartSec=0.0` |

### 1.3 Metadata flags [U]

| # | What | Input | Expected |
|---|---|---|---|
| 1.3.1 | `isDuet` detected from `P1`/`P2` in body | S11 | `isDuet=true` |
| 1.3.2 | `hasRap` detected from `R`/`G` notes | inline: body with `R 0 4 0 ra` | `hasRap=true` |
| 1.3.3 | `canMedley=false` for duet | `isDuet=true`, any `medleySource` | `canMedley=false` |
| 1.3.4 | `canMedley=true` via tags | `#MEDLEYSTARTBEAT:10`, `#MEDLEYENDBEAT:80`, `isDuet=false` | `canMedley=true`, `medleySource="tag"` |
| 1.3.5 | `canMedley=false` — no medley tags | no medley headers | `canMedley=false`, `medleySource=null` |

### 1.4 Recursive discovery [I]

> Requires real `FileManager.enumerator` traversal with a security-scoped bookmark. Must run on-device or simulator with a pre-seeded temporary directory.

| # | What | Fixture | Expected |
|---|---|---|---|
| 1.4.1 | Recursive scan finds all `.txt` | F01/`songs_root/` tree copied to temp dir | All 8 entries discovered, validity matches `expected.discovery.json` |

---

> **Modules 2–4, 6, 10–12 are TV-side (Kotlin only) and are not tested here.**
> See `test_strategy_android.md` for those modules.

---

## Module 5 — Binary PitchFrame Codec (iOS/Swift)

> §8.3: 16-byte little-endian UDP datagram. Swift `Data` + `withUnsafeBytes` / `CFSwapInt*LittleToHost` family for encode/decode. All Apple silicon and x86-64 simulators are natively little-endian; byte-swap calls are no-ops but must still be present for correctness.

**New fixture**: `fixtures/F12v2_binary_pitch_codec/`

```
frames.bin          # 3 hand-authored datagrams (48 bytes total)
expected.json       # decoded field values per frame
```

`expected.json`:
```json
[
  {"offset":0,  "seq":1, "tvTimeMs":5000, "songInstanceSeq":3, "playerId":0, "midiNote":60,  "toneValid":true,  "connectionId":7},
  {"offset":16, "seq":2, "tvTimeMs":5020, "songInstanceSeq":3, "playerId":1, "midiNote":255, "toneValid":false, "connectionId":8},
  {"offset":32, "seq":3, "tvTimeMs":5040, "songInstanceSeq":99,"playerId":0, "midiNote":36,  "toneValid":true,  "connectionId":7}
]
```

### 5.1 Codec correctness [U]

| # | What | Expected |
|---|---|---|
| 5.1.1 | Decode frame 0 | All fields match row 0 of `expected.json` |
| 5.1.2 | `midiNote=255` → `toneValid=false` | Row 1: `toneValid=false` |
| 5.1.3 | `midiNote=0` → `toneValid=true` | 0 is a valid MIDI note, not silence |
| 5.1.4 | encode(decode(frame)) round-trip | Identical bytes |

### 5.2 Phone-side encode [U]

> The iOS phone only **encodes and sends** frames. TV-side drop rules (connectionId mismatch, songInstanceSeq mismatch, etc.) are tested in `test_strategy_android.md` Module 5.2.

| # | What | Expected |
|---|---|---|
| 5.2.1 | `toneValid=false` encodes `midiNote=255` | Encoded byte at offset 14 == 0xFF |
| 5.2.2 | `toneValid=true`, `midiNote=0` | Encoded byte at offset 14 == 0x00; field not confused with silence |
| 5.2.3 | `tvTimeMs` set from clock sync estimate | Frame field matches `clockOffsetMs + phoneMonotonicMs` |

---

## Module 7 — Clock Sync (NTP-lite, Phone-side / iOS)

> §9.1.1: phone computes `clockOffsetMs` after receiving `clockAck`. `URLSessionWebSocketTask` delivers ping/pong/clockAck messages.

**New fixture**: `fixtures/F14v2_clock_sync_phone_side/`

```jsonl
// clockSync.jsonl — ping/pong/clockAck tuples
{"pingId":"a1","t1":1000,"t2":520,"t3":530,"t4":1050}
{"pingId":"a2","t1":2000,"t2":1600,"t3":1620,"t4":2200}
{"pingId":"a3","t1":3000,"t2":2515,"t3":2520,"t4":3035}
```

```json
// expected.clockSync.json
{
  "samples": [
    {"pingId":"a1","rttMs":40,  "clockOffsetMs":-500.0},
    {"pingId":"a2","rttMs":180, "clockOffsetMs":-490.0},
    {"pingId":"a3","rttMs":30,  "clockOffsetMs":-500.0}
  ],
  "chosen": {"pingId":"a3","rttMs":30,"clockOffsetMs":-500.0}
}
```

### 7.1 Per-sample math [U]

`RTT = (t4-t1)-(t3-t2)` | `offset = ((t2-t1)+(t3-t4))/2`

All three samples, assert RTT and clockOffsetMs match fixture to 0.5ms.

### 7.2 Best-of-N selection [U]

- Choose sample with smallest RTT → a3
- RTT < 0 or RTT > 2000 → discard (inject one invalid sample, assert not chosen)

### 7.3 tvTimeMs estimation [U]

- `clockOffsetMs=-500`, `phoneMonotonicMs=2000` → `tvTimeMs=1500`
- This value is embedded in the binary pitchFrame

---

## Module 8 — Control Message Protocol

> §8.2: WebSocket JSON control messages over `URLSessionWebSocketTask`.

**Updated fixture**: F15 — transcripts updated per §8.2:
- `hello` includes `httpPort`
- `sessionState` response to `hello` includes `connectionId`
- `requestSongList` step inserted after each `hello`
- `assignSinger` uses `songInstanceSeq` (uint32), includes `endTimeTvMs`, `udpPort`; `connectionId` is NOT in `assignSinger`
- `assignPlayer` messages removed

### 8.1 Hello handshake [U]

| # | What | Expected |
|---|---|---|
| 8.1.1 | Valid `hello` | TV responds with `sessionState` carrying `connectionId` |
| 8.1.2 | `hello` without `httpPort` | TV rejects; error code is implementation-defined (schema validation failure) |
| 8.1.3 | TV sends `requestSongList` after `sessionState` | Present in transcript immediately after hello |
| 8.1.4 | Wrong `protocolVersion` | `error(code="protocol_mismatch")` |
| 8.1.5 | Wrong token | `error(code="invalid_token")` |
| 8.1.6 | Join during Locked state | `error(code="session_locked")` |
| 8.1.7 | Roster full (>10) | `error(code="session_full")` |

### 8.2 songListUpdate handling [U]

| # | What | Expected |
|---|---|---|
| 8.2.1 | Phone A sends songs → library updated | Songs attributed to `clientId=A` visible |
| 8.2.2 | Phone A disconnects | All songs for `clientId=A` removed immediately |
| 8.2.3 | Rescan: phone sends new `songListUpdate` | Replaces all prior entries for that `clientId` (not appended) |

### 8.3 Reconnect with new connectionId [U]

**Fixture**: F15/`case_reconnect_reclaim` (updated)

| # | What | Expected |
|---|---|---|
| 8.3.1 | First connection assigns `connectionId=1` | In `sessionState` response to first `hello` |
| 8.3.2 | Reconnect `hello` response carries new `connectionId=2` | Value differs from first connection |
| 8.3.3 | `assignSinger` re-sent after reconnect | Contains recomputed `endTimeTvMs` and new `songInstanceSeq`; `connectionId` NOT present |
| 8.3.4 | PitchFrames with old `connectionId=1` | Silently dropped |
| 8.3.5 | Third phone rejected | `error(code="session_full")` |

### 8.4 assignSinger fields [U]

Verify `assignSinger` contains all required fields per schema B.2.6:
`sessionId`, `songInstanceSeq` (uint32), `playerId`, `difficulty`, `thresholdIndex`, `effectiveMicDelayMs`, `expectedPitchFps`, `startMode`, `endTimeTvMs`, `udpPort`.

Optional fields when supplied: `songTitle`, `songArtist`.

`connectionId` MUST NOT appear in `assignSinger`.

For `startMode="countdown"`, additionally assert `countdownMs` is present.

---

## Module 9 — HTTP File Server (Phone-side / iOS)

> §8.6: **Swifter** (`1.5.0`) HTTP server. File access via `FileManager` + security-scoped bookmarks. Swifter has built-in range-request support via `HttpResponse.raw` with `Content-Range`; assert behaviour at the HTTP level.

**Mock**: inject a `FileProviding` protocol stub returning `Data` objects. No real disk access.

### 9.1 Range requests [U]

| # | What | Input | Expected |
|---|---|---|---|
| 9.1.1 | Full file | No `Range` header | 200, `Content-Length` set, full bytes |
| 9.1.2 | Partial range | `Range: bytes=0-99` | 206, `Content-Range: bytes 0-99/<total>`, 100 bytes |
| 9.1.3 | Open-ended range | `Range: bytes=500-` | 206, bytes from 500 to EOF |
| 9.1.4 | All audio/video responses | Any request | `Accept-Ranges: bytes` header present |
| 9.1.5 | Unsatisfiable range | `Range: bytes=9999-9999` on 100-byte file | 416 |

### 9.2 Routing and security [U]

| # | What | Expected |
|---|---|---|
| 9.2.1 | `/songs/Artist/Song/audio.ogg` | 200 |
| 9.2.2 | Percent-encoded path | `Queen/Bohemian%20Rhapsody/` correctly decoded |
| 9.2.3 | Path traversal `../etc/passwd` | 404 |
| 9.2.4 | Unknown path | 404 |

### 9.3 Server lifecycle [I]

> Requires real socket binding. Run on-simulator with loopback.

| # | What | Expected |
|---|---|---|
| 9.3.1 | Server starts before `hello` is sent | `httpPort` in `hello` is reachable |
| 9.3.2 | Default port 34781 busy → ephemeral fallback | `httpPort` in `hello` reflects actual bound port |

### 9.4 iCloud-evicted file handling [U]

| # | What | Expected |
|---|---|---|
| 9.4.1 | `URLResourceValues.fileSize == 0` and `isUbiquitousItem == true` | URL is `nil` in `SongEntry`; no HTTP request attempted |
| 9.4.2 | Security-scoped bookmark not accessed via raw path | Verify no `url.path` → `FileManager.contents(atPath:)` call without `startAccessingSecurityScopedResource` (code review / static analysis) |

---

> **Modules 6, 10, 11 (TV screens), 12 are TV-side (Kotlin only) and are not tested here.**
> See `test_strategy_android.md` for those modules.

---

## Module 11 — Key UI Invariants (Phone — iOS)

> Minimal UI tests only — SwiftUI + XCTestUI. No layout assertions, no snapshot tests.

| # | What | Expected |
|---|---|---|
| 11.4.1 | Swipe-back gesture during Active Mic | Suppressed (interactive pop gesture / `navigationBarBackButtonHidden` active) |
| 11.4.2 | `tvNowMs >= endTimeTvMs` | Screen transitions to Waiting/Connected |
| 11.4.3 | Leave session | Returns to Join screen; cached endpoint cleared |

---

## Instrumented Tests Summary

| Area | Why instrumented | Module |
|---|---|---|
| Recursive `FileManager.enumerator` scan (1.4.1) | Requires real temp directory on simulator | 1.4 |
| HTTP server socket binding (9.3) | Requires real OS socket; loopback on simulator | 9.3 |
| mDNS advertisement + join-code resolution | Network-dependent; requires two devices | Manual / separate integration test |

---

## Fixture Change Summary

> Fixtures are shared across both platform test files. Changes listed here mirror `test_strategy_android.md`; the authoritative change log is maintained there to avoid duplication.

| Fixture | Action |
|---|---|
| S01–S17 | No change |
| F01–F11 | No change |
| F07 | **Delete** — variable BPM unsupported; rejected at parse time |
| F12 | **Delete**; replace with F12v2 (binary codec) |
| F13 | **Confirm**: field name is `tvTimeMs` (not `tCaptureMs`) |
| F14 | **Delete**; replace with F14v2 (phone-side clock sync) |
| F15 | **Update**: add `httpPort`, `connectionId` in `sessionState`, `requestSongList` step; remove `assignPlayer` |
| F16 | **New**: medley sequencer (TV-only; not exercised in this file) |
| manifest.json | Bump `specVersion` to `4.19`; remove F07; add F12v2, F14v2, F16; update `covers` refs |

---

## Explicitly Out of Scope

- Rust/pYIN pitch DSP (tested in Rust crate's own test suite)
- TV-side modules: parser (2), beat model (3), scoring engine (4), jitter buffer (6), library aggregation (10), TV UI (11.1–11.3), medley sequencer (12) — see `test_strategy_android.md`
- AVAudioEngine / AVAudioSession hardware latency characterisation
- AVPlayer streaming latency
- mDNS timing / multi-device discovery
- Advanced Search (§3.5 is POST-MVP)
- ISO-8859-1 encoding test (F02 `encoding_legacy_honors`) — skip
- Snapshot / screenshot tests
