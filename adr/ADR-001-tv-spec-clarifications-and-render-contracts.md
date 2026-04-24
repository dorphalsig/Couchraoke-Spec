# ADR-001: TV spec clarifications, render contracts, and cross-device message contracts

**Status:** Accepted
**Date:** 2026-04-24
**Deciders:** Product/spec author, Claude Code

## Context

The TV app spec and TV↔phone boundary accumulated several implementation-blocking ambiguities while refining singing, medley, and phone-session behavior.

The main issues were:
- countdown and song start timing did not clearly require a valid clock-sync sample before countdown/live playback
- media-player ownership across Song List, Singing, and medley transitions was not explicit enough
- phone exit semantics were split across `playbackState` and `sessionState.inSong` without a clear authoritative rule
- library refresh behavior during reconnect conflicted with the desire to avoid gameplay-time refreshes
- medley playback lacked a complete playback/render contract for single-track vs dual-track audio and timing authority
- singing UI requirements (lyrics, note rails, gap indicators, live pitch) depended on chart-derived data, but the public UI boundary exposed only media playback intents/events
- medley rendering needed stable vertical scaling and one coherent time timeline without forcing the renderer to stitch per-segment charts together
- Settings > Connect Phones required more administration behavior than the product really needed, and no clear narrow-interface owner existed for that larger surface
- "Forget" implied remembered-device semantics that were not actually defined anywhere in the spec
- Scoring rules depended on per-player difficulty and the line-bonus gameplay toggle, but the public `ScoringEngine` contract did not receive those gameplay inputs explicitly
- TV Song Library wording referenced invalid-song counts per phone even though the phone-side interfaces only publish valid songs to the TV
- `songStartTvMs` ownership was described inconsistently: one section put Media3 listener ownership in the coordinator while the intent/event boundary and blocker notes put capture in the UI layer
- Playback stop-boundary enforcement was only implied: the spec named `stopAtLyricsTimeMs` as authoritative, but did not explicitly state that the UI enforces it on Media3 and emits the end event consumed by the coordinator
- the TV↔phone message contracts carried redundant fields and unclear source-of-truth rules, especially around active-song metadata
- `playbackState` schema requirements contradicted field semantics for conditional `countdownRemainingMs`, optional `tsTvMs`, and enum-bounded `reason`
- `assignSinger` still exposed `effectiveMicDelayMs` even though the phone was forbidden to act on it
- the phone-side `SongEntry` required-field prose lagged behind the TV-side schema for `/manifest.json`
- clock sync validity across reconnects and session changes was implicit instead of being stated as an explicit cross-device invariant

A recurring constraint throughout the work was: solve real problems completely, but keep the solution as simple as possible and avoid introducing new abstractions unless they close a real loose end.

## Decision

We updated the spec to make the smallest complete set of clarifications needed to unblock implementation.

### 1. Countdown clock sync is required before start
- Before `assignSinger`, the TV must have at least one valid clock-sync sample for each assigned singer.
- Countdown must not begin until that condition is satisfied.
- This clarifies that countdown belongs to the pre-singing phase; clock sync is suspended only after countdown/live playback has actually begun.

### 2. Media players are screen-scoped
- Preview playback belongs only to SongListScreen and is torn down on screen exit.
- Singing/medley playback players belong to SingingScreen and are torn down on screen exit.
- During medley, the current segment remains authoritative until the replacement segment emits `PlaybackEvent.Ready`; then authority transfers and the old player is torn down.

### 3. Session exit authority is split cleanly
- `playbackState` governs in-song runtime substate (`countdown`/`playing`/`paused`/`stopped`).
- `sessionState.inSong` governs whether the phone is in singing mode at all.
- `sessionState.inSong=false` is the authoritative exit signal and was tightened from SHOULD to MUST in quit flows.

### 4. Library refresh never happens during gameplay
- Reconnect-time manifest refresh is allowed immediately only in Open/Results.
- During Countdown/Playing/Paused/DisconnectPaused/Stopped, the phone catalog is marked stale and refresh is deferred until Results/Open.

