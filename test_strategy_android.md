# Karaoke App — Test Strategy (Android) v4.19

**Spec**: 4.19 | **Coverage target**: 80% overall, ≥60% per file | **Stack**: Kotlin (Android TV host + Android Phone companion)

> **Spec inconsistency on record**: `§5.2.5` lists a different `thresholdTable` from `§8.3`.
> This file uses the **§8.3 values** as authoritative: `[0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.60]`.
> The §5.2.5 table `[0.01, 0.02, 0.04, ...]` should be treated as a spec bug until resolved.

---

## Conventions

- **[U]** = Unit test (JUnit5 + MockK; no device, no network, no platform channels)
- **[I]** = Instrumented test (on-device via AndroidX Test / Espresso or Robolectric where sufficient)
- **Fixture** references use the existing `fixtures/` repo layout
- Mock boundary: `ContentResolver` (wraps SAF), `OkHttpClient` (WebSocket), `DatagramSocket`

### Test framework

- Unit: **JUnit5** (`junit-jupiter 5.10.x`) + **MockK** (`1.13.x`)
- Instrumented: **AndroidX Test** (`1.5.x`) + **Espresso** (`3.5.x`) for TV UI
- Coroutine testing: `kotlinx-coroutines-test` (same version as production coroutines)
- JSON assertions: `kotlinx-serialization-json` (same version as production) — deserialise fixture
  files and compare field-by-field; do not string-compare JSON.

### Architecture clarifications
- **Phone**: header-only scan → produces `songListUpdate` metadata (`isValid`, `title`, `artist`, `isDuet`, `hasRap`, `canMedley`, asset URLs). Uses `DocumentFile`/`ContentResolver` for SAF traversal.
- **TV**: fetches `.txt` via HTTP when a song is selected, runs full parse (header + body → note timeline). Parser required for medley beat markers and note-level scoring.
- **Pitch frames**: 16-byte binary UDP datagrams, Kotlin `DatagramSocket` on TV.

---

## Module 1 — Phone-side Song Scanner (Android)

> Produces `songListUpdate` entries from header-only `.txt` scan via SAF.

### 1.1 Validation [U]

Mock: inject `FakeContentResolver` that returns pre-seeded `DocumentFile` trees and `InputStream` stubs.

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

> Requires real SAF tree traversal via `DocumentFile`. Must run on-device or Robolectric with a seeded content provider.

| # | What | Fixture | Expected |
|---|---|---|---|
| 1.4.1 | Recursive scan finds all `.txt` | F01/`songs_root/` tree | All 8 entries discovered, validity matches `expected.discovery.json` |

---

## Module 2 — TV-side TXT Parser

> Full parse (header + body) when TV fetches a selected song's `.txt` over HTTP.

### 2.1 Body grammar [U]

| # | What | Fixture | Expected |
|---|---|---|---|
| 2.1.1 | Unknown body token ignored | F03/`a/unknown_token_ignored` | `isValid=true`, note type = Normal |
| 2.1.2 | Malformed numeric in body | F03/`b/invalid_malformed_numeric` | `isValid=false`, `ERROR_CORRUPT_SONG_MALFORMED_BODY`, `invalidLineNumber=7` |
| 2.1.3 | `duration=0` → Freestyle | F03/`c/duration_zero_converts_to_freestyle` | note stored as `Freestyle` |
| 2.1.4 | No `-` lines → single implicit sentence | S09 | `isValid=true`, 1 line, 1 note |
| 2.1.5 | No notes after cleanup | S10 | `isValid=false`, `ERROR_CORRUPT_SONG_NO_NOTES` |
| 2.1.6 | Body contains `B` token (variable BPM) | F03/`d/variable_bpm_rejected` — any valid header + `B 100 180.0` body line | `isValid=false`, `ERROR_CORRUPT_SONG_UNSUPPORTED_VARIABLE_BPM` |

### 2.2 RELATIVE tag and body format [U]

