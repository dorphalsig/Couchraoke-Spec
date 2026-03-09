# 1 - Product Contract
**Platform**: Shared (Android TV / Android Mobile / iOS)  
### What to migrate
- Rules: overarching goals, platform scope, parity requirements, session states applicability.
- Defaults (difficulty, duet, rap, instrumental/vocals semantics) apply to all platforms.
- Instrumental gap indicator visual requirement (shared UX rule, TV rendering).
### Reference test section from testing/test_guide_tv.md
§8.2.2, §8.2.1 (UI invariants), §8.3.1 (song list empty states)
### Relevant fixtures:
- None (conceptual contract; no direct fixture mapping)

## 1.2 Definition of Done
**Platform**: Shared  
### What to migrate
- Rules: MVP pass criteria, parity-critical behaviors.
### Reference test section from testing/test_guide_tv.md
N/A
### Relevant fixtures:
- None

# 2 - Architecture Overview
**Platform**: Shared  
### What to migrate
- Rules: component responsibilities, data ownership (TV authoritative vs phone authoritative), HTTP streaming architecture.
### Reference test section from testing/test_guide_tv.md
§8.2.3 (library state), §6.1–6.3 (control protocol behaviors)
### Relevant fixtures:
- F18_http_server_range_coordination (covers §8.6)
- F15_session_lifecycle_disconnect_reconnect (covers §8.1/§7.4)

# 3 - Songs and Library
## 3.1 Storage Access
**Platform**: Shared (concept), Android Mobile (SAF), iOS (bookmarks)
### What to migrate
- Rules: recursive `.txt` discovery on phones, SAF/NSFileCoordinator specifics.
### Reference test section from testing/test_guide_tv.md
§7.1–§7.2 (library state/filtering)
### Relevant fixtures:
- F01_song_discovery_validation_acceptance (covers 1.1,1.4)
- F02_header_parsing_edge_cases (covers 1.2)
- Discovery fixtures under testing/fixtures/F01*/F02* (manifest covers 1.x)

## 3.2 Discovery and Validation Rules
**Platform**: Shared
### What to migrate
- Rules: required headers, audio existence, body parsing validity, no notes check.
### Reference test section from testing/test_guide_tv.md
§1.1–§1.3 (body grammar, RELATIVE handling, duet parsing)
### Relevant fixtures:
- F01_song_discovery_validation_acceptance (covers 1.1,1.4)
- F02_header_parsing_edge_cases (covers 1.2)
- F04_duet_parsing_track_routing (covers 1.3)

## 3.3 Index Fields (Functional)
**Platform**: Shared (TV runtime consumes; phones populate)
### What to migrate
- Rules: identity derivation, validation flags, media flags, medley eligibility fields.
### Reference test section from testing/test_guide_tv.md
§7.1–§7.2 (library state/filtering)
### Relevant fixtures:
- F01 (covers 1.1,1.4), F04 (2.3), F16_medley_sequencer (12.x)

## 3.4 Song List (Landing Screen)
**Platform**: Android TV (UI), Shared rules for flags
### What to migrate
- Wireframes: Song List layout, QR/join widget, medley playlist area.
- UX behavior: focus map, search debounce, random actions, medley interactions, back behavior.
- Rules: tag overlays, search scope, medley playlist constraints.
### Reference test section from testing/test_guide_tv.md
§8.1–§8.3 (UI invariants: Select Players, Singing Screen, Song List)
### Relevant fixtures:
- None (UI invariants not covered by fixtures)

## 3.5 Advanced Search
**Platform**: Shared (post-MVP note)
### What to migrate
- Rules: deferred scope, no implementation required.
### Reference test section from testing/test_guide_tv.md
N/A
### Relevant fixtures:
- None

# 4 - USDX TXT Format Support
## 4.1 Supported Note Tokens
**Platform**: Shared
### What to migrate
- Rules: token set, duet markers, note field parsing.
### Reference test section from testing/test_guide_tv.md
§1.1 Body grammar (unknown tokens, malformed numeric), §1.3 Duet parsing
### Relevant fixtures:
- F03_body_grammar_token_recognition (covers 2.1,2.2,4.4)
- F04_duet_parsing_track_routing (covers 2.3)

