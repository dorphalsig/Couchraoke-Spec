# Couchraoke TV App Functional Specification
Version: 1.0
Date: 2026-04-11
Scope: Android TV host app functional behavior

**TV technical design:** See `architecture/tv_app_architecture.md`

This document defines **what** the TV app must do. TV-side implementation details such as component APIs, internal state machines, threading, buffering strategy, platform workarounds, and fixture planning are intentionally excluded and live in the technical architecture document.

The phone companion is treated here as an **external participant**. Phone behavior is specified only where the TV-facing functional contract depends on it.

---

# How to Use This Spec
This document is the functional contract for the Couchraoke Android TV host app.

Conventions:
- **Normative** means required for MVP conformance.
- If behavior is not described here, it is unspecified for MVP.
- TV implementation details belong in the technical architecture document, not in this spec.

---

# 1. Product Contract
- Goal: USDX-like karaoke gameplay on TV, including parsing, timing, duet behavior, scoring, medley, and results.
- Platform: Android TV host app.
- Connectivity: same-subnet Wi-Fi only; offline operation.
- Players: up to 2 singers per song.
- Out of scope: online song store, editors, party modes other than Medley, esports-grade calibration.

## 1.1 Locked Product Decisions
- Default per-player difficulty: **Medium**.
- Line bonus: **ON**.
- Duet: **YES**; duet part swapping: **YES**.
- Rap: **YES** (presence-based); Freestyle: no scoring.
- Video backgrounds: **YES**.
- Instrumental via `#INSTRUMENTAL`: **YES**.
- `#VOCALS` guide track: **YES**, with user-configurable TV-side mix level.

**Instrumental playback semantics (normative)**
- When `#INSTRUMENTAL` is present and available, it replaces the normal backing track for the entire song.
- If `#VOCALS` is also present, the TV MUST mix it as a user-adjustable guide track.
- If `#INSTRUMENTAL` is absent, normal song audio plays throughout.

**Instrumental gap indicator (visual only)**
- An instrumental gap is a region where the current player's track has no scorable note for more than **2 continuous seconds**.
- During such a region, that player's pitch lane MUST show an animated rest indicator.
- This indicator is visual only. It does not change playback behavior.

## 1.2 Definition of Done
MVP PASS requires:
- parity-critical behaviors in this spec,
- reliable pairing and singing flows on typical home Wi-Fi,
- correct TV-visible behavior for library browsing, song start, singing, scoring, and results.

## 1.3 Target Platform
- The product target is a living-room Android TV device used with a remote control at 1080p.
- The experience MUST remain readable and stable on low/mid-tier Android TV hardware commonly used for TV sticks and entry-level boxes.
- Detailed hardware constraints, performance budgets, and platform-specific workarounds are defined in `architecture/tv_app_architecture.md`.

---

# 2. System Overview

## 2.1 Scope Boundary
- **In scope:** TV host behavior, UI, playback control, timing authority, scoring, session state, and library aggregation.
- **Out of scope in this document:** phone app implementation details.

## 2.2 Data Responsibilities
- Songs live on connected phones.
- The TV aggregates the currently available song catalog from connected phones.
- The TV is authoritative for:
  - session state,
  - song selection,
  - playback timeline,
  - beat/time interpretation,
  - scoring,
  - TV UI and results.
- Phones are authoritative for:
  - local song storage,
  - manifest publication,
  - song asset serving,
  - microphone capture,
  - pitch observation generation.

**Library visibility rule (normative)**
- A phone's songs are visible on TV only while that phone is connected and has published a valid catalog.
- When a phone disconnects, its songs MUST be removed from the active TV library immediately.

## 2.3 TV App Technical Architecture
TV-side technical details are specified separately in:

**`architecture/tv_app_architecture.md`**

That document is the authoritative source for TV internal design, component boundaries, lifecycle/state-machine design, performance tactics, and TV-specific test fixtures.

---

# 3. Songs and Library

## 3.1 Storage Access

### 3.1.1 Song discovery
- Each phone exposes one configured songs folder.
- Discovery is recursive for `.txt` files under that folder.
- Each `.txt` file is treated as a distinct song entry.

### 3.1.2 Song file delivery
- During an active session, each connected phone serves a read-only HTTP catalog and read-only song asset URLs.
- The TV fetches catalog and asset URLs on demand.
- The TV does not become the owner of song files.

