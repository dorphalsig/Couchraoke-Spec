# ADR-007: LibVLC for USDX video format parity with gameplay-safe fallback

**Status:** Accepted
**Date:** 2026-04-25
**Deciders:** Product/spec author, Claude Code

## Context

The current TV spec hard-codes Media3/ExoPlayer into the playback boundary:
- `tv_app.md` §2.1 makes the UI layer responsible for Media3-specific `songStartTvMs` capture.
- `tv_app.md` §2.6 states that the UI owns Media3 for playback.
- `tv_app.md` §3.2 says the coordinator emits `PlaybackIntent` and the UI executes it on Media3.
- `tv_app.md` §4.2 requires medley prebuffering with a second ExoPlayer instance.

That coupling is now the wrong trade-off.

A core project principle is USDX parity. We need broader song/video format compatibility than the current Media3-based path reliably offers. At the same time, the TV app targets limited Android TV hardware and the singing experience is more important than video. The architecture therefore has two simultaneous requirements:
- improve playback compatibility enough to honor USDX parity
- never let video rendering degrade audio timing, lyrics timing, or scoring responsiveness

The migration also has operational constraints that differ from Media3:
- LibVLC playback callbacks are not modeled the same way as Media3 listeners
- LibVLC video output lifecycle is manual rather than `PlayerView`-managed
- LibVLC event callbacks may arrive off the main thread
- LibVLC does not own Android audio focus for us
- LibVLC adds LGPL 2.1 attribution requirements

We want the smallest complete architectural change that solves the real problem. That means changing the playback backend without redesigning `PlaybackCoordinator`, `ScoringEngine`, or the network protocol.

## Decision

We will replace Media3/ExoPlayer with LibVLC as the TV playback backend for song playback.

We will keep the existing coordinator-to-UI playback boundary intact:
- `PlaybackCoordinator` continues to emit `PlaybackIntent`
- the UI/playback layer continues to emit `PlaybackEvent`
- scoring still starts only after `PlaybackEvent.Ready(songStartTvMs)`
- the coordinator remains orchestration-only and does not take direct ownership of player callbacks or surfaces

We will preserve the current monotonic timing model. `songStartTvMs` remains a TV monotonic timestamp; the migration changes the source event that captures it, not the clock semantics.

LibVLC-specific behavior will be isolated to the UI/playback layer and to the spec sections that must describe it explicitly:
- capture `songStartTvMs` from the first advancing LibVLC playback-time signal, with the existing 500 ms fallback if that signal is delayed
- marshal LibVLC-driven UI state changes back onto the main thread before touching UI-owned state
- attach video output only after the view/surface exists, detach it before the view/surface is destroyed, and release player resources on screen teardown
- request audio focus before playback and abandon it on stop/teardown

Video playback will become conditional rather than assumed:
- admit video only when the device/video combination is considered safe for gameplay
- if the entry gate rejects video, fall back immediately to background-only rendering
- if runtime monitoring shows that pitch processing is being degraded, disable video and continue audio, lyrics, and scoring with a background fallback

The spec will become backend-neutral where possible. We will remove Media3/ExoPlayer names from architecture boundaries and keep LibVLC-specific wording only where the behavior is genuinely backend-specific: event capture, thread handoff, surface lifecycle, audio focus, and licensing.

We will not support dual playback backends. If LibVLC is the chosen path for USDX parity, the simplest complete solution is to standardize on it and protect gameplay with explicit fallback rules rather than maintain two media stacks.

## Options Considered

### Option A: Stay on Media3 and keep adding compatibility workarounds
| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium |
| Cost | Medium |
| Scalability | Poor |
| Team familiarity | High |

**Pros:**
- Smallest immediate code churn
- Preserves current Media3-specific tests and lifecycle assumptions
- Avoids LGPL attribution work

**Cons:**
- Does not satisfy the stated USDX parity goal
- Continues the current pattern of player-specific exceptions and device workarounds
- Keeps the spec coupled to one backend that is already creating compatibility pressure
- Risks repeated codec/container edge-case work without solving the root problem

### Option B: Replace Media3 with LibVLC behind the existing playback boundary and add gameplay-safety gates
| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium |
| Cost | Medium |
| Scalability | Good |
| Team familiarity | Medium |

**Pros:**
- Directly addresses the format-parity requirement
- Preserves the current coordinator/scoring/network architecture
- Keeps player-specific complexity contained in the UI/playback layer
- Protects low-end hardware by making video conditional instead of mandatory
- Produces a cleaner spec by separating architectural contracts from backend implementation details

