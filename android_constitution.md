# Project Constitution — Karaoke Companion App (Android)
> Non-negotiable. Read before every task. Violations must be flagged, not silently worked around.
---
## 1. Identity & Scope
Android Companion App for a local-network karaoke game. Responsibilities:
1. Discover and pair with the Android TV Host via mDNS.
2. Scan local songs folder (SAF) and serve assets to TV via HTTP.
3. Capture microphone audio, detect pitch, stream results to Host.
4. Display real-time score + lyrics from Host.
5. Act as D-pad controller when not singing.
No backend cloud services. LAN only.
---
## 2. Technology Constraints
| Concern | Mandatory | Forbidden |
|---|---|---|
| Language | Kotlin 2.1+ | Java, mixed new files |
| UI | Jetpack Compose (BOM `2026.02.01`+) | XML layouts (new code) |
| Concurrency | Coroutines + `Flow` | RxJava, LiveData, raw `Thread` |
| JSON Serialization | `kotlinx-serialization-json` (match TV host version) | Gson, Moshi, reflection-based parsing |
| Audio capture | `AudioRecord` (Java API, direct) | Oboe, TarsosDSP, MediaRecorder |
| FFT Operations | `com.github.wendykierp:JTransforms` (`3.2`) | Any other math/FFT library |
| Network Discovery | `NsdManager` (`_karaoke._tcp`) | Hardcoded IPs, Wi-Fi Direct |
| Network Transport | `DatagramSocket` UDP, OkHttp `5.3.0` WebSocket | gRPC, REST for control |
| HTTP File Server | `io.ktor:ktor-server-cio` + `io.ktor:ktor-server-partial-content` (`3.3.0`) | Any other server engine |
| SAF Traversal | `androidx.documentfile:documentfile` (`1.0.1`) | `java.io.File` on SAF URIs |
| QR Scanning | `com.google.mlkit:barcode-scanning` (`17.3.0`) + `camera-camera2/lifecycle/view` (`1.3.4`) | ZXing direct, manual image decode |
| Persistence | `DataStore` (prefs only) | Room, SQLite |
| DI | Hilt `2.59+` | Koin, manual Dagger |
| **Testing Stacks** | **Unit:** JUnit 5 (`5.10+`), MockK (`1.13+`), Turbine (`1.2.x`). **Instrumented:** Espresso (`3.5.1`), `androidx.test:runner` (`1.5.2`) | JUnit 4, Robolectric (for UI-only logic) |
| **Test Utilities** | `kotlinx-coroutines-test` & `kotlinx-serialization-json` (must match prod versions) | Hardcoded `Dispatchers.Main` or `Dispatchers.IO` in testable code |
| Min SDK | API 26 (Android 8.0) | API 28+ without `@RequiresApi` + fallback |
---
## 3. Architecture: MVVM + Clean Domain
```text
app/
├── domain/            # Pure Kotlin — zero Android imports
│   ├── model/         # Data classes, immutable (val)
│   ├── usecase/       # Suspend funs, one class each
│   └── repository/    # Interfaces only
├── data/
│   ├── audio/         # AudioRecord pipeline + pitch detection
│   ├── network/       # NsdManager wrapper, OkHttp WebSocket, UDP
│   ├── server/        # Ktor HTTP server + SAF-backed request handler
│   └── storage/       # SAF bookmark resolution and persistence
├── presentation/
│   ├── pairing/
│   ├── singing/
│   └── lobby/
└── di/                # Hilt modules only
```
Rules: ViewModels expose `StateFlow<UiState>` + `SharedFlow<UiEvent>`. No business logic in Composables. All Android-framework types (`Context`, `Resources`) stay in `data/` or `di/`. `@Inject constructor` everywhere — no `companion object` factories.
---
## 4. Audio Capture Pipeline
```text
Mic → AudioRecord (PCM_FLOAT)
    → Pre-allocated FloatArray ring buffer [coroutine producer]
    → Pitch detection processing [IO dispatcher]
    → DatagramSocket UDP → Host
```
Latency budget: **≤ 50ms** mic-to-UDP. `RECORD_AUDIO` permission checked in ViewModel before session start.
**Zero-Allocation Hot Loops:** All audio capture, buffering, and DSP must use pre-allocated primitive arrays (`FloatArray`, `DoubleArray`). No new object instantiation, boxed primitives, or complex data class construction inside the audio read-and-process loop. All buffers allocated at session initialisation and reused throughout.
---
## 5. HTTP File Server
- Server MUST start before `hello` is sent to the TV; `httpPort` in `hello` must reflect the actual bound port.
- Default port `34781`; fall back to any available ephemeral port if unavailable.
- All file access MUST go through `ContentResolver` / `DocumentFile` — never `java.io.File(path)` on SAF URIs.
- Must support HTTP `Range` requests (`206 Partial Content`, `Content-Range`, `Accept-Ranges: bytes`).
- Acquire `WifiManager.MulticastLock` (tag: `"karaoke_multicast"`) during mDNS browsing; release on discovery end.
---
## 6. Networking
* **Discovery:** Browse `_karaoke._tcp` via `NsdManager`, wrapped in `callbackFlow`.
* **Control:** OkHttp WebSocket client to Ktor server on TV. JSON ≤ 4KB. Reconnect: coroutine `retry` + exponential backoff.
* **Pitch:** `DatagramSocket` UDP. Fixed 16-byte binary frames, no batching, no TCP.
* No auth, no encryption (LAN-only, v1).
---
## 7. Testing
All code modifications require test coverage. Before writing, modifying, or reviewing any tests, you MUST retrieve and read `testing_policy.md` first. Test library versions are pinned in §2 above.
---
## 8. Code Quality
* `ktlint` — zero warnings in CI.
* `detekt` — cyclomatic complexity < 10 per function.
* `Timber` — `DebugTree` in debug builds only.
* Sealed classes for `UiState` + `UiEvent`.
* No `// TODO` / `// FIXME` in merged code.
---
## 9. Performance (Baseline: Pixel 3a, 2019)
| Metric | Target |
|---|---|
| Cold launch → pairing screen | < 2s |
| LAN discovery | < 3s |
| Mic-to-UDP latency | < 50ms |
| Main thread | 60fps — zero audio/network/server work |
| Memory (singing) | < 100MB |
| APK size | < 15MB |
---
## 10. Consistency Checklist (after every task)
- [ ] Every modified file has corresponding test coverage updated or created
- [ ] Zero allocation in audio hot-loops verified
- [ ] HTTP server started before `hello` is sent; `httpPort` reflects actual bound port
- [ ] All song file access via `ContentResolver`/`DocumentFile` — no bare `File()` on SAF URIs
- [ ] No unintended side effects introduced to adjacent system components
- [ ] New interface → `Fake` in `data/testing/`
- [ ] New ViewModel state → sealed class updated + Turbine test added
- [ ] New network message → mirrored in `MessageSchema.kt` (must match iOS repo)
- [ ] New dependency → justified in `libs.versions.toml` with `// DECISION:` comment