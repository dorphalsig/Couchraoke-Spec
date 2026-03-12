# Project Constitution — Couchraoke Platforms
> Non-negotiable. RFC 2119 terms are normative. Shared rules apply to all platforms; platform-specific rules are labeled. Violations MUST be flagged, not silently worked around.

## 1. Identity & Scope
- **Shared:** Service operates LAN-only with no backend cloud services.
- **Android Companion (Phone):** MUST discover and pair with the TV Host via mDNS; MUST scan local songs (SAF) and serve assets to TV via HTTP; MUST capture microphone audio, detect pitch, and stream results to Host via UDP; MUST display real-time score + lyrics from Host; MUST act as D-pad controller when not singing.
- **iOS Companion (Phone):** MUST discover/pair with TV Host via mDNS (`Network.framework`); MUST capture microphone audio, run FFT-YIN pitch DSP, and stream 16-byte UDP results; MUST serve local files via HTTP with Range support; MUST surface singer/spectator status, input levels, and Active Mic lifecycle.
- **TV Host (Android TV):** MUST act as authoritative session host and game engine; MUST aggregate song metadata from connected phones via HTTP; MUST stream audio/video assets directly from phones (no local storage); MUST compute timing, process UDP pitch frames, and evaluate scores; MUST display primary game UI (Song List, Select Players, Singing, Results).

## 2. Technology Constraints
### 2.1 Shared
- **Networking:** Control messages SHOULD remain ≤ 4KB JSON payloads. No authentication/encryption in v1; LAN-only.

### 2.2 Android Companion
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
| Testing Stacks | Unit: JUnit 5 (`5.10+`), MockK (`1.13+`), Turbine (`1.2.x`). Instrumented: Espresso (`3.5.1`), `androidx.test:runner` (`1.5.2`) | JUnit 4, Robolectric (for UI-only logic) |
| Test Utilities | `kotlinx-coroutines-test`, `kotlinx-serialization-json` (prod-matched) | Hardcoded `Dispatchers.Main`/`IO` in testable code |
| Min SDK | API 26 (Android 8.0) | Raising min SDK to 28+ without guarded fallbacks |

### 2.3 iOS Companion
| Concern | Mandatory | Forbidden |
| :--- | :--- | :--- |
| Language | Swift 6+ (Strict Concurrency) | Objective-C, C++ in UI layers |
| UI | SwiftUI | UIKit Storyboards / XIBs |
| Concurrency | Swift Concurrency (`async`/`await`, Actors) | `DispatchQueue` (GCD), RxSwift |
| Audio Capture | `AVAudioEngine` (`installTap`) | `AVAudioRecorder`, `AudioQueue` |
| FFT / DSP | `Accelerate.framework` (vDSP) | Third-party math/FFT libraries |
| Discovery | `Network.framework` (`NWBrowser`) | `NSNetServiceBrowser` |
| Network Transport | `NWConnection` (UDP), `URLSessionWebSocketTask` | CocoaAsyncSocket |
| HTTP Server | `Swifter` (`1.5.0`) | Vapor, GCDWebServer |
| Storage Access | `UIDocumentPicker` + `NSFileCoordinator` + Security Bookmarks | Direct path access to external URIs |
| Persistence | `UserDefaults` (for bookmarks/prefs) | CoreData, SwiftData, Realm |
| Testing | XCTest + Swift Testing (2024+); protocol-based test doubles | Reflection-based mocking, third-party mock libs |
| JSON Assertions | `JSONDecoder` + `Codable` | String-compare of JSON |

### 2.4 TV Host
| Concern | Mandatory | Forbidden |
|---|---|---|
| Language | Kotlin 2.1+ | Java, mixed new files |
| UI | Jetpack Compose for TV (`androidx.tv:tv-material`) | XML layouts (new code) |
| Concurrency | Coroutines + `Flow` | RxJava, LiveData, raw `Thread` |
| JSON Serialization | `kotlinx-serialization-json` (`1.7.3`) | Gson, Moshi, reflection-based parsing |
| Media Playback | `androidx.media3` (`1.6.1`), `datasource-okhttp` | Legacy ExoPlayer, MediaPlayer |
| Image Loading | `coil-compose` + `coil-network-okhttp` (`3.4.0`) | Glide, Picasso |
| Network Discovery | `jmdns` (`3.5.9`) with `MulticastLock` | Android `NsdManager` |
| Network Transport | `ktor-server-cio` + `websockets` (`3.3.0`) | Netty engine, Retrofit for WebSocket |
| UDP Receiver | `DatagramSocket` (fixed port at session start) | Batching frames, TCP for pitch |
| Persistence | `DataStore` (prefs only, `1.1.1`) | Room, SQLite, persisted song lists |
| QR Code | `zxing-android-embedded` (`4.3.0`) | Requesting Camera permission on TV |
| DI | Hilt `2.59+` | Koin, manual Dagger |
| Testing Stacks | Unit: JUnit 5 (`5.10+`), MockK (`1.13+`), Turbine (`1.2.x`) | JUnit 4, Robolectric for UI |