### 3.1.3 TV-Side Library and Lifecycle
- The TV maintains the active library from all currently connected phones.
- Invalid songs are excluded from the TV library.
- The TV library is rebuilt for each session rather than carried across sessions.

**Catalog fetch triggers (normative)**
The TV MUST fetch or refresh a phone's catalog at these moments:
1. after successful phone join,
2. when the Results screen is shown,
3. when the user triggers manual refresh in **Settings > Song Library**.

**Replacement semantics (normative)**
- When the TV receives a refreshed catalog for a phone, it MUST replace that phone's existing contributed songs, not append to them.

**Fetch failure behavior (normative)**
- If refresh for a phone fails, the TV MUST keep that phone's previous catalog and show a brief error toast.

**Disconnect behavior (normative)**
- When a phone disconnects, all songs attributed to that phone MUST be removed immediately.

## 3.2 Discovery and Validation Rules
A song is accepted into the TV-visible library if and only if all of the following are true:
1. Required headers are present and valid.
2. Required audio is resolvable.
3. The body parses without fatal errors.
4. Each parsed track contains singable structure after cleanup.

**Required headers**
- `#TITLE` and `#ARTIST` MUST be present and non-empty.
- `#BPM` MUST be present and non-zero.
- For `#VERSION >= 1.0.0`, at least one of `#AUDIO` or `#MP3` MUST be present; `#AUDIO` wins if both exist.
- For legacy format, `#MP3` is required.

**Body validity**
- Unknown or non-fatal body issues are warnings.
- Fatal numeric parse errors for recognized tokens reject the song.
- Unsupported variable-BPM charts reject the song.
- Unsupported relative-format sentence syntax rejects the song.

**Optional assets**
- Missing optional video, cover, background, instrumental, or vocals files do not invalidate a song.
- Missing required audio invalidates the song.

## 3.3 Index Fields (Functional)
The TV song index MUST contain enough data to drive song selection, preview, medley eligibility, and playback setup.

Minimum record fields:
- Identity / origin:
  - `phoneClientId`
  - `relativeTxtPath`
  - `songId = phoneClientId + "::" + relativeTxtPath`
  - `modifiedTimeMs`
- Display:
  - `artist`
  - `title`
  - `album` (optional)
- Flags:
  - `isDuet`
  - `hasRap`
  - `hasVideo`
  - `hasInstrumental`
  - `canMedley`
  - `medleySource`
  - `medleyStartBeat`
  - `medleyEndBeat`
- Preview metadata:
  - `startSec`
  - `previewStartSec`
- Asset URLs when available:
  - `txtUrl`
  - `audioUrl`
  - `videoUrl`
  - `coverUrl`
  - `backgroundUrl`
  - `instrumentalUrl`
  - `vocalsUrl`

## 3.4 Song List (Landing Screen) - TV

### 3.4.1 Purpose
- The Song List is the TV landing screen.
- Songs are displayed sorted by **Artist -> Album -> Title**.
- The screen owns a transient Medley playlist.
- The Medley playlist is cleared when leaving Song List for a non-modal screen.
- Opening and closing overlays does not clear the playlist.

### 3.4.2 Header actions and pairing widget
The Song List header MUST expose:
- Search,
- Join,
- Settings,
- current join code.

**Join behavior (normative)**
- Activating **Join** opens a pairing overlay showing the session QR code and join code.
- The QR payload MUST encode the full WebSocket endpoint URL including the session token.
- Song List MUST NOT show the connected-device roster.

### 3.4.3 Layout and preview pane
- The Song List uses a two-column layout.
- The left side contains the preview pane and Medley playlist.
- The right side contains search, random actions, and the song grid.
- The preview pane is display-only and non-focusable.
- The preview pane reflects the currently focused song tile.

**Empty states**
- No phones connected: show `No phones connected.` with guidance to connect a phone.
- Phones connected but no valid songs: show `No songs found.` with guidance to set the songs folder on the phone.

### 3.4.4 Search, song grid, and primary actions
**Song tile contents**
Each visible song tile shows:
- cover or placeholder,
- title,
- artist,
- feature tags as applicable:
  - `D` duet,
  - `R` rap,
  - `V` video,
  - `I` instrumental,
  - `M` medley-eligible.