## 4.2 Supported Header Tags and Semantics
**Platform**: Shared
### What to migrate
- Rules: required/optional tags, audio precedence, video URL rules, instrumental/vocals semantics.
### Reference test section from testing/test_guide_tv.md
§1.2 RELATIVE tag handling (treated as custom), §4.2 Video/asset flags (tag overlays)
### Relevant fixtures:
- F02_header_parsing_edge_cases (covers 1.2)
- F01_song_discovery_validation_acceptance (covers 1.1,1.4)

## 4.3 Error Handling
**Platform**: Shared
### What to migrate
- Rules: diagnostics, invalidation codes, unknown token behavior, RELATIVE/BPM change rejection.
### Reference test section from testing/test_guide_tv.md
§1.1–§1.3 (parser behaviors), §4.2.4 (drop rules)
### Relevant fixtures:
- F02_header_parsing_edge_cases (1.2)
- F03_body_grammar_token_recognition (2.1,2.2,4.4)
- F04_duet_parsing_track_routing (2.3)

## 4.4 Header Tags Reference
**Platform**: Shared
### What to migrate
- Rules: consolidated tag table, defaults.
### Reference test section from testing/test_guide_tv.md
Aligns with §1.x parser expectations.
### Relevant fixtures:
- Same as 4.2/4.3

## 4.5 Body Token Reference
**Platform**: Shared
### What to migrate
- Rules: grammar per token.
### Reference test section from testing/test_guide_tv.md
§1.1 Body grammar cases
### Relevant fixtures:
- F03_body_grammar_token_recognition

# 5 - Timing and Beat Model
## 5.1 Authoritative Beat Definitions
**Platform**: Shared
### What to migrate
- Rules: highlight vs scoring cursor, GAP, mic delay offsets, floor conventions.
### Reference test section from testing/test_guide_tv.md
§2.1 Beat cursors — static BPM
### Relevant fixtures:
- F06_beat_time_conversion_static_bpm (covers 3.1)

## 5.2 Pitch Frame Timing, Jitter, and Mic Delay
**Platform**: Shared (TV consumption; phones produce frames)
### What to migrate
- Rules: frame rate defaults, tvTimeMs mapping, jitter buffer selection, stale/late frame handling, mic delay semantics.
### Reference test section from testing/test_guide_tv.md
§5.1–§5.4 Jitter buffer selection (Module 5), §6.1–6.3 reconnect/assignSinger timing
### Relevant fixtures:
- F13_jitter_buffer_selection_staleness (covers 6.1–6.7)
- F14v2_clock_sync_phone_side (covers 7.1–7.3)

## 5.2.5 Mic Capture and FFT-YIN Pitch Detection Pipeline
**Platform**: Android Mobile / iOS (phone-side)
### What to migrate
- Rules: buffer sizes, no allocations, voicing gate thresholds, FFT pipeline, d’ selection, median smoothing.
### Reference test section from testing/test_guide_tv.md
N/A (phone-side DSP not covered)
### Relevant fixtures:
- None

## 5.3 Beat-Time Conversion
**Platform**: Shared
### What to migrate
- Rules: BPM_internal, time-to-beat, beat-to-time, boundary conventions.
### Reference test section from testing/test_guide_tv.md
§2.1 Beat cursors — static BPM
### Relevant fixtures:
- F06_beat_time_conversion_static_bpm (3.1)

## 5.4 START/END
**Platform**: Shared
### What to migrate
- Rules: start/end offsets, playback initialization.
### Reference test section from testing/test_guide_tv.md
§9.5 Countdown/Start behaviors (indirect)
### Relevant fixtures:
- None

# 6 - Scoring
## 6.1 Scoring Overview
**Platform**: Shared (TV runtime)
### What to migrate
- Rules: scoring coroutine rate, beat stepping interval, state exposure.
### Reference test section from testing/test_guide_tv.md
§3.1 Beat stepping; §3.2 Pitch tolerance cases
### Relevant fixtures:
- F03_body_grammar_token_recognition (4.4)
- F09_pitch_tolerance_octave_normalization (4.2)