| # | What | Fixture | Expected |
|---|---|---|---|
| 2.2.1 | `#RELATIVE:YES` header treated as unknown tag | F03/`e/relative_header_as_custom_tag` | `isValid=true`, `customTags` contains `{tag:"RELATIVE", content:"YES"}` |
| 2.2.2 | RELATIVE body format: `-` line with extra beat-delta parameter | F03/`f/relative_body_rejected` — sentence line `- 16 4` | `isValid=false`, `ERROR_CORRUPT_SONG_UNSUPPORTED_RELATIVE` |

### 2.3 Duet parsing [U]

| # | What | Fixture | Expected |
|---|---|---|---|
| 2.3.1 | P1/P2 routing | F04/`a/valid_duet_interleaved` + `expected.parsedSong.json` | 2 tracks, notes assigned per track |
| 2.3.2 | Invalid `P3` marker | F04/`b/invalid_duet_marker_p3` | `isValid=false`, `ERROR_CORRUPT_SONG_INVALID_DUET_MARKER`, `invalidLineNumber=6` |

---

## Module 3 — Timing and Beat Model

### 3.1 Beat cursors — static BPM [U]

**Fixture**: F06 / `expected.beat_cursors.json`

| Input | Computation | Expected |
|---|---|---|
| `lyricsTimeSec=5.0`, `GAPms=2000`, `micDelayMs=100`, `BPM_file=120` | `highlightTimeSec=3.0` → `midBeat=24.0` | `currentBeat=24` |
| Same | `scoringTimeSec=2.9` → `midBeat=23.2` → `-0.5=22.7` | `currentBeatD=22` |

Assert: `BeatInternalToTimeSec(TimeSecToMidBeatInternal(t)) ≈ t` to 1e-9s (E.2 round-trip).

> **F07 deleted** — variable BPM is unsupported (§4.3). Songs with a `B` token are rejected at parse time with `ERROR_CORRUPT_SONG_UNSUPPORTED_VARIABLE_BPM`. There is no variable BPM timing code path to test.

### 3.2 Note window boundary [U]

**Fixture**: Inline / Appendix E.3

- `startBeat=11`, `duration=2` → active at b=11, b=12; NOT active at b=13
- Scoring loop `(oldBeatD=10, currentBeatD=13]` → evaluates b=11,12,13 only
- **Medley addendum**: in medley mode, notes outside `[medleyStartBeat, medleyEndBeat)` are treated as Freestyle (ScoreFactor=0) at scoring time; the parsed note structure is not modified.

---

## Module 4 — Scoring Engine

### 4.1 Beat stepping [U]

**Fixture**: F08 / `expected.score.json`

- Only beats in `(oldBeatD, currentBeatD]` scored
- Note window: `startBeat ≤ b < endBeat`
- `scoreDelta` per beat matches fixture; `scoreTotalInt=10000`

### 4.2 Pitch tolerance + octave normalization [U]

**Fixtures**: F09 subcases

| Subcase | Difficulty | midiNote | Target toneUsdx | After octave norm | Result |
|---|---|---|---|---|---|
| `easy_hit_diff1` | Easy (±2) | 47 | 0 | 47-36=11 → 11-12=-1 → diff=1 | Hit |
| `medium_hit_diff1` | Medium (±1) | 47 | 0 | diff=1 | Hit |
| `medium_miss_diff2` | Medium (±1) | 38 | 0 | 38-36=2 → diff=2 | Miss |
| `hard_miss_diff1` | Hard (±0) | 47 | 0 | diff=1 | Miss |

Assert `scoreTotalInt` matches `expected.score.json` per subcase.

### 4.3 Rap scoring [U]

**Fixture**: F10 / `expected.score.json`

- `toneValid=true` → scores regardless of pitch
- `toneValid=false` → no score
- `scoreTotalInt=5000`

### 4.4 Freestyle exclusion [U]

**Fixture**: F03/`scoring/freestyle_only` / `expected.score.json`

