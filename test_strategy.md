# Karaoke App — Test Strategy v4.17

**Spec**: 4.17 | **Coverage target**: 80% overall, ≥60% per file | **Stack**: Flutter (Dart) TV + Phone

---

## Conventions

- **[U]** = Unit test (no device, no network, no platform channels)
- **[I]** = Instrumented test (on-device or integration harness)
- **Fixture** references use the existing `fixtures/` repo layout
- Mock boundary: `PlatformFileReader` (wraps SAF + iOS channel), `RawDatagramSocket`, `WebSocketChannel`

### Architecture clarifications
- **Phone**: header-only scan → produces `songListUpdate` metadata (`isValid`, `title`, `artist`, `isDuet`, `hasRap`, `canMedley`, asset URLs)
- **TV**: fetches `.txt` via HTTP when a song is selected, runs full parse (header + body → note timeline). Parser is required for medley beat markers and note-level scoring.
- **Pitch frames**: 16-byte binary UDP datagrams, Dart `RawDatagramSocket` on TV

---

## Module 1 — Phone-side Song Scanner

> Produces `songListUpdate` entries from header-only `.txt` scan.

### 1.1 Validation [U]

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
| 1.2.1 | Duplicate tags → last wins | F02/`a/dup_bpm_last_wins` (two `#BPM` lines) | `bpmFile=120.0` |
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

> Requires real filesystem traversal. Not mockable via platform channel stub alone.

| # | What | Fixture | Expected |
|---|---|---|---|
| 1.4.1 | Recursive scan finds all `.txt` | F01/`songs_root/` tree | All 8 entries discovered, validity matches `expected.discovery.json` |

---

## Module 2 — TV-side TXT Parser

> Full parse (header + body) when TV fetches a selected song's `.txt`.

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
| 2.2.1 | `#RELATIVE:YES` header treated as unknown tag | F03/`e/relative_header_as_custom_tag` — valid song with `#RELATIVE:YES` header | `isValid=true`, `customTags` contains `{tag:"RELATIVE", content:"YES"}` |
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

## Module 5 — Binary PitchFrame Codec

> §8.3: 16-byte little-endian UDP datagram

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
| 5.2.3 | `songInstanceSeq` mismatch | Silently dropped — §8.3 frame layout field description: "TV drops frames that don't match" (normative, same wording as the `connectionId` rule) |
| 5.2.4 | Unknown `playerId` (not P1/P2) | Silently dropped |

---

## Module 6 — Jitter Buffer

> §5.2: select most-recent frame with `tvTimeMs ≤ detectionTimeTvMs`; staleness cutoff 120ms; max playout delay 450ms

**Updated fixture**: F13 — rename `tCaptureMs` → `tvTimeMs` in `pitchFrames.jsonl` and `expected.selection.json`; update README. Logic unchanged.

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

## Module 7 — Clock Sync (NTP-lite, Phone-side)

> §9.1.1: phone computes `clockOffsetMs` after receiving `clockAck`

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

> §8.2: WebSocket JSON control messages

**Updated fixture**: F15 — update transcripts per §8.2 changes:
- Add `httpPort` to all `hello` messages
- Add `connectionId` to `sessionState` response to `hello`
- Insert `requestSongList` (TV→phone) and `songListUpdate` (phone→TV) after each `hello`
- Replace `songInstanceId` (string) with `songInstanceSeq` (uint32) in `assignSinger`
- Add required `assignSinger` fields: `sessionId`, `endTimeTvMs`, `udpPort`
- Add optional `assignSinger` fields where present: `songTitle`, `songArtist` (optional per schema B.2.6; not in `required` array)
- Note: `connectionId` is NOT a field of `assignSinger`; it is delivered in `sessionState` (see §8.5)
- Remove non-spec `assignPlayer` messages

### 8.1 Hello handshake [U]