## 6.2 Note Types
**Platform**: Shared
### What to migrate
- Rules: per-note scoring eligibility, freestyle exclusion.
### Reference test section from testing/test_guide_tv.md
§3.3 Rap scoring; §3.4 Freestyle exclusion
### Relevant fixtures:
- F03 (4.4), F09 (4.2)

### 6.2.1 ScoreFactor constants
**Platform**: Shared
### What to migrate
- Rules: factor table.
### Reference test section from testing/test_guide_tv.md
§3.5 Line bonus inputs
### Relevant fixtures:
- F11_line_bonus_and_rounding (4.5)

## 6.3 Player Level / Tolerance
**Platform**: Shared
### What to migrate
- Rules: Easy/Medium/Hard semitone ranges.
### Reference test section from testing/test_guide_tv.md
§3.2 Pitch tolerance table
### Relevant fixtures:
- F09_pitch_tolerance_octave_normalization (4.2)

## 6.4 Octave Normalization
**Platform**: Shared
### What to migrate
- Rules: while-loop shifting ±6, tone base at midiNote-36.
### Reference test section from testing/test_guide_tv.md
§3.2 Pitch tolerance behaviors
### Relevant fixtures:
- F09_pitch_tolerance_octave_normalization

## 6.5 Line Bonus
**Platform**: Shared
### What to migrate
- Rules: MaxSongPoints split, per-line budget, forgiveness term, medley window filtering.
### Reference test section from testing/test_guide_tv.md
§3.5 Line bonus
### Relevant fixtures:
- F11_line_bonus_and_rounding (4.5)
- F16_medley_sequencer (12.1–12.4)

## 6.6 Rounding and Display
**Platform**: Shared
### What to migrate
- Rules: rounding asymmetry, totals computation.
### Reference test section from testing/test_guide_tv.md
§3.5 Line bonus rounding
### Relevant fixtures:
- F11_line_bonus_and_rounding

# 7 - Multiplayer, Pairing, and Session Lifecycle
## 7.1 Session States
**Platform**: Shared
### What to migrate
- Rules: Open/Locked/Ended, transitions, reconnect policy.
### Reference test section from testing/test_guide_tv.md
§6.1 Hello handshake; §6.2 Reconnect logic
### Relevant fixtures:
- F15_session_lifecycle_disconnect_reconnect (8.1–8.4)

## 7.2 Pairing UX (TV)
**Platform**: Android TV
### What to migrate
- Wireframes: join widget placement.
- UX behavior: admission rules, roster actions.
### Reference test section from testing/test_guide_tv.md
§8.1 TV — Select Players; §8.3 Song List join widget
### Relevant fixtures:
- None

## 7.3 Pairing UX (Phone)
**Platform**: Android Mobile / iOS
### What to migrate
- UX behavior: phone screens, permissions, leave session flow.
### Reference test section from testing/test_guide_tv.md
N/A
### Relevant fixtures:
- None

## 7.4 Disconnect/Reconnect
**Platform**: Shared
### What to migrate
- Rules: auto-pause on singer disconnect, reconnect mechanics, connectionId rotation.
### Reference test section from testing/test_guide_tv.md
§6.2 Reconnect logic; §6.3 assignSinger fields
### Relevant fixtures:
- F15_session_lifecycle_disconnect_reconnect

# 8 - Network Protocol
## 8.1 Transport
**Platform**: Shared (TV + phones)
### What to migrate
- Rules: WS/HTTP/UDP roles, token, mDNS advertisement, security config.
### Reference test section from testing/test_guide_tv.md
§6.1 Hello handshake; §6.2 Reconnect; §6.3 assignSinger fields
### Relevant fixtures:
- F18_http_server_range_coordination (8.6)
- F14v2_clock_sync_phone_side (7.1–7.3)

## 8.2 Control Messages
**Platform**: Shared
### What to migrate
- Rules: schemas for hello/sessionState/ping/pong/clockAck/error/assignSinger/requestSongList/songListUpdate.
### Reference test section from testing/test_guide_tv.md
§6.1–6.3
### Relevant fixtures:
- F15_session_lifecycle_disconnect_reconnect
- F18_http_server_range_coordination (range coordination uses requestSongList context)

