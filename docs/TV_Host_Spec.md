<!-- Derived from couchraoke_spec.md v4.20 -->

# TV Host Spec (Android TV)

## Scope
This document is the TV-host split of the master spec. It is authoritative for:
- Song library aggregation/index behavior
- Timing/beat model
- Scoring
- TV UI/navigation
- Session authority and protocol handling

It excludes companion-app capture/storage/server implementation details.

---

## 3. Songs and Library (TV-relevant)

### 3.2 Discovery and Validation Rules (TV consumption model)
The TV consumes `songListUpdate` from phones and maintains an in-memory aggregate library index.  
The TV MUST:
- Replace all songs attributed to a `clientId` on each `songListUpdate` from that client.
- Remove all songs for a client immediately when that client disconnects.
- Treat index as session-memory only (no persistence across sessions).

### 3.3 Index Fields (Functional)
Normative minimum index record (per song):
- Identity/storage:
  - `phoneClientId`
  - `relativeTxtPath`
  - `songId = phoneClientId + "::" + relativeTxtPath`
  - `modifiedTimeMs`
- Validation:
  - `isValid`
  - `invalidReasonCode`
  - `invalidLineNumber`
- Display:
  - `artist`, `title`, optional `album`
- Flags:
  - `isDuet`, `hasRap`, `hasVideo`, `hasInstrumental`
  - `canMedley`, `medleySource` (`null | "tag"`), `medleyStartBeat`, `medleyEndBeat`, `calcMedleyEnabled`
- Timing metadata:
  - `startSec`
  - `previewStartSec`
- Asset URLs:
  - `txtUrl`, `audioUrl`, `videoUrl`, `coverUrl`, `backgroundUrl`, `instrumentalUrl`, `vocalsUrl`

### 3.4 Song List (Landing Screen)
TV behavior per master spec:
- Landing screen always Song List.
- Sort: Artist -> Album -> Title.
- Inline search: case-insensitive substring with 150 ms debounce.
- Random Song / Random Duet behaviors.
- Medley playlist rules (fixed-height list, reorder mode, delete by long-press, auto-medley random 5).
- Focus and DPAD map exactly as in master spec.
- Back behavior:
  - clear filter first if active
  - else exit app/launcher
- `canMedley` eligibility:
  - non-duet AND valid medley tags (`#MEDLEYSTARTBEAT`, `#MEDLEYENDBEAT`, start < end)
  - only `medleySource="tag"` is valid in MVP

---

## 5. Timing and Beat Model (Authoritative)

## 5.1 Authoritative Beat Definitions

Definitions:
- `GAPms`: float value of `#GAP:` in milliseconds
- `lyricsTimeSec`: current lyrics/playback clock in seconds
- `micDelayMs`: per-phone/per-player mic delay in milliseconds

Two beat cursors:

1) Highlight beat cursor (UI timing)
- `highlightTimeSec = lyricsTimeSec - (GAPms / 1000.0)`
- `CurrentBeat = floor(TimeSecToMidBeatInternal(highlightTimeSec))`

2) Scoring beat cursor (judgement timing)
- `scoringTimeSec = lyricsTimeSec - ((GAPms + micDelayMs) / 1000.0)`
- `CurrentBeatD = floor(TimeSecToMidBeatInternal(scoringTimeSec) - 0.5)`

`floor()` is mathematical floor.  
The `-0.5` shift is parity-critical.

## 5.2.5 Mic Capture and FFT-YIN Pitch Detection Pipeline
(Companion side computes pitch; TV consumes output. Included here for timing/protocol coherence)

- Frame window: 1024 @ 44100 Hz
- Voicing gate by threshold table index
- FFT autocorrelation -> difference -> normalized difference
- First local minimum under cutoff else absolute minimum
- Unvoiced if d’ > 0.40 -> `midiNote=255`
- 3-frame median with silence interruption rule:
  - if any of 3 is 255, emitted `midiNote=255`

## 5.2.5.3 Consolidated Sensitivity Table

| Index | maxAmpCutoff | dPrimeCutoff | Environment Profile |
|---|---|---|---|
| 0 | 0.01 | 0.10 | Very High Sensitivity (Whisper/Studio) |
| 1 | 0.02 | 0.15 | High Sensitivity |
| 2 | 0.04 | 0.20 | Medium-High |
| 3 | 0.06 | 0.25 | Medium (Default Karaoke Room) |
| 4 | 0.09 | 0.30 | Medium-Low (Noisy Room) |
| 5 | 0.13 | 0.35 | Low |
| 6 | 0.18 | 0.40 | Very Low (Loud Party) |
| 7 | 0.25 | 0.45 | Lowest (Extreme Noise) |

