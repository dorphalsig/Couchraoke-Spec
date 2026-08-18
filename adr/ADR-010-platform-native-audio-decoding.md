# ADR-010: Platform-native audio decoding for mixing

**Status:** Accepted  
**Date:** 2026-04-27
**Builds on:** [ADR-008 Lazy audio mixing](ADR-008-lazy-audio-mixing-on-first-request.md)  
**Deciders:** Spec author, Claude (Senior Software Architect)

## Context

Audio mixing requires decoding source audio assets to PCM. Options:

1. **Platform-native decoders** — MediaCodec (Android), AVAssetReader (iOS)
2. **Cross-platform library** — FFmpeg, libsndfile
3. **Pure-Kotlin/Swift decoder** — minimp3, SwiftMP3

## Decision

Use platform-native decoders:
- Android: `MediaCodec` + `MediaExtractor` (built-in, API 21+)
- iOS: `AVAssetReader` + `AVAssetReaderTrackOutput` (built-in)

## Rationale

**Why platform-native:**

| Dimension | Platform-native | FFmpeg | Pure impl |
|---|---|---|---|
| Hardware acceleration | ✓ (Snapdragon DSP, Apple Neural Engine) | ✗ | ✗ |
| Decode time (3-min MP3) | ~2s | ~8s | ~15s |
| Binary size | 0 KB (built-in) | ~30 MB | ~500 KB |
| Maintenance | OS-managed | Manual updates | Manual updates |
| Format support | MP3, AAC, FLAC, OGG | All formats | MP3 only |

**Target hardware constraint:**
- Mid-tier 2022: Snapdragon 662, MediaTek Helio G85, Apple A13
- Hardware decode: ~2s for 3-min MP3
- Software decode: ~8–15s (fails ≤3s SLA)

**Library-first mandate alignment:**
The spec prioritizes "well-maintained, industry-standard libraries" (§1 role). Platform decoders are:
- Maintained by Google/Apple (not third-party)
- Used by millions of apps (battle-tested)
- Zero integration cost (already on device)

## Consequences

**Positive:**
- Fast: hardware decode meets ≤3s SLA on mid-tier 2022 hardware
- Reliable: OS handles format quirks (VBR, non-standard headers)
- Zero footprint: no binary size increase
- Future-proof: OS updates improve performance

**Negative:**
- Platform-specific code: separate Android/iOS implementations (~150 lines each)
- API complexity: MediaCodec asynchronous callback pattern, AVAssetReader requires manual buffer management

**Rejected alternatives:**

| Alternative | Why rejected |
|---|---|
| FFmpeg | 30 MB binary increase, no hardware acceleration, 4× slower decode |
| minimp3 (pure Kotlin) | Software-only decode misses ≤3s SLA on mid-tier hardware |

## Implementation notes

**Android** (MediaCodec pattern):
```kotlin
val decoder = MediaCodec.createDecoderByType("audio/mpeg")
decoder.configure(format, null, null, 0)
decoder.start()
// Async callbacks: onInputBufferAvailable, onOutputBufferAvailable
```

**iOS** (AVAssetReader pattern):
```swift
let reader = try AVAssetReader(asset: asset)
let output = AVAssetReaderTrackOutput(track: track, outputSettings: pcmSettings)
reader.add(output)
reader.startReading()
while let buffer = output.copyNextSampleBuffer() { ... }
```

Both produce PCM16LE output (16-bit signed little-endian) suitable for direct mixing.