### 5. Dual-track playback and medley timing authority are explicit
- Single-track playback uses `audioUrl` as timing authority.
- Dual-track playback uses `instrumentalUrl` as timing authority; `vocalsUrl` follows it and never becomes an independent timing source.
- During medley, exactly one segment is authoritative at a time; the active segment's `songStartTvMs` remains in force until the next segment emits `PlaybackEvent.Ready`.

### 6. Singing UI receives a chart-derived render contract
- Added `SingingRenderModel` as the authoritative chart-derived contract for SingingScreen.
- `ParsedSong` may be used internally to build it, but raw `ParsedSong` is not the required UI boundary.
- Added a renderer contract stating that `LaneRenderState` is derived from immutable render data + current lane time + live pitch, not by directly reading parser models.

### 7. Medley render data must exist before countdown
- For medley, the coordinator must fetch and parse all required segment charts before countdown begins.
- If the full medley render model cannot be built, the medley fails before start rather than starting with incomplete chart data.

### 8. The lane coordinate system is explicit
- Lane height is the drawable area / coordinate-system bounds, not the tolerance band.
- Time maps to X; pitch maps to Y.
- `VerticalPitchMapping` is computed per player from that player's scorable notes, with ±2 semitone padding.
- For medley, vertical mapping is fixed for the full run using the union of that player's scorable notes across all medley segments.
- `SingingRenderModel` carries horizontal positions in lyrics-time ms; medleys use one continuous medley-local lyrics-time timeline.
- Difficulty remains a scoring-tolerance concept, but is also reflected visually through target-bar thickness; the live pitch glyph remains 1 semitone high.

### 9. Connect Phones was simplified to Kick-only administration
- We removed Rename, Forget, and End Session from the TV-side Connect Phones flow.
- `NetworkController` owns only the remaining real admin action: `kickPhone(clientId)`.
- Kick is narrowly defined to disconnect the phone, remove its `clientId` from the current session roster, remove that phone's songs from the TV song list, and revoke reconnect entitlement for the current session.

### 10. Friendly phone labels replace TV-side rename flows
- Instead of renaming devices from the TV, the phone sends a persisted human-friendly `deviceName` for TV display.
- `clientId` remains the stable opaque reconnect identity; it is not reused as a user-facing label.
- If labels collide, the TV may disambiguate in display without introducing a rename feature.

### 11. Forget was removed instead of inventing remembered devices
- The spec did not actually define remembered devices or persistent device trust.
- Rather than introduce a new concept, we removed Forget and kept the model session-scoped.
- Rejoin, if allowed after Kick, is as a fresh spectator.

### 12. Scoring receives explicit gameplay configuration
- Added `ScoringConfig` to the scoring boundary so `ScoringEngine.loadChart(...)` explicitly receives all gameplay inputs that affect scoring.
- `playerDifficulties` comes from Select Players.
- `lineBonusEnabled` comes from Settings > Gameplay.
- The scoring contract now forbids reading those values implicitly from UI/global state.

### 13. TV Song Library uses only data that already exists cross-device
- Invalid-song diagnostics remain phone-local.
- The TV Song Library screen was simplified to show per-phone device name and valid song count only.
- We explicitly chose not to introduce a new endpoint or summary field just to expose invalid-song counts on TV.

### 14. UI captures `songStartTvMs`, coordinator consumes it
- The UI layer owns Media3, so it also owns Media3 timing listeners and fallback timing capture.
- The UI emits `PlaybackEvent.Ready(songStartTvMs)` once timing is known.
- The coordinator remains responsible for orchestration: waiting for `PlaybackEvent.Ready`, gating scoring, and forwarding `songStartTvMs` into `ScoringEngine`.
- We explicitly rejected direct coordinator ownership of Media3 listeners because it conflicts with the narrow-interface intent/event boundary.