- All beats on Freestyle note → `scoreDelta=0` even with `toneValid=true`
- `scoreTotalInt=0`

### 4.5 Line bonus + rounding [U]

**Fixture**: F11 / `expected.score.json`

- Perfect performance: `ScoreLineInt=1000`, `ScoreTotalInt=10000`
- Golden opposite-rounding rule (E.5): `ScoreInt < Score` → `ScoreGoldenInt = ceil`
- Medley TOTAL: `round(sum(scoreTotalInt) / n)` → `9987` (non-multiple of 10 is valid)

---

## Module 5 — Binary PitchFrame Codec (Android/Kotlin)

> §8.3: 16-byte little-endian UDP datagram. JVM `ByteBuffer.order(LITTLE_ENDIAN)` for encode/decode.

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

### 5.2 TV-side validation / drop rules [U]

| # | What | Expected |
|---|---|---|
| 5.2.1 | Datagram ≠ 16 bytes | Silently dropped (return null) |
| 5.2.2 | `connectionId` doesn't match registered player | Silently dropped |
| 5.2.3 | `songInstanceSeq` mismatch | Silently dropped — §8.3 normative |
| 5.2.4 | Unknown `playerId` (not P1/P2) | Silently dropped |

---

## Module 6 — Jitter Buffer

> §5.2: select most-recent frame with `tvTimeMs ≤ detectionTimeTvMs`; staleness cutoff 120ms; max playout delay 450ms.

**Fixture**: F13 — field name is `tvTimeMs` (not `tCaptureMs`; F13 files use the updated name).

| # | What | F13 sample | Expected |
|---|---|---|---|
| 6.1 | Most recent frame ≤ now | `tvNowMs=1060` | seq=2 (`tvTimeMs=1050`) |
| 6.2 | Newer frame within range | `tvNowMs=1200` | seq=3 (`tvTimeMs=1090`) |
| 6.3 | All eligible frames stale (>120ms) | `tvNowMs=1400` | `toneValid=false` (treat as silence) |
| 6.4 | Frame arrives late: `arrivalTimeTvMs > detectionTimeTvMs + 450` | inject frame with `latenessMs=500` | `toneValid=false` |
| 6.5 | Decreasing `seq` | Inject seq=5 then seq=3 | seq=3 dropped |
| 6.6 | `tvTimeMs` regression >200ms | regression=300ms | Dropped |
| 6.7 | `tvTimeMs` regression ≤200ms | regression=100ms | Accepted |

---

## Module 7 — Clock Sync (NTP-lite, Phone-side / Android)

> §9.1.1: phone computes `clockOffsetMs` after receiving `clockAck`. OkHttp `WebSocket` delivers ping/pong/clockAck messages.

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

> §8.2: WebSocket JSON control messages over OkHttp `WebSocket`.

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

## Module 9 — HTTP File Server (Phone-side / Android)

> §8.6: Ktor CIO server (`ktor-server-cio 2.3.12`) + `ktor-server-partial-content`. SAF reads via `ContentResolver`.

**Mock**: inject `FakeContentResolver` returning `ByteArray` stubs. No real disk access.
`ktor-server-partial-content` handles `Accept-Ranges`/`206` automatically; assert behavior at the HTTP level.

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

> Requires real `ServerSocket` binding. Run on-device or with Robolectric socket support.

| # | What | Expected |
|---|---|---|
| 9.3.1 | Server starts before `hello` is sent | `httpPort` in `hello` is reachable |
| 9.3.2 | Default port 34781 busy → ephemeral fallback | `httpPort` in `hello` reflects actual bound port |

### 9.4 SAF cloud-evicted file handling [U]

| # | What | Expected |
|---|---|---|
| 9.4.1 | `ContentResolver.query()` returns `SIZE=0` | URL is `null` in `SongEntry`; no HTTP request attempted |
| 9.4.2 | SAF URI path not used directly | Verify no `uri.path` → `File()` call exists (static analysis or lint rule) |