## 8.3 Pitch Stream Messages
**Platform**: Shared (TV consume; phones send)
### What to migrate
- Rules: 16-byte binary layout, toneValid, validation rules.
### Reference test section from testing/test_guide_tv.md
§4.1 Codec correctness; §4.2 Drop rules
### Relevant fixtures:
- F12v2_binary_pitch_codec (5.1,5.2)

## 8.4 Versioning and Compatibility
**Platform**: Shared
### What to migrate
- Rules: protocolVersion=1 enforcement.
### Reference test section from testing/test_guide_tv.md
§6.1 Hello handshake (protocol mismatch)
### Relevant fixtures:
- None

## 8.5 Sender Identification
**Platform**: Shared
### What to migrate
- Rules: connectionId assignment/validation.
### Reference test section from testing/test_guide_tv.md
§6.2 Reconnect logic; §6.3 assignSinger fields
### Relevant fixtures:
- F15_session_lifecycle_disconnect_reconnect

## 8.6 Song File HTTP Server
**Platform**: Shared (TV consumer; phones host)
### What to migrate
- Rules: URL scheme, range support, storage access constraints, platform permissions.
### Reference test section from testing/test_guide_tv.md
§8.6 HTTP coordination
### Relevant fixtures:
- F18_http_server_range_coordination (8.6)

## 8.7 Time Sync and Jitter Handling
**Platform**: Shared
### What to migrate
- Rules: ping/pong/clockAck flow, offset computation, min-RTT selection.
### Reference test section from testing/test_guide_tv.md
§5.1–§5.4 Jitter buffer (timing dependencies)
### Relevant fixtures:
- F14v2_clock_sync_phone_side (7.1–7.3)
- F13_jitter_buffer_selection_staleness (6.x)

# 9 - UI Screens and Flows
## 9.1 Global navigation and input
**Platform**: Android TV
### What to migrate
- Wireframes: navigation model, back behavior.
- UX behavior: focus rules, long-press semantics.
### Reference test section from testing/test_guide_tv.md
§8.1–§8.3 UI invariants
### Relevant fixtures:
- None

## 9.2 Song preview playback
**Platform**: Android TV
### What to migrate
- UX behavior: preview start/stop conditions, preview volume use, video sync.
### Reference test section from testing/test_guide_tv.md
§8.2 TV — Singing Screen (preview prerequisites)
### Relevant fixtures:
- None

## 9.3 Select Players modal
**Platform**: Android TV
### What to migrate
- Wireframes: modal layout, duet gating, medley behavior.
- UX behavior: Start/Cancel, error states.
### Reference test section from testing/test_guide_tv.md
§8.1 TV — Select Players
### Relevant fixtures:
- None

## 9.4 Settings Screen (and sub-screens 9.4.1–9.4.6)
**Platform**: Android TV
### What to migrate
- Wireframes: Settings root and subsections.
- UX behavior: focus, numeric keypad dialog rules, toggles.
- Rules: specific settings semantics (Connect Phones, Song Library, Audio sliders, Scoring Timing, Gameplay, Video).
### Reference test section from testing/test_guide_tv.md
§8.1–§8.3 (UI invariants referenced in settings interactions)
### Relevant fixtures:
- None

## 9.5 Singing Screen (incl. 9.5.1 Medley mode)
**Platform**: Android TV
### What to migrate
- Wireframes: single vs dual singer layouts, countdown overlay, pause overlay, disconnect overlay, medley headers.
- UX behavior: countdown flow, pause/restart/quit, auto-pause on disconnect, medley segment transitions.
- Rules: instrumental gap indicator, elapsed time display, scoring boundaries for medley.
### Reference test section from testing/test_guide_tv.md
§8.2 TV — Singing Screen; §9.1–§9.4 Medley Sequencer
### Relevant fixtures:
- F16_medley_sequencer (12.1–12.4)
- F11_line_bonus_and_rounding (4.5) for line bonus interactions during singing

# 10 - Results
## 10.6 Results (post-song and post-medley)
**Platform**: Android TV
### What to migrate
- Wireframes: Song Score, Medley Results layouts.
- UX behavior: Back to Song List action, back key behavior.
- Rules: medley total averaging.
### Reference test section from testing/test_guide_tv.md
§9.2–§9.4 medley scoring window relevance
### Relevant fixtures:
- F16_medley_sequencer (12.x)