**Inline search (normative)**
- Search is case-insensitive substring matching across artist, album, and title.
- Filtering preserves the underlying sort order.
- Search updates MUST feel immediate during normal remote-driven text entry.

**Primary actions**
- OK on a song tile opens **Select Players**.
- Long-press OK attempts **Add to Medley**.
- If `canMedley=false`, show a blocking modal with the exact text:
  - `This song can't be used in a medley. Look for songs with an M tag in the lower right corner`

**Random actions**
The screen MUST provide:
- **Sing Random Song**
- **Sing Random Duet**
- **Sing Random Medley**

Eligibility is based on the currently visible filtered set.
Buttons with no eligible songs MUST be disabled.

### 3.4.5 Medley playlist
- The Medley playlist is a fixed-height list area.
- Playlist rows render as `<Artist>  <Title>`.
- **Play Medley** is disabled when the playlist is empty.
- OK on a playlist row enters reorder mode.
- Long-press OK on a playlist row deletes it immediately.

### 3.4.6 Focus, DPAD navigation, and Back behavior
- Primary input is TV remote.
- Initial focus on Song List MUST land on the first visible song tile, or the Search field if the grid is empty.
- The preview pane is non-focusable.
- Back from grid or left panel moves focus to Search.
- Back from top controls clears the active filter if present; otherwise exits the app.

### 3.4.7 Medley eligibility: `canMedley`
A song is medley-eligible if and only if:
- `isDuet = false`, and
- valid `#MEDLEYSTARTBEAT` and `#MEDLEYENDBEAT` are both present, and
- `startBeat < endBeat`.

`#CALCMEDLEY` is not part of MVP medley eligibility.

---

# 4. USDX TXT Format Support

## 4.1 Supported Note Tokens
Supported body tokens:
- `:` Normal
- `*` Golden
- `F` Freestyle
- `R` Rap
- `G` RapGolden
- `-` sentence break
- `E` end of song data
- `P1`, `P2` duet track markers

### 4.1.1 Per-note fields
For note tokens, the TV interprets:
`<token> <startBeat> <duration> <tone> <lyricText...>`

- `startBeat` and `duration` are file beat units.
- `tone` is the chart tone value.
- `lyricText` is the remaining text on the line.

### 4.1.2 Duet structure
- A song is duet if the first non-empty body line begins with `P`.
- `P1` and `P2` select the active track.
- Notes and sentence breaks belong to the currently active track.
- The body ends with a single `E`.

## 4.2 Supported Header Tags and Semantics

### 4.2.1 Required tags
- `#TITLE`
- `#ARTIST`
- `#BPM`
- required audio reference per version rules

### 4.2.2 Timing/alignment tags
- `#GAP`
- `#START`
- `#END`
- `#PREVIEWSTART`

### 4.2.3 Media tags
- `#VIDEO`
- `#VIDEOGAP`
- `#INSTRUMENTAL`
- `#VOCALS`
- `#COVER`
- `#BACKGROUND`

YouTube-style or external `#VIDEO` references are non-local video references and therefore do not produce a local `videoUrl`.

### 4.2.4 Duet tags
- `#P1`
- `#P2`

These are stored for song metadata but are not used as the singer labels shown during TV gameplay.

### 4.2.5 In-song BPM changes
- Body `B` lines are not supported in MVP.
- A song containing variable BPM body lines MUST be rejected.

## 4.3 Error Handling
Header and body parsing are best-effort except for explicitly invalidating conditions.

**Warnings / continue**
- unknown tags,
- unknown body tokens,
- missing optional assets,
- duplicate known tags where the last valid value wins,
- malformed optional tags treated as absent.

**Invalid song**
- missing required headers,
- malformed required headers,
- missing required audio,
- malformed numeric fields for recognized body tokens,
- invalid duet markers,
- unsupported variable BPM,
- unsupported relative-mode sentence syntax,
- no remaining singable sentences after cleanup,
- unsupported or malformed `#VERSION`.

Invalid songs remain local diagnostics and are not published to the TV library.