---

## Module 10 — TV Library Aggregation

### 10.1 Library state [U]

| # | What | Expected |
|---|---|---|
| 10.1.1 | Two phones each add 3 songs | Library = 6 entries |
| 10.1.2 | `songId` derivation | `phoneClientId + "::" + relativeTxtPath` |
| 10.1.3 | Sort order | Artist → Album → Title |
| 10.1.4 | Phone disconnects | Its songs removed immediately |
| 10.1.5 | `songListUpdate` replaces, not appends | Old entries for `clientId` gone |
| 10.1.6 | `medleySource="calculated"` in received entry | Rejected; `canMedley=false` forced |

### 10.2 Filtering [U]

| # | What | Expected |
|---|---|---|
| 10.2.1 | Inline search (150ms debounce) | Returns matching songs preserving sort |
| 10.2.2 | Empty filter set → Random/AutoMedley disabled | Actions return disabled state |
| 10.2.3 | `canMedley=true` filter for AutoMedley | Only eligible songs included |

---

## Module 11 — Key UI Invariants

> Minimal widget tests only — Compose UI + Espresso. No layout assertions, no screenshot tests.

### 11.1 TV — Select Players [U widget]

| # | What | Expected |
|---|---|---|
| 11.1.1 | No phones connected | Blocking error state; no Start button |
| 11.1.2 | Non-duet song | Player 2 row visible but disabled |
| 11.1.3 | Medley mode | Player 2 section hidden entirely |

### 11.2 TV — Singing Screen [U widget]

| # | What | Expected |
|---|---|---|
| 11.2.1 | Countdown sequence | Shows N → 1 at 1 Hz; playback starts after 1 |
| 11.2.2 | Singer disconnects mid-song | Singing screen pauses; shows `PAUSED — PLAYER DISCONNECTED` overlay with three choices: Wait / Continue / Quit (§10.4). Countdown-phase disconnect: implementation-defined — raise as spec clarification. |
| 11.2.3 | Pause overlay | Back opens it; Quit confirm has default focus on Cancel |

### 11.3 TV — Song List [U widget]

| # | What | Expected |
|---|---|---|
| 11.3.1 | No phones connected | "No phones connected." message + hint text (§3.4) |
| 11.3.2 | Phones connected, no valid songs | "No songs found." message + hint text (§3.4) |
| 11.3.3 | Song with `canMedley=false` long-pressed | Blocking modal with exact text: `This song can't be used in a medley. Look for songs with an M tag in the lower right corner` |
| 11.3.4 | Play Medley with empty playlist | Button disabled |
| 11.3.5 | Back with active filter | Filter cleared; remain on screen |
| 11.3.6 | Back with no filter | App exit triggered |

### 11.4 Phone — Android [U widget]

| # | What | Expected |
|---|---|---|
| 11.4.1 | Hardware Back during Active Mic | Suppressed (no-op) |
| 11.4.2 | `tvNowMs >= endTimeTvMs` | Screen transitions to Waiting/Connected |
| 11.4.3 | Leave session | Returns to Join screen; cached endpoint cleared |

---

## Module 12 — Medley Sequencer

> TV stitches N songs by seeking each to its medley window and scoring only notes within `[medleyStartBeat, medleyEndBeat)`.

**Fixture**: `fixtures/F16_medley_sequencer/`

```json
// medley_queue.json — 3-song medley
[
  {"songId":"A","bpmFile":120,"gapMs":0,"medleyStartBeat":96, "medleyEndBeat":192},
  {"songId":"B","bpmFile":100,"gapMs":0,"medleyStartBeat":100,"medleyEndBeat":160},
  {"songId":"C","bpmFile":140,"gapMs":0,"medleyStartBeat":112,"medleyEndBeat":200}
]
```

