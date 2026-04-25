# ADR-002: Native Kotlin + Swift over Flutter for companion apps

**Status:** Accepted
**Date:** 2026-03-06 (recorded retroactively 2026-04-24)
**Deciders:** Product/spec author, Claude Code

## Context

The original spec targeted a single Flutter (Dart) codebase for both companion apps, with an Android TV host app in Kotlin. Several problems surfaced as the spec matured:

- The pitch pipeline wanted native DSP performance. Integrating a Rust YIN implementation via `flutter_rust_bridge` added codegen complexity and a third toolchain to the build.
- The phone HTTP file server needed real HTTP `Range` request support with access to platform file APIs — SAF (Android, scoped storage) and `NSFileCoordinator`/iCloud ubiquity checks (iOS). Dart's `shelf` handled HTTP but platform channels were still required for both file backends.
- Mic capture and audio taps (`AudioRecord` on Android, `AVAudioEngine` on iOS) are inherently platform-specific; the Flutter abstraction layer added no value here and obscured real-time priority behaviour.
- The TV host was already fully Kotlin. The Android companion would be written in the same language as the TV host, minus TV-specific UI. Only iOS required a genuinely new codebase.
- Dart is thinly represented in LLM training corpora relative to Kotlin, Swift, and TypeScript, which materially affected AI-assisted development throughput.

The decision was forced by a combination of these: the supposed shared-code win of Flutter was thin because most of the companion app's complexity lives in platform-specific audio, file I/O, and mic capture.

## Decision

Drop Flutter. Implement:

- **Android TV host** in Kotlin with Jetpack Compose for TV (unchanged).
- **Android companion** in Kotlin (`AudioRecord`, `DocumentFile`/`ContentResolver`, Ktor server, OkHttp).
- **iOS companion** in Swift (`AVAudioEngine`, `UIDocumentPickerViewController`, `NSFileCoordinator`, Swifter, `URLSessionWebSocketTask`).

The pitch-detection algorithm is implemented independently in each language rather than shared through FFI — see [ADR-005](ADR-005-pitch-detection-native-fft-yin.md).

Protocol messages, wire formats, fixture-driven acceptance tests, and parser behaviour remain language-agnostic and defined once at the spec level.

## Options Considered

### Option A: Keep Flutter

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium (platform channels, Rust bridge, shelf) |
| Cost | One codebase |
| Scalability | Fine for app scope |
| Team familiarity | Moderate |

**Pros:** Single codebase. Working HTTP server via `shelf`.
**Cons:** Platform channels still needed for SAF, NSFileCoordinator, mic tap. Rust bridge added a third toolchain. Weak LLM codegen for Dart.

### Option B: Kotlin Multiplatform (KMP)

| Dimension | Assessment |
|-----------|------------|
| Complexity | High (Kotlin/Native for iOS, expect/actual boilerplate) |
| Cost | Partial shared code |
| Scalability | Good in theory |
| Team familiarity | Low for iOS target |

**Pros:** Kotlin everywhere. Shared domain logic.
**Cons:** Kotlin/Native for iOS is less mature than the JVM target; iOS interop for `AVAudioEngine` and SwiftUI still requires Swift anyway. Net saving over fully-native small.

### Option C: React Native

| Dimension | Assessment |
|-----------|------------|
| Complexity | High (three languages: TS, Kotlin, Swift for TurboModules) |
| Cost | One codebase for UI |
| Scalability | OK |
| Team familiarity | Moderate |

**Pros:** Strong LLM codegen for TypeScript. Rich ecosystem.
**Cons:** HTTP `Range` server requires a native TurboModule. Real-time audio tap needs native code. Net complexity higher than native.

### Option D: .NET MAUI, Capacitor/Ionic, NativeScript

**Eliminated immediately.** MAUI audio tap has no clean cross-platform abstraction and the MAUI layer is thin in production. WebView (Capacitor) cannot deliver sub-20 ms audio callback latency on mid-tier 2022 hardware. NativeScript is effectively dead.

### Option E: Native Kotlin + Swift (adopted)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low per codebase (no bridges, no codegen) |
| Cost | Two codebases |
| Scalability | Excellent |
| Team familiarity | High (TV is already Kotlin) |

**Pros:** Zero abstraction tax. Every platform API is directly accessible. Good LLM codegen for both Kotlin and Swift. Pitch pipeline, HTTP server, mic tap, and file access all use idiomatic platform code. iOS is the only genuinely new surface.
**Cons:** Two codebases. Pitch algorithm implemented twice (mitigated by a shared reference implementation in Rust and fixture-driven parity tests).

## Trade-off Analysis

The honest trade-off is **one codebase vs. zero abstraction tax**. Flutter's single-codebase advantage shrinks to near-zero for this app because most complexity (mic capture, file I/O, HTTP serving, real-time audio priority) is platform-specific regardless of the framework wrapping it.

Writing ~2 000 lines of Swift is a bounded cost. Fighting three simultaneous abstractions (Flutter, Rust bridge, platform channels) is an unbounded one that compounds over every feature.

KMP was the closest alternative but adds Kotlin/Native complexity for a marginal gain; the iOS side still needs Swift for `AVAudioEngine` and SwiftUI wrappers. React Native's TS codegen advantage was real but negated by the native-module burden for HTTP range server and audio tap.

## Consequences

- Two independent repositories for mobile (Android companion + iOS companion) plus the Android TV repository.
- Pitch algorithm must pass the same fixture-driven acceptance tests on both Kotlin and Swift implementations to guarantee parity.
- Shared protocol, binary wire formats, fixture definitions, and parser behaviour remain the single source of truth at the spec level; language-level divergence is disallowed.
- `shelf` and `flutter_rust_bridge` references were removed from the spec; Kotlin test stack is JUnit5 + MockK, Swift is XCTest + protocol-based fakes.
- LLM-assisted development throughput improved because Kotlin and Swift training corpora are substantially deeper than Dart's.
- Onboarding a genuine Swift iOS developer (or a capable agent) is still a prerequisite for iOS changes. The alternative of "Flutter developer touches everything" is no longer available.

## Action Items

1. [x] Removed Flutter/Dart references from spec (v4.19 → native split).
2. [x] Updated test strategy to name JUnit5 + MockK (Android) and XCTest (iOS).
3. [x] Rewrote `§3.1 Storage Access` to describe `ContentResolver` / `NSFileCoordinator` directly.
4. [ ] Confirm pitch-algorithm parity between Kotlin and Swift via shared fixture F17 at CI.