### 15. UI enforces the playback stop boundary, coordinator consumes the end event
- `stopAtLyricsTimeMs` remains the authoritative stop point.
- Because the UI owns Media3, the UI is responsible for enforcing the active stop boundary on playback.
- Before countdown or live playback begins, the UI emits `PlaybackEvent.Prepared(effectivePlaybackDurationMs)` so the coordinator can compute `stopAtLyricsTimeMs` from the actual playback plan.
- When playback begins, the UI emits `PlaybackEvent.Ready(songStartTvMs)`.
- When the UI reaches `stopAtLyricsTimeMs`, it stops Media3 and emits `PlaybackEvent.Ended`.
- The coordinator consumes that event and treats it as the authoritative trigger for `Stopped` → finalization → `Results`, unless an explicit error or quit path overrides it.

### 16. TV↔phone message contracts are minimal and authoritative
- `assignSinger` is the authoritative source for active-song metadata shown on the phone, so `songTitle` and `songArtist` are required there.
- `playbackState` carries runtime playback authority only and does not repeat active-song metadata.
- `effectiveMicDelayMs` is not part of the wire contract; TV-side mic delay remains an internal timing concern.
- `countdownRemainingMs` is conditional on `state="countdown"` instead of being globally required.
- `reason` is an enum-bounded wire field.
- `tsTvMs` remains optional under the shared message envelope.
- `clockOffsetMs` is scoped to the current TV session and active control connection; reconnect or session change requires fresh sync before resumed singer traffic.
- Playback startup is split into a prepared-duration boundary and a playback-start boundary: `Prepared(effectivePlaybackDurationMs)` is used for `stopAtLyricsTimeMs`, while `Ready(songStartTvMs)` is used for scoring start.
- In dual-track playback, `currentPositionMs` and other playback-control timing semantics follow the instrumental timing-authority track, while fallback duration comes from the effective coupled playback plan.
- Between `reset()+loadChart()` and `setSongStart(songStartTvMs)`, ScoringEngine is in a buffering state: frames for the active `songInstanceSeq` are admitted into the jitter buffer, finalization remains gated on `setSongStart`, and `setSongStart` discards buffered frames with `tvTimeMs < songStartTvMs` before scoring begins.
- During medley segment transition, the next segment becomes active for UDP `songInstanceSeq` validation when `loadChart()` completes, not when `start()` is called.
- Scoring finalization is deadline-driven rather than fixed-frequency polling: pending notes are kept in deadline order, scores are recomputed only when finalized-note processing changes visible score state, and the SLA is expressed as finalization latency rather than evaluation frequency.
- Phone-side pitch capture is standardized at 50 fps / 20 ms; the spec does not support a 10 ms / 100 fps capture path or cross-device pitch-rate negotiation.
- Phone-side `SongEntry` prose is aligned with the TV-side `/manifest.json` schema.

## Options Considered

### Option A: Keep patching the existing text with local clarifications only
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low |
| Cost | Low |
| Scalability | Poor |
| Team familiarity | High |

**Pros:**
- Minimal wording churn
- Low immediate editing effort

**Cons:**
- Leaves ownership and boundary gaps in place
- Forces implementers to infer missing contracts
- Risk of divergent implementations for medley/render/session behavior

### Option B: Add the smallest complete set of explicit contracts and ownership rules
| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium |
| Cost | Medium |
| Scalability | Good |
| Team familiarity | High |

**Pros:**
- Resolves the actual blockers without redesigning the whole architecture
- Keeps parser, scoring, playback, rendering, and session responsibilities separable
- Makes medley behavior predictable before implementation starts
- Removes undefined concepts instead of layering new features on top

**Cons:**
- Adds a few new types and normative rules
- Requires touching multiple sections of the spec in one pass

### Option C: Introduce broader new subsystems (dedicated session-admin controller, remembered-device model, richer rendering framework)
| Dimension | Assessment |
|-----------|------------|
| Complexity | High |
| Cost | High |
| Scalability | Mixed |
| Team familiarity | Medium |

**Pros:**
- Could centralize more logic behind dedicated abstractions
- Leaves room for future expansion

**Cons:**
- Solves more than the current problem requires
- Increases conceptual surface area in an already complex game
- High risk of creating new underspecified abstractions

## Trade-off Analysis

We chose Option B.

The key principle was: fix real issues fully, but with the simplest adequate solution.