**Cons:**
- Requires lifecycle, event, and thread-handling changes in the UI/playback layer
- Requires explicit audio-focus ownership in app code
- Requires test doubles and playback tests to move off Media3 assumptions
- Adds LGPL 2.1 attribution and compliance work

### Option C: Keep Media3 as the default path and add LibVLC as a selective fallback backend
| Dimension | Assessment |
|-----------|------------|
| Complexity | High |
| Cost | High |
| Scalability | Mixed |
| Team familiarity | Low |

**Pros:**
- Can reduce migration risk in the short term
- Leaves room for device-specific backend selection later

**Cons:**
- Duplicates the playback test matrix and lifecycle complexity
- Creates inconsistent behavior across songs/devices
- Expands the spec surface with backend-selection rules
- Violates the project preference for the simplest solution that fully solves the problem
- Solves more than the current need requires

## Trade-off Analysis

We chose Option B.

Option A fails the core product requirement. If USDX parity is a principle rather than a nice-to-have, continuing to patch Media3 keeps effort focused on symptoms instead of the compatibility gap itself.

Option C is the classic overengineered escape hatch. It looks safer because it defers commitment, but in practice it would multiply lifecycle rules, testing cost, and spec complexity. The project already has enough moving parts; carrying two playback stacks would add a large permanent tax just to avoid making the actual decision.

Option B is the smallest complete answer. It changes the playback backend, keeps the existing orchestration boundary, and adds only the extra rules needed to keep gameplay safe on constrained hardware. It also lets the spec stop pretending that Media3-specific details are architectural truths.

The important design constraint is containment:
- playback backend concerns stay in the UI/playback layer
- orchestration stays in `PlaybackCoordinator`
- scoring timing remains driven by monotonic `songStartTvMs`
- runtime fallback protects gameplay rather than trying to make every device render every video

## Consequences

- The TV playback architecture becomes backend-agnostic at the intent/event boundary, but LibVLC-specific lifecycle rules become explicit in the UI layer.
- `songStartTvMs` capture changes from a Media3 callback to a LibVLC time-advance event, but the coordinator/scoring contract stays the same.
- The spec must stop naming Media3/ExoPlayer in sections that are really describing ownership boundaries rather than library choices.
- Video playback becomes best-effort under explicit safety rules instead of being implicitly required whenever a video asset exists.
- Weak devices may show the background instead of video more often, but singing quality is preserved.
- The app takes on explicit audio-focus responsibility that Media3 previously helped hide.
- Playback tests need new fake-player coverage for event delivery, surface lifecycle, timing fallback, and video-disable fallback.
- We must add LibVLC attribution in the app UI and keep distribution compliant with LGPL 2.1 expectations.
- If implementation reveals a real gap in medley prebuffering with LibVLC, we should revisit only that playback subsection rather than re-opening the whole playback architecture.

## Action Items

1. [ ] Replace the Media3 playback dependency with the approved LibVLC Android dependency and remove Media3-specific playback assumptions from implementation planning.
2. [ ] Update `tv_app.md` §2.1 so `songStartTvMs` remains monotonic, is captured from a LibVLC playback-time event, and still uses the existing 500 ms fallback rule.
3. [ ] Update `tv_app.md` §2.6 UI ownership language so it owns playback/backend lifecycle rather than specifically owning Media3.
4. [ ] Update `tv_app.md` §3.2 so the coordinator↔UI contract stays `PlaybackIntent`/`PlaybackEvent`, but execution is no longer described as “on Media3”.
5. [ ] Update `tv_app.md` §4.2 medley prebuffering so it specifies the required capability (prepare next segment ahead of handoff, with sequential fallback if not ready) instead of requiring a second ExoPlayer instance by name.
6. [ ] Add normative UI-layer rules for main-thread handoff, manual video attach/detach/release timing, and audio-focus request/release around playback.
7. [ ] Add a video-admission rule to the playback spec: allow video only when the device/video combination is safe enough for gameplay; otherwise use background-only fallback.
8. [ ] Add a runtime gameplay-health rule: if video rendering degrades pitch-frame processing beyond the chosen threshold, disable video and continue audio, lyrics, and scoring.
9. [ ] Replace Media3-specific playback test doubles with LibVLC-oriented or backend-neutral fakes and add coverage for delayed timing events, lifecycle teardown, medley transitions, and fallback behavior.
10. [ ] Add LibVLC LGPL 2.1 attribution to Settings > About and confirm the release checklist covers compliance.