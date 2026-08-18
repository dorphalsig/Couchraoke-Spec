# ADR-005: Native FFT-YIN pitch detection on each platform

**Status:** Accepted
**Date:** 2026-03-07 (recorded retroactively 2026-04-24)
**Deciders:** Product/spec author, Claude Code

## Context

The companion app captures mic audio at 44 100 Hz in 1 024-sample windows (~23 ms) and must output a MIDI pitch estimate at 50 fps (20 ms interval) with sub-frame latency. This is the single most performance-critical component of the phone app, and its correctness determines whether scoring feels responsive.

Several candidates were evaluated. The constraints that narrowed the field:

- **Mid-tier 2022 hardware target.** FFT must complete well under 1 ms per frame on both platforms; any allocation on the hot path causes audible scoring glitches.
- **License compatibility.** The companion apps will be distributed through Play Store and the App Store; GPL-licensed DSP libraries are disqualifying for closed-source distribution.
- **No FFI/codegen burden.** The Flutter-era plan was a Rust YIN implementation called via `flutter_rust_bridge`; that plan was discarded alongside Flutter itself (see [ADR-002](ADR-002-framework-native-kotlin-swift-over-flutter.md)), and re-introducing JNI + Swift FFI to share a Rust core across the two native codebases would undo the simplification that motivated the framework change.
- **LAN party-game precision.** The score bins pitch to semitones. Musicological-grade precision (pYIN's HMM post-processing) is not required.

## Decision

Hand-rolled FFT-YIN pipeline on each platform, implemented independently in Kotlin and Swift against a shared normative specification.

**Library pins (platform-native only):**

- Android: `org.apache.commons:commons-math3:3.6.1` (`FastFourierTransformer`, Apache 2.0, ~1 MB JAR). Last stable release 2016 — stable in a good way for this use.
- iOS: `Accelerate.vDSP` (built-in Apple framework, hardware-accelerated, zero dependency). `vDSP_fft_zrip` for real FFT.

**Mic capture (platform-native):**

- Android: `AudioRecord` at 44 100 Hz, 16-bit mono, real-time priority.
- iOS: `AVAudioEngine.inputNode.installTap` with an engine-owned audio thread.

**Algorithm (normative, identical on both platforms):**

1. **Voicing gate.** `maxAmp = max(abs(sample_i))` normalized to `[0, 1]`. If below `sensitivityTable[index].maxAmpCutoff`, emit `midiNote = 255` and skip steps 2–4.
2. **Linear autocorrelation via FFT.** Zero-pad the 1 024-sample window into a 2 048-sample buffer; forward FFT in-place; power spectrum (`Re² + Im²`, zero imaginary); inverse FFT; first 1 024 reals are `r_t(τ)`.
3. **Squared difference and normalisation (CMNDF).** `d_t(τ) = E_start + E_shift(τ) − 2·r_t(τ)`, then `d'(0) = 1.0` and `d'(τ) = d_t(τ) / ((1/τ) · Σ d_t(1..τ))`.
4. **Candidate selection.** First local minimum where `d'(τ) < dPrimeCutoff`; fallback to absolute minimum. If `d'(τ) > 0.40`, unvoiced. Else `hz = 44100/τ`, `midiNote = clamp(round(69 + 12·log2(hz/440)), 0, 127)`.
5. **Temporal smoothing.** 3-frame rolling median. If any frame in the window is `255`, emit `255` (silence breaks combo).

**Pre-allocated buffers (zero GC):** `audioBuffer[1024]`, `paddedBuffer[2048]`, `fftComplexBuffer[4096]`, `diffBuffer[1024]`, `normBuffer[1024]`, `medianHistory[3]`. All allocated once at init and reused every frame.

**Sensitivity presets (0–7):** Eight entries in the table covering whisper/studio through extreme-noise environments, sourced from phone Settings > Mic Sensitivity. Default index 3 (Karaoke Room): `maxAmpCutoff = 0.06`, `dPrimeCutoff = 0.25`.

## Options Considered

### Option A: TarsosDSP (JVM DSP library)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low (drop-in library) |
| Cost | — |
| Scalability | Fine |
| Team familiarity | Medium |

**Pros:** Mature, includes YIN.
**Cons:** GPLv3. Disqualifying for closed-source Play Store distribution.

### Option B: Rust YIN via FFI (JNI on Android, Swift-to-C header on iOS)

| Dimension | Assessment |
|-----------|------------|
| Complexity | High (three toolchains, FFI boundary, build-system integration) |
| Cost | Low license cost but high complexity cost |
| Scalability | OK |
| Team familiarity | Low |

**Pros:** One reference implementation shared across platforms. Fast.
**Cons:** Reintroduces the FFI/codegen complexity that [ADR-002](ADR-002-framework-native-kotlin-swift-over-flutter.md) removed. Builds slow on CI. Debugging spans three languages. The Rust chromaprint+pYIN reference in the project is retained as a *reference*, not a build dependency.

### Option C: pYIN (YIN + HMM post-processing)

| Dimension | Assessment |
|-----------|------------|
| Complexity | High (Viterbi decoding on top of YIN) |
| Cost | Latency hit from state-tracking window |
| Scalability | Fine |
| Team familiarity | Low |

**Pros:** Musicological-grade precision and recall on breathy or noisy input.
**Cons:** Overkill for a party karaoke game whose scoring bins to semitones. Adds implementation and debugging complexity that gives no user-visible win.

### Option D: Hand-rolled FFT-YIN with a simple octave-error continuity check (adopted)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low (~150 lines per platform) |
| Cost | Native FFT on both sides, no dependencies |
| Scalability | Excellent |
| Team familiarity | High |

**Pros:** ~150 lines of Kotlin, ~150 lines of Swift. No GPL. No FFI. `Accelerate.vDSP` is already on every iOS device; `commons-math3` is small and Apache 2.0. Octave-error mitigation via a continuity check ("if new ≈ prev/2, double") is sufficient for semitone-bucketed scoring.
**Cons:** Algorithm implemented twice; parity must be enforced by shared fixture-driven tests.

## Trade-off Analysis

**License vs. convenience.** TarsosDSP's GPLv3 was a hard stop; no amount of convenience justifies it for this distribution model.

**Shared code vs. native simplicity.** Rust-via-FFI would share one implementation, at the cost of three toolchains, a codegen boundary, and every build-system headache that [ADR-002](ADR-002-framework-native-kotlin-swift-over-flutter.md) was written to avoid. Writing ~300 lines of tightly-specified DSP twice is cheaper than maintaining an FFI boundary forever.

**Precision vs. complexity.** pYIN's additional precision is wasted on a game that bins to semitones and displays visible feedback within one frame. The documented YIN failure mode we care about — octave errors — is fixable with a single continuity check, not a Hidden Markov Model.

The Rust implementation in the project (chromaprint + pyin) is kept as a **reference implementation for porting**, not as runtime code. Both Kotlin and Swift implementations should agree with it on the shared fixture F17 within the stated tolerance.

## Consequences

- Pitch algorithm is fully specified as normative pseudocode in `phone_app.md §2.3` (`PitchDetector`) — both platforms implement to the same spec, not to each other.
- Parity is enforced by the F17 fixture suite (pure A4 sine → MIDI 69, below-threshold amplitude → unvoiced, median filter silence-interrupts-combo). Any platform divergence is a conformance bug.
- The `ScoringConfig` boundary ([ADR-001 §12](ADR-001-tv-spec-clarifications-and-render-contracts.md)) receives `midiNote` after Tone normalisation — `Tone = midiNote − 36` (no mod reduction before octave-normalisation loop).
- Phones MUST NOT emit computed scoring, judgement, combo, or rating values — the phone authority boundary is DSP observations only.
- `toneValid` is implicit on the wire (`toneValid = (midiNote != 255)`); see [ADR-004](ADR-004-udp-pitch-frame-wire-protocol.md).
- No per-frame allocation on either platform; this is a normative requirement, not a style preference.
- Upgrading `commons-math3` is not anticipated (library is in maintenance mode); if a future transitive dependency forces change, an alternative Kotlin FFT (e.g., JTransforms 3.2) is available with the same in-place semantics.

## Action Items

1. [x] Removed TarsosDSP and `flutter_rust_bridge` from spec and library tables.
2. [x] Specified the FFT-YIN pipeline normatively in `phone_app.md §2.3`.
3. [x] Pinned `commons-math3:3.6.1` and `Accelerate.vDSP` as the only DSP dependencies.
4. [x] Added F17 pitch-detection fixture with A4 sine, below-threshold, and median-filter cases.
5. [ ] Enforce pitch-parity between Kotlin and Swift implementations via shared F17 acceptance in CI.
6. [ ] Add octave-error continuity-check unit test on each platform (synthetic input: 440 Hz → 220 Hz → 440 Hz sequence; assert no f/2 misreads).