## 5.3 Beat-Time Conversion
- `internalBeat = fileBeat` (no scaling)
- `BPM_internal = BPM_file * 4`
- `MidBeat_internal = tSec * (BPM_internal / 60.0)`
- `tSec = beatInt * (60.0 / BPM_internal)`
- Note-active boundary convention:
  - active iff `startBeat <= beat < endBeat`

## 5.4 START/END
- Start at `startSec` from `#START`
- End at `#END` if `endMs > 0`, otherwise audio duration
- Restart seeks back to `startSec` (and `videoGapSec + startSec` for video)

---

## 6. Scoring (Authoritative)

## 6.1 Scoring Overview
- Dedicated scoring coroutine, 10 ms polling from ExoPlayer position.
- Evaluate integer beats in `(oldBeatD, currentBeatD]`.
- Each beat evaluated exactly once.
- Active note by `startBeat <= b < endBeat`.

## 6.2 Note Types / Eligibility
- `F` freestyle: always 0 points
- Normal/Golden: require `toneValid=true` and pitch in tolerance after octave normalization
- Rap/RapGolden: require `toneValid=true`, ignore pitch diff

## 6.2.1 ScoreFactor
- Freestyle 0
- Normal 1
- Golden 2
- Rap 1
- RapGolden 2

## 6.3 Difficulty Tolerance
- Easy: ±2
- Medium: ±1
- Hard: ±0
Default Medium.

## 6.4 Octave Normalization
```
while (Tone - TargetTone > 6) Tone := Tone - 12
while (Tone - TargetTone < -6) Tone := Tone + 12
```
TV derives:
- `Tone = midiNote - 36`

## 6.5 Line Bonus
- ON => `MaxSongPoints=9000`, `MaxLineBonusPool=1000`
- OFF => `MaxSongPoints=10000`, `MaxLineBonusPool=0`
- `TrackScoreValue = sum(duration * ScoreFactor)`
- `MaxLineScore = MaxSongPoints * (LineScoreValue / TrackScoreValue)`
- At sentence end:
  - `LineScore = (Score + ScoreGolden) - ScoreLast`
  - if `MaxLineScore <= 2`: `LinePerfection = 1`
  - else `LinePerfection = clamp(LineScore / (MaxLineScore - 2), 0, 1)`
- `LineBonusPerLine = MaxLineBonusPool / NonEmptyLines`
- `ScoreLine += LineBonusPerLine * LinePerfection`

## 6.6 Rounding and Display
- Per-beat:
  - `CurBeatPoints = (MaxSongPoints / TrackScoreValue) * ScoreFactor[noteType]`
- `ScoreLineInt = floor(round(ScoreLine) / 10) * 10`
- `ScoreInt = round(Score/10) * 10`
- `ScoreGoldenInt` opposite-rounding rule:
  - if `ScoreInt < Score` then `ceil(ScoreGolden/10)*10`
  - else `floor(ScoreGolden/10)*10`
- `ScoreTotalInt = ScoreInt + ScoreGoldenInt + ScoreLineInt`

---

## 8. Network Protocol (verbatim parity section)

### 8.1 Transport
- WebSocket control channel
- UDP pitch channel (16-byte fixed frames)
- HTTP asset URLs consumed directly from phones
- mDNS service `_karaoke._tcp`
- Session token validation

### 8.2 Control Messages
Includes:
- `hello` (required `httpPort`)
- `sessionState` (`slots`, `inSong`, optional `connectionId`)
- `ping`/`pong`/`clockAck`
- `error`
- `assignSinger`
- `requestSongList`
- `songListUpdate`

### 8.3 Pitch Stream Messages (binary)
16-byte little-endian payload:

Offset | Size | Type | Field
---|---|---|---
0 | 4 | uint32 | `seq`
4 | 4 | int32 | `tvTimeMs`
8 | 4 | uint32 | `songInstanceSeq`
12 | 1 | uint8 | `playerId` (0=P1, 1=P2)
13 | 1 | uint8 | `midiNote` (0..127 voiced, 255 unvoiced)
14 | 2 | uint16 | `connectionId`

Total: 16 bytes.

`toneValid = (midiNote != 255)`.

### 8.4 Versioning and Compatibility
`protocolVersion = 1` required.

### 8.5 Sender Identification
`connectionId` assigned at `hello` handshake; embedded in every UDP `pitchFrame`; stale/unknown dropped.

### 8.6 Song File HTTP Server
TV consumes URLs via ExoPlayer/Coil. It does not serve files.

---

## 10. UI Screens and Flows (TV)

Includes TV-side behavior from master spec:
- Global navigation/back model
- Song preview playback
- Select Players modal
- Settings (Connect Phones, Song Library, Audio, Scoring Timing, Gameplay, Video)
- Singing screen (countdown/pause/disconnect overlays)
- Results (song/medley)
- Medley mode sequencing rules

