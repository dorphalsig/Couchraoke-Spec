# ADR-009: In-memory LRU cache for mixed audio

**Status:** Accepted  
**Date:** 2026-04-27
**Builds on:** [ADR-008 Lazy audio mixing](ADR-008-lazy-audio-mixing-on-first-request.md)  
**Deciders:** Spec author, Claude (Senior Software Architect)

## Context

Generated mixed WAV files need caching to meet the ≤100ms cached SLA. Three storage options:

1. **In-memory cache** — byte arrays in RAM, LRU eviction
2. **Temp files** — write to disk, track in memory
3. **No cache** — regenerate on every request

## Decision

In-memory LRU cache, max 3 songs (~102 MB for three 3-minute stereo 48kHz WAVs).

## Rationale

**Cache hit justification:**
- Typical session: user sings same song 2–3 times (practice, retry)
- Medley: all segment sources remain cached for duration
- TV seeks during playback → multiple Range requests for same song

**Size calculation:**
- 3 min × 48000 Hz × 2 channels × 2 bytes = ~34 MB per song
- 3 songs = ~102 MB
- Mid-tier 2022 phones: 6–8 GB RAM, leaves ~5.9 GB for other apps

**Why not temp files:**
- Complexity: path management, cleanup, permission handling
- Android 10+ scoped storage: writing to external storage requires SAF
- Performance: eMMC read ~100 MB/s vs RAM read ~20 GB/s (200× faster)
- Lifecycle: temp files persist across crashes; in-memory self-cleans

**Why not no-cache:**
- Every seek triggers 2–3s decode → unusable playback experience
- LibVLC seeks on start, on manual seek, on buffer underrun

## Consequences

**Positive:**
- Simple: `HashMap<String, ByteArray>` with access-time tracking
- Fast: <1ms to serve cached Range request
- Self-cleaning: eviction on app termination

**Negative:**
- Memory: ~102 MB typical baseline, spikes to ~136 MB during 4th song decode (before eviction)
- Cold start: first play of 4 songs in a row will evict and regenerate

## Implementation

```kotlin
class MixCache(private val maxEntries: Int = 3) {
    private val cache = LinkedHashMap<String, CachedMix>(maxEntries, 0.75f, true)
    
    fun get(path: String): ByteArray? = cache[path]?.data
    
    fun put(path: String, data: ByteArray) {
        if (cache.size >= maxEntries && !cache.containsKey(path)) {
            cache.remove(cache.keys.first())
        }
        cache[path] = CachedMix(data, System.currentTimeMillis())
    }
}
```

Eviction: automatic on 4th song via `LinkedHashMap` access-order mode.
