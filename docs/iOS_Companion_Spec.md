<!-- Derived from couchraoke_spec.md v4.20 -->

# iOS Companion Spec (Swift)

## Scope
iOS companion responsibilities:
- Join/pair and maintain control channel
- Scan songs via security-scoped bookmarks
- Run local HTTP server (Swifter) with range support
- Capture mic and run FFT-YIN pipeline using Accelerate/vDSP
- Stream 16-byte UDP pitch frames

Excludes TV scoring math and TV UI/navigation.

---

## 3.1 Storage Access (iOS)

- Folder picker: `UIDocumentPickerViewController`
- Persist security-scoped bookmark (`bookmarkData`)
- Resolve bookmark on launch and call `startAccessingSecurityScopedResource()`
- Enumerate recursively with `FileManager.enumerator`
- Read files with `Data(contentsOf:)`
- Stop security scope access after operations

---

## 5.2.5 Mic Capture and FFT-YIN Pitch Detection Pipeline (iOS)

Normative pipeline:
1. Voicing gate (`maxAmp`) by threshold index
2. FFT autocorrelation (zero-pad, FFT, power spectrum, IFFT)
3. Difference and CMND normalization
4. Candidate selection + hard unvoiced cutoff (d’ > 0.40)
5. 3-frame median smoothing with silence interruption:
   - if any of 3 frames is 255 => emit 255

Implementation note:
- Use Accelerate/vDSP for FFT and primitive-array operations
- Zero-allocation hot loop requirements apply

---

## Detection Threshold Table (reference only from scoring chapter)
(Use for sensitivity; no TV scoring formulas included)

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

---

<!-- TV-authoritative. Do not redefine. Reference only. -->
## Beat/Sync Timing Excerpt (read-only)
- TV computes authoritative beat cursors and scoring windows.
- Companion provides time-aligned `tvTimeMs` + `midiNote` only.
- `toneValid` on wire is implicit via `midiNote != 255`.
- Companion must not implement independent scoring or note-window decisions.

---

## 7.3 Pairing UX (Phone, iOS)

States:
- Join screen
- Waiting/Connected
- Active Mic

Wireframe behaviors retained:
- Scan QR / enter code / join
- Role display and VU meter
- Mute toggle streams unvoiced frames
- Active Mic:
  - no back/leave action during active song
  - auto-return when `tvNowMs >= endTimeTvMs`
- Settings includes songs folder + rescan + song count

iOS permission handling retained:
- Camera permission (QR)
- Local network entitlement/prompt flow

---

## 8. Network Protocol (verbatim parity section)

### 8.1 Transport
- WebSocket control
- UDP pitch
- HTTP file server (iOS companion serves assets)

### 8.2 Control Messages
`hello` includes required `httpPort`.

### 8.3 Pitch Stream Messages (binary)
16-byte little-endian payload:

Offset | Size | Type | Field
---|---|---|---
0 | 4 | uint32 | `seq`
4 | 4 | int32 | `tvTimeMs`
8 | 4 | uint32 | `songInstanceSeq`
12 | 1 | uint8 | `playerId`
13 | 1 | uint8 | `midiNote`
14 | 2 | uint16 | `connectionId`

Total: 16 bytes.

### 8.4 / 8.5
- protocolVersion=1
- `connectionId` assigned at hello/sessionState and included in every UDP frame

### 8.6 Song File HTTP Server (iOS-specific)
- Swifter 1.5.0
- Start server before sending `hello`
- Parse `Range` manually and return proper `206` and `Content-Range`
- Use `NSFileCoordinator` for coordinated reads in handlers
- Security-scoped access for sandbox-external files
- iCloud downloading status check; non-current -> null asset URL
- foreground requirement/known iOS background limitation acknowledged

---

## Fixtures (iOS Companion, by covers inheritance + task constraints)
iOS-only fixtures:
- F19_icloud_eviction_handling

Shared fixtures:
- F12v2_binary_pitch_codec
- F14v2_clock_sync_phone_side
- F15_session_lifecycle_disconnect_reconnect

---

## Appendix A (iOS companion-only dependency subset)
- URLSessionWebSocketTask
- AVFoundation QR scanning
- Network.framework (`NWBrowser`)
- Swifter
- UserDefaults
- Accelerate/vDSP
- UIImpactFeedbackGenerator

A.4 Prohibited patterns (iOS companion):
- No Android SAF/`DocumentFile`
- No JNI/Android-only APIs
- No deprecated `NSNetServiceBrowser`
- No alternative HTTP server stack replacing Swifter for MVP

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
