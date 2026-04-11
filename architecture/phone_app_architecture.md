# Couchraoke Phone Companion App — Technical Architecture

**Version**: 1.0  
**Date**: 2026-04-11  
**Scope**: Android Phone Companion (iOS follows same architecture)  
**Functional Spec Reference**: `../couchraoke_spec.md`  
**TV Architecture Reference**: `tv_app_architecture.md`

---

## Table of Contents

- [1. Non-Functional Requirements](#1-non-functional-requirements)
- [2. Top-Level Components](#2-top-level-components)
  - [2.1 SongScanner](#21-songscanner)
  - [2.2 HttpFileServer](#22-httpfileserver)
  - [2.3 PitchDetector](#23-pitchdetector)
  - [2.4 NetworkClient](#24-networkclient)
  - [2.5 ClockSync](#25-clocksync)
  - [2.6 SessionCoordinator](#26-sessioncoordinator)
- [3. Component APIs](#3-component-apis)
- [4. SLAs](#4-slas)
- [5. Resolved Blockers](#5-resolved-blockers)
- [6. Project Plan](#6-project-plan)
- [Appendix A: Mock TV Specification](#appendix-a-mock-tv-specification)

---

# 1. Non-Functional Requirements

Ordered by priority.

## 1.1 Pitch Latency (Critical)

**Why**: Frames arriving >150ms late are dropped by TV jitter buffer. Dropped frames = broken scoring.

| Requirement | Implementation |
|-------------|----------------|
| Frame generation ≤20ms | Process in AudioRecord callback thread |
| `tvTimeMs` accuracy ±5ms | Clock sync best-of-5 selection |
| No GC during pitch loop | Pre-allocated primitive arrays only |

**Tradeoff**: Pitch processing takes priority over HTTP serving. HTTP may briefly stall (~50ms) during heavy pitch activity. ExoPlayer's 2-4s buffer absorbs this.

## 1.2 Reliability (High)

**Why**: A 3-minute song interrupted by disconnect ruins the experience.

| Requirement | Implementation |
|-------------|----------------|
| Auto-reconnect on disconnect | 5x immediate retry at 500ms, then exponential backoff to 30s cap |
| No silent failures | All errors surface to UI or logs |
| Frame delivery best-effort | UDP fire-and-forget, TV handles missing frames |

## 1.3 HTTP Throughput (High)

**Why**: ExoPlayer needs responsive seeks and sustained streaming.

| Requirement | Implementation |
|-------------|----------------|
| First byte ≤100ms P95 | Ktor CIO async I/O |
| Sustained ≥2 Mbps | Direct SAF stream, no buffering |
| Range requests | Ktor partial-content plugin |

## 1.4 Scan Performance (Medium)

**Why**: Large libraries should scan in reasonable time with progress feedback.

| Requirement | Implementation |
|-------------|----------------|
| Parse rate ≥100 TXT/sec | Pure Kotlin parser, no regex |
| Progress updates | Callback every 100ms or 10 songs |
| Unbounded library | No artificial limits |

## 1.5 Memory Efficiency (Medium)

**Why**: Leave headroom for other apps on 6-8GB device.

| Requirement | Implementation |
|-------------|----------------|
| Total app ≤300MB | Lean allocations, no caching |
| Pitch buffers fixed 50KB | Pre-allocated at init |
| Manifest ≤2MB for 500 songs | ~4KB per SongEntry |

## 1.6 Battery (Low)

**Why**: Songs are 3-5 minutes. Hot is acceptable for accuracy.

| Requirement | Implementation |
|-------------|----------------|
| No thermal throttling mitigation | Run at full speed |
| Idle mode minimal drain | Stop pitch detection when not singing |

---

# 2. Top-Level Components

Six components in a layered monolith (single `:app` module with package boundaries).

```
┌─────────────────────────────────────────────────────────────────┐
│                        SessionCoordinator                        │
│  (orchestrates state, routes messages, coordinates lifecycle)   │
└─────────────────────────────────────────────────────────────────┘
        │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  Song    │ │   HTTP   │ │  Pitch   │ │ Network  │ │  Clock   │
│ Scanner  │ │  Server  │ │ Detector │ │  Client  │ │   Sync   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
     │              │           │           │           │
     ▼              │           │           │           │
┌──────────┐        │           └─────┬─────┘           │
│  Cloud/  │        │                 │                 │
│  Local   │        │           ┌─────▼─────┐           │
│  Storage │        │           │ WebSocket │           │
│ (SAF/    │        │           │    +      │◄──────────┘
│  iCloud) │        │           │   UDP TX  │
└──────────┘        │           └─────┬─────┘
     │   manifest   │                 │
     └──────────────┤                 │
        + file URIs │                 │
                    ▼                 ▼
              ┌─────────────────────────────────────────┐
              │              TV (Black Box)              │
              │  ◄── HTTP GET /manifest.json            │
              │  ◄── HTTP GET /songs/<path>             │
              │  ◄── UDP pitch frames                   │
              │  ──► WebSocket control messages         │
              └─────────────────────────────────────────┘
```

---

## 2.1 SongScanner

**Responsibility**: Discover, validate, and index songs from user's configured folder.

**Lifecycle**: 
- Initialized at app start
- Runs on: app launch, folder change, manual rescan
- Produces: in-memory `SongIndex` + serialized `manifest.json` byte array

**Functional Boundary**:
- SAF tree URI persistence (Android) / security-scoped bookmark (iOS)
- Recursive `.txt` discovery
- Header parsing and validation (§3.2)
- Asset existence checks
- Builds `SongEntry` list with HTTP URLs

**L2 Visible Shapes**:
- `FolderAccessor` — platform abstraction for SAF/security-scoped
- `TxtParser` — header + body parsing (shared with TV)
- `ValidationEngine` — applies §3.2 acceptance rules

### Validation Rules (Normative)

A song is accepted if and only if:

1. **Required headers present**:
   - `#TITLE` and `#ARTIST` non-empty
   - `#BPM` parseable as non-zero float
   - Audio tag: `#AUDIO` or `#MP3` (v1.0.0+: `#AUDIO` precedence; legacy: `#MP3` required)

2. **Required audio file exists**: resolved relative to `.txt` directory

3. **Notes parse without fatal errors**: unknown tokens warn, fatal numeric errors reject

4. **Each track has ≥1 non-empty sentence after cleanup**

**Error codes**:
- `ERROR_CORRUPT_SONG_MISSING_REQUIRED_HEADER`
- `ERROR_CORRUPT_SONG_FILE_NOT_FOUND`
- `ERROR_CORRUPT_SONG_MALFORMED_HEADER`
- `ERROR_CORRUPT_SONG_NO_NOTES`

**Source**: §3.1, §3.2, §3.3

**NFRs**: 1.4 (scan performance), 1.5 (memory)

**Acceptance**: F01, F02, F03, F04, F05

---

## 2.2 HttpFileServer

**Responsibility**: Serve song files and manifest to TV over HTTP.

**Lifecycle**:
- Starts before `hello` handshake (§8.7.2)
- Runs for session duration
- Stops on session end

**Functional Boundary**:
- `GET /manifest.json` from in-memory byte array (Cache-Control: no-cache)
- `GET /songs/<path>` with range request support
- Maps relative paths to SAF URIs
- 404 for missing, 416 for invalid ranges

**L2 Visible Shapes**:
- `KtorServer` — Ktor CIO + partial-content plugin
- `UriMapper` — relativePath → platformURI lookup
- `RangeHandler` — parses Range header, streams bytes

### Libraries (Pinned)

| Platform | Library | Version |
|----------|---------|---------|
| Android | `io.ktor:ktor-server-cio` | 2.3.12 |
| Android | `io.ktor:ktor-server-partial-content` | 2.3.12 |
| iOS | Swifter | 1.5.0 |

### Server Configuration

- Default port: `34781` (fallback to ephemeral if busy)
- Report actual port in `hello.httpPort`

### SAF File Reads (Android)

```kotlin
// File reads via ContentResolver (not java.io.File)
contentResolver.openAssetFileDescriptor(uri, "r")
contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), ...)

// Cloud file check: if SIZE=0 or null, treat as absent
```

### Security-Scoped Reads (iOS)

```swift
url.startAccessingSecurityScopedResource()
NSFileCoordinator().coordinate(readingItemAt: fileURL, options: .withoutChanges) { ... }
url.stopAccessingSecurityScopedResource()

// iCloud check: ubiquitousItemDownloadingStatus == .current
```

**Source**: §8.7.1, §8.7.2, §8.7.3

**NFRs**: 1.3 (HTTP throughput), 1.2 (reliability)

**Acceptance**: F18

---

## 2.3 PitchDetector

**Responsibility**: Capture mic audio and extract MIDI pitch at 50fps.

**Lifecycle**:
- Warms up on `assignSinger`
- Active during countdown (no frames sent) and singing (frames sent)
- Stops on `playbackState.stopped`

**Functional Boundary**:
- Mic capture at 44100Hz, 1024 samples/window (~23ms)
- FFT-YIN pitch detection (§5.2.5)
- Voicing gate + sensitivity presets (0-7)
- 3-frame median filter
- Outputs `midiNote` (0-127 or 255)

**L2 Visible Shapes**:
- `MicCapture` — AudioRecord (Android) / AVAudioEngine (iOS)
- `FftYinPipeline` — zero-allocation FFT, autocorrelation, d' computation
- `MedianFilter` — 3-byte circular buffer
- `SensitivityTable` — 8 presets from §5.2.5.3

### Pre-Allocated Buffers (Normative)

All buffers allocated once at init, reused every frame (zero GC):

| Buffer | Size | Purpose |
|--------|------|---------|
| `audioBuffer` | 1024 floats | Raw PCM input |
| `paddedBuffer` | 2048 floats | Zero-padded FFT input |
| `fftComplexBuffer` | 4096 floats | In-place FFT (interleaved real/imag) |
| `diffBuffer` | 1024 floats | d_t difference function |
| `normBuffer` | 1024 floats | d' normalized function |
| `medianHistory` | 3 bytes | Temporal smoothing |

### Algorithm Pipeline (Normative)

**Step 1: Voicing Gate**
```
maxAmp = max(abs(audioBuffer[i])) for i in 0..1023
if maxAmp < sensitivityTable[index].maxAmpCutoff:
    rawMidiNote = 255  // skip Steps 2-4
```

**Step 2: Linear Autocorrelation via FFT**
1. Zero-pad: copy audioBuffer to paddedBuffer[0..1023], fill [1024..2047] with 0
2. Forward FFT in-place
3. Power spectrum: `Re² + Im²`, zero imaginary
4. Inverse FFT: first 1024 reals = `r_t(tau)`

**Step 3: Squared Difference and Normalization**
```
d_t(tau) = E_start + E_shift(tau) - 2 * r_t(tau)
d'(0) = 1.0
d'(tau) = d_t(tau) / ((1/tau) * sum(d_t(1..tau)))
```

**Step 4: Candidate Selection**
- Find first local minimum where `d'(tau) < dPrimeCutoff`
- If none, use absolute minimum
- If `d'(tau) > 0.40`: unvoiced
- Else: `hz = 44100 / tau`, `rawMidiNote = clamp(round(69 + 12*log2(hz/440)), 0, 127)`

**Step 5: Temporal Smoothing**
- 3-frame rolling median
- If any of 3 frames is 255: output 255 (silence breaks combo)

### Sensitivity Table

| Index | maxAmpCutoff | dPrimeCutoff | Environment |
|-------|--------------|--------------|-------------|
| 0 | 0.01 | 0.10 | Whisper/Studio |
| 1 | 0.02 | 0.15 | High Sensitivity |
| 2 | 0.04 | 0.20 | Medium-High |
| **3** | **0.06** | **0.25** | **Default (Karaoke Room)** |
| 4 | 0.09 | 0.30 | Noisy Room |
| 5 | 0.13 | 0.35 | Low |
| 6 | 0.18 | 0.40 | Loud Party |
| 7 | 0.25 | 0.45 | Extreme Noise |

**Source**: §5.2.5

**NFRs**: 1.1 (pitch latency - CRITICAL), 1.6 (battery)

**Acceptance**: F17

---

## 2.4 NetworkClient

**Responsibility**: All network communication with TV.

**Lifecycle**:
- Starts on join (QR or code)
- Maintains WebSocket for session
- Handles reconnect

**Functional Boundary**:
- mDNS/NSD discovery for manual code
- QR payload parsing
- WebSocket client (hello, sessionState, ping/pong, assignSinger, playbackState, error)
- UDP sender (16-byte pitch frames)

**L2 Visible Shapes**:
- `ServiceDiscovery` — NSD (Android) / NWBrowser (iOS)
- `WebSocketClient` — OkHttp (Android) / URLSessionWebSocketTask (iOS)
- `UdpSender` — DatagramSocket (Android) / NWConnection (iOS)
- `MessageCodec` — JSON serialization
- `PitchFrameEncoder` — 16-byte binary encoding

### Pitch Frame Wire Format (16 bytes, little-endian)

```
Offset  Size  Type     Field
  0      4    uint32   seq              — frame counter
  4      4    int32    tvTimeMs         — phone's estimate of TV monotonic ms
  8      4    uint32   songInstanceSeq  — from assignSinger
 12      1    uint8    playerId         — 0=P1, 1=P2
 13      1    uint8    midiNote         — 0-127 voiced, 255=unvoiced
 14      2    uint16   connectionId     — from sessionState
```

### mDNS Discovery (Manual Code Entry)

1. Normalize input: strip spaces/hyphens, uppercase
2. Browse `_karaoke._tcp`
3. Match TXT field `code` against normalized input
4. Connect to matching service's host:port
5. Timeout: 5 seconds → "TV not found"

**Android**: Acquire `WifiManager.MulticastLock` during browse

**Required Permissions (Android)**:
```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />
<uses-permission android:name="android.permission.NEARBY_WIFI_DEVICES" android:usesPermissionFlags="neverForLocation" />
```

**Required Plist (iOS)**:
```xml
<key>NSLocalNetworkUsageDescription</key>
<key>NSBonjourServices</key><array><string>_karaoke._tcp</string></array>
<key>NSCameraUsageDescription</key>
<key>NSMicrophoneUsageDescription</key>
```

**Source**: §8.1, §8.2, §8.3, §8.5, §8.6

**NFRs**: 1.1 (pitch latency), 1.2 (reliability)

**Acceptance**: F12v2, F15, F20

---

## 2.5 ClockSync

**Responsibility**: Compute and maintain `clockOffsetMs` to estimate TV time.

**Lifecycle**:
- 5 exchanges on connect (100ms apart)
- Suspend during singing
- Resume on song end or reconnect
- Provides offset for frame `tvTimeMs`

**Functional Boundary**:
- Responds to `ping` with `pong`
- Processes `clockAck` to compute offset
- Best-of-N selection (smallest RTT)
- `toTvTime()` conversion

**L2 Visible Shapes**:
- `ClockSample` — t1, t2, t3, t4, RTT, offset
- `SampleBuffer` — 5-sample ring
- `BestOfNSelector` — picks lowest RTT

### Clock Sync Protocol

```
TV ──ping(pingId, tTvSendMs)──► Phone
              │
              ▼
         record t2 = phoneMonotonicMs at receipt
         record t3 = phoneMonotonicMs at send
              │
Phone ──pong(pingId, tTvSendMs, tPhoneRecvMs, tPhoneSendMs)──► TV
              │
              ▼
TV ──clockAck(pingId, tTvRecvMs)──► Phone
```

### Per-Sample Computation (Phone)

```
t1 = tTvSendMs      (from ping, echoed)
t2 = tPhoneRecvMs   (phone's record)
t3 = tPhoneSendMs   (phone's record)
t4 = tTvRecvMs      (from clockAck)

RTT = (t4 - t1) - (t3 - t2)
clockOffsetMs = ((t2 - t1) + (t3 - t4)) / 2
```

### Sample Selection

- Keep last 5 samples
- Discard if `RTT < 0` or `RTT > 2000`
- Use sample with smallest RTT

### TV Time Estimation

```kotlin
fun toTvTime(phoneMonotonicMs: Long): Long = phoneMonotonicMs + clockOffsetMs
```

**Source**: §8.8

**NFRs**: 1.1 (pitch latency)

**Acceptance**: F14v2

---

## 2.6 SessionCoordinator

**Responsibility**: Orchestrate phone state and coordinate components.

**Lifecycle**: App lifetime.

**Functional Boundary**:
- Phone state FSM: Disconnected → Connecting → Connected(Spectator|Singer)
- Routes incoming messages
- Triggers scan on folder change
- Starts/stops pitch detection on assignSinger/playbackState
- Exposes `StateFlow<PhoneState>` for UI

**L2 Visible Shapes**:
- `PhoneStateMachine` — transitions + guards
- `MessageRouter` — dispatches WebSocket messages
- `ReconnectPolicy` — 5x immediate + exponential backoff

**Source**: §7.3, §7.4

**NFRs**: 1.2 (reliability)

**Acceptance**: F15

---

# 3. Component APIs

## 3.1 SongScanner

```kotlin
interface SongScanner {
    val scanState: StateFlow<ScanState>
    val songIndex: StateFlow<SongIndex>
    
    suspend fun rescan(): ScanResult
    suspend fun setFolder(uri: Uri): ScanResult
    fun getFolder(): Uri?
}

data class ScanState(
    val phase: ScanPhase,        // IDLE, SCANNING, VALIDATING, COMPLETE, ERROR
    val songsDiscovered: Int,
    val songsValidated: Int,
    val songsInvalid: Int,
    val currentFile: String?
)

data class SongIndex(
    val entries: List<SongEntry>,
    val invalidEntries: List<InvalidSong>,
    val manifestJson: ByteArray,
    val uriMap: Map<String, Uri>
)
```

## 3.2 HttpFileServer

```kotlin
interface HttpFileServer {
    val serverState: StateFlow<ServerState>
    
    suspend fun start(uriMap: Map<String, Uri>, manifestJson: ByteArray): Int
    fun stop()
    fun updateManifest(manifestJson: ByteArray, uriMap: Map<String, Uri>)
}

data class ServerState(
    val running: Boolean,
    val port: Int,
    val activeRequests: Int,
    val totalBytesServed: Long
)
```

## 3.3 PitchDetector

```kotlin
interface PitchDetector {
    val detectorState: StateFlow<DetectorState>
    
    fun start()
    fun stop()
    fun setSensitivity(index: Int)
    fun setMuted(muted: Boolean)
    fun onPitchFrame(callback: (PitchFrame) -> Unit)
}

data class DetectorState(
    val active: Boolean,
    val muted: Boolean,
    val currentAmplitude: Float,
    val sensitivityIndex: Int
)

data class PitchFrame(
    val midiNote: UByte,
    val maxAmp: Float,
    val phoneMonotonicMs: Long
)
```

## 3.4 NetworkClient

```kotlin
interface NetworkClient {
    val connectionState: StateFlow<ConnectionState>
    val serverMessages: SharedFlow<ServerMessage>
    
    suspend fun connectViaQr(payload: String): ConnectResult
    suspend fun connectViaCode(code: String): ConnectResult
    fun disconnect()
    fun sendPitchFrame(frame: PitchFrameWire)
}

data class ConnectionState(
    val phase: ConnectionPhase,
    val sessionId: String?,
    val connectionId: UShort?,
    val tvEndpoint: String?,
    val udpPort: Int?,
    val tvIpAddress: String?
)

sealed class ServerMessage {
    data class SessionState(...) : ServerMessage()
    data class Ping(...) : ServerMessage()
    data class ClockAck(...) : ServerMessage()
    data class AssignSinger(...) : ServerMessage()
    data class PlaybackState(...) : ServerMessage()
    data class Error(...) : ServerMessage()
}

data class PitchFrameWire(
    val seq: UInt,
    val tvTimeMs: Int,
    val songInstanceSeq: UInt,
    val playerId: UByte,
    val midiNote: UByte,
    val connectionId: UShort
)
```

## 3.5 ClockSync

```kotlin
interface ClockSync {
    val clockOffsetMs: StateFlow<Long?>
    val syncQuality: StateFlow<SyncQuality>
    
    fun handlePing(ping: ServerMessage.Ping): ClientMessage.Pong
    fun handleClockAck(ack: ServerMessage.ClockAck)
    fun toTvTime(phoneMonotonicMs: Long): Long
    fun reset()
}

data class SyncQuality(
    val samplesCollected: Int,
    val bestRttMs: Long?,
    val synchronized: Boolean
)
```

## 3.6 SessionCoordinator

```kotlin
interface SessionCoordinator {
    val phoneState: StateFlow<PhoneState>
    
    suspend fun joinViaQr(payload: String): JoinResult
    suspend fun joinViaCode(code: String): JoinResult
    fun leave()
    fun setMuted(muted: Boolean)
    suspend fun rescanLibrary(): ScanResult
    suspend fun setLibraryFolder(uri: Uri): ScanResult
}

sealed class PhoneState {
    object Disconnected : PhoneState()
    data class Connecting(val method: String) : PhoneState()
    data class Connected(
        val role: Role,
        val playerId: String?,
        val sessionId: String,
        val isSourcePhone: Boolean
    ) : PhoneState()
    data class Reconnecting(val attempt: Int) : PhoneState()
}
```

## 3.7 SongEntry (manifest.json schema)

```kotlin
@Serializable
data class SongEntry(
    val relativeTxtPath: String,
    val modifiedTimeMs: Long,
    val title: String,
    val artist: String,
    val album: String? = null,
    val year: Int? = null,
    val genre: String? = null,
    val isDuet: Boolean,
    val hasRap: Boolean,
    val hasVideo: Boolean,
    val hasInstrumental: Boolean,
    val canMedley: Boolean,
    val medleySource: String? = null,
    val medleyStartBeat: Int? = null,
    val medleyEndBeat: Int? = null,
    val startSec: Float,
    val previewStartSec: Float,
    val txtUrl: String?,
    val audioUrl: String?,
    val videoUrl: String? = null,
    val coverUrl: String? = null,
    val backgroundUrl: String? = null,
    val instrumentalUrl: String? = null,
    val vocalsUrl: String? = null
)
```

---

# 4. SLAs

All tests are JVM-only unless noted.

## 4.1 Pitch Frame Latency

| Metric | Limit | Test |
|--------|-------|------|
| FFT-YIN computation | ≤10ms | F17 + timing wrapper |
| `tvTimeMs` accuracy | ±5ms | F14v2 clock math |

## 4.2 HTTP Range Response

| Metric | Limit | Test |
|--------|-------|------|
| First byte | ≤100ms | F18 with Ktor testApplication |
| Range correctness | Exact boundaries | F18 |

## 4.3 Scan Performance

| Metric | Limit | Test |
|--------|-------|------|
| Parse rate | ≥100 TXT/sec | F01-F05 batch timing |

## 4.4 Reconnect Timing

| Metric | Limit | Test |
|--------|-------|------|
| First retry | ≤500ms | F15 with fake clock |
| Backoff cap | 30s | F15 |

## 4.5 Clock Sync

| Metric | Limit | Test |
|--------|-------|------|
| 5-sample sync | ≤3s | F14v2 |
| Invalid RTT rejection | ≥2000ms discarded | F14v2 |

---

# 5. Resolved Blockers

## 5.1 Pitch Pipeline Threading

**Resolution**: Process in AudioRecord callback thread. FFT-YIN ≤10ms fits in 23ms window. UDP send is non-blocking.

## 5.2 HTTP vs Pitch Priority

**Resolution**: OS scheduling. AudioRecord has real-time priority; Ktor runs on Dispatchers.IO. No explicit management needed.

## 5.3 SAF URI Persistence

**Resolution**: `takePersistableUriPermission()` + SharedPreferences. Check permission on app start; prompt if revoked.

## 5.4 Mute Toggle

**Resolution**: Keep capturing, send `midiNote=255`. VU meter still works.

## 5.5 Clock Sync During Countdown

**Resolution**: No sync during countdown or singing. Sync on: connect (5 samples), song end, reconnect.

## 5.6 Manifest URL Construction

**Resolution**: Store relative paths. Build full URLs at manifest serialization time using server's bound address.

## 5.7 iOS Backgrounding

**Resolution**: Document as limitation. Show "Keep app in foreground" banner when singing or serving.

---

# 6. Project Plan

Aligned with TV iterations. Phone always uses Mock TV.

## 6.1 Iteration Overview

| Iter | TV Iter | Phone Goal | Mock TV Needed |
|------|---------|------------|----------------|
| 0 | 0 | Song scanning | No |
| 1 | 1 | HTTP server + Session join | Yes |
| 2 | 2 | Clock sync + Pitch detection | Yes |
| 3 | 3 | Full singing flow | Yes |
| 4 | 4 | Polish + iOS | Yes |

## 6.2 Iter 0 — Song Scanning (Week 1)

**Goal**: Parse and validate songs. No network.

| Deliverable | Fixtures |
|-------------|----------|
| SAF folder picker | — |
| TxtParser (shared with TV) | F01-F05 |
| Validation engine | F01 |
| Settings screen | — |
| Local song list UI | — |

**DOD**:
- [ ] F01–F05 pass (JVM)
- [ ] Select folder → songs scanned
- [ ] No Android deps in parser

## 6.3 Iter 1 — HTTP Server + Session Join (Week 2)

**Goal**: Serve manifest, join session.

| Deliverable | Fixtures |
|-------------|----------|
| Ktor HTTP server | F18 |
| `/manifest.json` + `/songs/<path>` | F18 |
| mDNS discovery | — |
| QR scanner | — |
| WebSocket client | F15, F20 |
| Join + Waiting screens | — |

**DOD**:
- [ ] F15, F18, F20 pass (JVM)
- [ ] curl manifest works
- [ ] Handshake completes with mock TV

**Mock TV**: `handshake_only.json`

## 6.4 Iter 2 — Clock Sync + Pitch Detection (Week 3-4)

**Goal**: Sync clock, detect pitch, stream frames.

| Deliverable | Fixtures |
|-------------|----------|
| Clock sync | F14v2 |
| Mic capture | — |
| FFT-YIN pipeline | F17 |
| UDP sender | F12v2 |
| VU meter | — |

**DOD**:
- [ ] F12v2, F14v2, F17 pass (JVM)
- [ ] Sing A4 → midiNote=69
- [ ] Frames stream at 50fps

**Mock TV**: `sing_10s.json`

## 6.5 Iter 3 — Full Singing Flow (Week 5-6)

**Goal**: Complete assign → countdown → sing → stop cycle.

| Deliverable | Fixtures |
|-------------|----------|
| AssignSinger handling | — |
| PlaybackState handling | — |
| Active Mic screen | — |
| Mute toggle | — |
| Reconnect logic | F15 |

**DOD**:
- [ ] Full sing cycle works
- [ ] Reconnect within 2.5s

**Mock TV**: `sing_10s.json`, `reconnect.json`

## 6.6 Iter 4 — Polish + iOS (Week 7-8)

**Goal**: Production quality, iOS port.

| Deliverable | Notes |
|-------------|-------|
| iOS song scanner | Security-scoped bookmarks |
| iOS HTTP server | Swifter |
| iOS pitch detection | AVAudioEngine + vDSP |
| Backgrounding warning | Both platforms |
| Error modals | — |
| Persistent settings | — |

**DOD**:
- [ ] Android polished
- [ ] iOS working
- [ ] F19 passes (iOS)

---

# Appendix A: Mock TV Specification

Simple JVM process. No REPL — runs scripted scenarios.

## A.1 Usage

```bash
# Basic handshake
./gradlew :mock-tv:run

# With scenario
./gradlew :mock-tv:run --args="--scenario=scenarios/sing_10s.json"
```

## A.2 Scenario Format

```json
{
  "joinCode": "TESTABCD",
  "wsPort": 8765,
  "udpPort": 34567,
  "steps": [
    { "action": "waitForHello" },
    { "action": "sendSessionState", "connectionId": 1 },
    { "action": "runClockSync", "samples": 5 },
    { "action": "wait", "ms": 1000 },
    { "action": "sendAssignSinger", "playerId": "P1", "countdown": 3000 },
    { "action": "wait", "ms": 3000 },
    { "action": "sendPlaybackState", "state": "playing" },
    { "action": "collectFrames", "durationMs": 10000 },
    { "action": "sendPlaybackState", "state": "stopped" },
    { "action": "printFrameStats" }
  ]
}
```

## A.3 Built-in Scenarios

| Scenario | Purpose |
|----------|---------|
| `handshake_only.json` | Connect + clock sync |
| `sing_10s.json` | P1 sings 10 seconds |
| `reconnect.json` | Disconnect after 5s, allow reconnect |
| `two_players.json` | Assign P1 and P2 |

## A.4 Output

```
[MockTV] Started on ws://192.168.1.10:8765, UDP :34567
[MockTV] Advertising _karaoke._tcp code=TESTABCD
[MockTV] Phone connected: clientId=abc123
[MockTV] Clock sync: offset=-42ms, RTT=28ms
[MockTV] Assigned P1
[MockTV] Received 487 frames (48.7 fps)
[MockTV] Done.
```

## A.5 Implementation

```
mock-tv/
├── src/main/kotlin/
│   ├── Main.kt
│   ├── MockTvServer.kt
│   ├── ScenarioRunner.kt
│   └── FrameCollector.kt
└── scenarios/
    ├── handshake_only.json
    ├── sing_10s.json
    └── reconnect.json
```

~300 lines total.