(Use master wireframes and exact modal text/DPAD maps as normative source.)

---

## Fixtures (TV scope by `covers` inheritance)
TV-specific references used by host testing:
- F01_song_discovery_validation_acceptance
- F02_header_parsing_edge_cases
- F03_body_grammar_token_recognition
- F04_duet_parsing_track_routing
- F05_legacy_relative_mode_semantics
- F06_beat_time_conversion_static_bpm
- F08_scoring_beat_stepping_interval_semantics
- F09_pitch_tolerance_octave_normalization
- F10_rap_scoring_tonevalid_gate
- F11_line_bonus_and_rounding
- Shared fixtures:
  - F12v2_binary_pitch_codec
  - F14v2_clock_sync_phone_side
  - F15_session_lifecycle_disconnect_reconnect

---

## Appendix A (TV-only dependency subset)
- Ktor server/websocket (TV host)
- kotlinx-serialization-json
- Media3 + datasource-okhttp
- Coil
- zxing-android-embedded (generation only)
- DataStore
- jmdns

A.4 Prohibited patterns (TV):
- reflection JSON on hot paths
- Netty engine for Ktor
- ZIP song transfer flow
- static middleware without proper range handling
- iOS/phone capture-specific patterns in TV runtime

---

## Appendix B: Protocol Schemas (duplicated for wire parity)

### B.2.1 `hello`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "hello",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "protocolVersion", "clientId", "deviceName", "appVersion", "capabilities", "httpPort"],
  "properties": {
    "type": {"const": "hello"},
    "protocolVersion": {"type": "integer", "const": 1},
    "clientId": {"type": "string", "minLength": 8},
    "deviceName": {"type": "string", "minLength": 1},
    "appVersion": {"type": "string", "minLength": 1},
    "httpPort": {"type": "integer", "minimum": 1024, "maximum": 65535, "description": "Port on which the phone's HTTP file server is listening"},
    "capabilities": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "pitchFps": {"type": "integer", "minimum": 1}
      }
    }
  }
}
```

### B.2.2 `sessionState`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "sessionState",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "protocolVersion", "sessionId", "slots", "inSong"],
  "properties": {
    "type": {"const": "sessionState"},
    "protocolVersion": {"type": "integer", "const": 1},
    "tsTvMs": {"type": "number"},
    "sessionId": {"type": "string", "minLength": 1},
    "slots": {
      "type": "object",
      "additionalProperties": false,
      "required": ["P1", "P2"],
      "properties": {
        "P1": {
          "type": "object",
          "additionalProperties": false,
          "required": ["connected", "deviceName"],
          "properties": {"connected": {"type": "boolean"}, "deviceName": {"type": "string"}}
        },
        "P2": {
          "type": "object",
          "additionalProperties": false,
          "required": ["connected", "deviceName"],
          "properties": {"connected": {"type": "boolean"}, "deviceName": {"type": "string"}}
        }
      }
    },
    "inSong": {"type": "boolean"},
    "songTimeSec": {"type": "number"},
    "connectionId": {"type": "integer", "description": "uint16 sender ID assigned by TV per connection; present only in the initial sessionState response to hello; included in every pitchFrame datagram"}
  }
}
```

### B.2.6 `assignSinger`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "assignSinger",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "protocolVersion", "sessionId", "songInstanceSeq", "playerId", "difficulty", "thresholdIndex", "effectiveMicDelayMs", "expectedPitchFps", "startMode", "endTimeTvMs", "udpPort"],
  "properties": {
    "type": {"const": "assignSinger"},
    "protocolVersion": {"type": "integer", "const": 1},
    "tsTvMs": {"type": "number"},
    "sessionId": {"type": "string", "minLength": 1},
    "songInstanceSeq": {"type": "integer", "minimum": 0, "description": "uint32 counter; increments on every song start including Restart"},
    "playerId": {"type": "string", "enum": ["P1", "P2"]},
    "difficulty": {"type": "string", "enum": ["Easy", "Medium", "Hard"]},
    "thresholdIndex": {"type": "integer", "minimum": 0, "maximum": 7},
    "effectiveMicDelayMs": {"type": "integer", "minimum": 0},
    "expectedPitchFps": {"type": "integer", "minimum": 1},
    "startMode": {"type": "string", "enum": ["countdown", "live"]},
    "countdownMs": {"type": "integer", "minimum": 0},
    "endTimeTvMs": {"type": "integer"},
    "udpPort": {"type": "integer", "minimum": 1024, "maximum": 65535},
    "songTitle": {"type": "string"},
    "songArtist": {"type": "string"}
  },
  "allOf": [{"if": {"properties": {"startMode": {"const": "countdown"}}}, "then": {"required": ["countdownMs"]}}]
}
```

(Other Appendix B schemas are identical to master and must be retained unchanged in implementation files.)