## 4.4 Header Tags Reference
| Tag | Required | Purpose |
|---|---:|---|
| `#VERSION` | no | format version |
| `#TITLE` | yes | song title |
| `#ARTIST` | yes | song artist |
| `#AUDIO` | versioned | preferred audio reference |
| `#MP3` | versioned | legacy/fallback audio reference |
| `#BPM` | yes | beat/time basis |
| `#GAP` | no | chart/audio alignment |
| `#START` | no | initial playback offset |
| `#END` | no | playback stop override |
| `#PREVIEWSTART` | no | preferred preview start |
| `#VIDEO` | no | optional video |
| `#VIDEOGAP` | no | video offset |
| `#COVER` | no | optional cover image |
| `#BACKGROUND` | no | optional background image |
| `#INSTRUMENTAL` | no | backing instrumental |
| `#VOCALS` | no | optional guide vocal |
| `#MEDLEYSTARTBEAT` | no | medley window start |
| `#MEDLEYENDBEAT` | no | medley window end |
| `#P1` | no | duet singer metadata |
| `#P2` | no | duet singer metadata |

## 4.5 Body Token Reference
| Token | Meaning |
|---|---|
| `E` | end of song data |
| `P1` / `P2` | switch active track |
| `-` | sentence break |
| `:` | normal note |
| `*` | golden note |
| `F` | freestyle note |
| `R` | rap note |
| `G` | rap-golden note |

---

# 5. Timing and Beat Model

## 5.1 Authoritative Beat Definitions
- The chart beat grid is authoritative.
- The TV MUST interpret note timing from chart beats, song start, `#GAP`, and the active mic delay setting.
- Lyrics highlighting and note scoring use the same chart but different timing consumers.
- Invalid or missing pitch frames are treated as unvoiced for scoring purposes.

## 5.2 Pitch Frame Timing, Late-Frame Handling, and Mic Delay

### 5.2.1 Pitch observations and missing frames
- Assigned singer phones send periodic pitch observations during active singing.
- Missing or invalid observations are treated as unvoiced.

### 5.2.2 Playback-start timing origin
- The TV MUST establish the playback-start timing origin when playback actually begins.
- This timing origin MUST be used consistently for scoring and playback-aligned UI behavior.
- Exact timestamp capture mechanics are defined in `architecture/tv_app_architecture.md`.

### 5.2.3 Late-frame handling and note finalization
- Pitch observations are evaluated against note windows in TV-authoritative song time.
- The TV MUST allow for bounded network delay before finalizing a note.
- Observations arriving too late MUST NOT affect already-finalized notes.
- Exact late-frame thresholds and note-finalization timing are defined in `architecture/tv_app_architecture.md`.

### 5.2.4 Effective mic delay (manual)
- The TV exposes a manual mic delay setting in milliseconds.
- Default: `0 ms`.
- Valid range: `0–400 ms`.
- Mic delay shifts pitch-lane targets and scoring windows.
- Lyrics highlighting does not use mic delay.

## 5.3 Beat-Time Conversion (TV/Host)
- File beat values are the authoritative internal beat positions for MVP.
- The TV MUST derive timing deterministically from chart beat positions, `#BPM`, `#GAP`, `#START`, and active mic delay.
- Lyrics progression MUST follow speaker-audible playback timing.
- Pitch-lane targets and scoring windows MUST use the mic-delay-adjusted timing model.
- Note windows use **start-inclusive, end-exclusive** boundaries.

## 5.4 START/END
- `#START` sets the initial playback position for the song.
- `#END`, when present and greater than zero, defines the song stop point.
- Restarting a song resets playback to the same `#START`-adjusted beginning.
- If `#END` is absent or non-positive, song end is based on media duration.

---

# 6. Scoring

## 6.1 Scoring Overview
- Scoring is note-based and normalized to **10000 total points**.
- With line bonus enabled, **9000** points are reserved for notes and **1000** for line bonus.
- Scoring MUST be independent of render frame rate.

**Per-note scoring (normative)**
For each finalized note:
- Let `samplesInNote` be the qualifying frames for that note.
- If `samplesInNote` is empty, the note earns `0`.
- Otherwise:
  - `hits` = number of qualifying frames matching the note,
  - `N` = number of qualifying frames,
  - `max_note_score = (MaxSongPoints / TrackScoreValue) × ScoreFactor[noteType] × durationBeats`,
  - `note_score = max_note_score × (hits / N)`.

