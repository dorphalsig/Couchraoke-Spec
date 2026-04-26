# Couchraoke TV App — Specification

**Version**: 1.3
**Date**: 2026-04-25
**Scope**: Android TV Host App (phone companion OOS)
**Changelog since 1.2**: Playback backend migrated from Media3/ExoPlayer to LibVLC. §1.1 Testability, §1.6 Minimal Footprint, §2.1 PlaybackCoordinator (songStartTvMs Capture, Playback error handling, new Audio Focus subsection), §2.6 UI Layer (new Playback Backend Seam), §2.6.16 SingingScreen (new SurfaceView z-order rule), §3.1/§3.2 flow diagrams, and §4.2 Medley Audio Prebuffering all updated. AV-sync and dual-track mixing resolved: §2.1 Audio/Video Asset Coupling added (two-MP model, audio master, #VIDEOGAP arithmetic). Phone pre-mixes #INSTRUMENTAL/#VOCALS; TV always receives a single audioUrl. instrumentalUrl/vocalsUrl removed from all wire schemas.
**Changelog since 1.1**: §2.6 Design Tokens and Visual System added; screen subsections updated with token references, revised song-card composition, interruption-overlay shell, winner-emphasis rule, and singing-screen motion budget. Source: `2026-04-21-tv-app-design.md` (merged and retired).
---

## Table of Contents

- [Navigation by Concern](#navigation-by-concern)
- [1. Non-Functional Requirements](#1-non-functional-requirements)
- [2. Top-Level Components](#2-top-level-components)
  - [2.1 PlaybackCoordinator](#21-playbackcoordinator)
  - [2.2 ScoringEngine](#22-scoringengine)
  - [2.3 NetworkController](#23-networkcontroller)
  - [2.4 UsdxParser](#24-usdxparser)
  - [2.5 LibraryManager](#25-librarymanager)
  - [2.6 UI Layer](#26-ui-layer)
  - [2.7 Mock Phone (Dev/Test Only)](#27-mock-phone-devtest-only)
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
- [Appendix A: Peer-Boundary Test Utilities](#appendix-a-peer-boundary-test-utilities)
- [Appendix B: Protocol JSON Schemas](#appendix-b-protocol-json-schemas)
- [Appendix E: Worked Examples](#appendix-e-worked-examples)

## Navigation by Concern

Use the owning component section as the primary home for each concern. Supporting sections provide mechanics, interaction context, schemas, and worked examples.

- **Scoring semantics**: [§2.2 ScoringEngine](#22-scoringengine). Supporting mechanics: [§4.3 Scoring Coroutine](#43-scoring-coroutine), [§4.4 Jitter Buffer](#44-jitter-buffer), [§4.6 Beat-Time Conversion](#46-beat-time-conversion), [Appendix E](#appendix-e-worked-examples).
- **Network protocol and session semantics**: [§2.3 NetworkController](#23-networkcontroller). Supporting sections: [§3.2 Interaction Contracts](#32-interaction-contracts), [§4.5 Clock Sync Logic](#45-clock-sync-logic), [Appendix B](#appendix-b-protocol-json-schemas).
- **UI behavior and screen specs**: [§2.6 UI Layer](#26-ui-layer). Supporting flow context: [§3.1 Data Flow Diagrams](#31-data-flow-diagrams) and [§3.2 Interaction Contracts](#32-interaction-contracts).
- **Parsing and library/catalog behavior**: [§2.4 UsdxParser](#24-usdxparser) and [§2.5 LibraryManager](#25-librarymanager).

---

# 1. Non-Functional Requirements

Ordered by priority. These describe *how* the system should be built.

## 1.1 Testability (Highest)

**Why**: Claude Code + TDD workflow. Components must be testable in isolation.

| Requirement | Implementation |
|-------------|----------------|
| Timing-sensitive logic accepts injected clocks | `FakeClock` / `TestCoroutineScheduler` |
| All I/O behind interfaces | Network, playback (LibVLC via `LibVlcPlayerHandle`), filesystem mockable |
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
| RAM | 2GB DDR3/DDR4 | App budget: ≤512MB including LibVLC buffers. |
| Storage | 16GB eMMC | Very slow R/W. No temp files during playback. |
| GPU | Mali-G31 MP2 (OpenGL ES 3.2) | Flat rendering only. No blur, glow, or post-processing. |
| OS | Android TV 11–14 | Min API 30. Multicast lock required for mDNS. |

Higher-spec devices (4GB RAM) must work without degradation; lower-spec (1GB RAM, S805) are out of scope.

### Memory Budgets

| Resource | Budget | Notes |
|----------|--------|-------|
| App total | ≤512MB | Heap + native + LibVLC. System overhead ~800MB–1GB on 2GB devices. |
| LibVLC caching | `--file-caching=2000`, `--network-caching=3000`, `--live-caching=300` (all ms). Passed at `LibVLC` construction. | Caching is time-based, not byte-based; LibVLC does not expose a hard byte budget. Empirically yields ≤80MB combined audio+video on the target SoC. |
| LibVLC AAR ABI filter | `splits.abi { include 'arm64-v8a' }` (build-time) | Drops the `org.videolan.android:libvlc-all:3.6.0` AAR from ~82MB to ~25MB. Android TV stick/box devices in scope are all arm64. |
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
| Single-activity architecture | No fragment transaction overhead; `navigation-compose` `NavHost` manages the screen back stack |
| Lazy initialization | LibVLC instance, mDNS created on demand |
| Amlogic S905X4 codec workaround | ⚠ Needs hardware retest under LibVLC. Pass `--codec=mediacodec_ndk,all` to LibVLC at construction. If HD/FHD playback still fails on the S905X4 reference device in QA, fall back to `#BACKGROUND` still image (existing fallback path in §2.6.15.6). See paragraph below for context. |

**LibVLC codec selection on Amlogic S905X4 (open)**: Under Media3, the S905X4 reported inaccurate `PerformancePoint` capabilities, causing unnecessary HD/FHD downscaling, and required a custom `MediaCodecSelector` workaround. LibVLC routes hardware decode through `MediaCodec` as well, so the same underlying device bug *may* still bite. The required mitigation under LibVLC is unknown until QA verification on the reference device. The construction-time option `--codec=mediacodec_ndk,all` instructs LibVLC to prefer the NDK MediaCodec backend, which is the closest analogue to the Media3 workaround. **Action**: verify HD/FHD playback on the S905X4 reference unit before MVP sign-off. If verification fails, the existing `#BACKGROUND` still-image fallback (§2.6.15.6) is the only ship-blocker mitigation and Video MUST be forced OFF on the affected device profile via runtime device-model match.

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
│    └── UI Layer (Compose + LibVLC)                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2.1 PlaybackCoordinator

**Responsibility**: Single source of truth for game phase. Orchestrates all subsystems during song lifecycle. Owns `songInstanceSeq`. Manages clock sync logic. Derives session locked state.

**Lifecycle**: Scoped to app lifetime.

### Responsibilities (Normative)

1. Own and increment `songInstanceSeq` (`UInt`) on every song start, including Restart.
2. Drive song start: fetch and parse chart, configure scoring, set active song for pitch ingestion, prepare playback, wait for UI-reported effective playback-plan duration, lock session, obtain at least one valid clock-sync sample for every assigned singer before entering countdown or live playback, compute `stopAtLyricsTimeMs`, send `assignSinger`, then start countdown or playback; capture `songStartTvMs` when playback begins and push into scoring.
3. Construct `PlaybackStateMessage` on each playback-bearing game-phase transition and push to network layer.
4. Coordinate pause, resume, restart, and quit across playback, scoring, and phone state.
5. Handle required-singer disconnects by auto-pausing and presenting wait / continue / quit options.
6. Handle reconnect by updating `connectionId`, re-sending `assignSinger`, and sending current `playbackState`.
7. Drive medley segment transitions ([§4.2](#42-medley-segment-transitions)).
8. Trigger clock-sync re-exchange at song end.
9. Transition session FSM between Open and Locked at song start/end.
10. Interact with subsystems only through narrow interfaces (`ScoringEngine`, `NetworkController`, etc.). No direct references to implementation classes.

### songStartTvMs Capture (Normative)

`songStartTvMs` is the TV monotonic ms value corresponding to audio position 0 (before any `#START` offset). The coordinator MUST gate scoring on this value. LibVLC timing capture belongs to the UI layer because the UI owns the `LibVlcPlayerHandle` (§2.6.1 Public API — Playback Backend Seam).

The TV's monotonic clock for all `*TvMs` values throughout this spec is `System.nanoTime() / 1_000_000`. Wall-clock sources (`System.currentTimeMillis()`) MUST NOT be used for any `*TvMs` field.

1. The UI layer MUST register a single event listener on the `LibVlcPlayerHandle` before calling `play()`. The underlying LibVLC `MediaPlayer.Event` callbacks fire on a libvlc native thread; the handle adapter MUST dispatch translated `LibVlcEvent` values onto the UI ViewModel's main scope before any coordinator-visible state is touched.
2. On the **first** `LibVlcEvent.Playing` after `play()`, the UI layer MUST compute `songStartTvMs = (System.nanoTime() / 1_000_000) − playerHandle.timeMs` and emit `PlaybackEvent.Ready(songStartTvMs)`. The first `Playing` event fires when audio output actually begins, which is the most accurate single-shot anchor LibVLC exposes; do **not** wait for `LibVlcEvent.TimeChanged`, whose default cadence (~250 ms) is too coarse to anchor scoring.
3. The UI layer MUST capture a fallback at the moment `play()` is called: `fallbackStartTvMs = System.nanoTime() / 1_000_000`.
4. If `LibVlcEvent.Playing` has not fired within 500 ms of `play()`, the UI layer MUST use `fallbackStartTvMs`, emit `PlaybackEvent.Ready(fallbackStartTvMs)`, and log a warning.
5. Before countdown or live playback begins, the UI layer MUST already have emitted `PlaybackEvent.Prepared(effectivePlaybackDurationMs)` to the coordinator.
6. The coordinator computes `stopAtLyricsTimeMs` from chart data plus the prepared playback-plan duration, sends `assignSinger`, then starts countdown or playback.
7. When playback begins, the UI layer emits `PlaybackEvent.Ready(songStartTvMs)` to the coordinator.
8. The coordinator MUST wait for `PlaybackEvent.Ready(songStartTvMs)` before calling `ScoringEngine.setSongStart(songStartTvMs)`.
9. The ScoringEngine MUST NOT finalize any notes until `songStartTvMs` has been set.
10. Pause/resume MUST preserve scoring alignment with playback position. The coordinator MUST record `pauseStartedTvMs` when entering `Paused` or `DisconnectPaused`.
11. On every transition from `Paused` or `DisconnectPaused` back to active playback, the coordinator MUST add `tvNowMs - pauseStartedTvMs` to `totalPausedDurationMs`.
12. All note-window and finalization-time calculations that use `songStartTvMs` MUST instead use `effectiveSongStartTvMs = songStartTvMs + totalPausedDurationMs`.
13. `totalPausedDurationMs` resets to `0` on every new song start and Restart.

### START/END Playback Behavior (Normative)

- `#START` (seconds): if present, audio MP seeks to `startSec`. Video MP target position is `(videoGapSec ?? 0) + startSec`, applied per the Audio/Video Asset Coupling rules below.
- `#END` (milliseconds): if present and > 0, playback MUST end when `songTimeSec >= endMs / 1000.0`.
- If `#END` is absent or ≤ 0, song duration is determined by audio track length.
- **Restart**: resets per-player scores/state and seeks audio MP back to `startSec`; video MP restarted per Audio/Video Asset Coupling rules.

### Audio/Video Asset Coupling (Normative)

The TV uses **two independent LibVLC `MediaPlayer` instances** for songs that carry a video asset: an audio MP (master) and a video MP (decoration). For audio-only songs a single audio MP is used. The video MP is an optional decoration; its failure MUST NOT affect audio, scoring, or session state.

**Phone-side audio preparation (normative)**: the phone's HTTP server MUST serve a single pre-mixed audio file at `audioUrl` for every song entry. If the song's source files contain both `#INSTRUMENTAL` and `#VOCALS` tracks, the phone MUST mix them into a single audio file before (or at first) serving. The TV MUST NOT attempt to fetch or mix `#INSTRUMENTAL`/`#VOCALS` URLs directly; those URLs MUST NOT appear in any TV-facing wire message.

**Two-MP start sequence (normative)**: when `videoUrl` is non-null and video is enabled (§2.6.15.6):

```kotlin
val gapMs = ((parsedSong.videoGapSec ?: 0f) * 1000L).toLong()

when {
    gapMs == 0L -> {
        audioHandle.play()
        videoHandle.play()                    // simultaneous start
    }
    gapMs > 0 -> {
        audioHandle.play()
        scope.launch {
            delay(gapMs)                      // #VIDEOGAP > 0: video starts after audio
            videoHandle.play()
        }
    }
    else /* gapMs < 0 */ -> {
        videoHandle.seekTo(-gapMs)            // #VIDEOGAP < 0: seek video forward, start together
        audioHandle.play()
        videoHandle.play()
    }
}
```

**`songStartTvMs` is always captured from the audio MP's `LibVlcEvent.Playing`**, regardless of whether a video MP is present. The video MP's event stream MUST NOT influence scoring timing.

**Video MP configuration**: the video MP MUST be constructed with `:no-audio` to disable its audio decoder and prevent audio-focus contention with the audio MP.

**Drift (normative)**: no active drift correction is required for MVP. The two MPs share the same device system clock; observed drift over a 3–5 minute song on the target hardware is expected to be imperceptible for a decorative music-video backdrop. If QA on the reference device (Amlogic S905X4) shows drift > 300 ms, add a single resync at medley segment boundaries only.

**Video MP failure handling**: if the video MP encounters `LibVlcEvent.EncounteredError`, the TV MUST release it and fall back to `#BACKGROUND` image (§2.6.15.6 fallback path). Audio MP continues unaffected. The error MUST be logged but MUST NOT surface an error modal.

**Multi-MP stability note**: running two LibVLC `MediaPlayer` instances in-process is not an officially documented use case for libvlc-android. The risk is assessed as low (Android's plugin set differs from desktop vlcj where warnings originate) but is a known yellow flag. If sustained QA on the reference device reveals instability, fall back to single-MP with `addSlave(Type.Audio, audioUri, true)` for audio, accepting that non-zero `#VIDEOGAP` values will produce a visually offset video.

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
    fun isLocked(): Boolean = gamePhase.value !in setOf(GamePhase.Idle, GamePhase.Results)
    
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

### Acceptance Criteria

- F14v2, F15, F16, F21, F22 pass

### Knowledge Gaps

None.

---

## 2.2 ScoringEngine

**Responsibility**: Evaluate pitch frames against chart notes, accumulate scores, compute line bonus. Owns jitter buffer for frame storage and range queries.

**Lifecycle**: Active during song. Reset on restart.

**Buffering invariant (normative)**: After `reset()` + `loadChart()` and before `setSongStart(songStartTvMs)`, the ScoringEngine is in a buffering state. Frames received for the active `songInstanceSeq` during this window MUST be stored in the jitter buffer. Finalization and note evaluation remain gated on `setSongStart(songStartTvMs)`. When `setSongStart(songStartTvMs)` is called, the ScoringEngine MUST discard any buffered frames with `tvTimeMs < songStartTvMs` before finalization begins.

### Scoring Overview

Use this section as the primary home for scoring semantics:
- core scoring rules and score budgets: **Scoring Algorithm**
- per-player tolerance and defaults: **Player Level / Tolerance**
- octave handling: **Octave Normalization**
- sentence completion and line bonus: **Line Bonus**
- score display rules: **Rounding and Display**

Supporting mechanics live in [§3.2](#32-interaction-contracts), [§4.3](#43-scoring-coroutine), [§4.4](#44-jitter-buffer), and [§4.6](#46-beat-time-conversion). Worked numeric examples live in [Appendix E](#appendix-e-worked-examples).

### Public API

```kotlin
interface ScoringEngine {
    val playerScores: StateFlow<Map<PlayerId, PlayerScore>>
    val livePitch: SharedFlow<PitchEvent>  // For UI pitch cursor
    
    fun loadChart(chart: ParsedSong, micDelayMs: Int, medleyWindow: BeatRange?, config: ScoringConfig)
    fun setSongStart(songStartTvMs: Long)
    fun start()
    fun suspend()
    fun resume()
    suspend fun finalizeAll(): Map<PlayerId, PlayerScore>
    fun reset()
    fun stop()
}

data class ScoringConfig(
    val playerDifficulties: Map<PlayerId, Difficulty>,
    val lineBonusEnabled: Boolean
)

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
| Note finalization latency | ≤ 50ms after ideal eligibility time on target hardware | Instrumented test |
| Jitter buffer capacity | 500ms × 50fps × 2 players (50ms safety margin over 450ms drop threshold) | Unit test, verify no overflow |
| Perfect score | `scoreTotalInt == 10000` | F08 with perfect input |

### Scoring Algorithm (Normative)

**Scoring coroutine (normative)**: scoring evaluation MUST run on a **dedicated coroutine**, independent of the UI render loop. The coroutine MUST:
1. Poll `System.nanoTime() / 1_000_000` (TV monotonic clock) often enough to finalize due notes within the latency SLA. (`ExoPlayer.getCurrentPosition()` is used separately for lyrics beat position, not for note-window comparisons.)
2. Maintain the jitter buffer of incoming pitch frames.
3. Keep pending note finalizations in chronological order by `noteEndTvMs + NOTE_FINALIZATION_DELAY_MS`.
4. Finalize every note whose deadline is due when TV monotonic clock reaches or exceeds that deadline.
5. Emit updated score state only when finalized-note processing changes score-visible state.

This decouples scoring accuracy from UI frame rate — render load, frame drops, or display Hz differences MUST NOT affect scoring. Score state MUST be exposed via `StateFlow<PlayerScore>` and observed by the Compose UI.

**Normalization check**: for a perfect performance (all frames are hits for every note), total across all notes equals `sum(max_note_score) = MaxSongPoints` ✓

Score is normalized to **10000 total**. Line bonus ON reserves 1000 for line bonus and distributes the remaining 9000 via note value normalization.

**Score budgets**:
- If `LineBonusEnabled = ON`: `MaxSongPoints = 9000`, `MaxLineBonusPool = 1000`.
- If `LineBonusEnabled = OFF`: `MaxSongPoints = 10000`, `MaxLineBonusPool = 0`.

**Per-note scoring** — when a note is finalized:

Let `samplesInNote` = the set of qualifying pitch frames collected for this note (from jitter buffer range query). `N = |samplesInNote|`.

If `N = 0`: `note_score = 0`.

If `N > 0`:
- Count hits: `hits = |{ s ∈ samplesInNote : isPitchMatch(s, note) }|`
- `max_note_score = (MaxSongPoints / TrackScoreValue) × ScoreFactor[noteType] × durationBeats`
- `note_score = max_note_score × (hits / N)` — `hits / N` MUST use IEEE 754 double-precision float division.

**Score accumulation**:
- Normal (`:`) or Rap (`R`): add `note_score` to `Player.Score`.
- Golden (`*`) or RapGolden (`G`): add `note_score` to `Player.ScoreGolden`.
- Freestyle (`F`): `ScoreFactor = 0`, so `max_note_score = 0`; no accumulation occurs.

**ScoreFactor constants**:

| Token | Type | ScoreFactor |
|-------|------|-------------|
| `F` | Freestyle | 0 |
| `:` | Normal | 1 |
| `*` | Golden | 2 |
| `R` | Rap | 1 |
| `G` | RapGolden | 2 |

**`TrackScoreValue`**: `sum(note.durationBeats × ScoreFactor[note.noteType])` over all notes in the track — equivalently, the pre-computed `track.trackScoreValue`. Medley exception: only notes within `[medleyStartBeat, medleyEndBeat)` are included; notes outside the window are treated as Freestyle (ScoreFactor=0).

**`toneValid` is implicit** (normative): `toneValid = (midiNote != 255)`. There is no separate boolean field in the wire format. Frames with `midiNote = 255` are always unvoiced.

**Per-sample hit detection (`isPitchMatch`)**:
- **Freestyle** (`F`): never evaluated (ScoreFactor = 0).
- **Normal** (`:`) and **Golden** (`*`): `s.toneValid = true` AND `abs(octaveNormalized(s.tone, note.toneSemitone) − note.toneSemitone) <= Range`.
- **Rap** (`R`) and **RapGolden** (`G`): `s.toneValid = true` (presence-only; pitch difference ignored).

Where `s.tone = s.midiNote − 36` (C2=36 → Tone=0, matching USDX's C2=0 pitch base).

**Scoring configuration contract (normative)**:
- `ScoringEngine.loadChart(...)` MUST receive all gameplay inputs that affect scoring through `ScoringConfig`.
- `playerDifficulties` comes from Select Players and MUST include one entry for each assigned singer.
- `lineBonusEnabled` comes from Settings > Gameplay.
- `ScoringEngine` MUST NOT read these values implicitly from UI state, global settings, or any source outside the explicit `ScoringConfig` passed for the current song/segment.

### Player Level / Tolerance (Normative)

Each player has a Difficulty setting. The pitch tolerance `Range` (in semitones):
- **Easy**: Range = 2
- **Medium**: Range = 1 (default for newly assigned singers)
- **Hard**: Range = 0

Range is applied only for Normal and Golden notes. Rap notes ignore pitch difference.

**Parity requirement**: implement the exact Range mapping above (Easy=2, Medium=1, Hard=0) per player. Default difficulty is **Medium** for each newly assigned singer.

### Octave Normalization (Normative)

Before comparing to the target note, normalize the detected pitch to the closest octave of the target:
```
while (Tone - TargetTone > 6) Tone := Tone - 12
while (Tone - TargetTone < -6) Tone := Tone + 12
```

Do NOT reduce to pitch class (`mod 12`) before the loop. The loop operates on the full semitone value and shifts by 12 until distance to `TargetTone` is within ±6.

### Line Bonus (Normative)

**Sentence finalization**: a sentence is complete when its last scorable note has been finalized. At that point, line bonus evaluation runs.

**Per-line max score**: `MaxLineScore = MaxSongPoints × (LineScoreValue / TrackScoreValue)`, where `LineScoreValue = line.lineScoreValue` (pre-computed by the parser as `Σ(note.durationBeats × ScoreFactor[note.noteType])` over notes in the line) and `TrackScoreValue = track.trackScoreValue`.

**Line perfection**:
- `LineScore = (Player.Score + Player.ScoreGolden) − Player.ScoreLast`
- If `MaxLineScore <= 2` then `LinePerfection = 1` (forgiveness term)
- Else `LinePerfection = clamp(LineScore / (MaxLineScore − 2), 0, 1)`

**Distribution** (when LineBonusEnabled=ON):
- Empty lines (`LineScoreValue = 0`) do not receive line bonus.
- `NonEmptyLines = NumLines − NumEmptyLines`
- `LineBonusPerLine = MaxLineBonusPool / NonEmptyLines` (float division; not integer-divide)
- `Player.ScoreLine += LineBonusPerLine × LinePerfection`
- `Player.ScoreLast` MUST be updated after each sentence's line bonus is applied.

### Rounding and Display (Normative)

**Line score rounding**: `Player.ScoreLineInt = floor(round(Player.ScoreLine) / 10) × 10`

**Tens rounding**:
- `ScoreInt = round(Player.Score / 10) × 10`
- `ScoreGoldenInt` rounds in the **opposite direction** to prevent sum exceeding 10000:
  - If `ScoreInt < Player.Score` then `ScoreGoldenInt = ceil(Player.ScoreGolden / 10) × 10`
  - Else `ScoreGoldenInt = floor(Player.ScoreGolden / 10) × 10`
- `ScoreTotalInt = ScoreInt + ScoreGoldenInt + Player.ScoreLineInt`

**Intentional rounding asymmetry**: `ScoreLineInt` uses `floor(round(x)/10)*10` while `ScoreInt`/`ScoreGoldenInt` use `round(x/10)*10`. This matches USDX behavior and MUST NOT be normalized.

### L2 Visible Shapes

- **JitterBuffer**: Ring buffer keyed by `tvTimeMs`, range query for note windows (see [§4.4](#44-jitter-buffer))
- **ScoringCoroutine**: deadline-driven loop, uses `System.nanoTime()`, triggers finalization (see [§4.3](#43-scoring-coroutine))
- **NoteEvaluator**: Hit detection, octave normalization, tolerance
- **LineBonusCalculator**: Sentence completion, -2 forgiveness

### Acceptance Tests (Jitter Buffer — 5.2.3)

| ID | What | Expected | Fixture |
|----|------|---------|---------|
| T5.2.3.1 | Note not finalized before `noteEndTvMs + 450` | No scoring result before finalization time |
| T5.2.3.2 | At finalization, all qualifying frames collected | `samplesInNote` contains every frame with `noteStartTvMs <= tvTimeMs < noteEndTvMs` and `latenessMs <= 450` |
| T5.2.3.3 | Frames outside note window excluded | Frames with `tvTimeMs < noteStartTvMs` or `>= noteEndTvMs` not in `samplesInNote` |
| T5.2.3.4 | Frame too late: `latenessMs > 450` | Frame excluded | F13 |
| T5.2.3.5 | Decreasing `seq` → drop | Seq=3 dropped after seq=5 accepted | F13 |
| T5.2.3.6 | `tvTimeMs` regression > 200ms → drop | Frame dropped | F13 |
| T5.2.3.7 | `tvTimeMs` regression ≤ 200ms → accept | Frame retained and eligible | F13 |
| T5.2.3.8 | No qualifying frames for a note | `samplesInNote` empty; `N=0` → `note_score=0` | inline |

### Acceptance Tests (Beat-Time — 5.3)

| ID | What | Fixture | Expected |
|----|------|---------|---------|
| T5.3.1 | Highlight cursor: `lyricsTimeSec=5.0`, `GAP=2000`, `BPM_file=120` | F06/`expected.beat_cursors.json` | `currentBeat=24` |
| T5.3.2 | Scoring cursor: same + `micDelayMs=100` | F06 | `currentBeatD=22` |
| T5.3.3 | Round-trip: `BeatInternalToTimeSec(TimeSecToMidBeatInternal(t)) ≈ t` | inline | Match to 1e-9s |
| T5.3.4 | Note window: `startBeat=11`, `duration=2` | inline | Active at b=11,12; NOT at b=13 |
| T5.3.5 | Medley: notes outside `[medleyStartBeat, medleyEndBeat)` treated as Freestyle | inline | ScoreFactor=0 at scoring time |

### Acceptance Tests (Scoring — 6.1 / 6.2 / 6.4 / 6.5 / 6.6)

**[Scoring Algorithm](#scoring-algorithm-normative) Scoring Overview**

| ID | What | Fixture | Expected |
|----|------|---------|---------|
| T6.1.1 | Perfect performance → `scoreTotalInt=10000` | F08/`expected.score.json` | All notes: `hits=N`, `note_score=max_note_score` |
| T6.1.2 | N=0 (no frames) → `note_score=0` | F08 | `note_score=0` |
| T6.1.3 | Partial hits: `note_score = max_note_score × (hits/N)` | F08 | Per-note values match fixture |
| T6.1.4 | Normal/Rap → `Player.Score`; Golden/RapGolden → `Player.ScoreGolden` | F08 | Accumulation fields match |
| T6.1.5 | Freestyle: `ScoreFactor=0` → `note_score=0` even with `toneValid=true` | F03/`scoring/freestyle_only` | `scoreTotalInt=0` |
| T6.1.6 | Sentence finalization triggers line bonus | F11 | Line bonus applied at sentence boundary |

**[§6.2](#scoring-algorithm-normative) Note Types**

| ID | What | Fixture | Expected |
|----|------|---------|---------|
| T6.2.1 | Rap: `toneValid=true` → hit regardless of pitch | F10 | Hit counted |
| T6.2.2 | Rap: `toneValid=false` → miss | F10 | Hit not counted |
| T6.2.3 | Rap scoring end-to-end | F10/`expected.score.json` | `scoreTotalInt` matches fixture |

**[Octave Normalization](#octave-normalization-normative) Octave Normalization**

| ID | What | Fixture | Expected |
|----|------|---------|---------|
| T6.4.1 | Easy (±2): midiNote=47, target=0 → diff=1 after norm | F09/`easy_hit_diff1` | Hit |
| T6.4.2 | Medium (±1): midiNote=47, target=0 → diff=1 | F09/`medium_hit_diff1` | Hit |
| T6.4.3 | Medium (±1): midiNote=38, target=0 → diff=2 | F09/`medium_miss_diff2` | Miss |
| T6.4.4 | Hard (±0): midiNote=47, target=0 → diff=1 | F09/`hard_miss_diff1` | Miss |
| T6.4.5 | Octave norm: `Tone - Target > 6` → subtract 12 | inline | Tone shifted down |
| T6.4.6 | Octave norm: `Tone - Target < -6` → add 12 | inline | Tone shifted up |
| T6.4.7 | Do NOT reduce to pitch class (mod 12) before loop | inline | Full semitone value preserved |

**[Line Bonus](#line-bonus-normative) Line Bonus**

| ID | What | Fixture | Expected |
|----|------|---------|---------|
| T6.5.1 | Perfect performance: `ScoreLineInt=1000`, `ScoreTotalInt=10000` | F11/`expected.score.json` | Matches fixture |
| T6.5.2 | `MaxLineScore <= 2` → `LinePerfection=1` (forgiveness) | F11 | Line treated as perfect |
| T6.5.3 | Empty line (`LineScoreValue=0`) → no line bonus | F11 | Empty line skipped |
| T6.5.4 | `LineBonusPerLine` uses float division (not integer) | F11 | Precision matches fixture |
| T6.5.5 | Medley: `TrackScoreValue` only sums notes in `[medleyStartBeat, medleyEndBeat)` | F11 | Window-filtered sum |

**[Rounding and Display](#rounding-and-display-normative) Rounding and Display**

| ID | What | Fixture | Expected |
|----|------|---------|---------|
| T6.6.1 | `ScoreInt = round(Score/10) * 10` | F11/`expected.score.json` | Matches fixture |
| T6.6.2 | Golden opposite-rounding: `ScoreInt < Score` → `ScoreGoldenInt = ceil` | F11 / Appendix E.5 | Opposite direction applied |
| T6.6.3 | Golden opposite-rounding: `ScoreInt >= Score` → `ScoreGoldenInt = floor` | inline | Floor applied |
| T6.6.4 | `ScoreLineInt = floor(round(ScoreLine)/10)*10` (intentional asymmetry) | F11 | Asymmetric formula used |
| T6.6.5 | `ScoreTotalInt` never exceeds 10000 | F11 | Verified |

### Acceptance Criteria

- F06, F08, F09, F10, F11, F13, F24 pass

### Knowledge Gaps

None.

---

## 2.3 NetworkController

**Responsibility**: All network I/O. WebSocket server for control messages. UDP socket for pitch frames (validates, emits to SharedFlow). HTTP client for manifest/txt fetches. Connection tracking.

**Lifecycle**: Active for app lifetime. Sockets bound at startup.

### Network Overview

Use this section as the primary home for network protocol and session semantics:
- session entry and transport bindings: **Transport Bindings**, **Session Lifecycle**, **Session Token / Join Code**
- runtime control semantics: **`assignSinger` Semantics** and **`playbackState` Emission Rules**
- wire-level protocol shape: **Pitch Frame Wire Format**, **Control Message Schemas**, and [Appendix B](#appendix-b-protocol-json-schemas)
- reconnect and runtime transport handling: **Disconnect/Reconnect Mechanics**, **connectionId Assignment**, **UDP Frame Validation**, and **Pitch Frame Processing**
- timing/discovery support: [§4.5](#45-clock-sync-logic) and **mDNS Service Advertisement**

[§3.2 Interaction Contracts](#32-interaction-contracts) summarizes call boundaries, but this section remains the authoritative home for network behavior.

### Public API

```kotlin
interface NetworkController {
    val connectedPhones: StateFlow<List<ConnectedPhone>>
    val pitchFrames: SharedFlow<PitchFrame>
    val phoneEvents: SharedFlow<PhoneEvent>
    
    // Lifecycle
    fun start(udpPort: Int, wsPort: Int)
    fun stop()
    
    // Session administration
    fun kickPhone(clientId: String)
    
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
    val seq: UInt          // uint32 per wire format offset 0; not UShort
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

### Transport Bindings (Normative)

- **WebSocket URL**: `ws://<tv-ip>:<wsPort>/?token=<sessionToken>`. The `token` query parameter is validated on every new connection; missing or incorrect token → `error(code="invalid_token")` then close.
- **UDP port**: The TV MUST bind its `DatagramSocket` on `udpPort` at session start, **before any phone connects**, so the port is stable for the session lifetime. This port is included in `assignSinger.udpPort`. Frames MUST NOT be batched; each datagram is exactly one frame.

### `assignSinger` Semantics (Normative)

The TV sends `assignSinger` to instruct the phone as follows:
- `startMode = "countdown"`: the phone MUST delay sending `pitchFrame` datagrams until the countdown completes (after `countdownMs`). The phone MAY warm up pitch detection locally during the countdown, but MUST NOT transmit frames.
- `startMode = "live"`: begin sending frames immediately.
- `assignSinger` provides initial pre-roll configuration, including the active-song metadata shown on the phone. Once a `playbackState` for the same `songInstanceSeq` arrives, `playbackState` is authoritative for countdown/playing/paused/stopped phone UI state.
- Authority split: `playbackState` governs in-song runtime substate; `sessionState.inSong` governs whether the phone is in singing mode at all.
- `sessionState.inSong=false` is the authoritative session-level exit signal. On receiving it, the phone MUST leave singing mode and clear active song UI/state even if the last `playbackState` was `countdown`, `playing`, `paused`, or `stopped`.

### `playbackState` Emission Rules (Normative)

**Emission responsibility**: The `PlaybackCoordinator` MUST construct every `PlaybackStateMessage` on each playback-bearing game-phase transition and push it to `NetworkController.broadcastPlaybackState()`. The `NetworkController` MUST NOT autonomously construct `playbackState` messages.

**Phases that do NOT emit** `playbackState`: `Idle`, `Loading`, `Results`.

**Phase → `state` field mapping**:
| GamePhase | `state` field |
|-----------|--------------|
| `Countdown` | `"countdown"` |
| `Playing` | `"playing"` |
| `Paused` or `DisconnectPaused` | `"paused"` |
| `Stopped` | `"stopped"` |

**`revision` semantics**: increments monotonically per `songInstanceSeq` on every emission; resets when `songInstanceSeq` changes. Phones MUST ignore any `playbackState` with a lower `revision` than the last accepted message for the same `songInstanceSeq`.

**`reason` value enum**: `""`, `"user_pause"`, `"singer_disconnected"`, `"song_end"`, `"user_quit"`, `"restart"`, `"segment_transition"`, `"medley_source"`, `"medley_end"`.

**`lyricsTimeMs`**: current ExoPlayer position at message construction time.

The TV MUST send `playbackState` whenever playback enters countdown, starts, pauses, resumes, seeks, or stops. On reconnect during an active song, after `sessionState` and any required `assignSinger`, the TV MUST send the current `playbackState` immediately.

### Session Lifecycle (Normative)

Session state is owned by the TV host app.

| State | Description |
|-------|-------------|
| **Open** | Phones may join and appear in connected roster |
| **Locked** | Song in progress; new joins rejected (existing phones may reconnect) |
| **Ended** | Current join code invalid; all phones must join a new session |

- On app launch, create a new session in **Open** state with pairing info displayed.
- On song start: transition to **Locked**. New `hello` attempts receive `error(code="session_locked")`.
- On song end (Results reached): transition to **Open**.

### Session Token / Join Code (Normative)

- Random token to prevent accidental LAN joins; minimum 32 bits entropy (recommended 64+).
- Same token shown as join code AND used as `token` query parameter on WebSocket URL.
- The session token is the single source of truth for joining. The displayed join code is the human-enterable representation of that token, the QR payload encodes that same token in the WebSocket URL, and mDNS TXT `code` advertises the same token in normalized form for manual-code matching.
- MUST be human-enterable: case-insensitive alphabet, MAY display in groups (e.g., `ABCD-EFGH`).
- Phone normalization: strip spaces/hyphens, case-insensitive comparison.
- Generated per session start; invalidated when session ends. Reuse across sessions NOT allowed.
- TV MUST reject WebSocket connections with missing or incorrect token: `error(code="invalid_token")`.

### Pitch Frame Wire Format (Normative)

`pitchFrame` is an **20-byte fixed-size binary UDP datagram**:

```
Offset  Size  Type    Field
  0      4   uint32  seq
  4      8   int64   tvTimeMs
 12      4   uint32  songInstanceSeq  (matches assignSinger.songInstanceSeq)
 16      1   uint8   playerId     (0=P1, 1=P2)
 17      1   uint8   midiNote     (0-127 voiced; 255=unvoiced)
 18      2   uint16  connectionId (assigned by TV at hello handshake)
```

Struct format: `<IqIBBH` (little-endian). Frames MUST NOT be batched. Each datagram is exactly one frame.

**`toneValid` is implicit**: `toneValid = (midiNote != 255)`. A `midiNote` of `0` is a valid MIDI note (not silence). Only `255` signals unvoiced/silence.

### Control Message Schemas (Normative)

All messages are JSON objects with common envelope: `type` (string), `protocolVersion` (int, MUST be `1`), `tsTvMs` (optional).

**`hello`** (Phone → TV): `clientId`, `deviceName`, `appVersion`, `httpPort`.
- `deviceName` is a persisted human-friendly phone label used for TV display. It MUST NOT default to a raw hardware model string if a friendlier label is available.

**`sessionState`** (TV → Phone): `sessionId`, `slots { P1: { connected, deviceName }, P2: { connected, deviceName } }`, `inSong`, `songTimeSec`, `connectionId` (present only in initial response to hello; null in broadcasts).

**`assignSinger`** (TV → Phone): `sessionId`, `songInstanceSeq` (uint32), `playerId` (`"P1"` / `"P2"`), `difficulty` (`"Easy"` / `"Medium"` / `"Hard"`), `startMode` (`"countdown"` or `"live"`), `countdownMs` (int; if countdown), `stopAtLyricsTimeMs` (int), `udpPort` (int), `songTitle`, `songArtist`.

Before the TV sends `assignSinger`, it MUST already have at least one valid clock-sync sample for that singer. If `startMode="countdown"`, this requirement applies before countdown begins.

**`stopAtLyricsTimeMs` computation (normative)**: for a normal song, if `#END` present and > 0, use `endMs`; otherwise use the effective playback-plan duration reported by the UI (`audioDurationMs` for single-track playback; for dual-track playback, the coupled plan's natural stop duration after applying the shorter-track rule). `#START` changes initial playback position only, not timing origin. For medley: lyrics-time ms at the end of the final segment's fade-out. MUST be recomputed on Restart or reconnect.

**`playbackState`** (TV → Phone): required fields per Appendix B [§B.2.7](#b27-playbackstate):

| Field | Type | Notes |
|-------|------|-------|
| `type` | `"playbackState"` | constant |
| `protocolVersion` | int `1` | |
| `sessionId` | string | identifies current session |
| `songInstanceSeq` | uint32 | matches active `assignSinger.songInstanceSeq` |
| `revision` | int ≥ 0 | monotonic counter; increments on every emission; resets when `songInstanceSeq` changes |
| `state` | enum | `"countdown"` \| `"playing"` \| `"paused"` \| `"stopped"` |
| `lyricsTimeMs` | int ≥ 0 | current lyrics-time position in ms |
| `stopAtLyricsTimeMs` | int ≥ 0 | when playback will end |
| `countdownRemainingMs` | int\|null | present only when `state="countdown"`; omitted otherwise |
| `reason` | string | enum: `""`, `"user_pause"`, `"singer_disconnected"`, `"song_end"`, `"user_quit"`, `"restart"`, `"segment_transition"`, `"medley_source"`, `"medley_end"` |
| `tsTvMs` | number\|null | optional TV wall-clock timestamp |

**`error`** (TV → Phone): `code` (e.g., `"session_full"`, `"session_locked"`, `"protocol_mismatch"`, `"invalid_token"`), `message`.

TV MUST reject clients whose `hello.protocolVersion != 1` with `error(code="protocol_mismatch")` and close.

**Unknown message type (normative)**: an unknown `type` field MUST be ignored with a warning. **Exception**: during the handshake sequence, an unexpected message type is a fatal error — close the connection.

**Versioning / backward compatibility**: `protocolVersion = 1` for MVP. Backward/forward compatibility is **out of scope** for MVP; future versions MUST increment `protocolVersion` and maintain a compatibility table.

### Disconnect/Reconnect Mechanics (Normative)

**Mid-song disconnect**:
- **Required singer** disconnects: TV auto-pauses (`DisconnectPaused`) and shows disconnect overlay.
- **Spectator / song-source-only** disconnects: no pause. Songs removed from library. If active song was streaming from that phone, stream breaks and playback-error handling applies.

**Reconnect behavior**:
- **Transport disconnect** (network drop, backgrounded): phone auto-reconnects with same `clientId`. No QR/code rescan.
- **User-initiated leave**: return to Join screen, clear cached endpoint. No auto-reconnect.
- **Host kick**: phone returns to Join screen, clears endpoint.
- On reconnect within same session: phone sends same `clientId` in `hello` to reclaim identity. **Reconnect admission MUST be based on `clientId` already present in the current session roster** — not only on a currently-live socket registry entry.
- TV assigns new `connectionId`. If the reconnecting phone remains an active Singer for the current song, the TV re-sends `assignSinger` with **recomputed `stopAtLyricsTimeMs` reflecting the remaining playback plan**; otherwise it MUST NOT send `assignSinger` for that song. The TV then immediately sends current `playbackState`.
- If the phone was assigned as a Singer when it disconnected, it MUST resume that singer role on reconnect unless the TV has removed the device via Kick or the host chose **Continue without them** for the current song. In the **Continue without them** case, the phone may reconnect to the session, but it MUST NOT resume singer role or contribute further score until the next song.
- On reconnect during **Open** or **Results**, the TV MUST fetch `/manifest.json` from the reconnecting phone to refresh the song index immediately.
- On reconnect during **Countdown**, **Playing**, **Paused**, **DisconnectPaused**, or **Stopped**, the TV MUST mark that phone's catalog stale and defer `/manifest.json` fetch until the session next reaches **Results** or **Open**. Library refresh MUST NOT occur during gameplay.
- **Socket cleanup**: when a new socket replaces an old one for the same `clientId`, cleanup of the closing socket MUST only remove connection/session state if that closing socket is still the active socket for that client.
- If roster full and reconnect does not match existing `clientId`: reject with `code="session_full"`.

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
| Instance name | `KaraokeTV-<last4>` (last 4 chars of join code, e.g., `KaraokeTV-EFGH`). MUST be unique on the LAN. |
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
1. Datagram must be exactly 20 bytes (else silently drop).
2. Look up `connectionId` (bytes 18–19) in active connection table.
3. Verify it matches expected connection for `playerId` (byte 16).
4. Verify `songInstanceSeq` matches the active song or medley segment target. During medley segment transition, the next segment becomes active for UDP validation when `loadChart()` completes, not when `start()` is called.
5. If any check fails: silently drop.

This is best-effort routing, not a security control.

### Pitch Frame Processing

**Pitch frame rate (normative)**:
- Phones MUST send pitch frames at **50 fps** (20ms interval).
- Missing or invalid frames MUST be treated as `toneValid=false`.
- **Countdown rule**: when `startMode="countdown"`, the phone MUST NOT send frames until the countdown completes. The TV MUST NOT score any frames received before the countdown ends.

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

**Song source policy (normative)**: after a successful `hello` handshake, the TV MUST fetch `/manifest.json` from the phone's HTTP server to populate the library with that phone's songs. No separate pairing, trust list, or approval step is required — the current join code already gates who can join.

**`/manifest.json` serving (normative)**: the phone MUST serve `/manifest.json` from an **in-memory JSON byte array** rebuilt on each scan. It MUST NOT read from disk on each HTTP request. The scan populates the byte array; the HTTP handler serves it directly. This ensures low-latency manifest responses and avoids I/O during playback.

- Pass song URLs directly to LibVLC or Coil (images). No intermediate storage.
- LibVLC begins playback after buffering (file-caching default 2000ms). MUST NOT wait for full download.
- HTTP failure (connection refused, 404, timeout): suppress for images; recoverable error for audio (treat same as missing optional asset vs. missing required audio respectively).

**HTTP contract requirements the TV relies on (normative)** — the phone server MUST satisfy these for LibVLC to work correctly:
- `Range` requests: server MUST support HTTP `Range` for all audio/video. ExoPlayer requires range support for seeking without re-downloading. Server MUST respond with `206 Partial Content` and a correct `Content-Range` header; MUST include `Accept-Ranges: bytes` on all audio/video responses.
- `Content-Length`: MUST be set on all responses.
- `/manifest.json`: server MUST set `Cache-Control: no-cache` to ensure the TV always receives the latest catalog.

### Acceptance Tests (Protocol — 8.3 / 8.5 / 8.6)

**[§8.3](#23-networkcontroller) Control Messages**

| ID | What | Fixture | Expected |
|----|------|---------|---------|
| T8.3.1 | Valid `hello` → `sessionState` with `connectionId` | F15 | `sessionState` carries `connectionId` |
| T8.3.2 | `hello` without `httpPort` → rejected | F15 | Error; code implementation-defined |
| T8.3.3 | TV fetches `/manifest.json` after `sessionState` | F15 | Manifest fetch occurs immediately |
| T8.3.4 | Wrong `protocolVersion` | F15 | `error(code="protocol_mismatch")` |
| T8.3.5 | Wrong token | F15 | `error(code="invalid_token")` |
| T8.3.6 | Join during Locked state | F15 | `error(code="session_locked")` |
| T8.3.7 | Roster full (> 10) | F15 | `error(code="session_full")` |
| T8.3.8 | Manifest fetch → library updated | F15 | Songs attributed to `clientId` visible |
| T8.3.9 | Phone disconnects → songs removed | F15 | All songs for `clientId` removed immediately |
| T8.3.10 | Manifest re-fetch replaces all prior songs for phone | F15 | Not appended; full replacement |
| T8.3.11 | `assignSinger` contains all required fields per B.2.6 | F15 | `sessionId`, `songInstanceSeq`, `playerId`, `difficulty`, `startMode`, `stopAtLyricsTimeMs`, `udpPort`, `songTitle`, `songArtist` |
| T8.3.12 | `playbackState` carries playback authority fields | F15 | `sessionId`, `songInstanceSeq`, `revision`, `state`, `lyricsTimeMs`, `stopAtLyricsTimeMs`, conditional `countdownRemainingMs`, enum-constrained `reason`, optional `tsTvMs` |
| T8.3.13 | `connectionId` NOT in `assignSinger` | F15 | Field absent; delivered only via `sessionState` |

**[§8.5](#23-networkcontroller) Sender Identification**

| ID | What | Fixture | Expected |
|----|------|---------|---------|
| T8.5.1 | First connection assigns `connectionId=1` | F15/`case_reconnect_reclaim` | In `sessionState` response |
| T8.5.2 | Reconnect → new `connectionId=2` | F15/`case_reconnect_reclaim` | Different from first |
| T8.5.3 | `assignSinger` re-sent after reconnect; `connectionId` absent | F15/`case_reconnect_reclaim` | Field absent from `assignSinger` |
| T8.5.4 | PitchFrames with old `connectionId=1` → dropped | F15/`case_reconnect_reclaim` | Silently dropped |
| T8.5.5 | Third phone rejected | F15 | `error(code="session_full")` |

**[§8.6](#pitch-frame-processing) Frame Ingestion and Validation**

| ID | What | Fixture | Expected |
|----|------|---------|---------|
| T8.6.1 | Decode frame 0: all fields match | F12v2/`expected.json` row 0 | All fields correct |
| T8.6.2 | `midiNote=255` → `toneValid=false` | F12v2/`expected.json` row 1 | `toneValid=false` |
| T8.6.3 | `midiNote=0` → `toneValid=true` (valid MIDI note, not silence) | inline | Not treated as unvoiced |
| T8.6.4 | `encode(decode(frame))` round-trip | F12v2 | Identical bytes |
| T8.6.5 | Datagram ≠ 20 bytes → silently dropped | inline | Returned/dropped |
| T8.6.6 | `connectionId` mismatch → silently dropped | inline | Dropped |
| T8.6.7 | `songInstanceSeq` mismatch → silently dropped | inline | Dropped |
| T8.6.8 | Unknown `playerId` (not P1/P2) → silently dropped | inline | Dropped |

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
    /**
     * Parse a USDX TXT file into a ParsedSong.
     *
     * @param songId canonical "clientId::relativeTxtPath" supplied by caller
     *               (LibraryManager); parser does not derive it.
     * @param txtBytes raw file bytes (encoding handled internally).
     * @return Result.success with ParsedSong whose `diagnostics` may contain
     *         info/warn entries. Hard-invalid songs → Result.failure with
     *         ParseException carrying the populated diagnostics list.
     */
    fun parse(songId: String, txtBytes: ByteArray): Result<ParsedSong>
}

class ParseException(
    val diagnostics: List<DiagnosticEntry>
) : RuntimeException(diagnostics.firstOrNull { it.severity == Severity.Invalid }?.message)

// ────────────────────────────────────────────────────────────────
// Canonical parsed-song model (single source of truth).
// Both code and normative-prose references in this document defer
// to this block. DO NOT redefine these types elsewhere.
// ────────────────────────────────────────────────────────────────

data class ParsedSong(
    val songId: String,                     // "clientId::relativeTxtPath" — supplied by caller
    val header: SongHeader,
    val timing: SongTiming,
    val tracks: List<Track>,                // size 1 for solo, 2 for duet; invariant enforced by parser
    val diagnostics: List<DiagnosticEntry>  // info/warn entries collected during parse
)

data class SongHeader(
    // Required fields
    val title: String,
    val artist: String,
    val bpmFile: Float,              // Raw #BPM (file units; internal = ×4)
    val gapMs: Float,                // #GAP in milliseconds (fractional ms allowed); default 0
    val audio: String,               // Resolved audio filename (#AUDIO if version≥1.0.0 and present, else #MP3)
    val songPath: String,            // Canonical path/URI to song root directory

    // Optional playback-timing offsets (sourced from header tags)
    val startSec: Float?,            // #START in seconds
    val endMs: Int?,                 // #END in milliseconds
    val videoGapSec: Float?,         // #VIDEOGAP in seconds
    val previewStartSec: Float?,     // #PREVIEWSTART in seconds

    // Optional media
    val video: String?,              // #VIDEO
    val cover: String?,              // #COVER
    val background: String?,         // #BACKGROUND
    val instrumental: String?,       // #INSTRUMENTAL (sole backing track when present; replaces #AUDIO/#MP3)
    val vocals: String?,             // #VOCALS (phone mixes with #INSTRUMENTAL before serving; TV receives single pre-mixed audioUrl)

    // Optional metadata
    val version: String,             // #VERSION if present; "0.3.0" treated as default when absent
    val year: Int?,                  // #YEAR
    val genre: String?,              // #GENRE
    val album: String?,              // #ALBUM (custom tag, preserved if present)

    // Duet (stored only; device names shown in UI)
    val isDuet: Boolean,             // true iff first non-empty body token begins with P
    val p1Name: String?,             // #P1 duet singer name
    val p2Name: String?,             // #P2 duet singer name

    // Medley
    val medleyStartBeat: Int?,       // #MEDLEYSTARTBEAT (file beats)
    val medleyEndBeat: Int?,         // #MEDLEYENDBEAT (file beats)

    // Unknown/malformed tags preserved in encounter order (ordered, no dedup)
    val customTags: List<CustomHeaderTag>
)

// Represents any unknown or malformed header tag, preserved in encounter order.
// tag: tag name without leading '#' (empty string when the header line had no ':')
// content: remainder of the header line after the colon (decoded per error-handling rules)
data class CustomHeaderTag(
    val tag: String,
    val content: String
)

data class SongTiming(
    val bpmFile: Float   // #BPM as written in file (sole BPM; variable-BPM charts are rejected at parse time)
    // Note: #GAP / #START / #END live in SongHeader — not duplicated here.
)

data class Track(
    val playerId: PlayerId,          // P1 or P2
    val lines: List<Line>,
    val trackScoreValue: Long        // Pre-computed: Σ(note.durationBeats × ScoreFactor[note.noteType]) over all notes
)

data class Line(
    val lineIndex: Int,              // 0-based within track
    val notes: List<NoteEvent>,      // ordered by startBeatFile
    val lineScoreValue: Long         // Pre-computed: Σ(note.durationBeats × ScoreFactor[note.noteType]) over notes in this line
) {
    val startBeatFile: Int
        get() = notes.firstOrNull()?.startBeatFile ?: 0
    val endBeatFileExclusive: Int
        get() = notes.maxOfOrNull { it.endBeatFileExclusive } ?: 0
    val isEmpty: Boolean
        get() = lineScoreValue == 0L    // covers both "no notes" and "only Freestyle" cases
}

data class NoteEvent(
    val noteType: NoteType,          // Normal (:), Golden (*), Rap (R), RapGolden (G), Freestyle (F)
    val startBeatFile: Int,          // Chart beat (file units; not ×4)
    val durationBeats: Int,          // Chart beats; duration=0 parser-converted to Freestyle (warn)
    val toneSemitone: Int,           // Semitone (USDX scale, C2 = 0). Used directly as TargetTone.
    val lyric: String                // As authored; may be empty
) {
    val endBeatFileExclusive: Int
        get() = startBeatFile + durationBeats
}

enum class NoteType { Normal, Golden, Rap, RapGolden, Freestyle }

// ────────────────────────────────────────────────────────────────
// Diagnostics — schema matches §2.4 "Error Handling" normative list
// ────────────────────────────────────────────────────────────────

data class DiagnosticEntry(
    val severity: Severity,
    val code: String,                // Short stable string; see error-handling table in §2.4
    val message: String,             // Human-readable description
    val txtUri: String,              // Song TXT identifier
    val lineNumber: Int? = null      // 1-based; present when a specific line caused the issue
)

enum class Severity { Info, Warn, Invalid }
```

**Invariants**:

- All `NoteEvent` in all tracks MUST satisfy `durationBeats >= 0`. `durationBeats == 0` is parser-converted to `Freestyle` (warn) and contributes 0 score.
- `tracks.size` MUST be **2** iff `header.isDuet` is true; otherwise MUST be **1**.
- Variable-BPM songs (multiple `B` tokens) MUST be rejected at parse time (`Result.failure`).
- `lineScoreValue` and `trackScoreValue` MUST be computed by the parser in a single pass; they are canonical and MUST NOT be recomputed by consumers.

**Beat convention**: `noteActive if startBeatFile <= beat < endBeatFileExclusive`.

### Supporting Types

```kotlin
// Shared across components — defined here as the canonical TV-side model

enum class PlayerId { P1, P2 }

data class BeatRange(
    val startBeat: Int,   // medleyStartBeat (file beats, inclusive)
    val endBeat: Int      // medleyEndBeat (file beats, exclusive)
)

data class MedleySegment(
    val index: Int,               // 0-based position in the medley run
    val txtUrl: String,
    val audioUrl: String?,        // pre-mixed backing track (phone mixes stems); null → segment skipped
    val videoUrl: String?,        // optional video asset for this segment
    val videoGapSec: Float?,      // #VIDEOGAP for this segment's video asset
    val medleyStartSec: Float,    // max(0, timeFromBeat(startBeat) − MEDLEY_FADE_IN_SEC)
    val medleyEndSec: Float,      // timeFromBeat(endBeat) + MEDLEY_FADE_OUT_SEC
    val beatWindow: BeatRange,    // scoring window and medley beat bounds: startBeat inclusive, endBeat exclusive
    val durationMs: Long,         // medleyEndSec − medleyStartSec, in ms (used for prebuffer trigger)
    val songTitle: String,
    val songArtist: String
)

data class PlayerAssignment(
    val playerId: PlayerId,
    val phone: ConnectedPhone,
    val difficulty: Difficulty,
    val duetPart: PlayerId? = null  // non-null only for single-player duet: which track to sing
)

enum class Difficulty { Easy, Medium, Hard }
```

### NFRs Applied

- **Testability**: Pure function, no I/O
- **Modularity**: Zero knowledge of network, playback, scoring

### SLAs

| Metric | Target | Test |
|--------|--------|------|
| Parse time | <50ms for 10KB txt | Benchmark with F03 fixtures |
| Memory | No allocation beyond result | Verify with profiler |

### Supported Note Tokens (Normative)

| Token | Type | Scoring |
|-------|------|---------|
| `:` | Normal note | ScoreFactor=1 |
| `*` | Golden note | ScoreFactor=2 |
| `F` | Freestyle note | ScoreFactor=0 (scored as 0) |
| `R` | Rap note | ScoreFactor=1 |
| `G` | RapGolden note | ScoreFactor=2 |
| `-` | Line break / new sentence | — |
| `E` | End of song data | — |
| `P1`, `P2` | Duet part delimiters | — |

**Per-note fields** (for `:`, `*`, `F`, `R`, `G`): `<token> <startBeatFile> <durationBeats> <toneSemitone> <lyric...>`
- `startBeatFile` and `durationBeats` are integers in chart beat units (file units; internal = ×4).
- `toneSemitone` is an integer semitone index (USDX scale, C2 = 0).
- `lyric` is the remainder of the line after the numeric fields.

**Duet structure**: if the first non-empty body line begins with `P`, the song is duet (`isDuet = true`) with two tracks. `P1`/`P2` markers set the active track (0/1). Notes and `-` breaks are assigned to the current active track. A single `E` ends the file.

### Supported Header Tags (Normative)

| Tag | Required | Type | Semantics |
|-----|----------|------|-----------|
| `#TITLE` | yes | string | Song title |
| `#ARTIST` | yes | string | Song artist |
| `#BPM` | yes | float | Beats per minute (file BPM; internal = ×4) |
| `#GAP` | no | float | Delay from audio start to first beat (ms); default `0` if absent |
| `#MP3` / `#AUDIO` | yes (one) | string | Relative path to audio file |
| `#VIDEO` | no | string | Relative path to video file |
| `#VIDEOGAP` | no | float | Video offset in seconds |
| `#COVER` | no | string | Relative path to cover image |
| `#BACKGROUND` | no | string | Relative path to background image |
| `#INSTRUMENTAL` | no | string | Instrumental audio track (replaces `#AUDIO` as sole backing; `>= 1.1.0`) |
| `#VOCALS` | no | string | Acapella track (mixed with `#INSTRUMENTAL`; ignored if `#INSTRUMENTAL` absent; `>= 1.1.0`) |
| `#START` | no | float | Skip to this second on playback start |
| `#END` | no | int | Stop playback at this millisecond |
| `#PREVIEWSTART` | no | float | Preview start position in seconds |
| `#VERSION` | no | string | File format version (e.g., `1.0.0`) |
| `#MEDLEYSTARTBEAT` | no | int | Medley window start (file beats) |
| `#MEDLEYENDBEAT` | no | int | Medley window end (file beats) |
| `#P1` | no | string | Duet singer name for Player 1 (stored only) |
| `#P2` | no | string | Duet singer name for Player 2 (stored only) |
| `#YEAR` | no | int | Metadata year |
| `#GENRE` | no | string | Metadata genre (multi-valued) |
| `#EDITION` | no | string | Metadata edition (multi-valued; used for filtering/sorting) |
| `#CREATOR` | no | string | Metadata creator (multi-valued; used for filtering/sorting) |
| `#LANGUAGE` | no | string | Metadata language (multi-valued; used for filtering/sorting) |
| `#TAGS` | no | string | Metadata tags (multi-valued; parsed only for `>= 1.0.0`) |

All other tags (including `#ENCODING`, `#RESOLUTION`, `#NOTESGAP`, `#CALCMEDLEY`, and any unknown tags) MUST be preserved as `CustomHeaderTag` entries in encounter order.

### Error Handling (Normative)

**Header tags**:
- Header lines read while first character is `#`; any other line ends header parsing.
- Tag names are case-insensitive; matching on `Uppercase(Trim(TagName))`.
- Duplicate known tags: last successfully parsed value wins.
- Malformed required tag (TITLE/ARTIST/AUDIO-or-MP3/BPM): mark song **invalid**. Malformed optional tag: **warn**, treat as absent.
- Unknown tags, empty-value tags (`#NAME:`), and no-separator tags (no `:`): **warn** and preserve in `customTags`.

- Songs with `#BPM` missing or ≤ 0 MUST be rejected.
- Songs with no valid note lines MUST be rejected.
- Variable-BPM songs (multiple BPM change lines) MUST be rejected at parse time.
- Unknown header tags MUST be collected as `CustomHeaderTag` entries, not rejected.
- Unknown body tokens MUST be silently skipped (warn, don't reject).

**Version/encoding rules**:
- `#VERSION` absent → treat as legacy `0.3.0`.
- `#VERSION` present but fails to parse as dotted numeric → **invalid**.
- Supported versions are `< 2.0.0`; if `>= 2.0.0` → **invalid** (`ERROR_CORRUPT_SONG_INVALID_VERSION`).
- `#ENCODING`, `#RESOLUTION`, `#NOTESGAP`, `#DUETSINGERP1`, `#DUETSINGERP2`, `#CALCMEDLEY` MUST be treated as **unknown tags** regardless of version — preserved in `customTags`, no semantic processing.

**Body grammar**:
- `duration = 0` on any note token: **warn** with line number ("found note with length zero -> converted to FreeStyle") and convert the note to `F` (Freestyle); `duration` stays 0.
- `#RELATIVE` as a **header tag**: treated as unknown custom tag (no semantic effect); does NOT trigger an error. Songs authored with `#RELATIVE` are parsed as absolute-beat format, which may produce incorrect note timing.
- **RELATIVE body format** (`- <startBeat> <extraDelta>`): any sentence line with an extra numeric beat-delta parameter → **invalid** (`ERROR_CORRUPT_SONG_UNSUPPORTED_RELATIVE`).
- `B` (BPM change) body token: **invalid** (`ERROR_CORRUPT_SONG_UNSUPPORTED_VARIABLE_BPM`).
- `P` with value other than `1` or `2`: **invalid** (`ERROR_CORRUPT_SONG_INVALID_DUET_MARKER`).
- After body parsing, empty sentences (zero note events after parsing) MUST be removed. After cleanup, each track MUST have at least one remaining sentence; if not → **invalid** (`ERROR_CORRUPT_SONG_NO_NOTES`).
- Hardcoded: `RapToFreestyle = false`, `OutOfBoundsToFreestyle = false`.

**Diagnostics record schema** (normative):
Each parse attempt MUST produce a structured diagnostics list. Each entry has:
- `severity`: `"info"` | `"warn"` | `"invalid"`
- `code`: short stable string (see codes below)
- `message`: human-readable description
- `txtUri`: song TXT identifier
- `lineNumber`: optional 1-based line number, present when a specific line caused the issue

Invalid songs remain local scan results on the phone and are NOT published in `/manifest.json`.

**Minimum invalidation codes**:
| Code | Meaning |
|------|---------|
| `ERROR_CORRUPT_SONG_FILE_NOT_FOUND` | Required audio file missing or unresolvable |
| `ERROR_CORRUPT_SONG_NO_NOTES` | After sentence cleanup, no remaining sentences |
| `ERROR_CORRUPT_SONG_NO_BREAKS` | Reserved — could not construct any sentence container |
| `ERROR_CORRUPT_SONG_MISSING_REQUIRED_HEADER` | Missing TITLE/ARTIST/AUDIO-or-MP3/BPM |
| `ERROR_CORRUPT_SONG_MALFORMED_HEADER` | Required header present but malformed/unparseable |
| `ERROR_CORRUPT_SONG_MALFORMED_BODY` | Recognized body token but numeric field parse fails |
| `ERROR_CORRUPT_SONG_UNSUPPORTED_VARIABLE_BPM` | `B` (BPM change) token present |
| `ERROR_CORRUPT_SONG_UNSUPPORTED_RELATIVE` | Sentence line with legacy beat-delta parameter |
| `ERROR_CORRUPT_SONG_INVALID_VERSION` | VERSION fails to parse or VERSION >= 2.0.0 |
| `ERROR_CORRUPT_SONG_INVALID_DUET_MARKER` | `P` token with value other than P1/P2 |

### Parsed Song Model (Normative)

The canonical definitions of `ParsedSong`, `SongHeader`, `SongTiming`, `Track`, `Line`, `NoteEvent`, `NoteType`, `DiagnosticEntry`, and `Severity` are the Kotlin data classes in **§2.4 Public API** above. See that block for fields, types, nullability, and derived-property contracts. Invariants and the beat convention are stated immediately after the code block.

### L2 Visible Shapes
- **BodyTokenizer**: Tokenizes note lines (`:`, `*`, `F`, `R`, `G`, `-`, `E`, `P`)
- **BeatCalculator**: Applies BPM×4 rule for supported static-BPM charts
- **ErrorCollector**: Accumulates warnings, decides accept/reject

### Acceptance Tests (Error Handling)

| ID | What | Fixture | Expected |
|----|------|---------|---------|
| T4.3.1 | Unknown body token ignored | F03/`a/unknown_token_ignored` | `isValid=true` |
| T4.3.2 | Malformed numeric in body | F03/`b/invalid_malformed_numeric` | `isValid=false`, `ERROR_CORRUPT_SONG_MALFORMED_BODY`, `invalidLineNumber=7` |
| T4.3.3 | `duration=0` converts to Freestyle | F03/`c/duration_zero_converts_to_freestyle` | Note stored as `Freestyle` |
| T4.3.4 | No `-` lines → single implicit sentence | inline | `isValid=true`, 1 line, 1 note |
| T4.3.5 | No notes after cleanup | inline | `isValid=false`, `ERROR_CORRUPT_SONG_NO_NOTES` |
| T4.3.6 | `B` token (variable BPM) rejected | F03/`d/variable_bpm_rejected` | `isValid=false`, `ERROR_CORRUPT_SONG_UNSUPPORTED_VARIABLE_BPM` |
| T4.3.7 | `#RELATIVE:YES` treated as unknown custom tag | F03/`e/relative_header_as_custom_tag` | `isValid=true`, `customTags` contains `{RELATIVE, YES}` |
| T4.3.8 | RELATIVE body format (`- 16 4`) rejected | F03/`f/relative_body_rejected` | `isValid=false`, `ERROR_CORRUPT_SONG_UNSUPPORTED_RELATIVE` |
| T4.3.9 | Legacy RELATIVE fixture rejected | F05 | `isValid=false`, `ERROR_CORRUPT_SONG_UNSUPPORTED_RELATIVE` |

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
    // TV-side derived identifiers (not present in wire SongEntry)
    val songId: String,              // "{phoneClientId}::{relativeTxtPath}" — unique across library
    val phoneClientId: String,       // which phone contributed this song

    // Wire-format fields (mirror SongEntry 1:1)
    val relativeTxtPath: String,     // normalized per §2.5 rules (forward slashes, no leading /, no . or ..)
    val modifiedTimeMs: Long,        // TXT last-modified timestamp at scan time
    val title: String,
    val artist: String,
    val album: String?,
    val year: Int?,
    val genre: String?,

    // URLs (served by phone HTTP server)
    val txtUrl: String,              // non-null: validity invariant (see §2.5)
    val audioUrl: String,            // non-null: validity invariant (see §2.5)
    val videoUrl: String?,
    val coverUrl: String?,
    val backgroundUrl: String?,
    // Chart feature flags (computed by phone during validation, wired in manifest)
    val isDuet: Boolean,
    val hasRap: Boolean,             // R/G tokens detected in body
    val hasVideo: Boolean,           // invariant: == (videoUrl != null)
    val hasInstrumental: Boolean,    // phone-detected: true if song has #INSTRUMENTAL track (phone serves pre-mixed audio regardless)

    // Medley
    val canMedley: Boolean,
    val medleySource: String?,       // "tag" | null (future: "auto" post-MVP for #CALCMEDLEY)
    val medleyStartBeat: Int?,       // non-null iff medleySource == "tag"
    val medleyEndBeat: Int?,         // non-null iff medleySource == "tag"

    // Playback timing (non-null; defaults applied by parser)
    val startSec: Float,             // #START or 0.0
    val previewStartSec: Float       // per preview-start rule in §2.5; 0.0 if none applies
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

### Discovery and Validation Rules (Normative)

Songs are discovered on the phone side. The phone scans its songs folder, validates each song, and serves only valid song metadata from `/manifest.json`. Invalid songs remain as local diagnostics on the phone.

A song is **valid** if:
- A `.txt` file is found in a song directory.
- The `#TITLE`, `#ARTIST`, and `#BPM` headers are present and parseable.
- `#BPM` is > 0.
- A required audio file is resolved (version-conditional):
  - **`#VERSION >= 1.0.0`**: `#AUDIO` takes precedence over `#MP3`; at least one MUST be present. If both present, `#AUDIO` is used.
  - **Legacy (`#VERSION` absent or `< 1.0.0`)**: `#MP3` MUST be present; `#AUDIO` (if present) MUST be ignored for audio resolution.
- The resolved audio file MUST exist on disk; missing file → invalid.
- At least one valid note line exists in the body (after empty-sentence cleanup).

### Index Fields (Normative)

The `IndexedSong` fields are defined by the data class in §2.5 Public API above. Additional constraints:

- `songId` MUST equal `phoneClientId + "::" + relativeTxtPath` (byte-exact).
- `relativeTxtPath` normalization: path separators MUST be `/`; MUST NOT start with `/`; MUST NOT contain `.` or `..` segments; case MUST be preserved.
- `modifiedTimeMs`: Unix epoch milliseconds, TXT last-modified at scan time on phone.
- `txtUrl` and `audioUrl` MUST be non-null for entries that appear in `/manifest.json` (validity prerequisite from the Discovery and Validation Rules above).
- `hasVideo == (videoUrl != null)`. Violation → reject manifest entry.
- `hasInstrumental`: set by the phone based on whether the song source contains a `#INSTRUMENTAL` tag. The TV uses this flag only to display the `I` chip (§2.5 Song Grid Tag Overlays); it MUST NOT use it to decide playback strategy. `instrumentalUrl` and `vocalsUrl` are NOT present in the manifest.
- `medleySource == "tag"` ⇒ `medleyStartBeat` and `medleyEndBeat` both non-null, and `medleyStartBeat < medleyEndBeat`.
- `medleySource == null` ⇒ `canMedley == false`.
- `previewStartSec` derivation: `#PREVIEWSTART` if present and > 0; else if `medleySource != null` use `timeFromBeat(medleyStartBeat)`; else `0.0`.
- `startSec`: from `#START` if present; else `0.0`.

### Medley Eligibility: `canMedley` (Normative)

A song is medley-eligible iff ALL are true:
- `isDuet = false`, AND
- Valid medley tags exist (`medleySource = "tag"`)

Valid medley tags: `#MEDLEYSTARTBEAT` and `#MEDLEYENDBEAT` are both present, both parse as integers, and `startBeat < endBeat`. If valid tags exist, `medleySource = "tag"`; otherwise `medleySource = null` and `canMedley = false`.

**Medley auto-calc deferred**: USDX's refrain-finding algorithm (`#CALCMEDLEY`) is not specified for MVP. Only songs with explicit medley beat tags are eligible.

### Song Grid Tag Overlays

Each song tile shows single-letter chips:
- `D` = duet (`isDuet=true`)
- `R` = rap (`hasRap=true`)
- `V` = video (`hasVideo=true`)
- `I` = instrumental (`hasInstrumental=true`)
- `M` = medley-eligible (`canMedley=true`)

### Catalog Fetch Triggers (Normative)

TV rebuilds library by fetching `GET /manifest.json` from each phone at exactly these points:

1. **Phone connection**: After successful `hello`/`sessionState` handshake, fetch manifest before making songs visible.
2. **Results screen**: When Results displayed (after any song/medley run), re-fetch all manifests. Ensures catalog changes (e.g., rescan during song) are reflected. Any catalog marked stale during gameplay MUST be refreshed here before the next selection flow continues.
3. **Manual refresh**: When user triggers Refresh in Settings > Song Library.

Fetch replaces all songs for that `clientId` (not append). On failure: retain previous catalog, show error toast.

**Phone disconnect**: Immediately remove all songs for that `clientId` from library.

### SongEntry Manifest Schema (Normative)

The `/manifest.json` response is a JSON array of `SongEntry` objects. Each entry MUST include:

```json
{
  "relativeTxtPath": "Artist - Title/song.txt",
  "modifiedTimeMs": 1712000000000,
  "title": "Song Title",
  "artist": "Artist Name",
  "album": null,
  "year": null,
  "genre": null,
  "isDuet": false,
  "hasRap": false,
  "hasVideo": true,
  "hasInstrumental": false,
  "canMedley": true,
  "medleySource": "tag",
  "medleyStartBeat": 100,
  "medleyEndBeat": 400,
  "startSec": 0.0,
  "previewStartSec": 30.0,
  "txtUrl": "http://<phone-ip>:<port>/songs/Artist - Title/song.txt",
  "audioUrl": "http://<phone-ip>:<port>/songs/Artist - Title/audio.mp3",
  "videoUrl": "http://<phone-ip>:<port>/songs/Artist - Title/video.mp4",
  "coverUrl": "http://<phone-ip>:<port>/songs/Artist - Title/cover.jpg",
  "backgroundUrl": null
}
```

Required fields: `relativeTxtPath`, `modifiedTimeMs`, `title`, `artist`, `isDuet`, `hasRap`, `hasVideo`, `hasInstrumental`, `canMedley`, `startSec`, `previewStartSec`, `txtUrl`, `audioUrl`. Optional URL fields (`videoUrl`, `coverUrl`, `backgroundUrl`) are `null` when the corresponding file is absent. `instrumentalUrl` and `vocalsUrl` are NOT included in the manifest; the phone serves a pre-mixed `audioUrl`.

### Acceptance Tests (Library, Discovery, Index)

**T3.1 — TV-Side Library**

| ID | What | Expected |
|----|------|---------|
| T3.1.1 | Two phones each add 3 songs → library = 6 | Count correct |
| T3.1.2 | `songId = phoneClientId + "::" + relativeTxtPath` | Format matches |
| T3.1.3 | Sort order: Artist → Album → Title | Sorted correctly |
| T3.1.4 | Phone disconnects → songs removed immediately | Immediate removal |
| T3.1.5 | Manifest fetch replaces, not appends, for that `clientId` | Old entries gone |

**T3.2 — Validation**

| ID | What | Fixture | Expected |
|----|------|---------|---------|
| T3.2.1 | Missing `#ARTIST` | F01/`a/invalid_missing_required_header` | `isValid=false`, `ERROR_CORRUPT_SONG_MISSING_REQUIRED_HEADER` |
| T3.2.2 | `#AUDIO` file missing on disk | F01/`b/invalid_missing_audio` | `isValid=false`, `ERROR_CORRUPT_SONG_FILE_NOT_FOUND`, `invalidLineNumber=4` |
| T3.2.3 | v1.0.0: `#AUDIO` beats `#MP3` | F01/`c/v1_audio_precedence` | `isValid=true`, `resolvedAudio=audio.ogg` |
| T3.2.4 | Legacy: `#MP3` required, `#AUDIO` ignored | F01/`c/legacy_mp3_preferred` | `isValid=true`, `resolvedAudio=audio.mp3` |
| T3.2.5 | Legacy: no `#MP3` | F01/`c/legacy_missing_mp3_invalid` | `isValid=false`, `ERROR_CORRUPT_SONG_MISSING_REQUIRED_HEADER` |
| T3.2.6 | Missing optional `#VIDEO` | F01/`c/v1_missing_optional_video` | `isValid=true`, `hasVideo=false` |
| T3.2.7 | `#BPM:0` | inline | `isValid=false`, `ERROR_CORRUPT_SONG_MALFORMED_HEADER` |
| T3.2.8 | Non-numeric `#BPM` | F02/`b/invalid_malformed_bpm` | `isValid=false`, `ERROR_CORRUPT_SONG_MALFORMED_HEADER`, `invalidLineNumber=5` |
| T3.2.9 | Recursive scan finds all `.txt` | F01/`songs_root/` | All entries discovered, validity matches `expected.discovery.json` |

**T3.3 — Index Fields**

| ID | What | Expected |
|----|------|---------|
| T3.3.1 | `isDuet` detected from P1/P2 in body | `isDuet=true` |
| T3.3.2 | `hasRap` detected from R/G notes | `hasRap=true` |
| T3.3.3 | `canMedley=false` for duet songs | `canMedley=false` |
| T3.3.4 | `canMedley=true` via medley tags | `canMedley=true`, `medleySource="tag"` |
| T3.3.5 | `canMedley=false` when no medley tags | `canMedley=false`, `medleySource=null` |

### Acceptance Criteria

- F01, F23 pass

### Knowledge Gaps

None.

---

## 2.6 UI Layer

**Responsibility**: All Compose screens. Owns the `LibVlcPlayerHandle` (the single seam to the LibVLC `MediaPlayer`; see §2.6.1 Public API — Playback Backend Seam) for playback. Observes state from other components. Emits user intents and playback events.

**Lifecycle**: Standard Android Activity/Compose lifecycle.

### UI Overview

Use this section as the primary home for UI behavior and screen-level requirements:
- entry point, theme, navigation, and DI wiring: **Entry Point and Wiring** (below)
- API/render contracts and ownership boundaries: **2.6.1–2.6.4**
- shared visual foundations: **2.6.5 Design Tokens and Visual System** and **2.6.11 Interruption Overlay Shell**
- singing-specific playback and rendering: **2.6.6–2.6.10**
- browse, pairing, and setup flows: **2.6.12–2.6.15**
- in-song and results behavior: **2.6.16–2.6.18**
- UI verification and completion criteria: **2.6.19–2.6.22**

Use [§3.1](#31-data-flow-diagrams) and [§3.2](#32-interaction-contracts) for end-to-end flow context; screen behavior remains owned here.

### Entry Point and Wiring (Normative)

**Entry point**: `MainActivity` is the single Android Activity. `setContent {}` is the only call site for theme and navigation host instantiation.

```kotlin
@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            CouchraokeTheme {
                AppNavHost()
            }
        }
    }
}
```

**Theme**: `CouchraokeTheme` is a thin Compose function in `ui/theme/CouchraokeTheme.kt` that applies the §2.6.5 design tokens as a `MaterialTheme` color scheme and typography. It is called exactly once, at the `setContent {}` root. No other file in the codebase applies theme overrides or creates a nested `MaterialTheme`.

**Navigation**: `AppNavHost` uses `androidx.navigation:navigation-compose`. Routes are a sealed type:

```kotlin
sealed class Screen(val route: String) {
    object SongList      : Screen("song_list")
    object SelectPlayers : Screen("select_players")
    object Singing       : Screen("singing")
    object Results       : Screen("results")
    object Settings      : Screen("settings")
    // settings sub-screens as nested objects, e.g. Screen.Settings.ConnectPhones
}
```

`NavHost` manages the back stack. Back handling uses the default `BackHandler` provided by `navigation-compose` — no custom stack management. The back rules in [§2.6.9](#269-global-navigation-and-input) are implemented as `navController.navigate()` and `navController.popBackStack()` calls in each screen composable's DPAD Back handler. `SelectPlayersModal` and `JoinOverlay` are modal composables shown within `SongListScreen`, not separate `NavHost` destinations.

**Dependency injection**: Hilt. `Application` is annotated `@HiltAndroidApp`; `MainActivity` is annotated `@AndroidEntryPoint`. All six top-level components (`PlaybackCoordinator`, `ScoringEngine`, `NetworkController`, `UsdxParser`, `LibraryManager`, and the `LibVLC` instance) are provided as `@Singleton` from a Hilt `@Module`. No component is instantiated directly in screen or ViewModel code.

**ViewModels**: per-screen, scoped to the `NavBackStackEntry`, obtained via `hiltViewModel()`. Each ViewModel receives only the components its screen needs — e.g. `SingingViewModel` receives `PlaybackCoordinator` and `ScoringEngine`; `SongListViewModel` receives `LibraryManager` and `NetworkController`. There is no top-level `AppViewModel`; the domain components are the app-level state owners.

**Library versions** (normative; also pin in constitution):

| Artifact | Version |
|---|---|
| `androidx.navigation:navigation-compose` | `2.8.x` |
| `com.google.dagger:hilt-android` | `2.51.x` |
| `androidx.hilt:hilt-navigation-compose` | `1.2.x` |

### 2.6.1 Public API (Exposed to System)

```kotlin
// Provided by SingingScreen ViewModel
interface PlaybackObservable {
    val currentPositionMs: StateFlow<Long>
    val isPlaying: StateFlow<Boolean>
    val playbackEvents: SharedFlow<PlaybackEvent>
}

sealed class PlaybackEvent {
    data class Prepared(val effectivePlaybackDurationMs: Long) : PlaybackEvent()
    data class Ready(val songStartTvMs: Long) : PlaybackEvent()
    data class Error(val cause: Throwable) : PlaybackEvent()
    object Ended : PlaybackEvent()
}

// Commands from PlaybackCoordinator (via state/intents)
sealed class PlaybackIntent {
    data class Prepare(
        val audioUrl: String,
        val videoUrl: String?,
        val videoGapSec: Float?,      // #VIDEOGAP in seconds; null treated as 0
        val seekToSec: Float
    ) : PlaybackIntent()
    object Play : PlaybackIntent()
    object Pause : PlaybackIntent()
    object Stop : PlaybackIntent()
    data class Seek(val positionMs: Long) : PlaybackIntent()
    data class PrebufferNext(
        val audioUrl: String,
        val videoUrl: String? = null,
        val videoGapSec: Float? = null,
        val seekToSec: Float
    ) : PlaybackIntent()
    data class FadeOut(val durationSec: Float) : PlaybackIntent()   // Fade out current segment and stop
    data class Crossfade(val fadeOutSec: Float, val fadeInSec: Float) : PlaybackIntent()
}

// ─── Playback Backend Seam (normative) ────────────────────────────────
// The UI layer is the ONLY component that imports `org.videolan.libvlc.*`.
// All other components (PlaybackCoordinator, ScoringEngine, tests) interact
// with playback exclusively through the `LibVlcPlayerHandle` interface and
// the `LibVlcEvent` sealed class defined below.
//
// This seam exists so that:
//   1. Production code can be unit-tested without instantiating a real
//      `org.videolan.libvlc.MediaPlayer` (whose `Event` constructors are
//      package-private and cannot be invoked from test code).
//   2. The playback backend can be swapped (e.g., back to Media3, or to a
//      future LibVLC 4.x) by replacing the adapter implementation alone.

interface LibVlcPlayerHandle {
    /** Translated, main-thread-dispatched event stream. */
    val events: SharedFlow<LibVlcEvent>

    /** Current playhead position in ms. Reads `mediaPlayer.time` directly. */
    val timeMs: Long

    fun prepare(audioUrl: String, videoUrl: String?, seekToSec: Float)
    fun play()
    fun pause()
    fun stop()
    fun seekTo(positionMs: Long)
    fun setAudioDelay(micros: Long)         // for #VIDEOGAP — see Playback Backend Configuration
    fun setVolume(percent: Int)             // 0..100
    fun release()
}

sealed class LibVlcEvent {
    object Playing : LibVlcEvent()
    object Paused : LibVlcEvent()
    object EndReached : LibVlcEvent()
    data class TimeChanged(val timeMs: Long) : LibVlcEvent()
    data class EncounteredError(val lastLogLine: String?) : LibVlcEvent()
}

// The adapter implementation (production) wraps `org.videolan.libvlc.MediaPlayer`,
// translates raw `MediaPlayer.Event` values into `LibVlcEvent`, and dispatches
// onto the UI ViewModel's main scope. Tests use a fake implementation that
// emits `LibVlcEvent` values directly with no libvlc dependency.

// Chart-derived render contract for SingingScreen.
// Built before countdown or active singing begins.
data class SingingRenderModel(
    val lyrics: LyricsRenderModel,
    val lanes: List<LaneStaticModel>,
    val horizontalMapping: HorizontalTimeMapping,
    val verticalMappings: Map<PlayerId, VerticalPitchMapping>
)

data class LyricsRenderModel(
    val lines: List<LyricLineRenderModel>
)

data class LyricLineRenderModel(
    val playerId: PlayerId?,
    val lineIndex: Int,
    val startTimeMs: Long,
    val endTimeMs: Long,
    val syllables: List<LyricSyllableRenderModel>
)

data class LyricSyllableRenderModel(
    val text: String,
    val startTimeMs: Long,
    val endTimeMs: Long
)

data class LaneStaticModel(
    val playerId: PlayerId,
    val notes: List<NoteRenderSegment>,
    val instrumentalGaps: List<TimeRangeMs>
)

data class NoteRenderSegment(
    val startTimeMs: Long,
    val endTimeMs: Long,
    val toneSemitone: Int,
    val noteType: NoteType
)

data class TimeRangeMs(
    val startTimeMs: Long,
    val endTimeMs: Long
)

data class HorizontalTimeMapping(
    val visibleTimeMs: Long,
    val nowAnchorFraction: Float
)

data class VerticalPitchMapping(
    val minToneSemitone: Int,
    val maxToneSemitone: Int
)
```

**Render-model contract (normative)**:
- `SingingRenderModel` is the authoritative chart-derived render contract for SingingScreen.
- SingingScreen MUST receive `SingingRenderModel` before entering countdown or active singing.
- `ParsedSong` MAY be used internally to build `SingingRenderModel`, but `ParsedSong` is not the required UI boundary.
- `Difficulty` affects scoring tolerance only. It MUST NOT change lane layout height or the lane coordinate-system bounds.
- All horizontal positions in `SingingRenderModel` are expressed in lyrics-time milliseconds.
- For a normal song, render times are song-local lyrics-time values.
- For medley, render times MUST be expressed on one continuous medley-local lyrics-time axis before delivery to SingingScreen. The renderer MUST NOT stitch together per-segment timelines itself.
- `VerticalPitchMapping` is derived from the player's scorable notes only; notes for the other player MUST NOT affect that player's Y-scale.
- For medley, `VerticalPitchMapping` MUST be fixed for the full run using the union of that player's scorable notes across all medley segments.

### 2.6.2 NFRs Applied

- **Testability**: ViewModels testable with fake data sources
- **Minimal Footprint**: Flat rendering, no shaders, pre-baked effects

### 2.6.3 SLAs

| Metric | Target | Test |
|--------|--------|------|
| Singing screen FPS | ≥30 sustained | GPU profiler on target device |
| Song grid scroll FPS | ≥60 at 1080p | Manual + profiler |
| Memory (UI heap) | <100MB | Heap dump during singing |

### 2.6.4 L2 Visible Shapes

- **SongListScreen**: Grid, preview, medley playlist, search
- **SingingScreen**: Lyrics, pitch lane, score overlay, LibVLC `SurfaceView` (via `LibVlcPlayerHandle`)
- **ResultsScreen**: Final scores, per-segment breakdown for medley
- **SettingsScreen**: Connect Phones, Song Library, Audio, Scoring Timing, Gameplay, Video (see SettingsScreen Behavior below)
- **SelectPlayersModal**: Player assignment, difficulty selection
- **PitchLaneRenderer**: SurfaceView-based, 30fps render loop (see below)

### 2.6.5 Design Tokens and Visual System

This subsection defines the cross-cutting visual system for the TV app. Screen subsections below reference these tokens instead of inline values. The rendering constraints here extend — and do not relax — the hardware constraints in [§1.6](#16-minimal-footprint).

#### 2.6.5.1 Design intent

Dark concert-like presentation with competitive karaoke HUD structure. Visual priorities, in order:

1. gameplay readability during singing
2. stable remote navigation and focus clarity
3. song recognition from the browse grid
4. restrained motion that does not compete with scoring, playback, or video decode

The singing screen is designed for video backgrounds as the default case. Overlay surfaces over moving footage MUST remain fully readable.

#### 2.6.5.2 Performance hierarchy

Any treatment that risks singing stability, preview responsiveness, or focus reliability is not permitted, regardless of visual merit. Order of precedence:

1. gameplay correctness and smoothness
2. readability and input response
3. decorative motion

#### 2.6.5.3 Allowed rendering style

The app uses **flat rendering only**. The following treatments are forbidden across all screens:

- runtime blur
- bloom
- glow
- frosted glass
- shader-heavy full-screen effects
- particle systems during gameplay
- background animation that repaints large parts of the screen during active singing

This rule extends the Mali-G31 constraint in [§1.6](#16-minimal-footprint) from "no post-processing" to "no decorative GPU effects anywhere, anytime."

#### 2.6.5.4 Spacing, radius, border, layout tokens

| Token | Value | Notes |
|---|---:|---|
| Space8 | 8dp |  |
| Space12 | 12dp |  |
| Space16 | 16dp |  |
| Space24 | 24dp |  |
| Space32 | 32dp |  |
| Space48 | 48dp |  |
| RadiusSmall | 8dp |  |
| RadiusMedium | 12dp |  |
| RadiusLarge | 16dp |  |
| BorderThin | 1dp |  |
| FocusBorderWidth | 3dp |  |
| FocusBorderInset | 2dp |  |
| UnfocusedBorderOpacity | 20% |  |
| FocusInDuration | 150ms | fade-in on focus arrival |
| FocusOutDuration | 100ms | fade-out on focus departure |
| AppMarginHorizontal | 48dp |  |
| AppMarginVertical | 36dp |  |
| HeaderHeight | 76dp |  |
| StandardButtonHeight | 72dp |  |
| StandardRowHeight | 76dp |  |
| DenseRowHeight | 56dp |  |
| PrimaryModalWidth | 960dp |  |
| PrimaryModalPadding | 32dp |  |
| QRCodeSize | 400dp | pinned (supersedes earlier 320–420dp range) |

#### 2.6.5.5 Typography

Two faces only:
- **Display face**: decorative squared face. Used for hero numerals and hero titles only. Not used for body or UI chrome.
- **Operational sans**: high-legibility sans-serif used for all other text (readability at TV viewing distance is the primary constraint).

**Display face tokens**

| Token | Value |
|---|---:|
| DisplayHeroNumber | 160sp |
| DisplayHeroTitle | 56sp |
| DisplayAccentTitle | 44sp |

**Operational sans tokens**

| Token | Value |
|---|---:|
| ScreenTitle | 40sp |
| SectionTitle | 32sp |
| PanelTitle | 28sp |
| SongCardTitle | 24sp |
| SongCardArtistFocused | 18sp |
| PreviewTitle | 32sp |
| PreviewArtist | 24sp |
| TagChipLabel | 16sp |
| BodyPrimary | 24sp |
| BodySecondary | 20sp |
| ButtonLabel | 22sp |
| FieldLabel | 20sp |
| Caption | 18sp |
| LyricsCurrent | 40sp |
| LyricsNext | 32sp |
| LiveScore | 56sp |
| SentenceRating | 28sp |
| TopMetadataMinimal | 20sp |
| SingerBadge | 22sp |
| Timer | 24sp |
| ResultBreakdownLabel | 22sp |
| ResultBreakdownValue | 28sp |
| ResultTotalValue | 64sp |
| MedleyRowText | 22sp |
| MedleyTotalValue | 48sp |

#### 2.6.5.6 Color and surface system

Semantic color roles (concrete hex values are deferred to theme assets; roles are normative):

| Role | Use |
|---|---|
| AppBackground | darkest cool graphite base |
| SurfacePrimary | standard dark surface |
| SurfaceElevated | elevated modal and overlay surface |
| SurfaceLaneBand | dark translucent graphite lane plate |
| SurfaceLyricsBand | darkest overlay plate on singing screen |
| BorderSubtle | unfocused structure border |
| BorderFocus | focused border |
| TextPrimary | highest-priority text |
| TextSecondary | secondary metadata |
| TextDisabled | disabled state |
| Player1Accent | cyan |
| Player2Accent | magenta |
| RewardAccent | gold |
| Success | success state |
| Warning | warning state |
| Error | error state |

Usage rules (normative):
- Player identity uses `Player1Accent` (cyan) for P1 and `Player2Accent` (magenta) for P2.
- `RewardAccent` (gold) is reserved for reward treatment only (see [ResultsScreen Behavior](#2618-resultsscreen-behavior)). It MUST NOT be used for focus, for `Start`, for general buttons, or for Medley Total.
- Focus uses `BorderFocus` — not cyan, magenta, or gold.
- Lane bodies remain neutral (`SurfaceLaneBand`). Player color appears in accents only, never as a full-lane tint.

Surface levels:

| Token | Use | Alpha |
|---|---|---:|
| SurfaceLevel0 | app background | — |
| SurfaceLevel1 | standard cards, rows, panels | — |
| SurfaceLevel2 | modal, pause, disconnect, error, and similar interruption surfaces | — |
| LaneBandAlpha | lane band over video/background | 68% |
| LyricsBandAlpha | lyrics band over video/background | 82% |

#### 2.6.5.7 Scale tiers

Typography tokens are grouped into three scale tiers; screen subsections below indicate which tier to use.

- **Oversized tier** — singing, countdown, interruption states, hero result values.
- **Balanced tier** — Select Players, Join/QR, Settings, song list preview metadata.
- **Compact-balanced tier** — song list grid cards only.

#### 2.6.5.8 Motion and VFX budget

**Motion language:**
- Short directional motion for structural transitions.
- Fades for overlays and interruption states.
- No looping decorative motion as a default screen treatment.
- During active singing, layout MUST NOT animate except where the product state already changes layout (e.g., single→dual lane state change is a mode change, not an animation).

**VFX budget scale:**

| Level | Meaning |
|---|---|
| V0 | static only |
| V1 | one local motion zone |
| V2 | one hero motion or two local motions |
| V3 | not allowed |

**Per-screen budgets (normative):**

| Screen / state | Budget | Allowed pattern |
|---|---|---|
| Song List, settled | V2 | local polish only |
| Song List, active navigation | V1 | focus and state motion only |
| Join / QR overlay | V1 | modal entrance, then static |
| Select Players | V1 | focus and short row transitions |
| Settings | V2 | local control motion only |
| Loading / pre-song setup | V0 | static poster or simple progress only |
| Countdown | V2 | one hero number animation |
| Singing | V0 | functional motion only (see [SingingScreen Behavior](#2616-singingscreen-behavior) motion budget) |
| Pause / Disconnect / Error overlay | V1 | modal entrance and focus only |
| Medley segment transition | V0 | text swap only |
| Single-song Results | V2 | one entry payoff, then static |
| Medley Results | V1 | calm table reveal, then static |

#### 2.6.5.9 Component definitions

**Button variants** — selected per surface role:

| Variant | Use |
|---|---|
| Primary | local main action for the current surface |
| Secondary | peer action with lower emphasis |
| Quiet | utility action |
| Destructive | quit, delete, end-session, or similar |

**Tag chips** (Song List cards):

| Chip | Meaning |
|---|---|
| D | duet |
| M | medley |
| R | rap |
| I | instrumental |
| V | video |

**Player accent usage** — `Player1Accent` / `Player2Accent` are used on:
- singer badge
- score box accents
- lane markers and cursor accents
- focused identity cues where player ownership matters

Player accent color MUST NOT be used for: generic focus border, general app chrome, default button system.

#### 2.6.5.10 Design conformance acceptance

A build conforms to this design system when:

1. all typography uses the token values above
2. all sizes use fixed dp/sp values or explicit proportions defined in this spec
3. song list preserves block placement while applying card, rail, and action rules below
4. singing uses the fixed one-lane or two-lane states defined below
5. lyrics remain bottom-banded and two-line only
6. Medley Total uses the Medley table treatment below (no gold, no display face)
7. no prohibited glow, blur, bloom, or particle effects appear
8. no gameplay-adjacent decorative effect can interfere with singing smoothness

### 2.6.6 Pitch Lane Rendering Architecture

Singing screen MUST separate real-time pitch lane rendering from Compose UI:

| Layer | Content | Technology |
|-------|---------|------------|
| Background | Pitch lane (note targets, pitch cursor, hit/miss, instrumental gap) | `SurfaceView` with dedicated render thread @30fps |
| Foreground | Score counters, lyrics, rating labels, countdown, pause overlay | Compose overlay on top of SurfaceView |

**Compose / SurfaceView separation (normative)**: the singing screen MAY use Jetpack Compose for non-real-time screen structure only. Real-time lane rendering MUST follow the `SurfaceView` architecture; Compose MUST NOT own pitch-lane frame rendering.

**Implementation Requirements**:
- Render thread decoupled from Compose recomposition.
- Drawing logic as pure function: `drawPitchLane(canvas: Canvas, viewport: Rect, state: LaneRenderState)` where `LaneRenderState` is immutable.
- No references to Views, Contexts, or lifecycle-scoped objects in drawing function.
- Enables JVM-based screenshot testing via `Bitmap`-backed `Canvas` in Robolectric `@GraphicsMode(Mode.NATIVE)`.

**Renderer contract (normative)**:
- `LaneRenderState` is the frame-by-frame dynamic state consumed by `drawPitchLane(...)`.
- `LaneRenderState` MUST be derived from:
  1. the immutable `SingingRenderModel`
  2. current lane time in lyrics-time ms
  3. current live pitch for the player
  4. transient in-lane feedback state if shown
- `LaneRenderState` MUST NOT require direct access to `ParsedSong`.
- For medley, `SingingRenderModel` MUST already contain the chart-derived data for all medley segments needed by SingingScreen before countdown begins.

**Performance Guidelines**:
- Each singer lane as single drawing surface (not one UI element per note).
- Reuse cached geometry/primitives across frames.
- No per-frame object allocation in lane rendering.
- Static dark panel or gradient for readability overlays (no runtime blur).
- Flat rectangular shapes for pitch targets (no live glow/shadow).

### 2.6.7 #INSTRUMENTAL / #VOCALS Playback

The TV always plays a single pre-mixed `audioUrl` per song. The phone is responsible for mixing `#INSTRUMENTAL` and `#VOCALS` tracks before serving; the TV MUST NOT attempt dual-track mixing.

- `hasInstrumental == true` affects only the `I` chip display in the song list (§2.5). It has no effect on TV playback logic.
- **Settings > Audio > Vocals Volume** (default 50%): this control is reserved for a future release in which the phone exposes a mix-parameter endpoint. For MVP it MUST be rendered as a disabled slider with a "Coming soon" label.
- Before countdown or live playback begins, the UI MUST emit `PlaybackEvent.Prepared(effectivePlaybackDurationMs)` equal to the duration of the prepared `audioUrl`.

### 2.6.8 Instrumental Gap Indicator

An **instrumental gap** is a region of the chart where no scorable note (Normal, Golden, Rap, RapGolden) is active for the current player's track for more than **2 continuous seconds**.

During such a region, the pitch lane for that player MUST display a visible rest indicator (e.g., a horizontal dashed line or small wave graphic) rendered as part of lane gameplay drawing. This indicator:
- Is purely **visual** — it has no effect on audio track selection or scoring.
- Is **local** — it occupies the lane area the rest indicator needs, not the full lane band. A full-lane pulse is forbidden per the singing motion budget ([SingingScreen Behavior](#2616-singingscreen-behavior)).
- MAY use subtle opacity motion on itself only. MUST NOT trigger animation of the surrounding lane band, lyrics region, or score.
- MUST disappear as soon as the next scorable note approaches within the highlight window.

The `PitchLaneRenderer` owns this indicator; it is driven by the note schedule from `ParsedSong` and counts as "note lane rendering already required by gameplay" under the singing motion budget.

### 2.6.9 Global Navigation and Input

Primary input is TV remote (DPAD + OK/Enter + Back).

**Navigation model**: simple navigation stack. Entering a full-screen screen pushes it; Back pops and returns to previous. Overlays/modals do not affect the stack; Back closes them.

**Back behavior**:
- From Song List: if filter active, clear filter; otherwise exit app.
- From Settings (root): return to previous screen (Song List or Select Players depending on entry context).
- From Settings sub-screens: return to Settings root.
- From modal dialogs/overlays: close overlay, return to underlying screen.
- From Singing: open Pause overlay (Resume / Restart Song / Quit to Song List).
- From Results: return to Song List.
- **Special case**: Settings entered from Select Players "No phones connected" action — Back on Settings root returns to Select Players modal, not Song List.

**Focus indicator (normative)**:
- Focused element: draw a `FocusBorderWidth` (3dp) solid border in `BorderFocus`, inset `FocusBorderInset` (2dp) from the component edge, plus a subtle filled plate on the component body for additional contrast against video/background content.
- Unfocused enabled element: draw a `BorderThin` (1dp) border using `BorderSubtle` at `UnfocusedBorderOpacity` (20%) so grid/list structure remains legible at TV distance.
- Border corner radius MUST follow the component shape (buttons and cards use `RadiusSmall`–`RadiusMedium` rounded, square-edged fields may use 0dp).
- Focus MUST be border-plus-plate only; do not add focus shadows, blur, elevation changes, glow, or background pulse.
- Focus MUST NOT use `Player1Accent`, `Player2Accent`, or `RewardAccent`.
- Disabled elements MUST NOT be focusable.

**Focus animation (optional)**:
- If the target hardware sustains it without visible frame drops, focus arrival MAY fade in over `FocusInDuration` (150ms ease-out) and departure MAY fade out over `FocusOutDuration` (100ms ease-out).
- If focus animation causes jank on target devices, implementations MUST fall back to an instant state change.
- Forbidden focus treatments: scale transforms, blur, background pulse, and dynamic drop shadows.

**Long-press OK**: press-and-hold of OK/Enter for >= 500ms triggers secondary action where defined; otherwise behaves as normal OK.

### 2.6.10 Song Preview Playback

**When preview plays**:
- Song tile is focused AND focus remains on same song for **500ms** (debounce) AND Preview Volume is non-zero.

**Preview stops immediately when**:
- Focus moves to a different song tile, leaves grid, or overlay/modal/settings/singing opens.

**What plays**:
- Uses `audioUrl` from cached manifest, seeks to `previewStartSec`.
- If `previewStartSec > 0.0`, use it; otherwise fallback: `pos = audioLengthSec / 4` (clamped to 60s if > 120s).
- Plays from start position until stopped (no fixed 10s limit).
- Uses Settings > Audio > Preview Volume. Value of 0 disables preview.
- If `audioUrl` is null or HTTP fails, suppress silently.

**Media player lifetime (normative)**:
- Media players are screen-scoped.
- A preview player belongs only to SongListScreen and MUST be torn down when SongListScreen exits.
- Any media player created for SingingScreen, including medley transition players, MUST be torn down when SingingScreen exits.
- During medley transition, the currently active player remains authoritative until the replacement player emits `PlaybackEvent.Ready`; any replacement-plan duration needed for fallback stop computation MUST already have been reported via `PlaybackEvent.Prepared` before authority transfers. Once authority transfers, the old player MUST be torn down.

### 2.6.11 Interruption Overlay Shell

Pause, Disconnect auto-pause, Restart/Quit confirm dialogs, the Countdown-disconnect modal, the Start-failure / Playback error modal, the Song-Library refresh errors, the Select-Players "No phones connected" state, and any similar interruption surfaces all reuse the same centered elevated shell.

**Shell tokens:**

| Token | Value |
|---|---:|
| InterruptionModalWidth | 960dp |
| InterruptionModalTitleBottomGap | 16dp |
| InterruptionModalBodyBottomGap | 24dp |
| InterruptionActionRowHeight | 72dp |

**Visual rules (normative)**:
- Use `SurfaceLevel2` with `PrimaryModalPadding` (32dp).
- Dim the underlying scene with a dark scrim. MUST NOT use runtime blur on the frozen background.
- Operational sans only. Balanced tier typography.
- No large entrance sequences, no cinematic wipes.

**Motion (V1 budget)**:
- One short modal entrance: fade or scale-fade of the modal shell only.
- Focus movement happens only after entry completes.
- When a reconnect is in progress on the Disconnect auto-pause overlay, a single small reconnect spinner MAY be rendered on that modal; other interruption overlays MUST NOT add spinners.

**Default focus**: each overlay specifies its own default focus target (see per-overlay rules under [SingingScreen Behavior](#2616-singingscreen-behavior) and related sections). In general, destructive or irreversible actions (Restart, Quit, Kick) default focus on Cancel.

#### Browse, Pairing, and Setup Flows

### 2.6.12 SongListScreen Behavior

**Purpose**: always the landing screen. Displays songs sorted by Artist → Album → Title. Maintains a transient Medley playlist (initialized empty each time shown, cleared on leaving for non-modal screen).

**Layout**: two-column. Left rail: preview pane (16:9, display-only, non-focusable), Medley playlist, Play Medley. Right body: Search field, Random actions row (Random Song / Random Duet / Random Medley), song grid. Screen uses `AppMarginHorizontal` / `AppMarginVertical` margins.

**Layout proportions and tokens:**

| Token | Value |
|---|---:|
| SongListLeftRailFraction | 0.34 |
| SongListGridFraction | 0.66 |
| SongListRailGridGap | 32dp |
| SongListHeaderToBodyGap | 24dp |
| SongListRandomRowHeight | 72dp |
| SongListRandomRowGap | 24dp |
| SongListGridColumns1080 | 3 |
| SongListGridColumns4K | 4 |
| SongListGridColumnGap | 24dp |
| SongListGridRowGap | 24dp |
| SongListPreviewAspect | 16:9 |
| SongListPreviewToMetaGap | 16dp |
| SongListMetaToPlaylistGap | 24dp |
| SongListPlaylistRowHeight | 52dp |
| SongListPlaylistVisibleRows | 5 |
| SongListPlayMedleyTopGap | 16dp |

**Header composition:**
- Contents: Search field, Join button, Settings button. Header uses `HeaderHeight` (76dp), operational sans only.
- Emphasis: Search is the visually strongest control. Join and Settings are equal secondary controls.

**Tier:** preview metadata uses balanced tier (`PreviewTitle`, `PreviewArtist`). Grid cards use compact-balanced tier (see card rules below).

**Empty states**:
- No phones connected: `No phones connected.` / `Connect a phone to see songs. Open the karaoke app on your phone and scan the QR code.`
- Phones connected but no valid songs: `No songs found.` / `Open the karaoke app on your phone and make sure the songs folder is set.`

**Search**: case-insensitive substring match across {artist, album, title}. Debounce 150ms. OK on Search field opens Android TV system text input dialog.

**Primary actions**: OK on song tile → Select Players. Long-press OK → Add to Medley (if `canMedley=false`, show blocking modal with exact text: `This song can't be used in a medley. Look for songs with an M tag in the lower right corner`).

**Random actions row:**
- Contents: Random Song, Random Duet, Random Medley. All three use equal visual weight (equal sizing, equal emphasis). Row uses `SongListRandomRowHeight`.
- Sing Random Song: random valid song from filtered set → Select Players.
- Sing Random Duet: random valid duet from filtered set → Select Players.
- Sing Random Medley: 5 random valid medley songs (all if < 5; needs ≥ 2 to be active) → Select Players.
- Disabled when no eligible songs exist.
- **Random Medley lives in this row, not in the left rail.**

**Left rail:**
- Preview pane uses `SongListPreviewAspect` (16:9), is display-only and non-focusable.
- Focused-song preview metadata always shows full title (`PreviewTitle`) and artist (`PreviewArtist`) — no truncation of the preview metadata block.
- Medley playlist occupies the lower half of the rail with `SongListPlaylistVisibleRows` (5) visible rows at `SongListPlaylistRowHeight` (52dp). Rows: `<Artist>  <Title>` in operational sans.
- `Play Medley` sits directly below the playlist at `SongListPlayMedleyTopGap`.
- OK on a playlist row → Reorder mode (Up/Down moves, OK confirms, Back cancels). Long-press OK on row → delete immediately.

**Song grid:** `SongListGridColumns1080` (3) at 1080p, `SongListGridColumns4K` (4) at 4K. Column count fixed per resolution. Gaps use `SongListGridColumnGap` / `SongListGridRowGap`.

**Song cards (normative):** image-led composition with fixed metadata behavior.

| Token | Value |
|---|---:|
| SongCardHeight | 252dp |
| SongCardPadding | 12dp |
| SongCardImageHeight | 148dp |
| SongCardImageCornerRadius | 8dp |
| SongCardTitleMaxLines | 2 |
| SongCardFocusedArtistSlotHeight | 20dp |
| SongCardTitleToArtistGap | 4dp |
| SongCardTagCornerInset | 8dp |
| SongCardTagGap | 6dp |
| SongCardMaxVisibleTags | 3 |

Card content rules:
- **Default (unfocused) state** shows: cover image, title (`SongCardTitle`, up to 2 lines), up to 3 tag chips.
- **Focused state** additionally shows: one artist line in the reserved artist slot (`SongCardArtistFocused`).
- The artist slot is always reserved (`SongCardFocusedArtistSlotHeight`); revealing the artist on focus MUST NOT reflow the card.
- **Weak-artwork fallback:** if a card's cover is missing, placeholder, or unusable, keep title primary, keep tag chips visible, and show the artist in the default state for that card.

Tag placement and priority:
- Tag chips are rendered **on-image, in the lower-right corner** of the cover image, inset by `SongCardTagCornerInset` with `SongCardTagGap` between chips. Chip label uses `TagChipLabel`.
- Maximum visible chips: `SongCardMaxVisibleTags` (3).
- Priority order when more than three apply: `D`, `M`, `R`, `I`, `V`. `V` is always the first chip omitted.

**Initial focus**: first grid tile (top-left); if empty, Search field.

**DPAD navigation** (normative):

| Current focus | DPAD Up | DPAD Down | DPAD Left | DPAD Right |
|---|---|---|---|---|
| Search field | — | First grid tile | Join button | Settings button |
| Grid tile (top row) | Search field | Tile below | Left tile, or left panel entry | Right tile |
| Grid tile (non-top row) | Tile above | Tile below | Left tile, or left panel entry | Right tile |
| Medley playlist row | Previous row (or Play Medley) | Next row (or Random Medley) | — | Search field |
| Play Medley | Last playlist row | Random Medley | — | Search field |

**Left-panel entry target** (from leftmost grid column): 1) first Medley playlist row if present, 2) Play Medley if empty, 3) Random Medley as fallback.

**Back from grid/left panel**: move focus to Search field. Back from top controls: clear filter if active; else exit app.

**Motion and focus behavior on Song List:**
- Settled state (V2): local preview crossfade and restrained chip or border fade.
- Active navigation (V1): focus transition only.
- No per-card ambient animation.
- No animated background behind the grid.
- No card scale on focus (card stays at fixed `SongCardHeight`; focus is border + plate only).

**Join button**: opens the Join and QR overlay — see [Join Overlay Behavior](#2613-join-overlay-behavior) for visual and interaction rules.

**QR payload (normative)**: The QR code MUST encode the full WebSocket endpoint URL including the `token` query parameter (e.g., `ws://192.168.1.10:8080/?token=ABCDEFGH`). It MUST NOT encode an NSD/mDNS service-discovery identifier. Phones that scan the QR code connect directly to the encoded URL without any additional discovery step.

#### Song List Wireframe

Song Grid: 4 cards / row at 4K, 3 at 1080p. Cover art fills top of card; title sits below; tag chips overlay the cover in the lower-right corner; artist only appears under the title on the focused card.

```wireframe
+------------------------------------------------------------------------------------------------------+
|  Search: [________________________________________________________]     [ JOIN ]   [ ⚙ SETTINGS ]   |
|                                                                                                      |
|  +--------------------------------------+   [ Random Song ] [ Random Duet ] [ Random Medley ]       |
|  | PREVIEW PANE (16:9)                  |                                                           |
|  | (display-only; non-focusable)        |   +-----------------------------------------------------+ |
|  |                                      |   | SONG GRID                                           | |
|  +--------------------------------------+   |  +---------+  +---------+  +---------+              | |
|  | Title                                |   |  | Cover   |  | Cover   |  | Cover   |   (focused)  | |
|  | Artist                               |   |  |     [D] |  |   [R][V]|  |  [D][M] |              | |
|  +--------------------------------------+   |  +---------+  +---------+  +---------+              | |
|  | MEDLEY PLAYLIST                      |   |  Title        Title        Title                    | |
|  | (5 visible rows; scrolls)            |   |  Artist                                             | |
|  |  +-------------------------------+   |   |  (only focused card shows artist line)              | |
|  |  | <artist>  <song>              |   |   |                                                     | |
|  |  | <artist>  <song>              |   |   |  +---------+  +---------+  +---------+              | |
|  |  | <artist>  <song>              |   |   |  | Cover   |  | Cover   |  | Cover   |              | |
|  |  | <artist>  <song>              |   |   |  |     [V] |  |     [I] |  |   [D][M]|              | |
|  |  | <artist>  <song>              |   |   |  +---------+  +---------+  +---------+              | |
|  |  +-------------------------------+   |   |  Title        Title        Title                    | |
|  |  [Play Medley]                   |   |   |                                                     | |
|  +--------------------------------------+   |  Tags: D=Duet  M=Medley  R=Rap  I=Instr  V=Video    | |
|                                              +-----------------------------------------------------+ |
+------------------------------------------------------------------------------------------------------+
|                     Hints: OK=Select   Long OK=Add Medley   Back=Search/Exit                         |
+------------------------------------------------------------------------------------------------------+
```

### 2.6.13 Join Overlay Behavior

**Purpose**: show the QR code and short join code so a phone can connect to the session. Opened from the Song List header's Join button. Also reachable from *Settings > Connect Phones* but that sub-screen is a superset; this overlay is the lightweight join surface.

**Presentation**: modal over Song List. Uses `SurfaceLevel2` shell at `PrimaryModalWidth` (960dp) with `PrimaryModalPadding` (32dp). Balanced tier typography, operational sans only.

| Token | Value |
|---|---:|
| JoinPanelWidth | 960dp |
| JoinQRCodeSize | 400dp |
| JoinCodeTopGap | 16dp |
| JoinConnectedRowHeight | 56dp |

**Visual rules (normative)**:
- QR is the dominant object on the overlay. It uses `JoinQRCodeSize` (400dp), 4-module quiet zone, high-contrast dark-on-light, centered.
- The short join code sits directly below the QR at `JoinCodeTopGap` using `PanelTitle` or `DisplayAccentTitle` weight.
- The QR MUST remain static. No animation or overlay element may intrude into the QR or its quiet zone.
- Entrance animation is a single short fade or scale-fade of the modal shell only (V1 budget).

**Back behavior**: closes overlay, returns to Song List.

### 2.6.14 SelectPlayersModal Behavior

**Purpose**: handoff between song selection and singing. Select which phone(s) sing.

**Presentation**: modal overlay on `SurfaceLevel2`. Title: `SELECT PLAYERS`. Subtitle: `<Artist> — <Title>` (single-song) or `Medley — <n> songs` (medley).

**Layout tokens:**

| Token | Value |
|---|---:|
| SelectPlayersPanelWidth | 960dp |
| SelectPlayersSectionGap | 32dp |
| SelectPlayersFieldRowHeight | 76dp |
| SelectPlayersActionRowGap | 24dp |

**Visual rules (normative)**:
- Balanced tier typography. Operational sans only.
- `Start` is emphasized through placement (primary action position), size, and surface contrast — not color. `Start` MUST NOT use `RewardAccent` (gold is reserved for post-song winner treatment).
- Background posters or modal backdrops MUST NOT animate beyond the initial modal entrance (V1 budget).

**Fields**: Player 1 device (required, dropdown of connected phones), Player 2 device (may be disabled/hidden), Difficulty per player (Easy / Medium / Hard). Field rows use `SelectPlayersFieldRowHeight`.

**State-specific presentation:**
- **Non-duet**: Player 1 block is active and visually primary. Player 2 block remains visible but disabled.
- **Duet**: two player blocks remain symmetric. `Swap Parts` is secondary to `Start`.
- **Medley**: single-flow version only. No Player 2 section. Subtitle remains `Medley — <n> songs`.

**Gating rules**:
- **Duet**: P1 required, P2 optional. Two players → P1 sings track 1, P2 sings track 2; provide Swap Parts. One player → select which duet part.
- **Non-duet**: P1 required. P2 selector visible but disabled. P2 Difficulty hidden when P2 is `(none)`.
- **Medley**: P2 section hidden entirely (all medley songs are non-duet).

**Empty state**: no phones connected → blocking message `No phones connected` with action to open Settings > Connect Phones.

**Song start**: asset URLs from manifest. On Start, TV fetches `txtUrl` synchronously, parses, hands `audioUrl`/`videoUrl` to ExoPlayer. If `audioUrl` is null: error `Cannot load song — audio file is unavailable on the phone.`

**Medley render-model build (normative)**: for medley play, the coordinator MUST fetch and parse all segment `txtUrl` values required to build the full medley `SingingRenderModel` before countdown begins. This pre-start build MUST compute medley-wide vertical pitch bounds for each player from the union of that player's scorable notes across all medley segments.

**Medley prefetch (normative)**: fetching and parsing the full medley render model is required and blocks Start. Additional eager fetches beyond that are optional and MAY continue in the background once the medley playlist is confirmed.

**Start failure**: abort, return to Song List, show blocking error: title `ERROR`, body `This song can't be played.` / `Check Settings > Song Library — the song's phone may be disconnected.`, single `OK` action.

**Protocol side effects on Start**:
- TV sends `assignSinger` to each selected singer phone with `playerId`, `songInstanceSeq`, `startMode`, `countdownMs`, `udpPort`, `stopAtLyricsTimeMs`.
- Non-duet: P1 → `P1`. Duet with two players: P1 → `P1`, P2 → `P2` (swapped if Swap Parts). One player duet: `P1` or `P2` per selection.
- TV MUST NOT send `assignSinger` to non-selected devices.
- Medley: players remain assigned for entire run — no additional prompts between segments.
- **Countdown mapping**: if Ready countdown is ON, send `startMode="countdown"` and `countdownMs = countdownSeconds * 1000`. If OFF, send `startMode="live"` and omit `countdownMs`.
- **Quit early protocol**: when the user quits before or during a song, the TV MUST stop scoring and MUST transition phones out of singing by sending `sessionState.inSong=false`.
- `sessionState.inSong=false` is the authoritative session-level signal that phones MUST leave singing mode and clear active song UI/state, regardless of the last `playbackState` received.

#### Select Players Wireframes

```wireframe
Non-duet song
+--------------------------------------------------------------------------------+
| SELECT PLAYERS                                                   <Artist> — <Title> |
+--------------------------------------------------------------------------------+
| Player 1 (required)                                                             |
|  Phone:      [ Pixel-7 ▾ ]                                                      |
|  Difficulty: [ Medium ▾ ]                                                       |
+--------------------------------------------------------------------------------+
| Player 2                                                                        |
|  Phone:      [ (disabled) ]                                                     |
+--------------------------------------------------------------------------------+
| [Start]   [Cancel]                                                              |
+--------------------------------------------------------------------------------+
| Hints: OK=Select   Back=Cancel                                                  |
+--------------------------------------------------------------------------------+

Duet song
+--------------------------------------------------------------------------------+
| SELECT PLAYERS (DUET)                                           <Artist> — <Title> |
+--------------------------------------------------------------------------------+
| Player 1 (P1)                                Player 2 (P2)                      |
|  Phone: [ Pixel-7 ▾ ]                        Phone: [ (none) ▾ ] (optional)    |
|  Difficulty: [ Medium ▾ ]                    Difficulty: [ Medium ▾ ]          |
|                                                                                |
| If Player 2 is (none):  Solo duet part:  (• P1) (  P2)                         |
| If both players selected:  [Swap Parts]                                        |
+--------------------------------------------------------------------------------+
| [Start]   [Cancel]                                                              |
+--------------------------------------------------------------------------------+
| Hints: OK=Select   Back=Cancel                                                  |
+--------------------------------------------------------------------------------+

No phones connected
+--------------------------------------------------------------------------------+
| SELECT PLAYERS                                              <Artist> — <Title> |
+--------------------------------------------------------------------------------+
|                                                                                |
|   ⚠ No phones connected.                                                       |
|   Connect phones in Settings to sing.                                          |
|                                                                                |
| [Open Settings > Connect Phones]   [Cancel]                                    |
+--------------------------------------------------------------------------------+
```

### 2.6.15 SettingsScreen Behavior

Root Settings is a list routing to sub-screens: Connect Phones, Song Library, Audio, Scoring Timing, Gameplay, Video.

**Layout tokens:**

| Token | Value |
|---|---:|
| SettingsListWidth | 960dp |
| SettingsRowHeight | 76dp |
| SettingsRowGap | 8dp |
| SettingsSectionTopGap | 24dp |

**Visual rules (normative)**:
- Balanced tier typography. Operational sans only.
- Use broad, readable rows at `SettingsRowHeight` for DPAD reachability.
- Reuse the app-wide surface, focus, and spacing system. No screen-specific decorative treatments.

**Initial focus**: first settings row on entry.

**Root navigation (normative)**:
- Each settings row is a single primary focus target.
- OK on the row or its trailing navigation affordance opens the selected sub-screen.
- DPAD Up/Down moves between rows.
- DPAD Right moves from the row body to its trailing navigation affordance when one is shown.
- DPAD Left from the trailing affordance returns focus to the parent row.
- Back on Settings root returns to the caller per the global navigation rules above.

**Sub-screen navigation (normative)**:
- DPAD Up/Down moves between rows within the current settings sub-screen.
- Back from any settings sub-screen returns to Settings root.
- Dialogs opened from Settings are overlays; dismissing them returns focus to the control that launched them.

**Numeric setting edit**: OK on boolean toggles immediately. OK on numeric opens modal numeric keypad. First digit replaces entire value (replace-on-first-digit), subsequent append. Del deletes last digit, long-press Del clears all. Default focus on Cancel. **On validation failure, the dialog MUST remain open and show an error** — it MUST NOT close and apply an invalid value.

#### Settings Root Wireframe

```wireframe
+--------------------------------------+
| SETTINGS                              |
|  > Connect Phones                     |
|    Song Library                       |
|    Audio                              |
|    Scoring Timing                     |
|    Gameplay                           |
|    Video                              |
+--------------------------------------+
| Hints: OK=Open   Back=Return          |
+--------------------------------------+
```

#### Numeric Keypad Dialog Wireframe

```wireframe
+--------------------------------------+
| EDIT VALUE                            |
| Setting: <SettingName>                |
|                                      |
| Value: [ 123 ]                        |
|                                      |
|  [1] [2] [3]                          |
|  [4] [5] [6]                          |
|  [7] [8] [9]                          |
|  [Del] [0]                            |
|                                      |
|  > Cancel     OK                      |
+--------------------------------------+
```

#### 2.6.15.1 Settings > Connect Phones
QR code + short join code for pairing. Connected device list with Kick action (confirm dialog, default focus Cancel).

**Initial focus**: first connected-device row if any devices are present; otherwise the first available pairing/join affordance.

**Connect Phones navigation (normative)**:
- DPAD Up/Down moves through the connected-device roster and then to the action row.
- The selected device row owns the Kick action shown for that row.
- DPAD Up from the action row returns to the selected device row.
- Back returns to Settings root.

**Join admission (normative)**:
- Phones MAY join while the session is **Open** until the roster reaches **10 devices**.
- Additional phones beyond 10 MUST be rejected with `error(code="session_full")`.
- During **Locked** state (song in progress), new joins MUST be rejected with `error(code="session_locked")`.

**Kick**: disconnects the phone (closes WebSocket), removes its `clientId` from the current session roster, removes that phone's songs from the in-memory library/song list, and revokes reconnect entitlement for the current session. Phone returns to Join screen. If the session remains **Open**, the phone MAY join again as a fresh spectator.

##### Connect Phones Wireframe

```wireframe
+--------------------------------------------------------------------------------+
| SETTINGS > CONNECT PHONES                                                      |
+--------------------------------------------------------------------------------+
| Join this session:                                                             |
|   [   QR CODE   ]             Code: ABCD-EFGH                                       |
|                                                                                |
| Connected devices (up to 10):                                                  |
|  > Pixel-7        Connected                                                    |
|    iPhone-13      Connected                                                    |
|    ...                                                                         |
|                                                                                |
| Actions on selected device:  [Kick]                                             |
|                                                                                |
+--------------------------------------------------------------------------------+
| Hints: OK=Select/Action   Back=Return                                          |
+--------------------------------------------------------------------------------+
```

##### Confirm Dialog Wireframe

```wireframe
+--------------------------------------+
| CONFIRM                              |
| Kick <DeviceName>?                   |
|                                      |
|  > Cancel     OK                     |
+--------------------------------------+
```

#### 2.6.15.2 Settings > Song Library
Shows song contribution status per connected phone: device name and song count. Per-row Refresh action. Refresh All button.

##### Song Library Wireframe

```wireframe
+--------------------------------------------------------------------------------+
| SETTINGS > SONG LIBRARY                                                        |
+--------------------------------------------------------------------------------+
| Connected phones:                                                               |
|                                                                                |
|  > Alice's Pixel 7    songs: 423                           [Refresh]           |
|    Bob's Galaxy S24   songs: 198                           [Refresh]           |
|                                                                                |
| [Refresh all]                                                                  |
+--------------------------------------------------------------------------------+
| Hints: OK=Action  Back=Return                                                  |
+--------------------------------------------------------------------------------+
```

#### 2.6.15.3 Settings > Audio
- **Preview Volume**: slider 0–100. Controls Song List preview only. 0 = silence and disables preview. **Slider DPAD interaction**: Left/Right adjusts ±1 per press; long-press Left/Right adjusts ±10 per repeat. OK opens numeric keypad dialog.
- **Vocals Volume**: slider 0–100 (default 50). Reserved for a future release; the phone will expose a mix-parameter endpoint. For MVP this control MUST be rendered as a **disabled slider** with a `Coming soon` sub-label beneath it. It MUST NOT affect playback.
- **Mic sensitivity**: configured on each phone in phone Settings. The TV MUST NOT own or override this setting in MVP.

##### Audio Wireframe

```wireframe
+--------------------------------------+
| SETTINGS > AUDIO                      |
+--------------------------------------+
| Preview Volume:  [=====|-----]  60    |
| Vocals Volume:   [==|------]    50    |
+--------------------------------------+
| Hints: Left/Right=Adjust  OK=Enter value  Back=Return |
+--------------------------------------+
```

#### 2.6.15.4 Settings > Scoring Timing
Manual mic delay (ms): integer 0–400.
##### Scoring Timing Wireframe

```wireframe
+--------------------------------------+
| SETTINGS > SCORING TIMING             |
+--------------------------------------+
| Manual mic delay (ms):   0            |
+--------------------------------------+
| Hints: OK=Edit  Back=Return           |
+--------------------------------------+
```

#### 2.6.15.5 Settings > Gameplay
- Line bonus ON/OFF (default ON).
- Ready countdown ON/OFF (default ON).
- Countdown seconds: integer 1–10 (default 3). Displays at 1 Hz: N, N-1, ..., 1. After `1`, playback starts.
- Show note lines ON/OFF (visual only).

##### Gameplay Wireframe

```wireframe
+--------------------------------------+
| SETTINGS > GAMEPLAY                   |
+--------------------------------------+
| Line bonus:             ON            |
| Ready countdown:        ON            |
| Countdown seconds:      3             |
| Show note lines:        ON            |
+--------------------------------------+
| Hints: OK=Toggle/Keypad  Back=Return  |
+--------------------------------------+
```

#### 2.6.15.6 Settings > Video
Video enabled ON/OFF. When disabled or unavailable, background fallback: 1) `#BACKGROUND` image if available, 2) app-shipped default background image.

##### Video Wireframe

```wireframe
+--------------------------------------+
| SETTINGS > VIDEO                     |
+--------------------------------------+
| Video enabled:          ON           |
+--------------------------------------+
| Hints: OK=Toggle  Back=Return        |
+--------------------------------------+
```

#### In-Song and Results Flows

### 2.6.16 SingingScreen Behavior

**Overall layout**: top metadata strip, lane region, full-width bottom lyrics band. The screen is designed for video backgrounds; overlay surfaces remain readable over moving footage via `SurfaceLaneBand` / `SurfaceLyricsBand` at `LaneBandAlpha` / `LyricsBandAlpha`.

**Video surface z-order (normative)**: the video surface MUST be a `SurfaceView` with `setZOrderMediaOverlay(true)`. With this flag set, Compose lane bands, lyrics, score boxes, badges, and the pause/quit interruption overlay all composite **above** the video without routing through Compose's GPU composition pipeline. `TextureView` MUST NOT be used for fullscreen video on the singing screen — the additional GL composition cost on the Mali-G31 reference GPU is incompatible with the §1.6 30fps singing-screen target.

**Layout tokens (global):**

| Token | Value |
|---|---:|
| SingingTopIntroStripHeight | 72dp |
| SingingTopMinimalStripHeight | 40dp |
| SingingBottomLyricsBandHeight | 160dp |
| SingingBodyToLyricsGap | 16dp |

**Lane tokens — single-singer state:**

| Token | Value |
|---|---:|
| SingingSingleLaneHeight | 192dp |
| SingingSingleLaneVerticalPosition | centered |

**Lane tokens — two-singer state:**

| Token | Value |
|---|---:|
| SingingDualLaneHeight | 144dp |
| SingingDualLaneGap | 24dp |

**Lane internals:**

| Token | Value |
|---|---:|
| SingingLaneHorizontalPadding | 20dp |
| SingingLaneVerticalPadding | 16dp |
| SingingScoreBoxWidth | 144dp |
| SingingScoreBoxHeight | 88dp |
| SingingScoreBoxRightInset | 16dp |
| SingingScoreBoxToRatingGap | 8dp |
| SingingBadgeHeight | 40dp |
| SingingBadgeTopInset | 8dp |

**Lyrics band internals:**

| Token | Value |
|---|---:|
| LyricsBandPaddingHorizontal | 24dp |
| LyricsBandPaddingTop | 20dp |
| LyricsBandLineGap | 8dp |

**Minimum content**: progressive-highlight lyrics, pitch bars per active singer, live score per singer (normative: display format `XXXXX` using `LiveScore`), elapsed time, song title/artist. Oversized tier typography throughout.

**Top metadata rules (normative)**:
- On song start and on medley segment change, render the top metadata in the intro strip at `SingingTopIntroStripHeight` (title + artist, oversized tier).
- During active singing, collapse metadata to the minimal strip at `SingingTopMinimalStripHeight` using `TopMetadataMinimal`.
- In medley, the minimal strip renders as `<i>/<n>: <Artist> — <Title>`.

**Singer lane layout rules (normative)**:
- **Single singer**: exactly one centered lane band at `SingingSingleLaneHeight` (192dp), full width, vertically centered on screen.
- **Two singers**: exactly two stacked lane bands at `SingingDualLaneHeight` (144dp) separated by `SingingDualLaneGap`.
- Lane bands are long horizontal plates with `RadiusMedium` corners.
- Lane fill uses `SurfaceLaneBand` with `LaneBandAlpha`.
- Lane bodies remain **neutral**. Player color appears only in accents (singer badge, score-box accents, pitch cursor, note markers). MUST NOT tint the full lane body with `Player1Accent` / `Player2Accent`.
- P1 uses `Player1Accent` (cyan); P2 uses `Player2Accent` (magenta).

**Score and sentence rating (normative)**:
- Each lane has exactly one score box anchored on the right edge at `SingingScoreBoxWidth` × `SingingScoreBoxHeight`, inset by `SingingScoreBoxRightInset` from the lane's right edge.
- Sentence rating is rendered directly under the score box at `SingingScoreBoxToRatingGap`.
- Score text uses `LiveScore`. Sentence rating uses `SentenceRating`.

**Elapsed time**: displayed bottom-right using `Timer` typography, formatted as `MM:SS` (always two digits each, zero-padded; e.g., `00:35`, `01:23`). This is elapsed time from song start.

**Lyrics rendering (normative)**:
- Lyrics render in the bottom lyrics band only, at `SingingBottomLyricsBandHeight` using `SurfaceLyricsBand` with `LyricsBandAlpha`. Band uses `LyricsBandPaddingHorizontal` / `LyricsBandPaddingTop` / `LyricsBandLineGap`.
- The band always shows **exactly two lines**: current line and next line. MUST NOT render a third line.
- Current line uses `LyricsCurrent` and is stronger in contrast/emphasis; next line uses `LyricsNext` and is muted.
- Lyrics MUST remain spatially stable during a sentence (no continuous scroll).
- Sentence-based paging. Current sentence stays in place while highlight progresses.
- Page to next sentence when lyrics beat position reaches `startBeat` of first note in next sentence.
- During instrumental gaps, completed sentence remains at 100% highlight — MUST NOT pre-page or show blank.
- Implementations MAY render the active highlight as a **clipped reveal** over an inactive base text pass.
- Typography uses operational sans (`LyricsCurrent` / `LyricsNext`), prioritizing readability at TV viewing distance.

**Sentence rating** (USDX parity): after each sentence ends, display rating label for ~800ms then fade:

| LinePerfection | Label |
|---|---|
| 1.00 | `Perfect!` |
| ≥ 0.80 | `Great` |
| ≥ 0.60 | `Good` |
| ≥ 0.40 | `Cool` |
| ≥ 0.20 | `Okay` |
| < 0.20 | `Poor` |

**Singing motion budget (normative — V0 per [§VFX table](#2658-motion-and-vfx-budget))**:

Allowed during active singing:
- lyric highlight progression (the clipped reveal)
- sentence rating opacity fade
- score update pulse of minimal amplitude (small opacity/scale pop on the score box numeral only, no lane-body motion)
- note lane rendering already required by gameplay (pitch cursor, note target bars, hit/miss indicators, the instrumental gap indicator per [§Instrumental Gap Indicator](#268-instrumental-gap-indicator))

Not allowed during active singing:
- background animation over video
- blur or bloom transitions on lyric change
- multi-panel HUD entrance sequences
- particle feedback on notes or line completion
- full-lane pulses (a full lane band cannot animate its fill, opacity, or border)
- layout-affecting animation of the lane, lyrics region, or score placement

This supersedes the prior single-line "Sentence rating animation" rule with a complete allow/deny enumeration.

**Countdown**: if Ready countdown ON, show an N-second countdown at 1 Hz then begin playback + scoring. If OFF, begin immediately. Visual rules:
- The numeral is centered and rendered in `DisplayHeroNumber`.
- Background remains dimmed and static (no video motion during countdown).
- Only the numeral animates: one scale-pop per count. MUST NOT add secondary full-screen pulses, flashes, or particle effects.

If a required singer disconnects during countdown: cancel, return to Select Players with blocking error modal (title `DISCONNECTED`, body `A required singer disconnected during countdown. Please reconnect and start again.`, single `OK`). **Default focus on `OK`**. On `OK`, modal closes and user remains on Select Players.

#### Countdown Disconnect Modal Wireframe

```wireframe
+--------------------------------------+
| DISCONNECTED                          |
| A required singer disconnected         |
| during countdown.                      |
| Please reconnect and start again.      |
|                                      |
|  > OK                                 |
+--------------------------------------+
```

**Pause** (Back key):
```wireframe
+--------------------------------------+
| PAUSED                               |
|  > Resume                            |
|    Restart Song                      |
|    Quit to Song List                 |
+--------------------------------------+
```
- Resume: resume from current position.
- Restart Song: confirm dialog (default Cancel). On OK: reset all per-player scores, new `songInstanceSeq`, re-send `assignSinger`. **Normal song**: seek audio to `startSec` (and video to `videoGapSec + startSec`). **Medley**: restart full medley from segment 1, seeking to segment 1's `medleyStartSec`.
- Quit: confirm dialog (default Cancel). Returns to Song List.

**Disconnect auto-pause**:
```wireframe
+--------------------------------------+
| PAUSED — PLAYER DISCONNECTED         |
| <PhoneName> has disconnected.         |
|                                      |
|  > Wait for reconnect                |
|    Continue without them             |
|    Quit to Song List                 |
+--------------------------------------+
```
- **Wait for reconnect**: song stays paused. On reconnect ([§2.3](#23-networkcontroller)), TV re-sends `assignSinger` with updated `stopAtLyricsTimeMs` reflecting remaining playback, then sends current `playbackState`. Song resumes from paused position.
- **Continue without them**: song resumes immediately. That player's singer assignment is revoked for the current song. No further `pitchFrame` datagrams arrive for that player; they contribute no further score for the remainder of the song. If the phone reconnects before song end, it may rejoin the session, but MUST NOT resume singer role or score contribution until the next song.
- **Quit to Song List**: same behavior as normal Quit (confirm dialog, default Cancel; on OK stop playback, return to Song List).

Spectator disconnects (phones not assigned as singers) MUST NOT trigger auto-pause.

**Song end (normative)**:
- `stopAtLyricsTimeMs` is the authoritative stop point, expressed in lyrics-time milliseconds.
  - Normal song: if `#END > 0`, `stopAtLyricsTimeMs = endMs`; otherwise `stopAtLyricsTimeMs` uses the effective playback-plan duration reported by `PlaybackEvent.Prepared` (`audioDurationMs` for single-track playback; for dual-track playback, the coupled plan's natural stop duration after applying the shorter-track rule). `#START` changes initial playback position only — it does NOT change the timing origin.
  - Medley: `stopAtLyricsTimeMs` is lyrics-time ms at the end of the final segment's `medleyEndSec`.
- UI MUST enforce `stopAtLyricsTimeMs` as the active playback stop boundary on the LibVLC `MediaPlayer` (via `LibVlcPlayerHandle`).
- When UI reaches `stopAtLyricsTimeMs`, it MUST call `LibVlcPlayerHandle.stop()` and emit `PlaybackEvent.Ended`; the coordinator treats that event as the authoritative trigger for `Stopped` → scoring finalization → `Results`, unless an explicit error or quit path overrides it.
- The TV MUST **ignore** any `pitchFrame` whose corresponding note lies at or beyond `stopAtLyricsTimeMs`.

**Playback error handling (normative)**:
LibVLC's error model is coarse: a single `LibVlcEvent.EncounteredError` with no granular code. To preserve diagnostic value the TV MUST register a `LibVLC.OnLogListener` at LibVLC construction and maintain a single-slot ring buffer of the most recent log line at level `WARNING` or `ERROR`:

```kotlin
@Volatile private var lastLogLine: String? = null
libVLC.setOnLogListener { level, ctx, msg ->
    if (level == LogLevel.WARNING || level == LogLevel.ERROR) {
        lastLogLine = msg.take(120)
    }
}
```

The log listener fires on a libvlc native thread; the volatile field is the only synchronisation needed and there is no allocation in the steady state.

On `LibVlcEvent.EncounteredError` during singing, the TV MUST:
1. Stop playback and scoring immediately (`LibVlcPlayerHandle.stop()`).
2. Return to Song List.
3. Show blocking error modal: title `ERROR`, body line 1 `This song can't be played.`, body line 2 = the volatile `lastLogLine` truncated to 120 chars; if `lastLogLine` is `null`, body line 2 is omitted. Single `OK`.

The error MUST NOT crash the app, corrupt session state, or leave the session Locked. Session returns to Open on error exit.

**Codec support (normative)**: supported audio and video formats are determined by the device's hardware and software decoders at runtime, surfaced through LibVLC. No compile-time format whitelist is maintained. Songs with unsupported formats fail at playback time and are handled by this error path.

**Audio focus (normative)**: LibVLC does not interact with `AudioManager` automatically. The UI layer MUST request audio focus before playback and respond to focus changes:

1. Before `LibVlcPlayerHandle.play()`, request `AUDIOFOCUS_GAIN` on `STREAM_MUSIC` via `AudioManager.requestAudioFocus(AudioFocusRequest)`. If the request is not granted, the UI layer MUST emit `PlaybackEvent.Error` and follow the Playback error handling path above.
2. Register an `OnAudioFocusChangeListener` for the lifetime of playback:
   - `AUDIOFOCUS_LOSS_TRANSIENT` or `AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK` → emit `PlaybackIntent.Pause`. The coordinator pauses scoring per the existing pause/resume rules (`pauseStartedTvMs` / `totalPausedDurationMs`, steps 10–12 of §2.1 songStartTvMs Capture).
   - `AUDIOFOCUS_GAIN` after a transient loss → emit `PlaybackIntent.Play` (resume).
   - `AUDIOFOCUS_LOSS` (permanent) → follow the Playback error handling path above.
3. The listener fires on a binder thread; the UI layer MUST dispatch onto the ViewModel's main scope before emitting any intent.
4. On song end, error exit, or Restart, the UI layer MUST call `AudioManager.abandonAudioFocusRequest`.

#### Singing Screen Wireframe

```wireframe
Active singing screen — two singers
+--------------------------------------------------------------------------------+
|                          (FULLSCREEN VIDEO / BACKGROUND)                       |
|                                                                                |
| P1 [badge]                                                                     |
|  ───────────────────────────────────────────────────────────────────────────   |
|   [note bars / pitch lane P1]                                                  |
|                                                                +--------+      |
|                                                                | 00710  |      |
|                                                                +--------+      |
|                                                                  Great         |
|                                                                                |
| P2 [badge]                                                                     |
|  ───────────────────────────────────────────────────────────────────────────   |
|   [note bars / pitch lane P2]                                                  |
|                                                                +--------+      |
|                                                                | 00720  |      |
|                                                                +--------+      |
|                                                                  Perfect!      |
|                                                                                |
+--------------------------------------------------------------------------------+
| Lyrics (USDX style: active syllables highlighted)                               |
|   CUz this life is too short                                                   |
|   to live it just for you                                                      |
+--------------------------------------------------------------------------------+
|                                                                      00:35     |
+--------------------------------------------------------------------------------+

Active singing screen — single singer (vertically centered lane)
+--------------------------------------------------------------------------------+
|                          (FULLSCREEN VIDEO / BACKGROUND)                       |
|                                                                                |
|                                                                                |
| P1 [badge]                                                                     |
|  ───────────────────────────────────────────────────────────────────────────   |
|   [note bars / pitch lane P1 — vertically centered]                            |
|                                                                +--------+      |
|                                                                | 00710  |      |
|                                                                +--------+      |
|                                                                  Perfect!      |
|                                                                                |
+--------------------------------------------------------------------------------+
| Lyrics                                                                          |
|   CUz this life is too short                                                   |
+--------------------------------------------------------------------------------+
|                                                                      00:35     |
+--------------------------------------------------------------------------------+

Countdown overlay (before playback and scoring start; 1 Hz)
+--------------------------------------------------------------------------------+
|                                                                                |
|                                     3                                          |
|                                                                                |
+--------------------------------------------------------------------------------+
(then 2, 1; after showing 1, playback + scoring start)

Pause overlay (Back key)
+--------------------------------------+
| PAUSED                               |
|  > Resume                            |
|    Restart Song                      |
|    Quit to Song List                 |
+--------------------------------------+

Restart confirm (default focus Cancel)
+--------------------------------------+
| CONFIRM                              |
| Restart song?                        |
|                                      |
|  > Cancel     OK                     |
+--------------------------------------+

Quit confirm (default focus Cancel)
+--------------------------------------+
| CONFIRM                              |
| Quit to Song List?                   |
|                                      |
|  > Cancel     OK                     |
+--------------------------------------+
```

### 2.6.17 SingingScreen — Medley Mode

**Medley run context**: on start, create immutable snapshot from Medley playlist (preserves order, decoupled from Song List lifecycle).

**Start flow**: Show Select Players once (subtitle `Medley — <n> songs`). On Start, build the full medley `SingingRenderModel`; only after that succeeds may countdown begin and segment 1 start. Players remain assigned for entire run.

**Medley window**: defined by `medleyStartBeat` / `medleyEndBeat` from parsed chart.
- `MEDLEY_FADE_IN_SEC = 8` (extends playback before `startBeat`)
- `MEDLEY_FADE_OUT_SEC = 2` (extends playback after `endBeat`)
- `medleyStartSec = max(0, timeFromBeat(startBeat) − MEDLEY_FADE_IN_SEC)`
- `medleyEndSec = timeFromBeat(endBeat) + MEDLEY_FADE_OUT_SEC`
- Scoring window: only notes within `[medleyStartBeat, medleyEndBeat)` use normal ScoreFactor; notes outside treated as Freestyle (ScoreFactor=0).

**Video positioning**: if video present and enabled, position to `videoGapSec + medleyStartSec`.
- `MedleySegment` and `PlaybackIntent.PrebufferNext` MUST carry the per-segment media assets needed for medley playback: `audioUrl` (pre-mixed, non-null for playable segments), optional `videoUrl`, and optional `videoGapSec`.

**Segment failure handling (normative)**:
- If the full medley `SingingRenderModel` cannot be built before countdown (e.g., any required segment `txtUrl` fetch or parse fails), the medley MUST fail before start and return to Song List with an error modal.
- `audioUrl` null when medley reaches a segment: skip that segment, show brief error toast, proceed to next.
- Audio URL becomes unreachable during playback (e.g., source phone disconnected): abort medley, follow playback-error exit path (return to Song List, show error modal).

**Segment indicator (normative)**: when `n > 1` segments remain, the in-song artist/title label MUST render as `<i>/<n>: <Artist> — <Title>`. A segment progress indicator MUST be shown in the top-left corner alongside this label. (When only one segment — i.e. a single-song medley — no indicator is required.)

**Segment transition visual (normative)**: segment-to-segment transitions rely on audio crossfade as the primary perceptual transition (V0 per [§VFX table](#2658-motion-and-vfx-budget)). The visual transition is limited to the top metadata intro-strip swap described in [§SingingScreen Behavior — Top metadata rules](#2616-singingscreen-behavior). MUST NOT add a full-screen overlay transition, wipe, or cinematic cut between segments.

**Medley source notification (normative)**: before the run starts, the coordinator MUST identify all phones whose songs appear in the medley playlist and send each of them `playbackState(state="playing", reason="medley_source")` with `stopAtLyricsTimeMs` = end of the final segment. This includes phones that are not assigned as singers. Phones receiving this state MUST keep their HTTP server active and SHOULD discourage the user from backgrounding the app.

**Cancel in Select Players**: abort medley, return to Song List, playlist unchanged.

#### Medley Singing Header Wireframe

```wireframe
| 2/5: Daft Punk — Get Lucky          P1 [badge]
|  ─────────────────────────────────────────────
```

### 2.6.18 ResultsScreen Behavior

Results is a terminal full-screen route reached after scoring finalization completes. It does not own modal follow-up flows. Leaving Results always returns to Song List and re-enters the normal browse flow.

#### 2.6.18.1 Post-song results

Show per singer: Notes score, Golden score, Line bonus, Song Total (tens-rounded per [Rounding and Display](#rounding-and-display-normative)). Only action: Back to Song List.

**Layout tokens (single-song):**

| Token | Value |
|---|---:|
| ResultsHeaderBottomGap | 24dp |
| ResultsPlayerColumnGap | 32dp |
| ResultsPlayerCardPadding | 24dp |
| ResultsBreakdownRowHeight | 44dp |
| ResultsBreakdownRowGap | 12dp |
| ResultsTotalTopGap | 24dp |
| ResultsBackButtonTopGap | 32dp |

**Presentation rules (normative)**:
- Oversized tier typography. Operational sans for labels and body; display face reserved for `ResultTotalValue`.
- Header shows screen title and song title line.
- Each player column shows Notes, Golden, Line Bonus, Song Total.
- Breakdown labels use `ResultBreakdownLabel`; breakdown values use `ResultBreakdownValue`; Song Total uses `ResultTotalValue`.
- **Winner emphasis (normative)**: when one player's Song Total is strictly greater than the other's, render `RewardAccent` (gold) on the winning player's identity marker (singer badge and/or Song Total value). **Ties MUST NOT use gold** on either player — both remain neutral.
- The `Back to Song List` action sits below the results board at `ResultsBackButtonTopGap`.

**Initial focus**: first singer result card when result cards are individually focusable; otherwise the sole **Back to Song List** action.

**Song results navigation (normative)**:
- If individual singer result cards are focusable, DPAD Up/Down moves between result cards and the final action.
- The final action is **Back to Song List**.
- DPAD Left/Right does not move focus unless the implementation adds a horizontally arranged comparison affordance.
- Pressing OK on **Back to Song List** returns to Song List.
- Pressing TV remote Back on the Results screen MUST behave identically to selecting **Back to Song List**.

**Motion (V2 budget)**:
- One entry payoff sequence (e.g., panels slide or fade into place).
- One count-up sequence on the Song Total values.
- One winner-emphasis pass on the winning marker when the result is not a tie.
- After that sequence completes, the screen is fully static.

#### Song Score Wireframe

```wireframe
+--------------------------------------------------------------------------------+
| Song Score                                                                     |
| <Artist> — <Title>                                                             |
+--------------------------------------------------------------------------------+
| P1: <PhoneName>                                  | Comparison |     P2: <PhoneName> |
|                                                                                |
| Notes score        00000                          |█████       |   Notes score        00000 |
| Golden score       00000                          |███████     |   Golden score       00000 |
| Line bonus         00000                          |████        |   Line bonus         00000 |
|                                                                                |
| Song Total        00000                           |██████      |   Song Total    ★ 00000 |
|                                                                                |
+--------------------------------------------------------------------------------+
| [Back to Song List]                                                            |
+--------------------------------------------------------------------------------+
```
(Gold star ★ denotes winner-marker emphasis; rendered in `RewardAccent` on the winning player only, and only when scores differ.)

#### 2.6.18.2 Post-medley results

Single results screen with static table: per-segment scores + Medley Total (mean of `scoreTotalInt` values).

**Layout tokens (medley):**

| Token | Value |
|---|---:|
| MedleyResultsTableRowHeight | 64dp |
| MedleyResultsTableRowGap | 0dp |
| MedleyResultsTotalRowHeight | 80dp |
| MedleyResultsTotalTopGap | 16dp |
| MedleyResultsBackButtonTopGap | 32dp |

**Aggregation**: `MedleyTotal.scoreTotalInt = round(sum(segment.scoreTotalInt) / nSegments)` — may be non-multiple-of-10 (USDX parity).

**Row display format**: `<i>. <Artist> — <Title>   <P1 scoreTotalInt>   <P2 scoreTotalInt>` (omit P2 column if no P2 assigned).

**Presentation rules (normative)**:
- Operational sans only. Normal rows use `MedleyRowText`; Medley Total values use `MedleyTotalValue`.
- The score table is informational and non-focusable.
- Render the Back to Song List button as the only focusable control.
- Use row spacing, row weight, and the taller `MedleyResultsTotalRowHeight` to emphasize the Medley Total row.
- **MUST NOT use `RewardAccent` (gold) on the Medley Total row.** Medley is a multi-song run and does not declare a single-song winner.
- **MUST NOT use the decorative display face on the Medley Total row** (operational sans only).

**Initial focus**: the sole **Back to Song List** action.

**Medley results navigation (normative)**:
- The score table itself is informational and non-focusable.
- The only focusable control is **Back to Song List**.
- Pressing OK on **Back to Song List** returns to Song List.
- Pressing TV remote Back MUST return to Song List.

**Motion (V1 budget)**:
- A single 180ms opacity fade on entry.
- No celebratory background treatment.
- No continuous animation after entry.

#### Medley Results Wireframe

```wireframe
+--------------------------------------------------------------------------------+
| Medley Results                                                                  |
+--------------------------------------------------------------------------------+
| P1: <PhoneName>                                          P2: <PhoneName>        |
+--------------------------------------------------------------------------------+
|  1. PSY — Gangnam Style                          01840         07200           |
|  2. Daft Punk — Get Lucky                        07200         04100           |
|  3. Queen — Bohemian Rhapsody                    06100         08300           |
|  ──────────────────────────────────────────────────────────────────────────   |
|  Medley Total                                    05047         06533           |
+--------------------------------------------------------------------------------+
| [Back to Song List]                                                            |
+--------------------------------------------------------------------------------+
| Hints: OK=Back to Song List   Back=Back to Song List                           |
+--------------------------------------------------------------------------------+
```
(No gold on Medley Total; operational sans only on the Medley Total row.)

### 2.6.19 Acceptance Tests (Medley — 9.5.7)

| ID | What | Fixture | Expected |
|----|------|---------|---------|
| T9.5.7.1 | `medleyStartSec` and `medleyEndSec` computation | F16/`expected.segments.json` | All 3 songs match fixture |
| T9.5.7.2 | Clamped: `timeFromBeat(startBeat) <= 8` → `medleyStartSec=0.0` | inline | Clamped to 0 |
| T9.5.7.3 | Notes in `[start, end)` → normal ScoreFactor | F16 | Applied normally |
| T9.5.7.4 | Notes outside medley window → ScoreFactor=0 | F16 | Freestyle treatment |
| T9.5.7.5 | `TrackScoreValue` window-filtered | F16 | Only in-window notes summed |
| T9.5.7.6 | Per-note ratio scoring within medley window | F16 | `note_score = max_note_score × (hits/N)` per [Scoring Algorithm](#scoring-algorithm-normative) |
| T9.5.7.7 | Playback order preserved | F16 | A → B → C |
| T9.5.7.8 | `medleyStartBeat >= medleyEndBeat` → assertion error | inline | Internal defensive error |
| T9.5.7.9 | `audioUrl` null → segment skipped, next proceeds | inline | Error toast + continue |
| T9.5.7.10 | Scan-time: `#MEDLEYSTARTBEAT >= #MEDLEYENDBEAT` → `canMedley=false` | inline | Song excluded from playlist |

### 2.6.20 Acceptance Tests (Results — 9.6)

| ID | What | Expected | Fixture |
|----|------|---------|---------|
| T9.6.1 | Medley Total = `round(sum(scoreTotalInt) / nSegments)` per player | Aggregated score matches formula | F16 |
| T9.6.2 | Medley Total may be non-multiple-of-10 (USDX parity) | Non-tens result accepted (e.g. [10000,9960,0] → 6653) | inline |
| T9.6.3 | Per-segment row displays `scoreTotalInt` for each player | All segments listed with P1/P2 scores | inline |
| T9.6.4 | Back key returns to Song List | Navigation correct | inline |

### 2.6.21 Acceptance Criteria

- Manual verification on target device
- F16 medley UI states

### 2.6.22 Knowledge Gaps

None.

---

## 2.7 Mock Phone (Dev/Test Only)

A `:mock-phone` Gradle module MUST be maintained in the repository to enable TV app development and testing without a real phone companion. The mock phone provides three services:

**1. Mock HTTP server**: Ktor CIO server on `localhost:34781` serving `/manifest.json` from fixture songs and `GET /songs/<path>` from the fixture directory. Launched via `./gradlew :mock-phone:run`.

**2. Mock WebSocket client**: Connects to the TV's WebSocket, performs `hello` handshake (with `httpPort` pointing at the mock HTTP server), responds to `ping`/`pong` clock sync, and handles `assignSinger` by entering pitch-streaming mode.

**3. Mock pitch frame generator**: Produces 20-byte UDP `pitchFrame` datagrams at 50fps during singing. Accepts a **performance profile**:

| Profile | Behaviour |
|---------|-----------|
| `PERFECT` | Every frame within a note window emits `midiNote = note.toneSemitone + 36` |
| `PARTIAL(hitRate: Float)` | Randomly sets `midiNote = 255` for `(1 - hitRate)` fraction of frames |
| `SILENCE` | All frames `midiNote = 255` |
| `OCTAVE_OFF` | Emits `midiNote = note.toneSemitone + 36 + 12` (validates octave normalization) |
| `REPLAY(path: Path)` | Replays a `pitchFrames.bin` fixture file with original timing |

The generator computes `tvTimeMs` from `clockOffsetMs` (derived from clock sync exchange with the TV) plus local monotonic time. `songInstanceSeq` and `connectionId` are taken from `assignSinger` and `sessionState` messages received over the WebSocket.

The mock phone is a **development dependency only** and MUST NOT be included in release builds.

---

# 3. Component Interactions

This section summarizes cross-component data flow and call boundaries. Owning component sections in [§2](#2-top-level-components) remain authoritative for responsibilities, protocol rules, scoring rules, and screen behavior.

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
fetchTxt()   parse()       loadChart(config) (via Intent)
    │           │              │            Prepare()
    │           │              │                │
    └─────┬─────┘              │                │
          ▼                    │                │
    ParsedSong ────────────────┘                │
                                                │
    ┌───────────────────────────────────────────┘
    ▼
PlaybackEvent.Prepared(durationMs)
    │
    ▼
NetworkCtrl.broadcastPlaybackState()
NetworkCtrl.sendAssignSinger()
    │
    ▼
UI.Play() ──→ LibVLC starts ──→ PlaybackEvent.Ready(songStartTvMs)
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
ScoringCoroutine (deadline-driven loop)
         │
         ├── Peek earliest pending finalizeAtTvMs
         │
         ├── Wait until deadline is due
         │
         ▼ (one or more notes ready to finalize)
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
Coordinator ──(PlaybackIntent)──→ UI ──(executes via LibVlcPlayerHandle)
           ←──(PlaybackEvent)────┘
           ←──(StateFlow<positionMs>)──┘
```

- Coordinator emits `PlaybackIntent` (Prepare, Play, Pause, etc.)
- UI observes and executes on Media3
- UI is responsible for enforcing the active `stopAtLyricsTimeMs` boundary on Media3 using the current playback plan.
- When UI detects that playback has reached the active `stopAtLyricsTimeMs`, it MUST stop Media3 and emit `PlaybackEvent.Ended`.
- UI emits `PlaybackEvent` (`Prepared` with effective playback-plan duration, `Ready` with songStartTvMs, `Error`, `Ended`)
- UI exposes `currentPositionMs: StateFlow<Long>` for observation; in dual-track mode this is the timing-authority instrumental position

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
scoringEngine.loadChart(chart, micDelayMs, medleyWindow, scoringConfig)
scoringEngine.setSongStart(songStartTvMs)
scoringEngine.start()
scoringEngine.suspend()
scoringEngine.resume()
scoringEngine.finalizeAll()
scoringEngine.reset()
scoringEngine.stop()
```

### PlaybackCoordinator ↔ NetworkController

**Pattern**: Direct interface calls + event/state observation

```kotlin
// Coordinator calls:
networkController.sendAssignSinger(phoneId, message)
networkController.broadcastPlaybackState(message)
networkController.sendPing(phoneId)
networkController.sendClockAck(phoneId, ack)

// Settings UI calls:
networkController.kickPhone(clientId)

// Coordinator / UI observe:
networkController.phoneEvents.collect { event -> ... }
networkController.connectedPhones.collect { phones -> ... }
```

---

# 4. Internal Architectures

This section captures supporting mechanics and implementation shape for behavior defined in [§2](#2-top-level-components). Use it to understand timing and orchestration internals, not as a second home for externally visible responsibilities.

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
                       ┌─────────┐finalize┌──────┐           │
                       │ Stopped │───────→│Results│──────────┘
                       └─────────┘        └──────┘
```

**Transition Rules** (normative):

| From | To | Trigger |
|------|----|---------|
| Idle | Loading | User starts song from SelectPlayers |
| Loading | Countdown | Playback plan prepared, `assignSinger` sent, countdown enabled |
| Loading | Playing | Playback plan prepared, `assignSinger` sent, countdown disabled |
| Loading | Idle | Media3 error or audio URL unreachable |
| Countdown | Playing | Countdown reaches 0 |
| Countdown | Idle | Required singer disconnects |
| Playing | Paused | User presses Back |
| Playing | DisconnectPaused | Required singer WebSocket drops |
| Playing | Stopped | Playback reaches `stopAtLyricsTimeMs` or final medley segment ends |
| Paused | Playing | User selects Resume |
| Paused | Loading | User confirms Restart (new songInstanceSeq) |
| Paused | Idle | User confirms Quit |
| DisconnectPaused | Playing | Singer reconnects + Resume, or Continue Without Them (revokes that player's singer assignment for the current song) |
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
    scoringEngine.loadChart(chart, micDelayMs, next.beatWindow, scoringConfig)
    // During a medley run, songInstanceSeq remains stable across segment transitions.
    // The next segment becomes the active target for UDP validation when loadChart()
    // completes; frames are buffered immediately, but finalization stays gated on
    // setSongStart(songStartTvMs).
    
    // Step 6: Crossfade to prebuffered audio (8s fade in)
    uiIntents.emit(PlaybackIntent.Crossfade(0f, MEDLEY_FADE_IN_SEC))
    
    // Step 7: Capture new songStartTvMs
    val readyEvent = uiPlaybackEvents.first { it is PlaybackEvent.Ready }
    // During medley playback, exactly one segment is authoritative at a time. The
    // replacement segment becomes authoritative only when its PlaybackEvent.Ready
    // arrives and supplies the new songStartTvMs.
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
            uiIntents.emit(
                PlaybackIntent.PrebufferNext(
                    audioUrl = nextNext.audioUrl,
                    videoUrl = nextNext.videoUrl,
                    videoGapSec = nextNext.videoGapSec,
                    seekToSec = nextNext.medleyStartSec
                )
            )
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

`PlaybackController` MUST support preparing a second **audio+video pair** (`LibVlcPlayerHandle` × 2, or audio-only if no `videoUrl`) in background. At segment boundary, the active pair is released and the prebuffered pair becomes active (with fade-in). If prebuffering is not complete at transition point, coordinator MUST fall back to sequential prepare-and-play with a brief audio gap. All `LibVlcPlayerHandle` instances within a session share a single `LibVLC` engine — only the `MediaPlayer` is duplicated.

---

## 4.3 Scoring Coroutine

Runs independently of UI frame rate and is driven by note-finalization deadlines rather than a fixed polling frequency.

```kotlin
// Flat scoring schedule, built once at ScoringEngine.loadChart() time.
// Denormalizes Track.playerId and Line.lineIndex onto each scorable note and
// precomputes noteStartTvMs, noteEndTvMs, and finalizeAtTvMs.
data class ScheduledNote(
    val note: NoteEvent,
    val playerId: PlayerId,
    val lineIndex: Int,
    val isLastInLine: Boolean,
    val noteStartTvMs: Long,
    val noteEndTvMs: Long,
    val finalizeAtTvMs: Long
)

private fun startScoringCoroutine() = scope.launch {
    while (isActive && _isRunning.value) {
        val next = pendingNotes.peek() ?: break
        val tvNowMs = System.nanoTime() / 1_000_000
        val waitMs = (next.finalizeAtTvMs - tvNowMs).coerceAtLeast(0)
        if (waitMs > 0) {
            delay(waitMs.coerceAtMost(50))
            continue
        }

        var scoreChanged = false
        while (pendingNotes.peek()?.finalizeAtTvMs?.let { it <= tvNowMs } == true) {
            val sn = pendingNotes.remove()
            finalizeNote(sn, tvNowMs)
            scoreChanged = true
        }

        if (scoreChanged) {
            _playerScores.value = computeCurrentScores()
        }
    }
}

private fun finalizeNote(sn: ScheduledNote, tvNowMs: Long) {
    val frames = jitterBuffer.getFramesInWindow(
        sn.playerId, sn.noteStartTvMs, sn.noteEndTvMs
    )
    
    val result = noteEvaluator.evaluate(sn.note, frames)
    accumulator.addNoteScore(sn.playerId, result)
    
    // Check for sentence completion
    if (sn.isLastInLine) {
        lineBonusCalculator.applyLineBonus(sn.playerId, sn.lineIndex)
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
- Before any `assignSinger` with `startMode="countdown"` or `startMode="live"`, the TV MUST have at least one valid clock-sync sample for each assigned singer. Countdown MUST NOT begin until this requirement has been satisfied.
- **Suspend** during active singing after countdown completes or live playback begins. LAN clock drift over ~3 min song is negligible (<1ms).
- Resume with single exchange on song end or disconnect/reconnect.
- Any prior clock-sync result is scoped to the current TV session and active control connection. After reconnect, the TV MUST complete a fresh clock-sync exchange before treating resumed singer pitch traffic as valid for scoring.

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
                samples.add(ClockSample(rtt, offset, pong.pingId, t4))
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
            tTvRecvMs = best.tTvRecvMs
        ))
        
        return ClockSyncResult.Success(best.offsetMs, best.rtt)
    }
}

data class ClockSample(val rtt: Long, val offsetMs: Long, val pingId: String, val tTvRecvMs: Long)
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

**Mic Delay (Normative)**:

The TV-side mic delay is applied to all note-window calculations. For MVP:

```
micDelayMs = manualMicDelayMs   // from Settings > Scoring Timing (integer 0–400)
```

This shifts all scoring windows later by the configured number of milliseconds to compensate for audio pipeline latency on the phone. A value of 0 means no compensation. The value MUST be recomputed on every song start, restart, and reconnect.

**Implementation**: `BeatCalculator` MUST accept `micDelayMs` as a parameter (default 0). Passing the wrong delay for a consumer is a conformance error: lyrics beat uses `micDelayMs=0`; lane beat and note scoring windows use the configured `micDelayMs`.

Two beat computations from the same `BPM_internal` and `GAPms`:

| Consumer | Formula | micDelayMs |
|----------|---------|------------|
| **Lyrics beat** (highlight, elapsed display) | `floor(timeSecToMidBeatInternal(lyricsTimeSec - GAPms/1000.0))` | 0 |
| **Lane beat** (pitch targets, scoring windows) | `songStartTvMs + beatInternalToTimeSec(startBeat)*1000 + GAPms + micDelayMs` | Configured |

- Lyrics beat tracks what audience hears from speakers.
- Lane beat tracks where singer's voice should appear given mic/network delay.
- Pitch lane renders targets using lane beat. Live cursor driven by `PitchEvent.tvTimeMs` — correct performance aligns cursor with targets.

**Pitch lane coordinate system (normative)**:
- The pitch lane is a 2D coordinate system:
  - horizontal axis = lyrics-time position in ms
  - vertical axis = note pitch in semitones
- Lane layout height defines the player's drawable area and bounds the coordinate system; it is not derived from `Difficulty`.
- Horizontal mapping MUST be derived from `HorizontalTimeMapping`.
- Vertical mapping MUST be derived from `VerticalPitchMapping`.

**Horizontal mapping (normative)**:
- `visibleTimeMs` defines the total lyrics-time span visible within the drawable lane width.
- `nowAnchorFraction` defines where the current lane time is drawn within the drawable lane width, as a fraction in `[0,1]` from left to right.
- Note target width on screen is proportional to `(endTimeMs - startTimeMs) / visibleTimeMs`.
- Note target X position on screen is derived from `(noteTimeMs - currentLaneTimeMs)` relative to the anchor position.
- All pitch-target geometry MUST use the render-model lyrics-time axis.

**Vertical mapping (normative)**:
- `minToneSemitone` and `maxToneSemitone` define the visible pitch range for the lane.
- Note target Y position is derived from linear interpolation of `toneSemitone` within `[minToneSemitone, maxToneSemitone]`.
- Live pitch cursor Y position uses the same mapping as note targets.
- Notes or live pitch outside the visible range MUST clip at the lane boundary; they MUST NOT rescale the lane during active singing.
- `VerticalPitchMapping` is computed per player from that player's scorable notes only.
- For a normal song, compute `VerticalPitchMapping` from the active song's scorable notes for that player, then pad the range by 2 semitones above and below.
- For duet, each player's lane computes its own `VerticalPitchMapping` from that player's own scorable notes, with the same ±2 semitone padding.
- For medley, `VerticalPitchMapping` is fixed for the full medley run per player and is computed before countdown from the union of that player's scorable notes across all medley segments, with the same ±2 semitone padding.
- Lane layout height defines the drawable area only; it does not express tolerance.
- The note target bar's vertical thickness MUST express scoring tolerance for the active `Difficulty`: Easy = ±2 semitones, Medium = ±1 semitone, Hard = ±0 semitones around the target pitch.
- The live pitch glyph MUST represent exactly 1 semitone of vertical height.
- Note target bars MUST remain neutral; the live pitch glyph MUST use the player's accent color.

**Boundary Convention**: `noteActive if startBeat <= beat < endBeat` (start inclusive, end exclusive).

**Note Scoring Windows in TV Time (Normative)**:

For a note with `startBeat` and `durationBeats`, the scoring window in TV monotonic time is:

```
noteStartTvMs = songStartTvMs + (startBeat × 15000 / BPM_file) + GAPms + micDelayMs
noteEndTvMs   = songStartTvMs + ((startBeat + durationBeats) × 15000 / BPM_file) + GAPms + micDelayMs
```

Where `songStartTvMs` is captured per [§2.1](#21-playbackcoordinator) by the UI layer and delivered to the coordinator via `PlaybackEvent.Ready`, `BPM_file` is the raw `#BPM` before ×4, `GAPms` is `#GAP` in ms, and `micDelayMs` is the effective mic delay (shifts window later to account for audio pipeline latency).

A pitch frame falls within the window if: `noteStartTvMs <= frame.tvTimeMs < noteEndTvMs`.

The note is finalized when TV monotonic clock reaches `noteEndTvMs + NOTE_FINALIZATION_DELAY_MS` (450ms), ensuring late-arriving frames have been received. At finalization, qualifying frames satisfy both: (1) within `[noteStartTvMs, noteEndTvMs)`, and (2) `arrivalTimeTvMs − tvTimeMs <= 450` (not excessively late).

**Implementation**: Beat conversion logic MUST accept `micDelayMs` parameter (default 0). Using wrong delay for a consumer is a conformance error.

---

# 5. Resolved Blockers

| ID | Issue | Resolution |
|----|-------|------------|
| BLOCKER-1 | LibVLC ↔ PlaybackCoordinator interaction | Intent/Event pattern via `LibVlcPlayerHandle`. Coordinator emits `PlaybackIntent`, UI layer executes via audio/video handle pair, emits `PlaybackEvent` back. |
| BLOCKER-3 | playback start and duration handoff | UI reports effective playback-plan duration in `PlaybackEvent.Prepared`, then captures `songStartTvMs` from `LibVlcEvent.Playing` on the audio MP in `PlaybackEvent.Ready`; Coordinator uses the former for `stopAtLyricsTimeMs` and the latter for ScoringEngine start. |
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
| F18 | HTTP asset client smoke test | NetworkController |

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
├── expected.score_perfect.json   # scoreTotalInt=10000
├── expected.score_partial.json
└── expected.score_silence.json   # scoreTotalInt=0
```

Pitch frames for F24 SHOULD be constructed inline in test code unless a case needs shared or timing-sensitive replay data. Do not create fixture files just to store a handful of fixed frames.

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

| Deliverable | Component | Spec Ref | Fixtures |
|-------------|-----------|----------|----------|
| USDX parser | UsdxParser | [§2.4](#24-usdxparser) | F01, F02, F03, F04, F05 |
| Beat↔time conversion | ScoringEngine (partial) | [§4.6](#46-beat-time-conversion) | F06 |
| Per-note scoring math | ScoringEngine (partial) | [§2.2](#22-scoringengine) | F08, F09, F10 |
| Line bonus + rounding | ScoringEngine (partial) | [§2.2](#22-scoringengine) | F11 |
| Fixture harness | Test infra | [Appendix A](#appendix-a-peer-boundary-test-utilities) | — |

**DOD**:
- [x] All fixture tests pass: F01–F06, F08–F11
- [x] Coverage ≥80% on UsdxParser, scoring math modules
- [x] No Android dependencies — pure Kotlin, runs on JVM

**Mock Phone**: Not needed.

## 7.3 Iter 1 — Solo Sing (1 Phone, 1 Player)

**Goal**: End-to-end: browse library → select song → play audio with lyrics.

| Deliverable | Component | Spec Ref | Fixtures |
|-------------|-----------|----------|----------|
| WebSocket server | NetworkController | [§2.3](#23-networkcontroller) | F15 |
| mDNS advertisement | NetworkController | [§2.3](#23-networkcontroller) | F15 |
| HTTP client | NetworkController | [§2.3](#23-networkcontroller) | F15 |
| Manifest aggregation | LibraryManager | [§2.5](#25-librarymanager) | F14 |
| Song grid UI | UI: SongListScreen | [§2.6.12](#2612-songlistscreen-behavior) | F14 |
| Join overlay | UI: JoinOverlay | [§2.6.13](#2613-join-overlay-behavior) | F15 |
| Interruption overlay shell (loading/error variants) | UI: Shared overlay shell | [§2.6.11](#2611-interruption-overlay-shell) | F22 |
| Playback UI | UI: SingingScreen | [§2.6.16](#2616-singingscreen-behavior) | F22 |
| `CouchraokeTheme` + `AppNavHost` wiring | UI | [Entry Point and Wiring](#entry-point-and-wiring-normative) | — |
| LibVLC integration (`LibVlcPlayerHandle` wiring) | UI | [§2.6.1](#261-public-api-exposed-to-system) | F22 |
| GamePhase FSM | PlaybackCoordinator | [§4.1](#41-gamephase-fsm) | F22 |

**DOD**:
- [ ] App discovers phone via mDNS, completes handshake
- [ ] Song list displays songs from phone manifest
- [ ] Select song → plays audio, shows sentence-paged lyrics
- [ ] Back → returns to song list
- [ ] F15 session lifecycle passes
- [ ] F22 GamePhase FSM passes
- [ ] Runs on emulator
- [ ] Peer-boundary behavior covered by direct WebSocket/UDP tests plus targeted instrumented checks

**Peer Test Utilities**: Prefer direct test clients and fakes; no general mock-phone harness required.

## 7.4 Iter 2 — Scored Singing + Pitch Pipeline

**Goal**: Complete scoring loop — pitch frames flow, scores accumulate, results display.

| Deliverable | Component | Spec Ref | Fixtures |
|-------------|-----------|----------|----------|
| Clock sync protocol | PlaybackCoordinator | [§2.1](#21-playbackcoordinator) | F14v2, F21 |
| UDP listener | NetworkController | [§2.3](#23-networkcontroller) | F12v2 |
| Pitch frame validation | NetworkController | [§2.3](#23-networkcontroller) | — |
| Jitter buffer | ScoringEngine | [§5.2.3](#523-jitter-buffer-behavior) | F13 |
| Scoring coroutine | ScoringEngine | [§2.2](#22-scoringengine) | F08, F24 |
| Pitch lane UI | UI: SingingScreen | [§2.6.6](#266-pitch-lane-rendering-architecture), [§2.6.16](#2616-singingscreen-behavior) | — |
| Live score display | UI: SingingScreen | [§2.6.16](#2616-singingscreen-behavior) | — |
| Results screen | UI: ResultsScreen | [§2.6.18](#2618-resultsscreen) | — |

**DOD**:
- [ ] Clock sync completes before song start
- [ ] Pitch frames flow from phone → jitter buffer → scoring
- [ ] Pitch lane shows live cursor
- [ ] Score updates in real-time
- [ ] Song ends → Results screen shows final score
- [ ] F13, F21, F24 pass
- [ ] Perfect mock performance → `scoreTotalInt == 10000`

**Peer Test Utilities**: Prefer direct UDP sender tests. Construct datagrams inline for small cases; use replay fixtures only when timing-sensitive data is reused across tests.

## 7.5 Iter 3 — Multiplayer + Duet + Polish

**Goal**: 2-player support, duet songs, production-quality UX.

| Deliverable | Component | Spec Ref | Fixtures |
|-------------|-----------|----------|----------|
| 2-phone handling | NetworkController | [§2.3](#23-networkcontroller) | F23 |
| P1/P2 assignment | PlaybackCoordinator | [§2.6.16](#2616-singingscreen-behavior) | F23 |
| Duet chart routing | UsdxParser, ScoringEngine | [§2.4](#24-usdxparser), [§2.2](#22-scoringengine) | F23, F24 |
| Disconnect/reconnect | PlaybackCoordinator | [§2.3](#23-networkcontroller) | F23 |
| Pause overlay | UI: SingingScreen | [§2.6.11](#2611-interruption-overlay-shell) | F22 |
| Settings screens | UI: SettingsScreen | [§2.6.15](#2615-settingsscreen) | — |
| Video backgrounds | UI: SingingScreen | [§2.6.16](#2616-singingscreen-behavior) | — |
| Instrumental + vocals mixing | Phone (see phone spec) | Phone pre-mixes before serving; no TV deliverable | — |

**DOD**:
- [ ] Two phones connect, both appear in SelectPlayers
- [ ] Duet song → P1 sings track 1, P2 sings track 2
- [ ] Swap Parts works
- [ ] Singer disconnect → pause overlay, reconnect resumes
- [ ] All settings screens functional
- [ ] Video background plays
- [ ] F04, F23 pass
- [ ] Demo: Two people sing a duet

**Peer Test Utilities**: Use lightweight WebSocket test clients to simulate disconnect/reconnect and multi-phone session behavior. A full mock-phone harness is not required.

## 7.6 Iter 4 — Medley + Hardening

**Goal**: Medley mode complete, performance optimized, MVP shippable.

| Deliverable | Component | Spec Ref | Fixtures |
|-------------|-----------|----------|----------|
| Medley playlist UI | UI: SongListScreen | [§2.6.12](#2612-songlistscreen-behavior) | — |
| Medley sequencer | PlaybackCoordinator | [§4.2](#42-medley-queue-management) | F16 |
| Segment transitions | PlaybackCoordinator + UI | [§4.2](#42-medley-queue-management), [§2.6.17](#2617-singingscreen-medley-mode) | F16 |
| Audio prebuffer/crossfade | UI (LibVLC) | [§4.2](#42-medley-queue-management) | — |
| Medley scoring windows | ScoringEngine | [§6.6](#66-medley-aggregation) | F11 |
| Medley results | UI: ResultsScreen | [§2.6.18](#2618-resultsscreen) | — |
| Preview playback | UI: SongListScreen | [§2.6.12](#2612-songlistscreen-behavior) | — |
| Search/filter | UI: SongListScreen | [§2.6.12](#2612-songlistscreen-behavior) | — |
| Device tuning | All | [§1.1](#11-testability), [§1.6](#16-minimal-footprint) | — |

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

**Peer Test Utilities**: Use targeted test doubles for peer behavior. Keep medley validation focused on coordinator logic plus small instrumented playback checks.

---

# Appendix A: Peer-Boundary Test Utilities

A general mock-phone harness is NOT required. Test only the TV-owned boundary using the smallest utilities that exercise app behavior directly.

## A.1 Scope

Use these utilities only for behavior that cannot be covered cleanly by pure unit tests:

- WebSocket session handshake and validation
- disconnect / reconnect handling
- UDP pitch-frame ingress and validation
- a small number of targeted instrumented checks where Android runtime behavior matters

Do NOT build or maintain a separate simulated phone application unless later evidence shows the smaller approach is insufficient.

## A.2 Preferred Test Shapes

| Boundary | Preferred test shape | Notes |
|---------|-----------------------|-------|
| Parser, scoring math, jitter buffer, FSM, clock-sync math | Pure unit tests | Use fixtures/fakes; no sockets required. |
| WebSocket control path | Lightweight WebSocket test client | Exercise `hello`, session lock, protocol mismatch, disconnect, reconnect. |
| UDP pitch ingress | Direct UDP sender from test code | Send real datagrams to the listener; assert emitted `PitchFrame` values or downstream effects. |
| HTTP client behavior | Small instrumented smoke test | Keep this narrow; do not justify a general harness with HTTP alone. |
| Media3 / Android timing | Instrumented test | Cover runtime-specific behavior separately from peer simulation. |

## A.3 UDP Test Data Policy

For UDP ingress tests, prefer constructing binary datagrams inline in the test. This keeps simple cases obvious and avoids unnecessary fixture churn.

Use fixture or replay files only when one of the following is true:
- the same frame sequence is reused across multiple tests
- relative timing between frames is itself under test
- a regression case is easier to preserve as captured data than as generated code

For a basic valid-frame test, a single hardcoded 20-byte datagram in the test is preferred over a separate fixture file.

## A.4 Disconnect / Reconnect Coverage

Disconnect and reconnect handling is NOT mere transport plumbing; it is required app behavior and MUST be tested. At minimum cover:

1. required singer disconnect during singing → `DisconnectPaused` behavior
2. reconnect with same `clientId` → new `connectionId` assignment
3. resend of `assignSinger` after reconnect
4. resend of current `playbackState` after reconnect
5. rejection of stale UDP frames carrying the old `connectionId`

These tests may use lightweight WebSocket clients and direct UDP senders. They do not require a general-purpose phone harness.

## A.5 Minimal Utility Surface

If shared helpers are needed, keep them small and local to tests:

- WebSocket test client helper
- UDP datagram builder / sender helper
- optional replay helper for timing-sensitive pitch streams

Avoid adding song serving, asset hosting, or phone-side UI behavior to this layer unless a specific failing test proves it is necessary.

## A.6 Acceptance Principle

The testing goal is to verify TV-host behavior at the external peer boundary, not to simulate an entire phone implementation. Favor direct tests of the owned boundary over broad end-to-end scaffolding.

---

# Appendix B: Protocol JSON Schemas

This appendix is **normative**. Schemas use JSON Schema Draft 2020-12. `additionalProperties: false` keeps fixtures deterministic.

## B.1 Common Envelope

All messages MUST include:
- `type` (string)
- `protocolVersion` (int; MUST be `1` in MVP)
- `tsTvMs` (optional; TV may include)

## B.2 Schemas

### B.2.1 `hello`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "hello",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "protocolVersion", "clientId", "deviceName", "appVersion", "httpPort"],
  "properties": {
    "type": {"const": "hello"},
    "protocolVersion": {"type": "integer", "const": 1},
    "clientId": {"type": "string", "minLength": 8},
    "deviceName": {"type": "string", "minLength": 1},
    "appVersion": {"type": "string", "minLength": 1},
    "httpPort": {"type": "integer", "minimum": 1024, "maximum": 65535}
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
    "tsTvMs": {"type": ["number", "null"]},
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
          "properties": {
            "connected": {"type": "boolean"},
            "deviceName": {"type": "string"}
          }
        },
        "P2": {
          "type": "object",
          "additionalProperties": false,
          "required": ["connected", "deviceName"],
          "properties": {
            "connected": {"type": "boolean"},
            "deviceName": {"type": "string"}
          }
        }
      }
    },
    "inSong": {"type": "boolean"},
    "songTimeSec": {"type": ["number", "null"]},
    "connectionId": {
      "type": ["integer", "null"],
      "description": "uint16; present only in initial sessionState response to hello. Null or absent in broadcast sessionState messages."
    }
  }
}
```

### B.2.3 `ping` / `pong` (clock sync)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ping_or_pong",
  "oneOf": [
    {"$ref": "#/$defs/ping"},
    {"$ref": "#/$defs/pong"}
  ],
  "$defs": {
    "ping": {
      "title": "ping",
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "protocolVersion", "pingId", "tTvSendMs"],
      "properties": {
        "type": {"const": "ping"},
        "protocolVersion": {"type": "integer", "const": 1},
        "tsTvMs": {"type": "number"},
        "pingId": {"type": "string", "minLength": 1},
        "tTvSendMs": {"type": "integer"}
      }
    },
    "pong": {
      "title": "pong",
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "protocolVersion", "pingId", "tTvSendMs", "tPhoneRecvMs", "tPhoneSendMs"],
      "properties": {
        "type": {"const": "pong"},
        "protocolVersion": {"type": "integer", "const": 1},
        "tsTvMs": {"type": "number"},
        "pingId": {"type": "string", "minLength": 1},
        "tTvSendMs": {"type": "integer"},
        "tPhoneRecvMs": {"type": "integer"},
        "tPhoneSendMs": {"type": "integer"}
      }
    }
  }
}
```

### B.2.4 `clockAck` (TV → Phone)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "clockAck",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "protocolVersion", "pingId", "tTvRecvMs"],
  "properties": {
    "type": {"const": "clockAck"},
    "protocolVersion": {"type": "integer", "const": 1},
    "tsTvMs": {"type": "number"},
    "pingId": {"type": "string", "minLength": 1},
    "tTvRecvMs": {"type": "integer"}
  }
}
```

### B.2.5 `error`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "error",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "protocolVersion", "code", "message"],
  "properties": {
    "type": {"const": "error"},
    "protocolVersion": {"type": "integer", "const": 1},
    "tsTvMs": {"type": "number"},
    "code": {"type": "string", "minLength": 1},
    "message": {"type": "string", "minLength": 1}
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
  "required": [
    "type", "protocolVersion", "sessionId", "songInstanceSeq",
    "playerId", "difficulty",
    "startMode", "stopAtLyricsTimeMs", "udpPort", "songTitle", "songArtist"
  ],
  "properties": {
    "type": {"const": "assignSinger"},
    "protocolVersion": {"type": "integer", "const": 1},
    "tsTvMs": {"type": ["number", "null"]},
    "sessionId": {"type": "string", "minLength": 1},
    "songInstanceSeq": {"type": "integer", "minimum": 0},
    "playerId": {"type": "string", "enum": ["P1", "P2"]},
    "difficulty": {"type": "string", "enum": ["Easy", "Medium", "Hard"]},
    "startMode": {"type": "string", "enum": ["countdown", "live"]},
    "countdownMs": {"type": ["integer", "null"], "minimum": 0},
    "stopAtLyricsTimeMs": {"type": "integer", "minimum": 0},
    "udpPort": {"type": "integer", "minimum": 1024, "maximum": 65535},
    "songTitle": {"type": "string"},
    "songArtist": {"type": "string"}
  },
  "allOf": [
    {
      "if": {"properties": {"startMode": {"const": "countdown"}}},
      "then": {"required": ["countdownMs"]}
    }
  ]
}
```

### B.2.7 `playbackState`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "playbackState",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "type", "protocolVersion", "sessionId", "songInstanceSeq",
    "revision", "state", "lyricsTimeMs", "stopAtLyricsTimeMs", "reason"
  ],
  "properties": {
    "type": {"const": "playbackState"},
    "protocolVersion": {"type": "integer", "const": 1},
    "sessionId": {"type": "string", "minLength": 1},
    "songInstanceSeq": {"type": "integer", "minimum": 0},
    "revision": {"type": "integer", "minimum": 0},
    "state": {"type": "string", "enum": ["countdown", "playing", "paused", "stopped"]},
    "lyricsTimeMs": {"type": "integer", "minimum": 0},
    "stopAtLyricsTimeMs": {"type": "integer", "minimum": 0},
    "countdownRemainingMs": {"type": ["integer", "null"], "minimum": 0},
    "reason": {
      "type": "string",
      "enum": ["", "user_pause", "singer_disconnected", "song_end", "user_quit", "restart", "segment_transition", "medley_source", "medley_end"]
    },
    "tsTvMs": {"type": ["number", "null"]}
  },
  "allOf": [
    {
      "if": {"properties": {"state": {"const": "countdown"}}},
      "then": {"required": ["countdownRemainingMs"]}
    }
  ]
}
```

### B.2.8 `pitchFrame` (binary UDP — no JSON schema)

See [§2.3](#23-networkcontroller) Pitch Frame Wire Format for the full 20-byte layout. Reference:
```
Offset  Size  Type    Field
  0      4   uint32  seq
  4      8   int64   tvTimeMs
 12      4   uint32  songInstanceSeq
 16      1   uint8   playerId     (0=P1, 1=P2)
 17      1   uint8   midiNote     (0-127 voiced; 255=unvoiced)
 18      2   uint16  connectionId
Struct: <IqIBBH (little-endian)
```

### B.2.9 `SongEntry` (HTTP `/manifest.json` response element)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SongEntry",
  "type": "object",
  "required": [
    "relativeTxtPath", "modifiedTimeMs", "title", "artist",
    "isDuet", "hasRap", "hasVideo", "hasInstrumental", "canMedley",
    "startSec", "previewStartSec", "txtUrl", "audioUrl"
  ],
  "properties": {
    "relativeTxtPath": {"type": "string", "minLength": 1},
    "modifiedTimeMs": {"type": "integer"},
    "title": {"type": "string"},
    "artist": {"type": "string"},
    "album": {"type": ["string", "null"]},
    "year": {"type": ["integer", "null"]},
    "genre": {"type": ["string", "null"]},
    "isDuet": {"type": "boolean"},
    "hasRap": {"type": "boolean"},
    "hasVideo": {"type": "boolean"},
    "hasInstrumental": {"type": "boolean"},
    "canMedley": {"type": "boolean"},
    "medleySource": {"type": ["string", "null"], "enum": ["tag", null]},
    "medleyStartBeat": {"type": ["integer", "null"]},
    "medleyEndBeat": {"type": ["integer", "null"]},
    "startSec": {"type": "number"},
    "previewStartSec": {"type": "number"},
    "txtUrl": {"type": "string", "format": "uri"},
    "audioUrl": {"type": "string", "format": "uri"},
    "videoUrl": {"type": ["string", "null"], "format": "uri"},
    "coverUrl": {"type": ["string", "null"], "format": "uri"},
    "backgroundUrl": {"type": ["string", "null"], "format": "uri"},
    "hasInstrumental": {"type": "boolean"}
  }
}
```

---

# Appendix E: Worked Examples

Numeric reference examples to remove ambiguity in timing/beat conversion ([§4.6](#46-beat-time-conversion)), note-window boundaries ([§4.3](#43-scoring-coroutine), [§2.2](#22-scoringengine)), scoring normalization ([§2.2](#22-scoringengine)), and line bonus/rounding ([§2.2](#22-scoringengine)). These examples are the reference for fixtures F06, F08, F24.

## E.1 Static BPM — Highlight Cursor and Note Scoring Windows

Given:
- `BPM_file = 120.0`, `BPM_internal = 120.0 × 4 = 480.0`
- `beatsPerSec = 480.0 / 60.0 = 8.0`
- `GAPms = 2000`, `micDelayMs = 100`, `songStartTvMs = 50000`
- `lyricsTimeSec = 5.0`

**Highlight cursor** (lyrics beat, `micDelayMs = 0`):
- `highlightTimeSec = 5.0 − 2.0 = 3.0`
- `MidBeat_internal = 3.0 × 8.0 = 24.0` → `CurrentBeat = floor(24.0) = 24`

**Note scoring window** (note `startBeatFile=20`, `durationBeats=4`):
- `noteStartTvMs = 50000 + (20 × 15000 / 120) + 2000 + 100 = 54600`
- `noteEndTvMs   = 50000 + (24 × 15000 / 120) + 2000 + 100 = 55100`
- Frames with `54600 <= tvTimeMs < 55100` are collected.
- Note finalized at `55100 + 450 = 55550`.

## E.2 Beat-to-Time and Time-to-Beat Round-Trip

Given `BPM_file=120`, `BPM_internal=480`, `GAPms=2000`:

Beat 24 → `lyricsTimeSec`:
- `chartSec = 24 × (60 / 480) = 3.0`
- `lyricsTimeSec = 3.0 + 2.0 = 5.0`

Round-trip `lyricsTimeSec=5.0` → beat:
- `highlightTimeSec = 5.0 − 2.0 = 3.0`
- `MidBeat = 3.0 × 8.0 = 24.0` → `CurrentBeat = 24` ✓

## E.3 Note-Window Boundary Convention

Note: `startBeatFile=11`, `durationBeats=2` → `endBeatFileExclusive=13`.

- Frame at beat 11: **included** (`11 <= 11 < 13`)
- Frame at beat 12: **included** (`11 <= 12 < 13`)
- Frame at beat 13: **excluded** (belongs to next note)

In TV time:
```
noteStartTvMs = songStartTvMs + (11 × 15000 / BPM_file) + GAPms + micDelayMs
noteEndTvMs   = songStartTvMs + (13 × 15000 / BPM_file) + GAPms + micDelayMs
Frame included if: noteStartTvMs <= frame.tvTimeMs < noteEndTvMs
```

## E.4 Scoring Normalization and Line Bonus (Fully-Worked)

Setup: Line bonus ON, `MaxSongPoints=9000`, `MaxLineBonusPool=1000`, `BPM_file=120`, `GAPms=0`, `micDelayMs=0`, `songStartTvMs=10000`, pitch rate 50 fps.

Minimal 2-line solo chart:
```
: 0 4 0 la       (Normal,  startBeat=0, duration=4, tone=0)
- 4
* 4 4 0 la       (Golden,  startBeat=4, duration=4, tone=0)
- 8
E
```

**TrackScoreValue**: `(4×1) + (4×2) = 12`

**Note scoring windows**:
- Note 1 (Normal, beats 0–4): `noteStartTvMs=10000`, `noteEndTvMs=10500` → ~25 frames at 50fps
- Note 2 (Golden, beats 4–8): `noteStartTvMs=10500`, `noteEndTvMs=11000` → ~25 frames

**Per-note max scores**:
- Note 1: `(9000/12) × 1 × 4 = 3000`
- Note 2: `(9000/12) × 2 × 4 = 6000`
- Sum = 9000 ✓

**Perfect performance** (all 25 frames hit per note):
- `Player.Score = 3000`, `Player.ScoreGolden = 6000`

Line bonus:
- `LineBonusPerLine = 1000 / 2 = 500`
- Line 1: `LinePerfection = clamp(3000 / (3000−2), 0, 1) = 1` → `ScoreLine += 500`
- Line 2: `LinePerfection = clamp(6000 / (6000−2), 0, 1) = 1` → `ScoreLine += 500`
- `Player.ScoreLine = 1000`

Rounding:
- `ScoreLineInt = floor(round(1000)/10)×10 = 1000`
- `ScoreInt = round(3000/10)×10 = 3000`
- `ScoreInt < Player.Score` is FALSE → `ScoreGoldenInt = floor(6000/10)×10 = 6000`
- `ScoreTotalInt = 3000 + 6000 + 1000 = 10000` ✓

**Partial performance** (Note 1: 20/25 hit; Note 2: 15/25 hit):
- `Player.Score = 3000×(20/25) = 2400`, `Player.ScoreGolden = 6000×(15/25) = 3600`
- Line 1: `LinePerfection = clamp(2400/2998, 0, 1) = 0.8005...` → `ScoreLine += 400.26...`
- Line 2: `LinePerfection = clamp(3600/5998, 0, 1) = 0.6002...` → `ScoreLine += 300.10...`
- `Player.ScoreLine = 700.36...`

## E.5 Golden Rounding Direction Rule

Demonstrates the "golden rounds opposite" rule to prevent `ScoreTotalInt > 10000`.

Given: `Player.Score = 4090.909...`, `Player.ScoreGolden = 100.909...`

- `ScoreInt = round(4090.909/10)×10 = 4090`
- `ScoreInt (4090) < Player.Score (4090.909)` is TRUE → apply **ceil** for golden:
  - `ScoreGoldenInt = ceil(100.909/10)×10 = 110`

## E.6 Minimal Fixture Layout for E.4

```
fixtures/E4_score_linebonus_perfect/
├── song.txt                  # 2-line chart from E.4
└── expected.score.json       # Contains: MaxSongPoints, MaxLineBonusPool,
                              # TrackScoreValue, per-note max_note_score/hits/N/note_score,
                              # Score, ScoreGolden, ScoreLine, ScoreInt, ScoreGoldenInt,
                              # ScoreLineInt, ScoreTotalInt
```

`pitchFrames.jsonl` is OPTIONAL if the test harness injects hit counts directly. If using the full pipeline, provide frames at 50fps with `toneValid=true` and matching `midiNote` for hit frames.

---

*Document updated: 2026-04-21*