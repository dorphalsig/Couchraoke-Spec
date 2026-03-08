# Couchraoke — Testing Guide (iOS) v4.20
**Spec**: 4.20 | **Coverage target**: 80% overall, ≥60% per file | **Stack**: Swift 6 (iOS Phone companion)
---
## 1. Conventions & Infrastructure
- **[U] Unit Test**: XCTest logic tests. Pure Swift, no device/network/filesystem.
- **[I] Instrumented Test**: On-device/Simulator tests for hardware-linked logic (Audio, Sockets, Discovery).
- **Mock boundary**: `FileManager`/`NSFileCoordinator` (file access), `URLSessionWebSocketTask` (WebSocket), `NWConnection` (UDP).
---
## 2. Module 1 — Phone-side Song Scanner
> Purpose: Discovers and validates song metadata to produce `songListUpdate`.
### 2.1 Recursive Discovery & iCloud [I/U]
- **Fixture**: `F01/songs_root/` and `F19_icloud_eviction_handling/`.
- **Assertion**: `FileManager.enumerator` finds files; URL is `nil` for `audio.ogg` if `ubiquitousItemDownloadingStatus != .current`.
### 2.2 Validation & Parsing [U]
| # | Test Scenario | Fixture | Expected Outcome |
|---|---|---|---|
| 2.2.1 | Missing `#ARTIST` | `F01/invalid_missing_required_header` | `isValid=false`, code `ERROR_CORRUPT_SONG_MISSING_REQUIRED_HEADER`. |
| 2.2.2 | Duplicate tags | `F02/dup_bpm_last_wins` | The last successfully parsed value wins. |
---
## 3. Module 5 — Pitch Detection (YIN) & Binary Codec
> Purpose: Real-time pitch extraction and 16-byte UDP datagram construction.
### 3.1 DSP Pipeline Accuracy (FFT-YIN) [U]
- **Fixture**: `F17_yin_dsp_pipeline_accuracy/`.
- **Thresholds (§5.2.5.3):** `[0.01, 0.02, 0.04, 0.06, 0.09, 0.13, 0.18, 0.25]`.
| # | Input | Expected Outcome |
|---|---|---|
| 3.1.1 | Waveform `maxAmp < threshold` | `midiNote=255` (Voicing Gate interrupts processing). |
| 3.1.2 | Pure 440Hz Sine Wave | `midiNote=69` (A4). |
| 3.1.3 | Sequence `[60, 255, 60]` | Result is `255` (Silence interrupts combo). |
### 3.2 Allocation & Codec [I/U]
- **Zero-Allocation [I]**: Use XCTest with Allocations Instrument; zero heap allocations during `installTap`.
- **Binary Codec [U]**: Verify 16-byte little-endian layout using fixture `F12v2_binary_pitch_codec/`.
---
## 4. Module 8 — Control Protocol
> Purpose: Handshake, identity management, and singer assignment.
### 4.1 Handshake & assignSinger [U]
- **Handshake**: Verify `hello` includes `httpPort`; capture `connectionId` from `sessionState`.
- **Schema**: Verify `assignSinger` includes **all** B.2.6 fields, including `connectionId`.
- **Haptics**: Verify a ~200ms haptic trigger occurs upon receipt.
---
## 5. Module 9 — HTTP File Server
> Purpose: Serving song assets via Swifter 1.5.0.
### 5.1 Range Requests & Coordination [U]
- **Fixture**: `F18_http_server_range_coordination/`.
- **Assertion**: `206 Partial Content` with correct `Content-Range`; routes wrapped in `NSFileCoordinator`.
---
## 6. Module 11 — Discovery & UI Invariants
> Purpose: mDNS pairing and singer-screen behavior.
### 6.1 Discovery & Active Mic [I]
- **Discovery**: MUST use `Network.framework` (`NWBrowser`) to match `_karaoke._tcp`.
- **Active Mic**: Hardware Back suppressed via `navigationBarBackButtonHidden`; auto-exit when `tvNowMs >= endTimeTvMs`.