**Accumulation (normative)**
- Normal and Rap notes add to `Score`.
- Golden and RapGolden notes add to `ScoreGolden`.
- Freestyle notes contribute `0`.

**Sentence completion (normative)**
- A sentence is complete when its last scorable note is finalized.
- Line bonus is evaluated at sentence completion.

## 6.2 Note Types
- Freestyle: `F`
- Normal: `:`
- Golden: `*`
- Rap: `R`
- RapGolden: `G`

**Per-sample hit detection**
- Freestyle: never scores.
- Normal / Golden: frame must be voiced and within tolerance after octave normalization.
- Rap / RapGolden: frame must be voiced; pitch difference is ignored.

### 6.2.1 ScoreFactor constants
- Freestyle: `0`
- Normal: `1`
- Golden: `2`
- Rap: `1`
- RapGolden: `2`

## 6.3 Player Level / Tolerance
Per-player pitch tolerance:
- Easy: `±2`
- Medium: `±1`
- Hard: `±0`

Default difficulty: **Medium**.

## 6.4 Octave Normalization
Before comparison to the target note, the detected semitone value is octave-normalized exactly as follows:

```text
while (Tone - TargetTone > 6) Tone := Tone - 12
while (Tone - TargetTone < -6) Tone := Tone + 12
```

Rules:
- The TV derives `Tone` from `midiNote - 36`.
- The TV MUST use the full semitone value, not pitch class modulo 12, before the loop.

## 6.5 Line Bonus
- If line bonus is ON:
  - `MaxSongPoints = 9000`
  - `MaxLineBonusPool = 1000`
- If line bonus is OFF:
  - `MaxSongPoints = 10000`
  - `MaxLineBonusPool = 0`

Definitions:
- `TrackScoreValue = sum(duration × ScoreFactor)` over the track.
- `LineScoreValue = sum(duration × ScoreFactor)` over the line.
- `MaxLineScore = MaxSongPoints × (LineScoreValue / TrackScoreValue)`.

At sentence completion:
- `LineScore = (Score + ScoreGolden) - ScoreLast`
- If `MaxLineScore <= 2`, `LinePerfection = 1`
- Else `LinePerfection = clamp(LineScore / (MaxLineScore - 2), 0, 1)`

When line bonus is enabled:
- Empty lines do not receive line bonus.
- `LineBonusPerLine = MaxLineBonusPool / NonEmptyLines`
- `ScoreLine += LineBonusPerLine × LinePerfection`

**Medley rule**
- For medley scoring, only notes inside the medley window contribute to track score value and scoring.

## 6.6 Rounding and Display
- `ScoreInt = round(Score / 10) × 10`
- `ScoreLineInt = floor(round(ScoreLine) / 10) × 10`
- `ScoreGoldenInt` rounds in the opposite direction from `ScoreInt` when needed so the total cannot exceed `10000` because of `.5` rounding.
- `ScoreTotalInt = ScoreInt + ScoreGoldenInt + ScoreLineInt`

The asymmetry between score rounding and line-bonus rounding is intentional and normative.

---

# 7. Multiplayer, Pairing, and Session Lifecycle

## 7.1 Session States
The TV owns session state.

States:
- **Open**: phones may join.
- **Locked**: a song is in progress; new joins are rejected.
- **Ended**: current session token is invalid.

Lifecycle:
- On TV app launch, a new **Open** session is created.
- The session becomes **Locked** when the TV starts the song-start sequence for assigned singers.
- Returning to Song List after song end or quit returns the session to **Open**.
- Ending the session from TV settings invalidates the old session and creates a new open session.
- TV navigation alone does not change session state.

## 7.2 Pairing UX (TV)
- The TV MUST expose join QR and join code.
- Song List provides a compact Join entry point.
- Settings > Connect Phones provides the join UI plus the connected-device roster.

**Admission rules**
- Up to **10** devices may join while the session is open.
- Additional joins are rejected with `session_full`.
- Joins during locked state are rejected with `session_locked`.

**Roster actions**
- Rename device
- Kick device
- Forget device

Kick and Forget require a confirm dialog with default focus on Cancel.