| Song | timeFromBeat(startBeat) | medleyStartSec | timeFromBeat(endBeat) | medleyEndSec |
|---|---|---|---|---|
| A | 12.0s | 4.0s | 24.0s | 26.0s |
| B | 15.0s | 7.0s | 24.0s | 26.0s |
| C | 12.0s | 4.0s | ≈21.43s | ≈23.43s |

### 12.1 medleyStartSec and medleyEndSec computation [U]

| # | What | Expected |
|---|---|---|
| 12.1.1 | Song A: timeFromBeat(96)=12s | startSec=4.0, endSec=26.0 |
| 12.1.2 | Song B: timeFromBeat(100)=15s | startSec=7.0, endSec=26.0 |
| 12.1.3 | Song C: timeFromBeat(112)≈12s | startSec=4.0, endSec≈23.43 (to 10ms) |
| 12.1.4 | timeFromBeat(startBeat) ≤ 8 → clamped | `medleyStartSec=0.0` |

### 12.2 Scoring window filter [U]

| # | What | Expected |
|---|---|---|
| 12.2.1 | Notes within `[medleyStartBeat, medleyEndBeat)` | ScoreFactor applied normally |
| 12.2.2 | Notes outside the window | ScoreFactor=0; parsed note structure unchanged |
| 12.2.3 | TrackScoreValue with window filter | Only in-window notes in normalization denominator |

### 12.3 Segment sequencing [U]

| # | What | Expected |
|---|---|---|
| 12.3.1 | Playback order | A → B → C preserved |
| 12.3.2 | `medleyStartBeat >= medleyEndBeat` segment received | Sequencer throws internal error (assertion / IllegalStateException) |
| 12.3.3 | `audioUrl` null when segment reached | Segment skipped; brief error toast; next segment proceeds |
| 12.3.4 | Scan-time guard: `#MEDLEYSTARTBEAT >= #MEDLEYENDBEAT` | `canMedley=false`; cannot enter playlist |

### 12.4 ExoPlayer seek accuracy [I]

> On-device only — seek precision requires real ExoPlayer + audio hardware.

Assert `player.getCurrentPosition()` after `seekTo(medleyStartSec × 1000)` is within ±100ms on a mid-tier Android TV device.

---

## Instrumented Tests Summary

| Area | Why instrumented | Module |
|---|---|---|
| Recursive SAF scan (1.4.1) | Requires `DocumentFile` / `ContentResolver` tree traversal | 1.4 |
| HTTP server socket binding (9.3) | Requires real OS `ServerSocket` | 9.3 |
| ExoPlayer seek accuracy (12.4) | Hardware-dependent; ±100ms tolerance | 12.4 |
| mDNS advertisement + join-code resolution | Network-dependent; requires two devices | Manual / separate integration test |

---

## Fixture Change Summary

| Fixture | Action |
|---|---|
| S01–S17 | No change |
| F01–F11 | No change |
| F07 | **Delete** — variable BPM unsupported; rejected at parse time |
| F12 | **Delete**; replace with F12v2 (binary codec) |
| F13 | **Confirm**: field name is `tvTimeMs` (not `tCaptureMs`) |
| F14 | **Delete**; replace with F14v2 (phone-side clock sync) |
| F15 | **Update**: add `httpPort`, `connectionId` in `sessionState`, `requestSongList` step; remove `assignPlayer` |
| F16 | **New**: medley sequencer (Module 12) |
| manifest.json | Bump `specVersion` to `4.19`; remove F07; add F12v2, F14v2, F16; update `covers` refs |

---

## Explicitly Out of Scope

- Rust/pYIN pitch DSP (tested in Rust crate's own test suite)
- JNI binding correctness beyond what §5.2.5 specifies (cargo-ndk build is a build concern, not a runtime test concern)
- `AudioRecord` hardware latency characterization
- ExoPlayer streaming latency (beyond 12.4 seek check)
- mDNS timing / multi-device discovery
- Advanced Search (§3.5 is POST-MVP)
- ISO-8859-1 encoding test (F02 `encoding_legacy_honors`) — skip
- Golden screenshot tests
