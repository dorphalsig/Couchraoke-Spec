# Project Constitution — Karaoke Companion App (Android)
> Non-negotiable. Read before every task. Violations must be flagged, not silently worked around.
---
## 1. Identity & Scope
Android Companion App for a local-network karaoke game. Responsibilities:
1. Discover and pair with the Android TV Host via mDNS.
2. Capture microphone audio, detect pitch, stream results to Host.
3. Display real-time score + lyrics from Host.
4. Act as D-pad controller when not singing.
No backend. No song library. LAN only.
---
## 2. Technology Constraints
| Concern | Mandatory | Forbidden |
|---|---|---|
| Language | Kotlin 2.1+ | Java, mixed new files |
| UI | Jetpack Compose (BOM `2026.02.01`+) | XML layouts (new code) |
| Concurrency | Coroutines + `Flow` | RxJava, LiveData, raw `Thread` |
| Audio capture | `AudioRecord` (Java API, direct) | Oboe, TarsosDSP, MediaRecorder |
| FFT Operations | `edu.emory.mathcs.jtransforms:jtransforms` (2.4) | any other math library |
| Network Discovery | `NsdManager` (`_karaoke._tcp`) | Hardcoded IPs, Wi-Fi Direct |
| Network Transport | `DatagramSocket` UDP, OkHttp `5.3.x` WebSocket | gRPC, REST for control |
| Persistence | `DataStore` (prefs only) | Room, SQLite |
| DI | Hilt `2.59+` | Koin, manual Dagger |
| **Testing Stacks** | **Unit:** JUnit 5 (`5.10+`), MockK (`1.13+`), Turbine (`1.2.x`). **Instrumented:** Espresso (`3.5.1`), `androidx.test:runner` (`1.5.2`) | JUnit 4 (`@RunWith`, `@Test` from `org.junit`), Robolectric (for UI-only logic) |
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
│   ├── audio/         # AudioRecord pipeline + Pitch detection
│   └── network/       # NsdManager wrapper, OkHttp socket
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
**Zero-Allocation Hot Loops:** * All audio capture, buffering, and DSP must be executed using pre-allocated primitive arrays (e.g., `FloatArray`, `DoubleArray`).
* Instantiating new objects, returning complex data classes, or utilizing boxed primitives within the audio read-and-process loop is strictly forbidden.
* Any required buffers or mathematical arrays must be allocated during session initialization and continually reused.
---
## 5. Networking
* **Discovery:** `NsdManager` on `_karaoke._tcp`, wrapped in `callbackFlow`.
* **Control:** OkHttp WebSocket. JSON ≤ 4KB. Reconnect: coroutine `retry` + exponential backoff.
* **Audio:** `DatagramSocket` UDP. Packet contains pitch and timestamp data.
* No auth, no encryption (v1 — LAN party game).
---
## 6. Testing
All code modifications require strict test coverage. **Before writing, modifying, or reviewing any tests, you MUST read and comply with the rules defined in `testing_policy.md`.**
**High-Level Mandates:**
* **Coverage:** Any file modified or created during a task must be accompanied by corresponding unit or integration tests verifying the new behavior.
* **Side-Effect Isolation:** Tests must explicitly verify the absence of unintended side effects in adjacent domains.
* **Architecture:** `UnconfinedTestDispatcher` is forbidden; use `StandardTestDispatcher` injected via constructor.
* **Fakes:** Provide one `Fake` per repository interface in `data/testing/`.
---
## 7. Code Quality
* `ktlint` — zero warnings in CI.
* `detekt` — cyclomatic complexity < 10 per function.
* `Timber` — `DebugTree` in debug builds only.
* Sealed classes for `UiState` + `UiEvent`.
* No `// TODO` / `// FIXME` in merged code.
---
## 8. Performance (Baseline: Pixel 3a, 2019)
| Metric | Target |
|---|---|
| Cold launch → pairing screen | < 2s |
| LAN discovery | < 3s |
| Mic-to-UDP latency | < 50ms |
| Main thread | 60fps — zero audio/network work |
| Memory (singing) | < 100MB |
| APK size | < 15MB |
---
## 9. Consistency Checklist (after every task)
- [ ] Every modified file has corresponding test coverage updated or created
- [ ] Zero allocation in audio hot-loops verified
- [ ] No unintended side effects introduced to adjacent system components
- [ ] New interface → `Fake` in `data/testing/`
- [ ] New ViewModel state → sealed class updated + Turbine test added
- [ ] New network message → mirrored in `MessageSchema.kt` (must match iOS repo)
- [ ] New dependency → justified in `libs.versions.toml` with `// DECISION:` comment