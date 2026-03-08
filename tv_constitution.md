cl# Project Constitution — Karaoke TV Host App (Android)
> Non-negotiable. Read before every task. Violations must be flagged, not silently worked around.

---

## 1. Identity & Scope
Android TV Host App for a local-network karaoke game. Responsibilities:
1. Act as the session host and authoritative game engine.
2. Aggregate the song library metadata from connected phones via HTTP.
3. Stream audio and video assets directly from phones over HTTP (no local storage).
4. Compute timing, process UDP pitch frames from clients, and evaluate scores.
5. Display the primary game UI (Song List, Select Players, Singing, Results).
No backend. No local song library persistence. LAN only.

---

## 2. Technology Constraints
| Concern | Mandatory | Forbidden |
|---|---|---|
| Language | Kotlin 2.1+ | Java, mixed new files |
| UI | Jetpack Compose for TV (`androidx.tv:tv-material`) | XML layouts (new code) |
| Concurrency | Coroutines + `Flow` | RxJava, LiveData, raw `Thread` |
| JSON Serialization | `kotlinx-serialization-json` (`1.7.3`) | Gson, Moshi, reflection-based parsing |
| Media Playback | `androidx.media3` (`1.6.1`), `datasource-okhttp` | Legacy ExoPlayer, MediaPlayer |
| Image Loading | `coil-compose` + `coil-network-okhttp` (`3.4.0`) | Glide, Picasso |
| Network Discovery | `jmdns` (`3.5.9`) with `MulticastLock` | Android `NsdManager` (unreliable on TV) |
| Network Transport | `ktor-server-cio` + `websockets` (`3.3.0`) | Netty engine, Retrofit for WebSocket |
| UDP Receiver | `DatagramSocket` (fixed port at session start) | Batching frames, TCP for pitch |
| Persistence | `DataStore` (prefs only, `1.1.1`) | Room, SQLite, persisted song lists |
| QR Code | `zxing-android-embedded` (`4.3.0`) | Requesting Camera permission on TV |
| DI | Hilt `2.59+` | Koin, manual Dagger |
| **Testing Stacks** | **Unit:** JUnit 5 (`5.10+`), MockK (`1.13+`), Turbine (`1.2.x`) | JUnit 4, Robolectric for UI |

---

## 3. Architecture: MVVM + Clean Domain

```text
app/
├── domain/            # Pure Kotlin — zero Android imports
│   ├── model/         # Immutable data (ParsedSong, PlayerScore, etc.)
│   ├── usecase/       # Suspend funs / flows
│   └── engine/        # Timing and scoring evaluation
├── data/
│   ├── library/       # Aggregates HTTP song fetching
│   └── network/       # Ktor WS Server, UDP Receiver, jmDNS advertiser
├── presentation/
│   ├── list/          # Song list & Preview
│   ├── session/       # Join QR / Connect Phones settings
│   └── singing/       # Media3 UI, lyrics render, pitch lanes
└── di/                # Hilt modules only
```

Rules: ViewModels expose `StateFlow<UiState>` + `SharedFlow<UiEvent>`. No business logic in Composables. All Android-framework types stay in `data/` or `di/`. `@Inject constructor` everywhere.

---

## 4. Playback & Scoring Engine
* **Media Streaming:** The TV holds NO song files. Audio and video must be streamed progressively via `Media3` directly from the phone's HTTP URL. Do NOT build or extract ZIP packages.
* **Audio Mixing:** Use `MergingMediaSource` + `ScalingAudioProcessor` for instrumental and vocal track mixing. Do NOT use `player.setVolume()` for per-track mix control.
* **Scoring Loop Isolation:** Scoring evaluation MUST run on a dedicated coroutine polling `ExoPlayer.getCurrentPosition()` every **10 ms (100 Hz)**. Scoring must be fully decoupled from the UI render frame rate.

---

## 5. Networking
* **Discovery (mDNS):** Advertise `_karaoke._tcp` using `jmdns`. You MUST acquire a `WifiManager.MulticastLock` on session start and release it on end.
* **Control (WebSocket):** TV acts as the Ktor server on `/`. Reject mismatched `protocolVersion` or invalid tokens instantly.
* **Pitch (UDP):** Expect fixed 16-byte binary frames. Drop invalid frames silently based on `connectionId`.
* **Cleartext HTTP:** Configure `network_security_config.xml` to permit RFC-1918 class A/B/C cleartext traffic for HTTP file streaming from phones.

---

## 6. Testing
All code modifications require test coverage. Before writing, modifying, or 
reviewing any tests, you MUST retrieve and read `testing_policy.md` first.
Test library versions are pinned in §2 Technology Constraints above.

---

## 7. Code Quality
* `ktlint` — zero warnings in CI.
* `detekt` — cyclomatic complexity < 10 per function.
* `Timber` — `DebugTree` in debug builds only.
* Sealed classes for `UiState` + `UiEvent` and network messages.
* No `// TODO` / `// FIXME` in merged code.

---

## 8. Performance (Baseline: Android TV standard hardware)
| Metric | Target |
|---|---|
| Main thread / Compose UI | 60fps — no frame drops during lyrics highlight |
| Scoring evaluation | < 2ms per 10ms tick (on IO/Default dispatcher) |
| Parse & Play latency | < 2s from "Start" click to Exoplayer buffering |
| Memory usage | < 150MB |

---

## 9. Consistency Checklist (after every task)
- [ ] Modified files have corresponding test coverage (per `testing_policy.md`)
- [ ] No reflection-based serialization (Gson/Moshi) introduced in hot paths
- [ ] Scoring loop remains decoupled from UI thread (10ms poll maintained)
- [ ] Zero local storage used for remote song assets (direct ExoPlayer HTTP streaming confirmed)
- [ ] New WebSocket messages mirrored in schema tests
- [ ] New dependency → justified in `libs.versions.toml` with `// DECISION:` comment