## 7.3 Phone as Session Participant (TV-facing contract)
- A joined phone may be a spectator or assigned singer.
- Assigned singers receive `assignSinger` and participate in countdown/singing.
- Non-selected phones do not receive singer assignment for that song.
- A phone may leave the session voluntarily; automatic reconnect is not used for explicit leave.
- If the TV rejects a join, the phone receives an error and returns to its join state.

## 7.4 Disconnect/Reconnect
**Required singer disconnect**
- If an assigned singer disconnects during a song, the TV MUST pause automatically and show the disconnect overlay.

**Spectator or non-singer disconnect**
- The TV MUST NOT pause solely because a spectator or non-singing song source disconnected.
- However, if active media came from that phone and becomes unavailable, playback follows the normal playback error path.

**Reconnect behavior**
- Reconnect within the same session reclaims the same logical phone identity via `clientId`.
- If the reconnecting phone was an assigned singer, the TV MUST restore that singer role and send current playback state.
- On reconnect, the TV refreshes that phone's catalog.
- Stale transport data from the pre-reconnect connection MUST NOT affect active gameplay.

---

# 8. Network Protocol

## 8.1 Transport Channels (Common)
The system uses:
- **WebSocket** for control messages,
- **HTTP** for manifest and song assets,
- **UDP** for binary pitch frames.

**Song source policy**
- After successful join, the TV fetches the phone's manifest and exposes those songs in the TV library.

**Session token / join code**
- The TV session token is also the human-enterable join code.
- It is generated per session and must not be reused across sessions.
- Missing or incorrect token results in `invalid_token`.

## 8.2 Session Discovery
- The QR code encodes the full WebSocket endpoint including the session token.
- Manual code entry resolves a matching TV session on the local network.
- If multiple sessions match, the phone must choose one explicitly.
- Internet-based discovery is out of scope.

## 8.3 Control Messages
The TV and phones exchange a small control-message set for:
- join handshake,
- session state,
- singer assignment,
- playback-state synchronization,
- error reporting,
- clock synchronization.

### 8.3.1 Handshake
- A joining phone identifies itself and its capabilities.
- The TV replies with current session state and either accepts or rejects the join.
- Rejection reasons include invalid token, protocol mismatch, full session, and locked session.

### 8.3.2 Singing
- When a phone is selected as a singer, the TV sends a singer-assignment message containing the information required to begin countdown or live singing.
- During an active run, the TV sends playback-state updates so phones can mirror countdown, active singing, pause, and stop state.
- The TV MUST emit playback-state updates whenever playback meaningfully changes for connected phones.

### 8.3.3 Validation Rules
- Unexpected control messages during handshake are fatal to the join attempt.
- Protocol version mismatch rejects the join.
- Unknown non-handshake message types are ignored.

## 8.4 Versioning & Compatibility
- MVP uses a single protocol version shared by TV and phone.
- A phone using a different protocol version is rejected.

## 8.5 Sender Identification
- Each successful phone connection receives a transport-level sender identity for its pitch stream.
- Reconnects receive a fresh transport identity.
- Stale or mismatched sender identity data must be discarded.

## 8.6 Pitch Stream
- During active singing, phones send binary pitch observations over UDP.
- Each observation identifies the current song run, singer slot, and voiced/unvoiced pitch state.
- Invalid, stale, malformed, or mismatched observations are dropped.
- Voiced pitch observations are converted into the semitone basis used for TV scoring.

The exact datagram layout is defined in `architecture/tv_app_architecture.md`.

## 8.7 Song File Delivery
**Manifest contract**
- The phone MUST serve its current song catalog at `GET /manifest.json`.

**Asset sourcing**
- Song asset URLs are published by the phone in the manifest.
- The TV MUST use asset URLs only from the joined peer that contributed the corresponding song.

**Failure behavior**
- Missing or failed optional images/video are treated as absent.
- Required audio failure during start or playback follows the song-start or playback-error rules in Section 9.

Detailed HTTP transport requirements are defined in `architecture/tv_app_architecture.md`.

## 8.8 Clock Sync
Goal: allow phones to timestamp pitch observations in the TV time domain.

Rules:
- Clock sync is TV-initiated.
- Initial sync occurs on connection.
- Sync is suspended during active singing.
- Reconnect or post-song refresh triggers a lightweight re-sync.