## 3. Architecture (MVVM + Clean Domain)
- **Shared:** ViewModels MUST be the single source of UI state and expose `StateFlow`/`SharedFlow` (Android/TV) or SwiftUI `@Observable` ViewModels (iOS). Business logic MUST NOT live in UI components.
- **Android Companion:**
  - Directory structure MUST match:
    ```text
    app/
    ├── domain/            # Pure Kotlin — zero Android imports
    │   ├── model/
    │   ├── usecase/
    │   └── repository/
    ├── data/
    │   ├── audio/
    │   ├── network/
    │   ├── server/
    │   └── storage/
    ├── presentation/
    │   ├── pairing/
    │   ├── singing/
    │   └── lobby/
    └── di/                # Hilt modules only
    ```
  - Android framework types MUST stay in `data/` or `di/`. Constructors MUST be `@Inject`; no `companion object` factories.
- **iOS Companion:**
  - Directory structure MUST match:
    ```text
    App/
    ├── Domain/
    │   ├── Models/
    │   ├── UseCases/
    │   └── Repositories/
    ├── Data/
    │   ├── Audio/
    │   ├── Network/
    │   ├── Server/
    │   └── Storage/
    ├── Presentation/      # SwiftUI Views + ViewModels (@Observable)
    │   ├── Pairing/
    │   ├── Singing/
    │   └── Lobby/
    └── DI/                # Manual injection or factories
    ```
  - Hardware/framework dependencies MUST be hidden behind Domain protocols. Business logic MUST NOT be in SwiftUI views.
- **TV Host:**
  - Directory structure MUST match:
    ```text
    app/
    ├── domain/
    │   ├── model/
    │   ├── usecase/
    │   └── engine/
    ├── data/
    │   ├── library/
    │   └── network/
    ├── presentation/
    │   ├── list/
    │   ├── session/
    │   └── singing/
    └── di/
    ```
  - Android framework types MUST stay in `data/` or `di/`. Constructors MUST be `@Inject`.

## 4. Platform-Specific Systems
### 4.1 Android Companion — Audio Capture Pipeline
- Mic input MUST flow: `AudioRecord (PCM_FLOAT) → pre-allocated FloatArray ring buffer (coroutine producer) → pitch detection (IO dispatcher) → DatagramSocket UDP → Host`.
- Mic-to-UDP latency MUST be ≤ 50ms.
- Zero-allocation hot loops: audio capture, buffering, and DSP MUST use pre-allocated primitive arrays. No object allocation, boxing, or new data classes inside the loop.
- `RECORD_AUDIO` permission MUST be verified in the ViewModel before session start.

### 4.2 TV Host — Playback & Scoring Engine
- TV MUST stream audio/video progressively via `Media3` directly from phone HTTP URLs; MUST NOT download/store assets locally or build ZIPs.
- Audio mixing MUST use `MergingMediaSource` + `ScalingAudioProcessor`; MUST NOT use `player.setVolume()` for per-track mix control.
- Scoring evaluation MUST run on a dedicated coroutine polling `ExoPlayer.getCurrentPosition()` every 10ms (100 Hz) and remain decoupled from UI frame rate.

### 4.3 iOS Companion — Audio & DSP Pipeline
- `AVAudioEngine` `installTap` callback (1024 samples @ 44.1kHz) MUST use pre-allocated primitive buffers (`UnsafeMutableBufferPointer`).
- No object instantiation, heap allocation, or string operations MAY occur inside the audio callback.
- Pitch logic MUST follow: Voicing Gate → FFT Autocorrelation → Squared Difference → Candidate Selection → 3-frame Median Filter.
- `AVAudioSession.Mode.measurement` MUST be used to avoid OS voice-processing interference.

### 4.4 Performance Targets
- **Android Companion (Pixel 3a baseline):** Cold launch to pairing < 2s; LAN discovery < 3s; mic-to-UDP latency < 50ms; main thread 60fps (no audio/network/server work); memory during singing < 100MB; APK size < 15MB.
- **TV Host (TV baseline):** UI 60fps; scoring eval < 2ms per 10ms tick on IO/Default dispatcher; parse & play latency < 2s from "Start" to ExoPlayer buffering; memory usage < 150MB.

## 5. Networking & Song Serving
- **Shared:** UDP pitch frames MUST be fixed 16-byte binary packets. Control JSON MUST be ≤ 4KB. No authentication/encryption (LAN-only v1).
- **Android Companion:**
  - Discovery MUST use `NsdManager` browsing `_karaoke._tcp`; `MulticastLock` (tag `"karaoke_multicast"`) MUST be held during mDNS browsing and released after.
  - Control MUST use OkHttp WebSocket client to TV host; reconnect via coroutine `retry` with exponential backoff.
  - Pitch MUST use `DatagramSocket` UDP with fixed 16-byte frames; no batching, no TCP.
  - HTTP file server MUST start before `hello` is sent; `httpPort` in `hello` MUST reflect bound port. Default port 34781; MAY fall back to an available ephemeral port. All file access MUST go through `ContentResolver`/`DocumentFile`; MUST support HTTP Range (`206 Partial Content`, `Content-Range`, `Accept-Ranges: bytes`).
