# Couchraoke TV App — Technical Architecture

**Version**: 1.0  
**Date**: 2026-04-10  
**Scope**: Android TV Host App (phone companion OOS)  
**Functional Spec Reference**: `../tv_app_functional_spec.md`

---

## Table of Contents

- [1. Non-Functional Requirements](#1-non-functional-requirements)
- [2. Top-Level Components](#2-top-level-components)
  - [2.1 PlaybackCoordinator](#21-playbackcoordinator)
  - [2.2 ScoringEngine](#22-scoringengine)
  - [2.3 NetworkController](#23-networkcontroller)
  - [2.4 UsdxParser](#24-usdxparser)
  - [2.5 LibraryManager](#25-librarymanager)
  - [2.6 UI Layer](#26-ui-layer)
- [3. Component Interactions](#3-component-interactions)
  - [3.1 Data Flow Diagrams](#31-data-flow-diagrams)
  - [3.2 Interaction Contracts](#32-interaction-contracts)
- [4. Internal Architectures](#4-internal-architectures)
  - [4.1 GamePhase FSM](#41-gamephase-fsm)
  - [4.2 Medley Segment Transitions](#42-medley-segment-transitions)
  - [4.3 Scoring Coroutine](#43-scoring-coroutine)
  - [4.4 Jitter Buffer](#44-jitter-buffer)
  - [4.5 Clock Sync Logic](#45-clock-sync-logic)
  - [4.6 Beat-Time Conversion](#46-beat-time-conversion)
- [5. Resolved Blockers](#5-resolved-blockers)
- [6. Test Fixtures](#6-test-fixtures)
- [7. Project Plan](#7-project-plan)
- [Appendix A: Mock Phone Specification](#appendix-a-mock-phone-specification)

---

# 1. Non-Functional Requirements

Ordered by priority. These describe *how* the system should be built.

## 1.1 Testability (Highest)

**Why**: Claude Code + TDD workflow. Components must be testable in isolation.

| Requirement | Implementation |
|-------------|----------------|
| Timing-sensitive logic accepts injected clocks | `FakeClock` / `TestCoroutineScheduler` |
| All I/O behind interfaces | Network, Media3, filesystem mockable |
| Scoring testable with fixture pitch streams | No real UDP required |
| Coverage gates | 80% overall / 60% per-file (see testing/testing_policy.md) |

## 1.2 Modularity

**Why**: Iteration plan builds features incrementally. Iter 0 has no network. Iter 1 has no scoring.

| Requirement | Implementation |
|-------------|----------------|
| Coordinator uses narrow interfaces | `ScoringEngine`, `NetworkController`, etc. |
| Scoring has zero UI knowledge | Pure math, emits `StateFlow` |
| Parser has zero network knowledge | `ByteArray` in, `ParsedSong` out |

## 1.3 Debuggability

**Why**: Timing bugs in distributed systems (phone-TV) are hard to reproduce.

| Requirement | Implementation |
|-------------|----------------|
| Pitch frames logged | `tvTimeMs`, `arrivalTvMs`, `songInstanceSeq` |
| Clock sync samples logged | RTT, offset, chosen sample |
| GamePhase transitions logged | State, timestamp, trigger |
| Structured logging | JSON or tagged format, not string concat |

## 1.4 Graceful Degradation

**Why**: Phones disconnect, Wi-Fi hiccups, files go missing.

| Scenario | Behavior |
|----------|----------|
| Singer disconnect | Auto-pause (`DisconnectPaused`), not crash |
| Song source disconnect | Error modal, return to song list |
| Clock sync failure | Use best available sample, log warning |
| Manifest fetch failure | Retain previous catalog, show toast |

## 1.5 Offline-First

**Why**: No cloud. Everything runs on LAN.

| Requirement | Implementation |
|-------------|----------------|
| Zero external network dependencies | No internet required |
| No cloud analytics/telemetry | All local |
| mDNS for discovery | No coordination server |

## 1.6 Minimal Footprint

**Why**: Target hardware constraints (2GB RAM, Mali-G31, slow eMMC).

### Target Hardware Profile

Normative target device: mid-tier Android TV stick/box.

| Component | Spec | Constraint |
|-----------|------|------------|
| SoC | Amlogic S905X4 (quad-core Cortex-A55 @ 1.8GHz) | Decent CPU, weak GPU. No complex shaders. |
| RAM | 2GB DDR3/DDR4 | App budget: ≤512MB including ExoPlayer buffers. |
| Storage | 16GB eMMC | Very slow R/W. No temp files during playback. |
| GPU | Mali-G31 MP2 (OpenGL ES 3.2) | Flat rendering only. No blur, glow, or post-processing. |
| OS | Android TV 11–14 | Min API 30. Multicast lock required for mDNS. |

Higher-spec devices (4GB RAM) must work without degradation; lower-spec (1GB RAM, S805) are out of scope.

### Memory Budgets

| Resource | Budget | Notes |
|----------|--------|-------|
| App total | ≤512MB | Heap + native + ExoPlayer. System overhead ~800MB–1GB on 2GB devices. |
| ExoPlayer audio buffer | ≤64MB | `DefaultLoadControl.Builder` |
| ExoPlayer video buffer | ≤128MB | `DefaultLoadControl.Builder` |
| Disk writes during playback | Zero | No temp files, no disk cache |

### Performance Targets

| Screen | Target |
|--------|--------|
| Singing screen | ≥30fps sustained with 1–2 active pitch lanes |
| Song list grid | ≥60fps scroll at 1080p, 3-column grid with covers |
| Library index | ≥1000 songs in memory without UI jank |

### Implementation Requirements

| Requirement | Implementation |
|-------------|----------------|
| No per-frame allocation in hot paths | Pre-allocated buffers |
| Single-activity architecture | No fragment transaction overhead |
| Lazy initialization | ExoPlayer, mDNS created on demand |
| ExoPlayer workaround for S905X4 | Custom `MediaCodecSelector` bypassing `PerformancePoint` checks (see below) |

**ExoPlayer Device Workaround**: Amlogic S905X4 devices report inaccurate `PerformancePoint` capabilities. Media3 may mark HD/FHD tracks as `NO_EXCEEDS_CAPABILITIES`, causing unnecessary downscaling. Add target `Build.DEVICE`/`Build.MODEL` to custom `MediaCodecSelector` that bypasses `PerformancePoint` checks, following Media3's `MediaCodecInfo.needsIgnorePerformancePointsWorkaround()` pattern.

---

# 2. Top-Level Components

Six L1 components directly under the TV app.

```
┌─────────────────────────────────────────────────────────────────┐
│                         TV App                                   │
├─────────────────────────────────────────────────────────────────┤
│  PlaybackCoordinator                                             │
│    │                                                             │
│    ├── ScoringEngine ←── pitchFrames: SharedFlow                │
│    │                                                             │
│    ├── NetworkController ──→ WebSocket, UDP, HTTP                │
│    │                                                             │
│    ├── UsdxParser                                                │
│    │                                                             │
│    ├── LibraryManager                                            │
│    │                                                             │
│    └── UI Layer (Compose + Media3)                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2.1 PlaybackCoordinator

**Responsibility**: Single source of truth for game phase. Orchestrates all subsystems during song lifecycle. Owns `songInstanceSeq`. Manages clock sync logic. Derives session locked state.

**Lifecycle**: Scoped to app lifetime.

### Responsibilities (Normative)

1. Own and increment `songInstanceSeq` (`UInt`) on every song start, including Restart.
2. Drive song start: fetch and parse chart, configure scoring, set active song for pitch ingestion, prepare playback, lock session, send `assignSinger`, then start countdown or playback; capture `songStartTvMs` when playback begins and push into scoring.
3. Construct `PlaybackStateMessage` on each playback-bearing game-phase transition and push to network layer.
4. Coordinate pause, resume, restart, and quit across playback, scoring, and phone state.
5. Handle required-singer disconnects by auto-pausing and presenting wait / continue / quit options.
6. Handle reconnect by updating `connectionId`, re-sending `assignSinger`, and sending current `playbackState`.
7. Drive medley segment transitions ([§4.2](#42-medley-segment-transitions)).
8. Capture `songStartTvMs` per timing spec and push into scoring before note finalization begins.
9. Trigger clock-sync re-exchange at song end.
10. Transition session FSM between Open and Locked at song start/end.
11. Interact with subsystems only through narrow interfaces (`ScoringEngine`, `NetworkController`, etc.). No direct references to implementation classes.

### Public API

```kotlin
interface PlaybackCoordinator {
    val gamePhase: StateFlow<GamePhase>
    val songInstanceSeq: StateFlow<UInt>
    
    // Song lifecycle
    suspend fun startSong(song: IndexedSong, players: List<PlayerAssignment>)
    suspend fun startMedley(playlist: List<MedleySegment>, players: List<PlayerAssignment>)
    fun pause()
    fun resume()
    suspend fun restart()
    fun quit()
    
    // Called by NetworkController
    fun onSingerDisconnected(playerId: PlayerId)
    fun onSingerReconnected(playerId: PlayerId, newConnectionId: UShort)
    
    // Derived state for NetworkController
    fun isLocked(): Boolean = gamePhase.value !in setOf(Idle, Results)
    
    // Clock sync (logic here, transport via NetworkController)
    suspend fun runClockSync(phoneId: String): ClockSyncResult
}
```

### NFRs Applied

- **Testability**: All subsystem interactions via injected interfaces
- **Modularity**: Knows nothing about UI rendering
- **Debuggability**: Logs every phase transition with timestamp

### SLAs

| Metric | Target | Test |
|--------|--------|------|
| Phase transition latency | <50ms | Unit test, measure emission time |
| Clock sync completes | <3s for 5 samples | F14v2 fixture |

### L2 Visible Shapes

- **GamePhaseFSM**: 8 states, validates transitions (see [§4.1](#41-gamephase-fsm))
- **MedleySequencer**: Segment index, prebuffer trigger, transition coroutine
- **ClockSyncLogic**: Offset computation, best-of-N selection, RTT filtering

### Source

Functional spec: system overview, session lifecycle, clock sync

### Acceptance Criteria

- F14v2, F15, F16, F21, F22 pass

### Knowledge Gaps

None.

---

## 2.2 ScoringEngine

**Responsibility**: Evaluate pitch frames against chart notes, accumulate scores, compute line bonus. Owns jitter buffer for frame storage and range queries.

**Lifecycle**: Active during song. Reset on restart.

### Public API

```kotlin
interface ScoringEngine {
    val playerScores: StateFlow<Map<PlayerId, PlayerScore>>
    val livePitch: SharedFlow<PitchEvent>  // For UI pitch cursor
    
    fun loadChart(chart: ParsedSong, micDelayMs: Int, medleyWindow: BeatRange?)
    fun setSongStart(songStartTvMs: Long)
    fun start()
    fun suspend()
    fun resume()
    suspend fun finalizeAll(): Map<PlayerId, PlayerScore>
    fun reset()
    fun stop()
}

data class PlayerScore(
    val score: Double,           // Normal + Rap accumulator
    val scoreGolden: Double,     // Golden + RapGolden accumulator
    val scoreLine: Double,       // Line bonus accumulator
    val scoreLast: Double,       // Score at last sentence end
    val scoreInt: Int,           // Rounded for display
    val scoreGoldenInt: Int,
    val scoreLineInt: Int,
    val scoreTotalInt: Int       // Final display score
)

data class PitchEvent(
    val playerId: PlayerId,
    val midiNote: UByte,
    val toneValid: Boolean,
    val tvTimeMs: Long,
    val arrivalTvMs: Long
)
```

### NFRs Applied

- **Testability**: Subscribes to `NetworkController.pitchFrames`, injectable
- **Modularity**: Pure math, no network/UI knowledge
- **Minimal Footprint**: Jitter buffer pre-allocated, no per-frame allocation

### SLAs

| Metric | Target | Test |
|--------|--------|------|
| Evaluation frequency | 100Hz ±5% | Instrumented test |
| Jitter buffer capacity | 450ms × 50fps × 2 players | Unit test, verify no overflow |
| Perfect score | `scoreTotalInt == 10000` | F08 with perfect input |

### L2 Visible Shapes

- **JitterBuffer**: Ring buffer keyed by `tvTimeMs`, range query for note windows (see [§4.4](#44-jitter-buffer))
- **ScoringCoroutine**: 100Hz loop, uses `System.nanoTime()`, triggers finalization (see [§4.3](#43-scoring-coroutine))
- **NoteEvaluator**: Hit detection, octave normalization, tolerance
- **LineBonusCalculator**: Sentence completion, -2 forgiveness

### Source

Functional spec: timing/scoring rules

### Acceptance Criteria

- F06, F08, F09, F10, F11, F13, F24 pass

### Knowledge Gaps

None.

---

## 2.3 NetworkController

**Responsibility**: All network I/O. WebSocket server for control messages. UDP socket for pitch frames (validates, emits to SharedFlow). HTTP client for manifest/txt fetches. Connection tracking.

**Lifecycle**: Active for app lifetime. Sockets bound at startup.

### Public API

```kotlin
interface NetworkController {
    val connectedPhones: StateFlow<List<ConnectedPhone>>
    val pitchFrames: SharedFlow<PitchFrame>
    val phoneEvents: SharedFlow<PhoneEvent>
    val joinCode: String
    
    // Lifecycle
    fun start(udpPort: Int, wsPort: Int)
    fun stop()
    
    // Outbound messages
    fun sendSessionState(phoneId: String)
    fun broadcastPlaybackState(message: PlaybackStateMessage)
    fun sendAssignSinger(phoneId: String, message: AssignSingerMessage)
    fun sendError(phoneId: String, code: String, message: String)
    
    // Clock sync transport
    suspend fun sendPing(phoneId: String): PongResponse
    fun sendClockAck(phoneId: String, ack: ClockAckMessage)
    
    // HTTP
    suspend fun fetchManifest(phone: ConnectedPhone): Result<List<SongEntry>>
    suspend fun fetchTxt(url: String): Result<ByteArray>
}

data class ConnectedPhone(
    val clientId: String,
    val connectionId: UShort,
    val deviceName: String,
    val httpPort: Int,
    val ipAddress: String
)

data class PitchFrame(
    val playerId: PlayerId,
    val midiNote: UByte,
    val tvTimeMs: Long,
    val arrivalTvMs: Long,
    val songInstanceSeq: UInt,
    val seq: UShort
)

sealed class PhoneEvent {
    data class Connected(val phone: ConnectedPhone) : PhoneEvent()
    data class Disconnected(val clientId: String, val wasAssignedSinger: Boolean) : PhoneEvent()
    data class Reconnected(val clientId: String, val newConnectionId: UShort) : PhoneEvent()
}
```

### NFRs Applied

- **Testability**: Interface-based, mock for unit tests
- **Graceful Degradation**: Emits events on disconnect, doesn't crash
- **Debuggability**: Logs all messages with timestamps

### SLAs

| Metric | Target | Test |
|--------|--------|------|
| UDP frame validation | <1ms per frame | Microbenchmark |
| Manifest fetch | <2s on LAN | Instrumented with real HTTP |
| WebSocket message latency | <50ms | Round-trip test |

### L2 Visible Shapes

- **WebSocketServer**: Ktor, handles control channel
- **UdpListener**: DatagramSocket, validates frames, emits to SharedFlow
- **HttpClient**: Ktor client, fetches manifests and txt files
- **ConnectionRegistry**: Tracks clientId → connectionId mapping
- **JoinCodeValidator**: Checks token on WebSocket connect
- **MdnsAdvertiser**: jmDNS-based service advertisement (see below)

### mDNS Service Advertisement (Normative)

TV MUST advertise via mDNS for session duration:

| Field | Value |
|-------|-------|
| Service type | `_karaoke._tcp` |
| Instance name | `KaraokeTV-<last4>` (last 4 chars of join code, e.g., `KaraokeTV-EFGH`) |
| Port | WebSocket server port |
| TXT `code` | Full join code, uppercase, no hyphens (e.g., `code=ABCDEFGH`) |
| TXT `v` | `1` (protocol version) |

**Library**: Use jmDNS (not NsdManager — unreliable on some OEM firmware).

**Multicast Lock (Required)**:
1. Declare permissions in `AndroidManifest.xml`:
   - `android.permission.CHANGE_WIFI_MULTICAST_STATE`
   - `android.permission.ACCESS_LOCAL_NETWORK`
2. Acquire `WifiManager.MulticastLock` (tag: `"jmdns_lock"`) before starting jmDNS.
3. Release on session end.

Without lock, multicast packets silently dropped on many Android TV devices.

**Android 17+**: Request local-network permission before starting mDNS, WebSocket server, UDP listener, or HTTP fetches to peers.

### connectionId Assignment (Normative)

- Assign unique `connectionId` (uint16) on successful `hello` handshake. Simple incrementing counter from 1.
- Deliver in `sessionState` response to `hello`.
- On reconnect: assign **new** `connectionId` (not reuse old one).

### UDP Frame Validation (Normative)

On receipt of UDP datagram:
1. Datagram must be exactly 16 bytes (else silently drop).
2. Look up `connectionId` (bytes 14–15) in active connection table.
3. Verify it matches expected connection for `playerId` (byte 12).
4. Verify `songInstanceSeq` matches active song.
5. If any check fails: silently drop.

This is best-effort routing, not a security control.

### Pitch Frame Processing

**MIDI-to-scoring conversion**:
```
Tone = midiNote - 36    (C2=36 → Tone=0)
```
This value is input to octave normalization in scoring.

**Live pitch stream**: After validation and jitter buffer insert, emit `PitchEvent` on `SharedFlow` for UI pitch cursor. `SharedFlow` config: `replay=0`, `extraBufferCapacity=64`, `onBufferOverflow=DROP_OLDEST`. UI stream does not affect scoring; jitter buffer is scoring source of truth.

### HTTP Cleartext Configuration (Required)

TV fetches HTTP assets from LAN phones. Include in `res/xml/network_security_config.xml` and reference via `android:networkSecurityConfig` in manifest:

```xml
<network-security-config>
    <base-config cleartextTrafficPermitted="true">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>
</network-security-config>
```

Without this, `http://` requests to phone IPs fail with `CLEARTEXT_NOT_PERMITTED` on API 28+.

### Asset Streaming

- Pass song URLs directly to ExoPlayer (`MediaItem.fromUri(audioUrl)`) or Coil (images). No intermediate storage.
- ExoPlayer begins playback after ~2–4s buffered. MUST NOT wait for full download.
- HTTP failure (404, timeout): suppress for images; recoverable error for audio.

### Source

Functional spec: transport and protocol contract

### Acceptance Criteria

- F12v2, F15, F18, F20 pass

### Knowledge Gaps

None.

---

## 2.4 UsdxParser

**Responsibility**: Parse USDX TXT format into `ParsedSong` model. Header extraction, body tokenization, beat computation, error handling.

**Lifecycle**: Stateless. Called on demand.

### Public API

```kotlin
interface UsdxParser {
    fun parse(txtBytes: ByteArray): Result<ParsedSong>
}

data class ParsedSong(
    val header: SongHeader,
    val timing: SongTiming,
    val tracks: List<Track>  // 1 for solo, 2 for duet
)

data class SongHeader(
    val title: String,
    val artist: String,
    val bpm: Float,           // Raw #BPM (before ×4)
    val gap: Float,           // #GAP in ms
    val videoGap: Float?,
    val start: Float?,
    val end: Float?,
    val isDuet: Boolean
    // ... other header fields per functional spec §4.2
)

data class SongTiming(
    val bpmInternal: Float,   // #BPM × 4
    val gapMs: Float
)

data class Track(
    val playerId: PlayerId,   // P1 or P2
    val lines: List<Line>
)

data class Line(
    val notes: List<NoteEvent>,
    val lineScoreValue: Int   // Precomputed sum(duration × ScoreFactor)
)

data class NoteEvent(
    val type: NoteType,       // Normal, Golden, Rap, RapGolden, Freestyle
    val startBeat: Int,
    val duration: Int,
    val tone: Int,            // Semitone (USDX scale, C2=0)
    val text: String
)

enum class NoteType { Normal, Golden, Rap, RapGolden, Freestyle }
```

### NFRs Applied

- **Testability**: Pure function, no I/O
- **Modularity**: Zero knowledge of network, playback, scoring

### SLAs

| Metric | Target | Test |
|--------|--------|------|
| Parse time | <50ms for 10KB txt | Benchmark with F03 fixtures |
| Memory | No allocation beyond result | Verify with profiler |

### L2 Visible Shapes

- **HeaderParser**: Extracts `#TAG:value` lines
- **BodyTokenizer**: Tokenizes note lines (`:`, `*`, `F`, `R`, `G`, `-`, `E`, `P`)
- **BeatCalculator**: Applies BPM×4 rule for supported static-BPM charts
- **ErrorCollector**: Accumulates warnings, decides accept/reject

### Source

Functional spec: USDX format support and parsed song model

### Acceptance Criteria

- F01, F02, F03, F04, F05 pass

### Knowledge Gaps

None — grammar fully specified.

---

## 2.5 LibraryManager

**Responsibility**: Aggregate song manifests from connected phones. Maintain in-memory song index. Handle phone disconnect (remove songs). Provide search/filter.

**Lifecycle**: Active for app lifetime. Index rebuilt on phone connect/disconnect.

### Public API

```kotlin
interface LibraryManager {
    val songs: StateFlow<List<IndexedSong>>
    
    suspend fun onPhoneConnected(phone: ConnectedPhone)
    fun onPhoneDisconnected(clientId: String)
    suspend fun refreshPhone(clientId: String)
    suspend fun refreshAll()
    
    fun getSong(songId: String): IndexedSong?
}

data class IndexedSong(
    val songId: String,        // "clientId::relativeTxtPath"
    val phoneClientId: String,
    val title: String,
    val artist: String,
    val album: String?,
    val coverUrl: String?,
    val audioUrl: String,
    val videoUrl: String?,
    val txtUrl: String,
    val isDuet: Boolean,
    val canMedley: Boolean,
    val previewStartSec: Float
)
```

### NFRs Applied

- **Testability**: NetworkController injected for fetches
- **Graceful Degradation**: Fetch failure retains previous catalog, shows toast

### SLAs

| Metric | Target | Test |
|--------|--------|------|
| Index capacity | ≥1000 songs without jank | Load test with synthetic manifest |
| Rebuild time | <500ms for 500 songs | Benchmark |

### L2 Visible Shapes

- **ManifestFetcher**: Uses NetworkController.fetchManifest()
- **SongIndex**: In-memory map, keyed by songId
- **SortComparator**: Artist → Album → Title ordering

### Catalog Fetch Triggers (Normative)

TV rebuilds library by fetching `GET /manifest.json` from each phone at exactly these points:

1. **Phone connection**: After successful `hello`/`sessionState` handshake, fetch manifest before making songs visible.
2. **Results screen**: When Results displayed (after any song/medley run), re-fetch all manifests. Ensures catalog changes (e.g., rescan during song) are reflected.
3. **Manual refresh**: When user triggers Refresh in Settings > Song Library.

Fetch replaces all songs for that `clientId` (not append). On failure: retain previous catalog, show error toast.

**Phone disconnect**: Immediately remove all songs for that `clientId` from library.

### Source

Functional spec: library lifecycle and song index

### Acceptance Criteria

- F01, F23 pass

### Knowledge Gaps

None.

---

## 2.6 UI Layer

**Responsibility**: All Compose screens. Owns Media3 for playback. Observes state from other components. Emits user intents and playback events.

**Lifecycle**: Standard Android Activity/Compose lifecycle.

### Public API (Exposed to System)

```kotlin
// Provided by SingingScreen ViewModel
interface PlaybackObservable {
    val currentPositionMs: StateFlow<Long>
    val isPlaying: StateFlow<Boolean>
    val playbackEvents: SharedFlow<PlaybackEvent>
}

sealed class PlaybackEvent {
    data class Ready(val songStartTvMs: Long) : PlaybackEvent()
    data class Error(val cause: Throwable) : PlaybackEvent()
    object Ended : PlaybackEvent()
}

// Commands from PlaybackCoordinator (via state/intents)
sealed class PlaybackIntent {
    data class Prepare(
        val audioUrl: String,
        val videoUrl: String?,
        val seekToSec: Float,
        val instrumentalUrl: String? = null,
        val vocalsUrl: String? = null
    ) : PlaybackIntent()
    object Play : PlaybackIntent()
    object Pause : PlaybackIntent()
    object Stop : PlaybackIntent()
    data class Seek(val positionMs: Long) : PlaybackIntent()
    data class PrebufferNext(val audioUrl: String, val seekToSec: Float) : PlaybackIntent()
    data class Crossfade(val fadeOutSec: Float, val fadeInSec: Float) : PlaybackIntent()
}
```

### NFRs Applied

- **Testability**: ViewModels testable with fake data sources
- **Minimal Footprint**: Flat rendering, no shaders, pre-baked effects

### SLAs

| Metric | Target | Test |
|--------|--------|------|
| Singing screen FPS | ≥30 sustained | GPU profiler on target device |
| Song grid scroll FPS | ≥60 at 1080p | Manual + profiler |
| Memory (UI heap) | <100MB | Heap dump during singing |

### L2 Visible Shapes

- **SongListScreen**: Grid, preview, medley playlist, search
- **SingingScreen**: Lyrics, pitch lane, score overlay, Media3 PlayerView
- **ResultsScreen**: Final scores, per-segment breakdown for medley
- **SettingsScreen**: Subpages per functional spec §9.4
- **SelectPlayersModal**: Player assignment, difficulty selection
- **PitchLaneRenderer**: SurfaceView-based, 30fps render loop (see below)

### Pitch Lane Rendering Architecture (Normative)

Singing screen MUST separate real-time pitch lane rendering from Compose UI:

| Layer | Content | Technology |
|-------|---------|------------|
| Background | Pitch lane (note targets, pitch cursor, hit/miss, instrumental gap) | `SurfaceView` with dedicated render thread @30fps |
| Foreground | Score counters, lyrics, rating labels, countdown, pause overlay | Compose overlay on top of SurfaceView |

**Implementation Requirements**:
- Render thread decoupled from Compose recomposition.
- Drawing logic as pure function: `drawPitchLane(canvas: Canvas, viewport: Rect, state: LaneRenderState)` where `LaneRenderState` is immutable.
- No references to Views, Contexts, or lifecycle-scoped objects in drawing function.
- Enables JVM-based screenshot testing via `Bitmap`-backed `Canvas` in Robolectric `@GraphicsMode(Mode.NATIVE)`.

**Performance Guidelines**:
- Each singer lane as single drawing surface (not one UI element per note).
- Reuse cached geometry/primitives across frames.
- No per-frame object allocation in lane rendering.
- Static dark panel or gradient for readability overlays (no runtime blur).
- Flat rectangular shapes for pitch targets (no live glow/shadow).

### Source

Functional spec: TV UI screens and flows

### Acceptance Criteria

- Manual verification on target device
- F16 medley UI states

### Knowledge Gaps

None.

---

# 3. Component Interactions

## 3.1 Data Flow Diagrams

### Song Start Flow

```
User selects song in UI
         │
         ▼
┌─────────────────────┐
│ PlaybackCoordinator │
│   startSong()       │
└─────────┬───────────┘
          │
    ┌─────┴─────┬──────────────┬─────────────────┐
    ▼           ▼              ▼                 ▼
NetworkCtrl  UsdxParser    ScoringEngine      UI Layer
fetchTxt()   parse()       loadChart()     (via Intent)
    │           │              │            Prepare()
    │           │              │                │
    └─────┬─────┘              │                │
          ▼                    │                │
    ParsedSong ────────────────┘                │
                                                │
    ┌───────────────────────────────────────────┘
    ▼
NetworkCtrl.broadcastPlaybackState()
NetworkCtrl.sendAssignSinger()
    │
    ▼
UI.Play() ──→ Media3 starts ──→ PlaybackEvent.Ready(songStartTvMs)
                                        │
                                        ▼
                              ScoringEngine.setSongStart()
                              ScoringEngine.start()
```

### Pitch Frame Flow

```
Phone ──UDP──→ NetworkController
                    │
                    ├── Validate (size, connectionId, songInstanceSeq)
                    │
                    ▼
              pitchFrames: SharedFlow<PitchFrame>
                    │
                    ▼
              ScoringEngine (subscribes)
                    │
                    ├── Insert into JitterBuffer
                    │
                    └── Emit to livePitch: SharedFlow<PitchEvent>
                                │
                                ▼
                          UI: PitchLaneRenderer
```

### Scoring Flow

```
ScoringCoroutine (100Hz loop)
         │
         ├── Check System.nanoTime() vs noteEndTvMs + 450ms
         │
         ▼ (note ready to finalize)
    JitterBuffer.getFramesInWindow(noteStartTvMs, noteEndTvMs)
         │
         ▼
    NoteEvaluator.evaluate(frames, note)
         │
         ├── Octave normalization
         ├── Tolerance check
         ├── Hit count
         │
         ▼
    Accumulate score
         │
         ▼
    playerScores: StateFlow ──→ UI: ScoreOverlay
```

## 3.2 Interaction Contracts

### PlaybackCoordinator ↔ UI Layer

**Pattern**: Intent/Event (unidirectional data flow)

```
Coordinator ──(PlaybackIntent)──→ UI ──(executes Media3)
           ←──(PlaybackEvent)────┘
           ←──(StateFlow<positionMs>)──┘
```

- Coordinator emits `PlaybackIntent` (Prepare, Play, Pause, etc.)
- UI observes and executes on Media3
- UI emits `PlaybackEvent` (Ready with songStartTvMs, Error, Ended)
- UI exposes `currentPositionMs: StateFlow<Long>` for observation

### NetworkController ↔ ScoringEngine

**Pattern**: Reactive stream (SharedFlow)

```
NetworkController.pitchFrames ──→ ScoringEngine (subscribes)
```

- NetworkController validates frames, emits to SharedFlow
- ScoringEngine subscribes, inserts into jitter buffer
- No direct method calls between them

### PlaybackCoordinator ↔ ScoringEngine

**Pattern**: Direct interface calls

```kotlin
// Coordinator calls:
scoringEngine.loadChart(chart, micDelayMs, medleyWindow)
scoringEngine.setSongStart(songStartTvMs)
scoringEngine.start()
scoringEngine.suspend()
scoringEngine.resume()
scoringEngine.finalizeAll()
scoringEngine.reset()
scoringEngine.stop()
```

### PlaybackCoordinator ↔ NetworkController

**Pattern**: Direct interface calls + event observation

```kotlin
// Coordinator calls:
networkController.sendAssignSinger(phoneId, message)
networkController.broadcastPlaybackState(message)
networkController.sendPing(phoneId)
networkController.sendClockAck(phoneId, ack)

// Coordinator observes:
networkController.phoneEvents.collect { event -> ... }
```

---

# 4. Internal Architectures

## 4.1 GamePhase FSM

**States** (8 total):

| State | Description |
|-------|-------------|
| `Idle` | No song loaded, session is Open |
| `Loading` | Chart fetch/parse in progress, Media3 preparing |
| `Countdown` | Countdown overlay visible, phones warming up mic |
| `Playing` | Audio playing, scoring active, pitch frames flowing |
| `Paused` | User-initiated pause |
| `DisconnectPaused` | Auto-pause because required singer disconnected |
| `Stopped` | Song/medley ended, finalizing before Results |
| `Results` | Results screen visible, session returned to Open |

**Transitions**:

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
                    ▼                                         │
┌──────┐  start  ┌─────────┐  ready   ┌───────────┐          │
│ Idle │────────→│ Loading │─────────→│ Countdown │          │
└──────┘         └─────────┘          └─────┬─────┘          │
    ▲                │                      │                │
    │                │ error                │ countdown=0    │
    │                ▼                      ▼                │
    │            ┌──────┐             ┌─────────┐            │
    │            │ Idle │             │ Playing │←───────────┤
    │            └──────┘             └────┬────┘            │
    │                                      │                 │
    │         ┌────────────────────────────┼─────────────┐   │
    │         │                            │             │   │
    │         ▼                            ▼             │   │
    │    ┌────────┐                 ┌──────────────┐     │   │
    │    │ Paused │                 │DisconnectPaus│     │   │
    │    └───┬────┘                 └──────┬───────┘     │   │
    │        │                             │             │   │
    │        │ quit                        │ quit        │   │
    │        ▼                             ▼             │   │
    │    ┌──────┐                      ┌──────┐          │   │
    └────│ Idle │                      │ Idle │          │   │
         └──────┘                      └──────┘          │   │
                                                         │   │
              song end ──────────────────────────────────┘   │
                            │                                │
                            ▼                                │
                       ┌─────────┐  back  ┌──────┐           │
                       │ Stopped │───────→│Results│──────────┘
                       └─────────┘        └──────┘
```

**Transition Rules** (normative):

| From | To | Trigger |
|------|----|---------|
| Idle | Loading | User starts song from SelectPlayers |
| Loading | Countdown | Media3 ready, countdown enabled |
| Loading | Playing | Media3 ready, countdown disabled |
| Loading | Idle | Media3 error or audio URL unreachable |
| Countdown | Playing | Countdown reaches 0 |
| Countdown | Idle | Required singer disconnects |
| Playing | Paused | User presses Back |
| Playing | DisconnectPaused | Required singer WebSocket drops |
| Playing | Stopped | Playback reaches `stopAtLyricsTimeMs` or final medley segment ends |
| Paused | Playing | User selects Resume |
| Paused | Loading | User confirms Restart (new songInstanceSeq) |
| Paused | Idle | User confirms Quit |
| DisconnectPaused | Playing | Singer reconnects + Resume, or Continue Without Them |
| DisconnectPaused | Idle | User confirms Quit |
| Stopped | Results | Scoring finalization complete |
| Results | Idle | User returns to Song List |

**Implementation**:

```kotlin
sealed class GamePhase {
    object Idle : GamePhase()
    data class Loading(val song: IndexedSong) : GamePhase()
    data class Countdown(val remainingMs: Int) : GamePhase()
    object Playing : GamePhase()
    object Paused : GamePhase()
    data class DisconnectPaused(val disconnectedPlayer: PlayerId) : GamePhase()
    object Stopped : GamePhase()
    data class Results(val scores: Map<PlayerId, PlayerScore>) : GamePhase()
}

class GamePhaseFSM {
    private val _phase = MutableStateFlow<GamePhase>(GamePhase.Idle)
    val phase: StateFlow<GamePhase> = _phase.asStateFlow()
    
    fun transition(to: GamePhase) {
        val from = _phase.value
        require(isValidTransition(from, to)) { "Invalid transition: $from → $to" }
        log("GamePhase: $from → $to")
        _phase.value = to
    }
    
    private fun isValidTransition(from: GamePhase, to: GamePhase): Boolean {
        // Validate against transition table
    }
}
```

---

## 4.2 Medley Segment Transitions

When the medley sequencer detects current segment has reached `medleyEndSec`, execute as structured coroutine:

```kotlin
private suspend fun transitionMedleySegment(
    completed: MedleySegment,
    next: MedleySegment?
) {
    // Step 1: Fade out (2s)
    uiIntents.emit(PlaybackIntent.FadeOut(MEDLEY_FADE_OUT_SEC))
    delay(MEDLEY_FADE_OUT_SEC * 1000L)
    
    // Step 2: Finalize scoring for completed segment
    val segmentScores = scoringEngine.finalizeAll()
    medleyAccumulator.addSegment(completed.index, segmentScores)
    
    // Step 3: Check if last segment
    if (next == null) {
        uiIntents.emit(PlaybackIntent.Stop)
        val total = medleyAccumulator.computeAverage()
        fsm.transition(GamePhase.Stopped)
        networkController.broadcastPlaybackState(stopped("medley_end"))
        fsm.transition(GamePhase.Results(total))
        return
    }
    
    // Step 4: Fetch and parse next chart
    val txtBytes = networkController.fetchTxt(next.txtUrl).getOrElse {
        // Skip segment, try next
        return transitionMedleySegment(completed, nextAfter(next))
    }
    val chart = usdxParser.parse(txtBytes).getOrThrow()
    
    // Step 5: Configure scoring
    scoringEngine.reset()
    scoringEngine.loadChart(chart, micDelayMs, next.beatWindow)
    
    // Step 6: Crossfade to prebuffered audio (8s fade in)
    uiIntents.emit(PlaybackIntent.Crossfade(0f, MEDLEY_FADE_IN_SEC))
    
    // Step 7: Capture new songStartTvMs
    val readyEvent = uiPlaybackEvents.first { it is PlaybackEvent.Ready }
    scoringEngine.setSongStart((readyEvent as PlaybackEvent.Ready).songStartTvMs)
    scoringEngine.start()
    
    // Step 8-9: Update phones
    val newStopMs = computeMedleyStopMs(remainingSegments)
    networkController.broadcastPlaybackState(
        playing("segment_transition", newStopMs, chart.header.title)
    )
    
    // Step 10: Prebuffer next-next segment
    nextAfter(next)?.let { nextNext ->
        launch {
            delay((next.durationMs - 5000).coerceAtLeast(0))
            uiIntents.emit(PlaybackIntent.PrebufferNext(nextNext.audioUrl, nextNext.startSec))
        }
    }
}
```

**Constants**:
- `MEDLEY_FADE_OUT_SEC = 2.0f`
- `MEDLEY_FADE_IN_SEC = 8.0f`
- Prebuffer trigger: 5 seconds before segment end

**Error Handling (Normative)**:
- If `txtUrl` fetch fails: skip that segment and continue to next remaining segment.
- If audio is unreachable: medley MUST abort and follow playback-error exit path (show error modal, return to song list).

**Audio Prebuffering (Normative)**:

`PlaybackController` MUST support preparing a second ExoPlayer instance in background. At segment boundary, active and prebuffered players swap: prebuffered becomes active (with fade-in), old active released. If prebuffering is not complete at transition point, coordinator MUST fall back to sequential prepare-and-play path with brief audio gap.

---

## 4.3 Scoring Coroutine

Runs at 100Hz, independent of UI frame rate.

```kotlin
private fun startScoringCoroutine() = scope.launch {
    while (isActive && _isRunning.value) {
        val tvNowMs = System.nanoTime() / 1_000_000
        
        // Find notes ready for finalization
        for (note in pendingNotes) {
            val noteEndTvMs = computeNoteEndTvMs(note)
            if (tvNowMs >= noteEndTvMs + NOTE_FINALIZATION_DELAY_MS) {
                finalizeNote(note, tvNowMs)
                pendingNotes.remove(note)
            }
        }
        
        // Emit current scores
        _playerScores.value = computeCurrentScores()
        
        delay(10) // 100Hz
    }
}

private fun finalizeNote(note: NoteEvent, tvNowMs: Long) {
    val noteStartTvMs = computeNoteStartTvMs(note)
    val noteEndTvMs = computeNoteEndTvMs(note)
    
    val frames = jitterBuffer.getFramesInWindow(
        note.playerId, noteStartTvMs, noteEndTvMs
    )
    
    val result = noteEvaluator.evaluate(note, frames)
    accumulator.addNoteScore(note.playerId, result)
    
    // Check for sentence completion
    if (isLastNoteInLine(note)) {
        lineBonusCalculator.applyLineBonus(note.playerId, note.lineIndex)
    }
}
```

**Constants**:
- `NOTE_FINALIZATION_DELAY_MS = 450` (matches max jitter buffer playout delay)

---

## 4.4 Jitter Buffer

Ring buffer holding pitch frames, queryable by time window.

```kotlin
class JitterBuffer(
    private val capacityMs: Long = 500,
    private val frameIntervalMs: Long = 20  // 50fps
) {
    // Pre-allocated capacity per player
    private val bufferP1 = RingBuffer<PitchFrame>(capacity = (capacityMs / frameIntervalMs).toInt())
    private val bufferP2 = RingBuffer<PitchFrame>(capacity = (capacityMs / frameIntervalMs).toInt())
    
    fun insert(frame: PitchFrame) {
        val buffer = if (frame.playerId == P1) bufferP1 else bufferP2
        
        // Validate lateness
        val latenessMs = frame.arrivalTvMs - frame.tvTimeMs
        if (latenessMs > MAX_PLAYOUT_DELAY_MS) {
            log("Frame too late: latenessMs=$latenessMs, dropping")
            return
        }
        
        // Validate sequence ordering (per-player)
        val lastSeq = buffer.lastOrNull()?.seq
        if (lastSeq != null && frame.seq <= lastSeq) {
            log("Decreasing seq: $lastSeq → ${frame.seq}, dropping")
            return
        }
        
        // Validate timestamp regression (per-player)
        val lastTvTimeMs = buffer.lastOrNull()?.tvTimeMs
        if (lastTvTimeMs != null) {
            val regression = lastTvTimeMs - frame.tvTimeMs
            if (regression > MAX_TIMESTAMP_REGRESSION_MS) {
                log("tvTimeMs regression ${regression}ms > 200ms, dropping")
                return
            }
            // Note: regression ≤200ms is accepted (network reordering tolerance)
        }
        
        buffer.add(frame)
    }
    
    fun getFramesInWindow(
        playerId: PlayerId,
        startTvMs: Long,
        endTvMs: Long
    ): List<PitchFrame> {
        val buffer = if (playerId == P1) bufferP1 else bufferP2
        return buffer.filter { frame ->
            frame.tvTimeMs >= startTvMs && 
            frame.tvTimeMs < endTvMs &&
            (frame.arrivalTvMs - frame.tvTimeMs) <= MAX_PLAYOUT_DELAY_MS
        }
    }
    
    companion object {
        const val TARGET_PLAYOUT_DELAY_MS = 220
        const val MAX_PLAYOUT_DELAY_MS = 450
        const val MAX_TIMESTAMP_REGRESSION_MS = 200
    }
}
```

---

## 4.5 Clock Sync Logic

NTP-lite protocol, best-of-N selection.

**Sync Schedule (Normative)**:
- Run **5 exchanges** (100ms apart) on connection to establish initial offset.
- **Suspend** during active singing. LAN clock drift over ~3 min song is negligible (<1ms).
- Resume with single exchange on song end or disconnect/reconnect.

```kotlin
class ClockSyncLogic(
    private val networkController: NetworkController,
    private val sampleCount: Int = 5
) {
    suspend fun sync(phoneId: String): ClockSyncResult {
        val samples = mutableListOf<ClockSample>()
        
        repeat(sampleCount) {
            val t1 = System.nanoTime() / 1_000_000
            val pong = networkController.sendPing(phoneId)
            val t4 = System.nanoTime() / 1_000_000
            
            val t2 = pong.tPhoneRecvMs
            val t3 = pong.tPhoneSendMs
            
            val rtt = (t4 - t1) - (t3 - t2)
            val offset = ((t2 - t1) + (t3 - t4)) / 2
            
            if (rtt in 0..2000) {
                samples.add(ClockSample(rtt, offset, pong.pingId))
            }
            
            delay(100) // Brief pause between samples
        }
        
        if (samples.isEmpty()) {
            return ClockSyncResult.Failed("No valid samples")
        }
        
        // Best-of-N: choose smallest RTT
        val best = samples.minByOrNull { it.rtt }!!
        
        networkController.sendClockAck(phoneId, ClockAckMessage(
            pingId = best.pingId,
            tTvRecvMs = /* t4 from that sample */
        ))
        
        return ClockSyncResult.Success(best.offsetMs, best.rtt)
    }
}

data class ClockSample(val rtt: Long, val offsetMs: Long, val pingId: String)
```

---

## 4.6 Beat-Time Conversion

USDX beat numbers in `.txt` files are the authoritative beat grid (quarter-beat resolution).

**Internal Beat Unit**:
- File beats: integers in note lines (`startBeat`, `duration`) and sentence lines.
- Internal beats: identical to file beats (no scaling): `internalBeat = fileBeat`.
- Parsing rule: use beat values as-is (no `*4`).

**Internal BPM**:
- `BPM_internal = BPM_file * 4`

```kotlin
object BeatCalculator {
    /**
     * Convert time (seconds relative to chart origin) to internal beat position.
     * Chart origin = lyricsTimeSec - GAPms/1000.0 (may be negative).
     */
    fun timeSecToMidBeatInternal(tSec: Double, bpmInternal: Float): Double {
        return tSec * (bpmInternal / 60.0)
    }
    
    /**
     * Convert internal beat to time (seconds relative to chart origin).
     */
    fun beatInternalToTimeSec(beatInt: Double, bpmInternal: Float): Double {
        return beatInt * (60.0 / bpmInternal)
    }
}
```

**Visual vs Scoring Beat (Normative)**:

Two beat computations from the same `BPM_internal` and `GAPms`:

| Consumer | Formula | micDelayMs |
|----------|---------|------------|
| **Lyrics beat** (highlight, elapsed display) | `floor(timeSecToMidBeatInternal(lyricsTimeSec - GAPms/1000.0))` | 0 |
| **Lane beat** (pitch targets, scoring windows) | `songStartTvMs + beatInternalToTimeSec(startBeat)*1000 + GAPms + effectiveMicDelayMs` | Configured |

- Lyrics beat tracks what audience hears from speakers.
- Lane beat tracks where singer's voice should appear given mic/network delay.
- Pitch lane renders targets using lane beat. Live cursor driven by `PitchEvent.tvTimeMs` — correct performance aligns cursor with targets.

**Boundary Convention**: `noteActive if startBeat <= beat < endBeat` (start inclusive, end exclusive).

**Implementation**: Beat conversion logic MUST accept `micDelayMs` parameter (default 0). Using wrong delay for a consumer is a conformance error.

---

# 5. Resolved Blockers

| ID | Issue | Resolution |
|----|-------|------------|
| BLOCKER-1 | Media3 ↔ PlaybackCoordinator interaction | Intent/Event pattern. Coordinator emits `PlaybackIntent`, UI observes and executes, emits `PlaybackEvent` back. |
| BLOCKER-3 | songStartTvMs capture chain | UI captures from Media3 `onAudioPositionAdvancing`, emits in `PlaybackEvent.Ready`, Coordinator passes to ScoringEngine. |
| GAP-1 | Clock sync timing relative to song start | Gate song start on ≥1 valid clock sync sample. Coordinator checks before `assignSinger`. |
| GAP-2 | Manifest re-fetch trigger on Results | Coordinator calls `libraryManager.refreshAll()` during Stopped→Results transition. |
| GAP-3 | Pitch frame routing | NetworkController exposes `pitchFrames: SharedFlow<PitchFrame>`. ScoringEngine subscribes. |
| L0-GAP-2 | connectionId validation on reconnect | Immediate invalidation on disconnect. Old connectionId rejected, new one assigned on reconnect. |

---

# 6. Test Fixtures

## 6.1 Existing Fixtures

| ID | Covers | Components |
|----|--------|------------|
| F01 | Song discovery validation | UsdxParser, LibraryManager |
| F02 | Header parsing edge cases | UsdxParser |
| F03 | Body grammar token recognition | UsdxParser |
| F04 | Duet parsing track routing | UsdxParser |
| F05 | Legacy relative mode semantics | UsdxParser |
| F06 | Beat-time conversion | ScoringEngine |
| F08 | Scoring beat stepping | ScoringEngine |
| F09 | Pitch tolerance, octave normalization | ScoringEngine |
| F10 | Rap scoring toneValid gate | ScoringEngine |
| F11 | Line bonus and rounding | ScoringEngine |
| F12v2 | Binary pitch codec | NetworkController |
| F13 | Jitter buffer selection/staleness | ScoringEngine |
| F14v2 | Clock sync (phone-side) | — (phone OOS) |
| F15 | Session lifecycle disconnect/reconnect | NetworkController, PlaybackCoordinator |
| F16 | Medley sequencer | PlaybackCoordinator |
| F18 | HTTP server range coordination | NetworkController |

## 6.2 New Fixtures Required

| ID | Purpose | Components | Priority |
|----|---------|------------|----------|
| F20 | WebSocket message validation | NetworkController | Should have |
| F21 | Clock sync TV-side | PlaybackCoordinator | Must have |
| F22 | GamePhase FSM transitions | PlaybackCoordinator | Must have |
| F23 | Library multi-phone aggregation | LibraryManager | Should have |
| F24 | Scoring integration (frames → score) | ScoringEngine | Must have |

### F20: WebSocket Message Validation

```
testing/fixtures/F20_websocket_message_validation/
├── README.md
├── case_valid_hello/
│   ├── input.hello.json
│   └── expected.sessionState.json
├── case_missing_clientId/
│   ├── input.hello.json
│   └── expected.error.json
├── case_bad_protocolVersion/
│   ├── input.hello.json
│   └── expected.error.json
└── case_missing_httpPort/
    ├── input.hello.json
    └── expected.error.json
```

### F21: Clock Sync TV-Side

```
testing/fixtures/F21_clock_sync_tv_side/
├── README.md
├── case_normal_5_samples/
│   ├── ping_pong_sequence.json
│   └── expected.clockSync.json
├── case_all_invalid_rtt/
│   ├── ping_pong_sequence.json
│   └── expected.failure.json
└── case_best_of_n_selection/
    ├── ping_pong_sequence.json   # RTTs: [50, 30, 80, 45, 60]
    └── expected.clockSync.json    # chosen: sample with RTT=30
```

### F22: GamePhase FSM Transitions

```
testing/fixtures/F22_gamephase_fsm_transitions/
├── README.md
├── valid_transitions.json        # All valid from→to pairs
├── invalid_transitions.json      # All invalid from→to pairs (should reject)
└── expected.transitions.json
```

### F23: Library Multi-Phone

```
testing/fixtures/F23_library_multiphone/
├── README.md
├── phone_a_manifest.json         # 3 songs
├── phone_b_manifest.json         # 3 songs
├── case_both_connected/
│   └── expected.library.json     # 6 songs, sorted
├── case_phone_a_disconnects/
│   └── expected.library.json     # 3 songs (phone_b only)
└── case_refresh_replaces/
    ├── phone_a_manifest_v2.json  # 2 songs (changed)
    └── expected.library.json     # 5 songs total
```

### F24: Scoring Integration

```
testing/fixtures/F24_scoring_integration/
├── README.md
├── chart.txt                     # Simple song, 3 notes
├── pitch_frames_perfect.bin      # PERFECT profile
├── pitch_frames_partial.bin      # 50% hit rate
├── pitch_frames_silence.bin      # All unvoiced
├── expected.score_perfect.json   # scoreTotalInt=10000
├── expected.score_partial.json
└── expected.score_silence.json   # scoreTotalInt=0
```

---

# 7. Project Plan

## 7.1 Iteration Overview

| Iter | Theme | Key Deliverable | DOD Gate |
|------|-------|-----------------|----------|
| 0 | Foundation | Parser + Scoring math | Fixtures pass |
| 1 | Solo sing | Browse + Play | Sing 1 song on emulator |
| 2 | Scored singing | Pitch pipeline + Results | Perfect = 10000 |
| 3 | Multiplayer | 2 players + Duet | Duet karaoke night |
| 4 | Medley + Hardening | Full MVP | Device performance targets met |

## 7.2 Iter 0 — Foundation (No Phone Needed)

**Goal**: Pure-logic components fully tested with fixtures.

| Deliverable | Component | Fixtures |
|-------------|-----------|----------|
| USDX parser | UsdxParser | F01, F02, F03, F04, F05 |
| Beat↔time conversion | ScoringEngine (partial) | F06 |
| Per-note scoring math | ScoringEngine (partial) | F08, F09, F10 |
| Line bonus + rounding | ScoringEngine (partial) | F11 |
| Fixture harness | Test infra | — |

**DOD**:
- [ ] All fixture tests pass: F01–F06, F08–F11
- [ ] Coverage ≥80% on UsdxParser, scoring math modules
- [ ] No Android dependencies — pure Kotlin, runs on JVM

**Mock Phone**: Not needed.

## 7.3 Iter 1 — Solo Sing (1 Phone, 1 Player)

**Goal**: End-to-end: browse library → select song → play audio with lyrics.

| Deliverable | Component | Spec Ref |
|-------------|-----------|----------|
| WebSocket server | NetworkController | §8.1, §8.3 |
| mDNS advertisement | NetworkController | session discovery |
| HTTP client | NetworkController | §8.7 |
| Manifest aggregation | LibraryManager | §3.1.3 |
| Song grid UI | UI: SongListScreen | §3.4 |
| Playback UI | UI: SingingScreen | §9.5 (lyrics only) |
| Media3 integration | UI | — |
| GamePhase FSM | PlaybackCoordinator | session/playback lifecycle |

**DOD**:
- [ ] App discovers phone via mDNS, completes handshake
- [ ] Song list displays songs from phone manifest
- [ ] Select song → plays audio, shows sentence-paged lyrics
- [ ] Back → returns to song list
- [ ] F15 session lifecycle passes
- [ ] F22 GamePhase FSM passes
- [ ] Runs on emulator with mock-phone module

**Mock Phone**: Required.

## 7.4 Iter 2 — Scored Singing + Pitch Pipeline

**Goal**: Complete scoring loop — pitch frames flow, scores accumulate, results display.

| Deliverable | Component | Fixtures |
|-------------|-----------|----------|
| Clock sync protocol | PlaybackCoordinator | F14v2, F21 |
| UDP listener | NetworkController | F12v2 |
| Pitch frame validation | NetworkController | — |
| Jitter buffer | ScoringEngine | F13 |
| Scoring coroutine | ScoringEngine | F08, F24 |
| Pitch lane UI | UI: SingingScreen | — |
| Live score display | UI: SingingScreen | — |
| Results screen | UI: ResultsScreen | — |

**DOD**:
- [ ] Clock sync completes before song start
- [ ] Pitch frames flow from phone → jitter buffer → scoring
- [ ] Pitch lane shows live cursor
- [ ] Score updates in real-time
- [ ] Song ends → Results screen shows final score
- [ ] F13, F21, F24 pass
- [ ] Perfect mock performance → `scoreTotalInt == 10000`

**Mock Phone**: Required (with pitch streaming).

## 7.5 Iter 3 — Multiplayer + Duet + Polish

**Goal**: 2-player support, duet songs, production-quality UX.

| Deliverable | Component | Spec Ref |
|-------------|-----------|----------|
| 2-phone handling | NetworkController | §7, §8.5 |
| P1/P2 assignment | PlaybackCoordinator | §9.3 |
| Duet chart routing | UsdxParser, ScoringEngine | duet format support |
| Disconnect/reconnect | PlaybackCoordinator | §7.4 |
| Pause overlay | UI: SingingScreen | §9.5.5 |
| Settings screens | UI: SettingsScreen | §9.4 |
| Video backgrounds | UI: SingingScreen | singing-screen behavior |
| Instrumental + vocals mixing | UI | §1.1, §9.4.3 |

**DOD**:
- [ ] Two phones connect, both appear in SelectPlayers
- [ ] Duet song → P1 sings track 1, P2 sings track 2
- [ ] Swap Parts works
- [ ] Singer disconnect → pause overlay, reconnect resumes
- [ ] All settings screens functional
- [ ] Video background plays
- [ ] F04, F23 pass
- [ ] Demo: Two people sing a duet

**Mock Phone**: Two instances required.

## 7.6 Iter 4 — Medley + Hardening

**Goal**: Medley mode complete, performance optimized, MVP shippable.

| Deliverable | Component | Fixtures |
|-------------|-----------|----------|
| Medley playlist UI | UI: SongListScreen | — |
| Medley sequencer | PlaybackCoordinator | F16 |
| Segment transitions | PlaybackCoordinator + UI | F16 |
| Audio prebuffer/crossfade | UI (Media3) | — |
| Medley scoring windows | ScoringEngine | F11 |
| Medley results | UI: ResultsScreen | — |
| Preview playback | UI: SongListScreen | — |
| Search/filter | UI: SongListScreen | — |
| Device tuning | All | — |

**DOD**:
- [ ] Medley playlist, start, transitions work
- [ ] Crossfade audible (<100ms gap if prebuffer ready)
- [ ] Medley results show per-segment + average
- [ ] Preview plays on focus
- [ ] Search filters grid
- [ ] F16, F18 pass
- [ ] Performance on target device:
  - Singing screen ≥30fps
  - Song grid ≥60fps
  - Memory ≤512MB
- [ ] Demo: Full medley karaoke session

**Mock Phone**: Required with multiple songs.

---

# Appendix A: Mock Phone Specification

The `:mock-phone` Gradle module enables TV app development without a real phone.

## A.1 Services

| Service | Description |
|---------|-------------|
| HTTP Server | Ktor CIO on `localhost:34781`, serves `/manifest.json` and `/songs/<path>` |
| WebSocket Client | Connects to TV, performs handshake, responds to messages |
| Pitch Frame Generator | UDP datagrams at 50fps during singing |

## A.2 Pitch Streaming Profiles

| Profile | Behavior |
|---------|----------|
| `PERFECT` | Every frame within note window: `midiNote = note.toneSemitone + 36` |
| `PARTIAL(hitRate: Float)` | Random `midiNote = 255` for `(1 - hitRate)` fraction |
| `SILENCE` | All frames `midiNote = 255` |
| `OCTAVE_OFF` | `midiNote = note.toneSemitone + 36 + 12` (validates octave norm) |
| `REPLAY(path: Path)` | Replay a recorded fixture stream (JSON or binary, implementation-defined) with original timing |

## A.3 Recorded Pitch Stream Format

The mock phone MUST support replaying recorded pitch streams from a fixture file.
The on-disk representation may be JSON or binary; the replay behavior is what matters:

- preserve frame order
- preserve relative timing between frames
- preserve `songInstanceSeq`, `playerId`, `midiNote`, and `tvTimeMs`
- allow deterministic replays for acceptance tests

A convenient JSON representation is an array of frames with fields:
- `playerId`
- `midiNote`
- `tvTimeMs`
- `arrivalTvMs` (optional for replay, useful for assertions)
- `songInstanceSeq`
- `seq`

## A.4 Failure Mode Injection

| Command | Effect |
|---------|--------|
| `mock.disconnectSinger(playerId)` | Close WebSocket for that phone |
| `mock.disconnectSongSource()` | Stop HTTP server mid-song |
| `mock.dropFrames(rate: Float)` | Drop N% of UDP frames |
| `mock.delayFrames(ms: Long)` | Add latency to all frames |
| `mock.corruptFrame()` | Send malformed frame (wrong size, bad seq) |

## A.5 Usage

```bash
# Start mock phone serving fixture songs
./gradlew :mock-phone:run --args="--songs=testing/fixtures/F03_body_grammar_token_recognition"

# With pitch profile
./gradlew :mock-phone:run --args="--profile=PERFECT"

# Replay recorded pitch stream
./gradlew :mock-phone:run --args="--replay=testing/fixtures/F24_scoring_integration/pitch_frames_perfect.json"
```

---

*Document generated: 2026-04-10*