Phones use the resulting TV-time estimate when timestamping pitch observations.
Detailed clock-sync message math and sampling rules are defined in `architecture/tv_app_architecture.md`.

---

# 9. UI Screens and Flows - TV

## 9.1 Global navigation and input
- Primary input is TV remote: DPAD, OK/Enter, Back.
- Overlays and dialogs close before underlying screens respond to Back.
- From Song List:
  - Back clears active filter first,
  - otherwise exits the app.
- From Settings root, Back returns to the previous TV screen.
- From Singing, Back opens the pause overlay.
- From Results, Back returns to Song List.

**Long-press OK (normative)**
- A long-press is `>= 500 ms`.
- If a screen defines a long-press action, it triggers that action.
- Otherwise it behaves like a normal OK.

## 9.2 Song preview playback
Preview may start only when:
- a song tile is focused,
- focus remains on that song for **500 ms**,
- preview volume is non-zero.

Preview MUST stop immediately when:
- focus changes song,
- focus leaves the grid,
- a modal opens,
- Settings opens,
- singing starts,
- Song List is hidden.

Preview behavior:
- Preview uses the selected song's preview audio.
- Start position uses `previewStartSec` when available.
- If no positive preview start is available, fallback is based on song duration.
- If preview audio is unavailable, preview is suppressed silently.

## 9.3 Select Players modal

### 9.3.1 Purpose and presentation
- This modal bridges song selection into active singing.
- It is used for normal song starts and medley starts.
- For medley, the same selected players remain assigned for the full medley run.

### 9.3.2 Fields and selection model
- Player 1 device: required.
- Player 2 device: optional for duet, disabled or hidden otherwise.
- Difficulty is configurable per player.

### 9.3.3 Gating rules by song type
- Duet song:
  - Player 1 required.
  - Player 2 optional.
  - If one player is selected, the singer chooses which duet part to sing.
  - If two players are selected, Swap Parts is available.
- Non-duet song:
  - Player 1 required.
  - Player 2 selector visible but disabled.
- Medley:
  - Player 2 controls are hidden entirely.

### 9.3.4 Empty states, start flow, and failure handling
- If no phones are connected, show a blocking `No phones connected` state with a path to **Settings > Connect Phones**.
- If required audio for the selected song is unavailable, the TV MUST block start and show an error.
- If song start fails after the user presses Start, the TV MUST:
  - abort start,
  - return to Song List,
  - show a blocking error modal with:
    - Title: `ERROR`
    - Body line 1: `This song can't be played.`
    - Body line 2: `Check Settings > Song Library — the song's phone may be disconnected.`

### 9.3.5 Actions and protocol side effects
- **Start** begins countdown or immediate playback depending on gameplay settings.
- **Cancel/Back** closes the modal.
- On Start, the TV sends `assignSinger` only to selected singer phones.
- Countdown ON uses `startMode="countdown"` with `countdownMs`.
- Countdown OFF uses `startMode="live"`.

## 9.4 Settings Screen
The TV root settings screen contains:
- Connect Phones
- Song Library
- Audio
- Scoring Timing
- Gameplay
- Video

### 9.4.1 Settings > Connect Phones
- Shows join QR/code and current connected devices.
- Supports Rename, Kick, Forget, and End session.
- End session invalidates the old session and creates a new open session.

### 9.4.2 Settings > Song Library
For each connected phone, show:
- device name,
- valid song count,
- invalid song count if any,
- Refresh action.

Also provide **Refresh all**.

### 9.4.3 Settings > Audio
- **Preview Volume**: 0–100, affects preview only.
- **Vocals Volume**: 0–100, default 50, affects `#VOCALS` guide track when present with `#INSTRUMENTAL`.
- Mic sensitivity remains phone-owned and is not a TV setting.

### 9.4.4 Settings > Scoring Timing
- Exposes manual mic delay in milliseconds.
- Valid range: `0–400`.

### 9.4.5 Settings > Gameplay
- Line bonus ON/OFF.
- Ready countdown ON/OFF.
- Countdown length: `1–10` seconds.
- Show note lines ON/OFF.

### 9.4.6 Settings > Video
- Video enabled ON/OFF.
- If video is disabled or unavailable, the singing screen uses the song background image if present, otherwise the app default background.

## 9.5 Singing Screen