That ruled out Option A because it would leave real blockers unresolved, especially around chart delivery to the singing UI, medley-wide rendering, and session-admin ownership.

It also ruled out Option C because the project already has enough moving parts; creating remembered-device semantics or a separate session-admin subsystem would increase complexity without being necessary to make the current behavior correct.

The adopted changes preserve existing architectural directions where possible:
- playback/media remains separate from singing render state
- the UI layer owns Media3-specific listeners and timing capture, while the coordinator owns orchestration through intent/event boundaries
- scoring remains the owner of scoring semantics, but now receives explicit gameplay configuration instead of relying on implicit settings reach-through
- rendering gets a chart-derived contract instead of raw parser ownership
- the remaining Connect Phones administration stays with the network/session owner instead of adding another controller
- medley stays predictable by requiring complete pre-start render data rather than dynamic rescaling or incremental patching later
- cross-device TV/phone messages are limited to authoritative receiver-needed data unless a duplicated field is explicitly justified

## Consequences

- SingingScreen now has an explicit chart-derived boundary and can be implemented without guessing how lyrics/targets/gaps arrive.
- Medley rendering is stable because the time axis and vertical bounds are fixed before countdown.
- Countdown/start timing is no longer ambiguous.
- Connect Phones actions have a clear, intentionally small API owner.
- Undefined remembered-device behavior is gone.
- Scoring configuration is explicit at the boundary, so difficulty and line-bonus behavior no longer depend on hidden coupling.
- TV Song Library no longer asks for phone-local invalid counts that were never available cross-device.
- TV↔phone runtime messages are smaller and have clearer source-of-truth rules, which reduces integration ambiguity.
- Clock-sync state is now explicitly session-scoped, which makes reconnect behavior safer but requires resumed singer traffic to wait for a fresh sync.
- Playback startup now has an explicit pre-start duration handoff (`Prepared`) and a later playback-start handoff (`Ready`), which closes the stop-boundary gap without adding a new public FSM phase.
- Medley segment handoff is less lossy because frames can be buffered after `loadChart()` and before `setSongStart()` instead of being forced into an underspecified gap.
- Score finalization no longer depends on maintaining an unrealistic fixed scheduler frequency; correctness is defined by deadline latency on target hardware instead.
- Phone pitch capture and wire-rate expectations are simpler because the optional 10 ms / 100 fps path was removed.
- The spec is more explicit, but still avoids introducing large new subsystems.
- Future changes to session joining, rendering, scoring inputs, or cross-device recovery may need to update `ConnectedPhone`, `SingingRenderModel`, `ScoringConfig`, or the message schemas rather than hiding behavior inside prose.

## Action Items

1. [ ] If implementation starts, ensure tests/fixtures are added for medley pre-start render-model build failure and Kick/session-roster behavior.
2. [ ] Add or update protocol fixture coverage for `assignSinger`/`playbackState` schema validation, especially conditional `countdownRemainingMs` and enum-bounded `reason`.
3. [ ] Add reconnect coverage that proves cached `clockOffsetMs` is cleared and fresh sync is required before resumed singer traffic.
4. [ ] Add playback startup coverage that proves `Prepared(effectivePlaybackDurationMs)` arrives before `assignSinger`, and `Ready(songStartTvMs)` remains the scoring-start boundary.
5. [ ] Add medley-transition scoring coverage that proves frames buffered after `loadChart()` and before `setSongStart()` are preserved, while pre-start buffered frames with `tvTimeMs < songStartTvMs` are discarded exactly once at `setSongStart()`.
6. [ ] Add scoring coverage that proves pending-note finalization follows deadline order and visible score state changes are emitted only when finalized-note processing changes results.
7. [ ] Add phone-capture coverage that proves pitch emission stays at 50 fps / 20 ms with no optional 100 fps negotiation path.
8. [ ] Revisit `SingingRenderModel` only if implementation reveals a real missing field; avoid expanding it speculatively.
9. [ ] Reintroduce duplicated runtime metadata only if reconnect or recovery requirements prove that `assignSinger` alone is insufficient.