| # | What | Expected |
|---|---|---|
| 8.1.1 | Valid `hello` | TV responds with `sessionState` carrying `connectionId` |
| 8.1.2 | `hello` without `httpPort` | TV rejects; error code is **implementation-defined** (spec mandates schema validation but does not specify which `code` to use for a missing required field; `protocol_mismatch` is reasonable but not normative) |
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
| 8.3.2 | Reconnect `hello` response carries new `connectionId=2` | In `sessionState` response to reconnect `hello`; value differs from first connection |
| 8.3.3 | `assignSinger` re-sent after reconnect | Contains recomputed `endTimeTvMs` and new `songInstanceSeq`; `connectionId` is NOT present (it was already delivered in 8.3.2's `sessionState`) |
| 8.3.4 | PitchFrames with old `connectionId=1` | Silently dropped |
| 8.3.5 | Third phone rejected | `error(code="session_full")` |

### 8.4 assignSinger fields [U]

Verify `assignSinger` message for a single non-duet song contains all required fields per schema B.2.6:
`sessionId`, `songInstanceSeq` (uint32), `playerId`, `difficulty`, `thresholdIndex`, `effectiveMicDelayMs`, `expectedPitchFps`, `startMode`, `endTimeTvMs`, `udpPort`.

Additionally assert the following **optional** fields are present when supplied by the TV (they are in `properties` but not `required` in schema B.2.6): `songTitle`, `songArtist`.

Note: `connectionId` is NOT a field of `assignSinger` — it is delivered to the phone exclusively in the `sessionState` response to `hello` (§8.5). Do not assert its presence in `assignSinger`.

For `startMode="countdown"`, additionally assert `countdownMs` is present.

---

## Module 9 — HTTP File Server (Phone-side)

> §8.6: shelf server, range requests, SAF/iOS abstraction

**Mock**: inject `FakePlatformFileReader` returning `Uint8List`. No real disk access.

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

> Requires real `ServerSocket` binding on device.

| # | What | Expected |
|---|---|---|
| 9.3.1 | Server starts before `hello` is sent | `httpPort` in `hello` is reachable |
| 9.3.2 | Default port 34781 busy → ephemeral fallback | `httpPort` in `hello` reflects actual bound port |

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
| 10.1.6 | `medleySource="calculated"` in received entry | Rejected; `canMedley=false` forced (field removed from spec 4.17) |

### 10.2 Filtering [U]

| # | What | Expected |
|---|---|---|
| 10.2.1 | Inline search (150ms debounce) | Returns matching songs preserving sort |
| 10.2.2 | Empty filter set → Random/AutoMedley disabled | Actions return disabled state |
| 10.2.3 | `canMedley=true` filter for AutoMedley | Only eligible songs included |

---

## Module 11 — Key UI Invariants

> Minimal widget tests only — no layout, no golden files.

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
| 11.2.2 | Singer disconnects **mid-song** | Singing screen pauses and shows `PAUSED — PLAYER DISCONNECTED` overlay with three choices: Wait / Continue / Quit (§10.4 wireframe). **Spec gap**: §10.4 uses the phrase "mid-song"; whether a disconnect during the countdown phase also triggers this overlay is not specified. Treat countdown-phase disconnect as implementation-defined — raise as a spec clarification item. |
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

### 11.4 Phone [U widget]

| # | What | Expected |
|---|---|---|
| 11.4.1 | Hardware Back during Active Mic | Suppressed (no-op) |
| 11.4.2 | `tvNowMs >= endTimeTvMs` | Screen transitions to Waiting/Connected |
| 11.4.3 | Leave session | Returns to Join screen; cached endpoint cleared |

---

## Module 12 — Medley Sequencer

> TV stitches N songs by seeking each to its medley window and scoring only notes within `[medleyStartBeat, medleyEndBeat)`.

**Fixture**: `fixtures/F16_medley_sequencer/`

The fixture uses songs where `timeFromBeat(medleyStartBeat) > MEDLEY_FADE_IN_SEC` to produce a non-zero `medleyStartSec` and exercise the full formula. Using songs where `timeFromBeat < FADE_IN_SEC` would collapse `medleyStartSec` to 0 and not test the subtraction.

```json
// medley_queue.json — 3-song medley
// BPM_internal = BPM_file × 4; timeFromBeat(b) = b × 60 / BPM_internal
// All three songs have timeFromBeat(startBeat) > 8s
[
  {"songId":"A","bpmFile":120,"gapMs":0,"medleyStartBeat":96, "medleyEndBeat":192},
  {"songId":"B","bpmFile":100,"gapMs":0,"medleyStartBeat":100,"medleyEndBeat":160},
  {"songId":"C","bpmFile":140,"gapMs":0,"medleyStartBeat":112,"medleyEndBeat":200}
]
```

Derivations:

| Song | timeFromBeat(startBeat) | medleyStartSec = max(0, t−8) | timeFromBeat(endBeat) | medleyEndSec = t+2 |
|---|---|---|---|---|
| A | 96×60/480 = 12.0s | **4.0s** | 192×60/480 = 24.0s | **26.0s** |
| B | 100×60/400 = 15.0s | **7.0s** | 160×60/400 = 24.0s | **26.0s** |
| C | 112×60/560 = 12.0s | **4.0s** | 200×60/560 ≈ 21.43s | **≈23.43s** |

```json
// expected.segments.json
[
  {"songId":"A","medleyStartSec":4.0,  "medleyEndSec":26.0,   "scoringStartBeat":96, "scoringEndBeat":192},
  {"songId":"B","medleyStartSec":7.0,  "medleyEndSec":26.0,   "scoringStartBeat":100,"scoringEndBeat":160},
  {"songId":"C","medleyStartSec":4.0,  "medleyEndSec":23.429, "scoringStartBeat":112,"scoringEndBeat":200}
]
```

> **Note on fade constants**: Spec §10.4.1 asserts `MEDLEY_FADE_IN_SEC=8` and `MEDLEY_FADE_OUT_SEC=2` as USDX parity values. The USDX source uses `DEFAULT_FADE_IN_TIME` / `DEFAULT_FADE_OUT_TIME` constants in `USong.pas`, confirmed present in public search snippets, but the raw numeric values could not be independently verified — GitHub's raw file endpoint is inaccessible without authentication. The fixture is authored on the spec's stated values. If parity testing against a real USDX build reveals different constants, update the fixture and the spec.

### 12.1 medleyStartSec and medleyEndSec computation [U]

| # | What | Expected |
|---|---|---|
| 12.1.1 | Song A: timeFromBeat(96)=12s → startSec=4.0, endSec=26.0 | Matches fixture |
| 12.1.2 | Song B: timeFromBeat(100)=15s → startSec=7.0, endSec=26.0 | Matches fixture |
| 12.1.3 | Song C: timeFromBeat(112)≈12s → startSec=4.0, endSec≈23.43 | Matches fixture to 10ms |
| 12.1.4 | Song where timeFromBeat(startBeat) ≤ 8 → clamped | `medleyStartSec=0.0` |

### 12.2 Scoring window filter [U]

| # | What | Expected |
|---|---|---|
| 12.2.1 | Notes within `[medleyStartBeat, medleyEndBeat)` | ScoreFactor applied normally |
| 12.2.2 | Notes outside the window | ScoreFactor=0 (Freestyle treatment); parsed note structure unchanged |
| 12.2.3 | TrackScoreValue with window filter | Only in-window notes contribute to normalization denominator |

### 12.3 Segment sequencing [U]

| # | What | Expected |
|---|---|---|
| 12.3.1 | Playback order | A → B → C preserved |
| 12.3.2 | Sequencer receives segment with `medleyStartBeat >= medleyEndBeat` | **Defensive invariant**: sequencer MUST throw an internal error (assertion failure / IllegalStateException). This state is architecturally unreachable in production — the spec's scan-time rule (`canMedley` requires `startBeat < endBeat`; §3.4) prevents such a segment from ever entering the playlist. This test guards against implementation bugs that bypass the scan-time guard. |
| 12.3.3 | `audioUrl` null when segment reached | Segment skipped; brief error toast; next segment proceeds |
| 12.3.4 | Scan-time guard: `#MEDLEYSTARTBEAT >= #MEDLEYENDBEAT` in TXT | `canMedley=false`; song cannot be added to medley playlist. This is the normative gate that makes 12.3.2 unreachable. |

### 12.4 ExoPlayer seek accuracy [I]

> Only this sub-test is instrumented — the math is unit-testable above; seek precision requires a real device.

Assert `player.getCurrentPosition()` after `seekTo(medleyStartSec × 1000)` is within ±100ms of target on a mid-tier Android TV device.

---

## Instrumented Tests Summary

| Area | Why instrumented | Module |
|---|---|---|
| Recursive file scan (1.4.1) | Requires SAF/iOS directory traversal | 1.4 |
| HTTP server socket binding (9.3) | Requires real OS socket | 9.3 |
| ExoPlayer seek accuracy (12.4) | Hardware-dependent; ±100ms tolerance | 12.4 |
| mDNS advertisement + join-code resolution | Network-dependent; requires two devices | Manual / separate integration test |

---

## Fixture Change Summary

| Fixture | Action |
|---|---|
| S01–S17 | No change |
| F01–F11 | No change |
| F07 | **Delete** — variable BPM timing; feature unsupported; song rejected at parse time |
| F12 | **Delete**; replace with F12v2 (binary codec) |
| F13 | **Update**: rename `tCaptureMs` → `tvTimeMs` |
| F14 | **Delete**; replace with F14v2 (phone-side clock sync) |
| F15 | **Update**: add `httpPort`, `connectionId`, `sessionId` in `assignSinger`, `requestSongList` step; remove `assignPlayer` |
| F16 | **New**: medley sequencer fixture (Module 12) |
| manifest.json | Bump `specVersion` to `4.17`; remove F07; add F12v2, F14v2, F16; update `covers` section refs |

---

## Explicitly Out of Scope

- Rust/frb pitch DSP (tested in Rust)
- Platform channel internals (SAF, NSFileCoordinator, iOS bookmarks)
- ExoPlayer streaming latency (beyond 12.4 seek check)
- mDNS timing / multi-device discovery
- Advanced Search (§3.5 is POST-MVP)
- ISO-8859-1 encoding test (F02 `encoding_legacy_honors`) — skip
- Golden screenshot tests