### 9.5.1 Layout and overlays
The singing screen MUST show:
- lyrics with progressive highlight,
- one or two pitch lanes depending on singer count,
- per-singer score,
- elapsed time,
- instrumental gap indicator when applicable.

A single singer uses a vertically centered lane.
Two singers use stacked lanes.

### 9.5.2 Visual stability and performance
- The singing screen MUST prioritize readability and stable motion over decorative effects.
- Visual treatment MUST NOT introduce noticeable lag, jumping, or readability loss during singing.

### 9.5.3 Lyrics and sentence rating
- Lyrics are sentence-paged, not continuously scrolled.
- The active sentence remains stable while highlight advances.
- During instrumental gaps between sentences, the completed sentence remains visible until the next one begins.

Sentence rating labels:
- `Perfect!` for `1.00`
- `Great` for `>= 0.80`
- `Good` for `>= 0.60`
- `Cool` for `>= 0.40`
- `Okay` for `>= 0.20`
- `Poor` for `< 0.20`

### 9.5.4 Countdown and start interruption
- If ready countdown is ON, countdown displays at 1 Hz and playback starts after `1`.
- If a required singer disconnects during countdown, the TV MUST cancel start, return to Select Players, and show a blocking disconnect modal.

### 9.5.5 Pause and disconnect handling
Back opens a pause overlay with:
- Resume
- Restart Song
- Quit to Song List

**Singer disconnect overlay**
If an assigned singer disconnects mid-song, the TV MUST pause automatically and show:
- Wait for reconnect
- Continue without them
- Quit to Song List

Spectator disconnects do not trigger auto-pause.

### 9.5.6 Playback error and song end behavior
**Playback error**
If playback fails during singing, the TV MUST:
1. stop playback and scoring,
2. return to Song List,
3. show a blocking error modal,
4. return the session to open state.

**Song end**
- `stopAtLyricsTimeMs` is the authoritative stop point communicated to assigned singer phones.
- At song end, phones stop sending frames and return to waiting state.
- The TV finalizes scoring and transitions to Results.

### 9.5.7 Singing Screen (Medley mode)
Medley mode plays a sequence of medley-eligible songs back-to-back.

Rules:
- Select Players is shown once at medley start.
- Selected players remain assigned for the whole medley.
- The current medley run uses an immutable snapshot of the playlist order.
- The TV sends medley-source playback state to phones whose songs are used as medley sources.

**Medley window**
For each segment:
- play and score only the medley window defined by `#MEDLEYSTARTBEAT` and `#MEDLEYENDBEAT`,
- extend playback with fade-in and fade-out windows,
- notes outside the medley window contribute no score.

**Segment transitions**
- At segment end, advance automatically to the next segment.
- If a segment's required audio is unavailable when reached, skip that segment with a brief error toast.
- If playback fails mid-segment, abort the medley run and follow the normal playback-error flow.

**Header display**
- While singing medley with multiple segments, display `<i>/<n>: <Artist> — <Title>`.

## 9.6 Results Screen (TV)

### 9.6.1 Post-song results
Show per singer:
- Notes score,
- Golden score,
- Line bonus,
- Song Total.

Only action: **Back to Song List**.
Back key behaves the same as selecting that action.

### 9.6.2 Post-medley results
- Show one row per medley segment.
- Show a final Medley Total row.
- Medley Total is the rounded mean of segment `scoreTotalInt` values per player.
- Only action: **Back to Song List**.

---

# Appendix C: Parsed Song Model (Functional)

## C.1 ParsedSong
Minimum functional structure:
- header metadata,
- song timing metadata,
- one or two tracks,
- medley metadata when present.

## C.2 SongHeader
Minimum functional fields:
- title
- artist
- album
- audio reference
- optional video/background/cover/instrumental/vocals references
- optional duet labels
- custom tags preserved in encounter order

## C.3 SongTiming
Minimum functional fields:
- `bpmFile`
- `gapMs`
- `startSec`
- `endMs`
- optional `previewStartSec`
- optional `videoGapSec`

## C.4 Track
A track contains ordered lines and notes for one singer lane.

## C.5 Line
A line contains ordered notes that are evaluated together for line bonus.

## C.6 NoteEvent
Each note event contains at least:
- note type,
- `startBeat`,
- `duration`,
- `tone`,
- lyric text.