- **iOS Companion:**
  - Discovery MUST use `NWBrowser` AsyncStream for `_karaoke._tcp`.
  - Control MUST use `URLSessionWebSocketTask` (JSON ≤ 4KB).
  - Pitch MUST use `NWConnection` UDP; packets MUST be exactly 16 bytes, Little-Endian.
  - HTTP server MUST use Swifter (`1.5.0`) with `NSFileCoordinator` for all routes; MUST use security bookmarks (`startAccessingSecurityScopedResource` / `stopAccessing...`) per request; MUST implement Range serving. `isIdleTimerDisabled` MUST be true during active sessions.
- **TV Host:**
  - Discovery MUST advertise `_karaoke._tcp` using `jmdns`; MUST acquire `MulticastLock` on session start and release on end.
  - Control MUST use Ktor WebSocket server on `/`; MUST reject mismatched `protocolVersion` or invalid tokens immediately.
  - Pitch MUST receive fixed 16-byte UDP frames on a fixed port set at session start; MUST drop invalid frames silently based on `connectionId`.
  - HTTP streaming MUST use cleartext RFC-1918 allowlist via `network_security_config.xml`. TV MUST stream directly from phone HTTP URLs; MUST NOT persist song assets locally.

## 6. Testing & Quality
- **Shared:** All code modifications MUST have test coverage. Android Companion and TV developers MUST read `testing/testing_policy.md` before writing/modifying/reviewing tests. RFC 2119 terms are normative.
- **Android Companion:**
  - Test stacks per §2.2 MUST be used. `kotlinx-coroutines-test` + `kotlinx-serialization-json` MUST match production versions. No hardcoded `Dispatchers.Main`/`IO` in testable code.
  - Code quality: `ktlint` MUST pass with zero warnings; `detekt` cyclomatic complexity MUST stay < 10 per function; `Timber` `DebugTree` ONLY in debug builds; sealed classes REQUIRED for `UiState` + `UiEvent`; MUST NOT introduce `// TODO` or `// FIXME` in merged code.
- **iOS Companion:**
  - Coverage MUST be ≥ 80% for all modified or new files. Use XCTest/Swift Testing with protocol-based fakes (no third-party mocks). Every repository protocol MUST have a corresponding manual Fake in `Data/Testing/`. Logging MUST use `os.Logger`; `print()` is forbidden in production. `Info.plist` MUST include `NSLocalNetworkUsageDescription`, `NSBonjourServices`, `NSCameraUsageDescription`, `NSMicrophoneUsageDescription`.
- **TV Host:**
  - Test stacks per §2.4 MUST be used. Robolectric MUST NOT be used for UI. Code quality: `ktlint` zero warnings; `detekt` cyclomatic complexity < 10; `Timber` `DebugTree` ONLY in debug builds; sealed classes REQUIRED for `UiState` + `UiEvent` and network messages; MUST NOT introduce `// TODO` or `// FIXME` in merged code.

## 7. Consistency Checklist (execute after every task)
- **Shared:**
  - [ ] Every modified file has corresponding test coverage updated or created.
  - [ ] No unintended side effects to adjacent system components.
- **Android Companion:**
  - [ ] Zero allocation in audio hot loops verified.
  - [ ] HTTP server started before `hello`; `httpPort` matches bound port.
  - [ ] All song file access via `ContentResolver`/`DocumentFile`; no bare `File()` on SAF URIs.
  - [ ] New interface → `Fake` in `data/testing/`.
  - [ ] New ViewModel state → sealed class updated + Turbine test added.
  - [ ] New network message → mirrored in `MessageSchema.kt` (must match iOS repo).
  - [ ] New dependency → justified in `libs.versions.toml` with `// DECISION:` comment.
- **iOS Companion:**
  - [ ] FFT-YIN pipeline verified zero-allocation in `installTap` block.
  - [ ] `NSFileCoordinator` used for all Swifter route handlers.
  - [ ] Manual Range parsing implemented for audio/video streaming.
  - [ ] All mDNS operations use `NWBrowser` (no `NSNetServiceBrowser`).
  - [ ] Haptic feedback (~200ms) triggered on `assignSinger` receipt.
- **TV Host:**
  - [ ] No reflection-based serialization introduced in hot paths.
  - [ ] Scoring loop remains decoupled from UI thread (10ms poll maintained).
  - [ ] Zero local storage used for remote song assets (direct ExoPlayer HTTP streaming confirmed).
  - [ ] New WebSocket messages mirrored in schema tests.
  - [ ] New dependency → justified in `libs.versions.toml` with `// DECISION:` comment.
