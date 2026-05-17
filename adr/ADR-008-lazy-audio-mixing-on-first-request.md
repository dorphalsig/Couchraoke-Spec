# ADR-008: Lazy audio mixing on first HTTP request

**Status:** Accepted  
**Date:** 2026-04-27
**Supersedes:** —
**Builds on:** [ADR-007 LibVLC for USDX video format parity](ADR-007-libvlc-for-usdx-video-format-parity.md) — the LibVLC HTTP client requires `Content-Length` for range support, which precludes streaming mix-on-the-fly and motivates this lazy-mix approach.  
**Deciders:** Spec author, Claude (Senior Software Architect)

## Context

Songs with `#INSTRUMENTAL` and `#VOCALS` require phone-side mixing to a single WAV file. The TV's LibVLC player needs `Content-Length` for HTTP Range support, so streaming mix-on-the-fly is not viable. Three timing options exist:

1. **Mix at scan time** — decode and mix all eligible songs during folder scan
2. **Background mix on song selection** — start mixing when user taps song card
3. **Lazy mix on first GET** — decode and mix when TV requests the audio URL

## Decision

Mix lazily on first HTTP GET request. Cache result in memory (LRU, max 3 songs).

## Consequences

**Positive:**
- Simple: single code path, no UI coordination
- No wasted work: only mix songs actually played
- Low memory: 3-song cache vs full library pre-render
- First-byte timing acceptable: 2–3s uncached (LibVLC 2–4s buffer absorbs delay), <100ms cached

**Negative:**
- First playback of unmixed song has 2–3s delay before audio starts
- Mid-tier 2022 hardware constraint: MediaCodec hardware decode required

**Rejected alternatives:**

| Alternative | Why rejected |
|---|---|
| Mix at scan time | Large libraries (100+ songs) → minutes of scan time, hundreds of MB RAM |
| Background on tap | Adds 100+ lines of coordination logic (job queue, cancellation, race handling) for marginal UX gain that only works if user takes >3s between tap and play |

## Implementation notes

- Android: `MediaCodec` + `MediaExtractor` (built-in, API 21+)
- iOS: `AVAssetReader` + `AVAssetReaderTrackOutput` (built-in)
- Cache: LRU eviction, ~30MB per 3-min stereo 48kHz WAV
- SLA: ≤3s uncached, ≤100ms cached (§4.2)
