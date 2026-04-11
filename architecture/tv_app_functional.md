# Couchraoke TV App — Functional Specification

**Version**: 1.0  
**Date**: 2026-04-11  
**Scope**: Android TV Host App — User Interface and Behavior  
**Technical Architecture Reference**: [tv_app_architecture.md](./tv_app_architecture.md)

---

## Table of Contents

- [1. Product Decisions](#1-product-decisions)
  - [1.1 Playback Modes](#11-playback-modes)
  - [1.2 Scoring Defaults](#12-scoring-defaults)
- [2. Global Navigation and Input](#2-global-navigation-and-input)
  - [2.1 Navigation Model](#21-navigation-model)
  - [2.2 Back Behavior](#22-back-behavior)
  - [2.3 Selection and Long-Press](#23-selection-and-long-press)
- [3. Song Library](#3-song-library)
  - [3.1 Library Lifecycle](#31-library-lifecycle)
  - [3.2 Discovery Rules](#32-discovery-rules)
  - [3.3 Validation Rules](#33-validation-rules)
  - [3.4 Index Fields](#34-index-fields)
- [4. Song List (Landing Screen)](#4-song-list-landing-screen)
  - [4.1 Header Actions and Pairing](#41-header-actions-and-pairing)
  - [4.2 Layout and Preview Pane](#42-layout-and-preview-pane)
  - [4.3 Song Grid and Search](#43-song-grid-and-search)
  - [4.4 Medley Playlist](#44-medley-playlist)
  - [4.5 Focus and Navigation](#45-focus-and-navigation)
  - [4.6 Medley Eligibility](#46-medley-eligibility)
  - [4.7 Wireframe](#47-wireframe)
- [5. Select Players Modal](#5-select-players-modal)
  - [5.1 Purpose and Presentation](#51-purpose-and-presentation)
  - [5.2 Fields and Selection](#52-fields-and-selection)
  - [5.3 Gating Rules by Song Type](#53-gating-rules-by-song-type)
  - [5.4 Start Flow and Error Handling](#54-start-flow-and-error-handling)
  - [5.5 Actions and Protocol Effects](#55-actions-and-protocol-effects)
  - [5.6 Wireframes](#56-wireframes)
- [6. Settings Screen](#6-settings-screen)
  - [6.1 Connect Phones](#61-connect-phones)
  - [6.2 Song Library](#62-song-library)
  - [6.3 Audio](#63-audio)
  - [6.4 Scoring Timing](#64-scoring-timing)
  - [6.5 Gameplay](#65-gameplay)
  - [6.6 Video](#66-video)
- [7. Singing Screen](#7-singing-screen)
  - [7.1 Layout and Overlays](#71-layout-and-overlays)
  - [7.2 Lyrics and Sentence Rating](#72-lyrics-and-sentence-rating)
  - [7.3 Countdown and Start](#73-countdown-and-start)
  - [7.4 Pause and Disconnect Handling](#74-pause-and-disconnect-handling)
  - [7.5 Song End Behavior](#75-song-end-behavior)
  - [7.6 Medley Mode](#76-medley-mode)
- [8. Scoring System](#8-scoring-system)
  - [8.1 Scoring Model](#81-scoring-model)
  - [8.2 Note Types](#82-note-types)
  - [8.3 Difficulty and Tolerance](#83-difficulty-and-tolerance)
  - [8.4 Octave Normalization](#84-octave-normalization)
  - [8.5 Line Bonus](#85-line-bonus)
  - [8.6 Rounding and Display](#86-rounding-and-display)
- [9. Session Lifecycle](#9-session-lifecycle)
  - [9.1 Session States](#91-session-states)
  - [9.2 Join and Admission](#92-join-and-admission)
  - [9.3 Disconnect and Reconnect](#93-disconnect-and-reconnect)
- [10. Results Screen](#10-results-screen)
  - [10.1 Post-Song Results](#101-post-song-results)
  - [10.2 Post-Medley Results](#102-post-medley-results)

---

# 1. Product Decisions

Locked decisions that affect functional behavior across the app.

## 1.1 Playback Modes

**Instrumental playback** (`#INSTRUMENTAL`)

When `#INSTRUMENTAL` is present and the file exists:
- The TV MUST use the instrumental file as the sole backing track (replacing `#AUDIO`/`#MP3`)
- Plays from start to end, uninterrupted (no gap-based track switching)

**Vocals mixing** (`#VOCALS`)

When `#VOCALS` is present alongside `#INSTRUMENTAL`:
- TV MUST mix vocals track at user-configurable volume (default: 50%)
- Adjustable via [Settings > Audio > Vocals Volume](#63-audio)
- Allows players to use original singer as pitch guide
- If `#INSTRUMENTAL` is absent, `#VOCALS` is ignored

**Instrumental gap indicator**

An "instrumental gap" is a chart region where no scorable note (Normal, Golden, Rap, RapGolden) is active for >2 continuous seconds. During such regions:
- Pitch lane MUST display a pulsing animated rest indicator (e.g., horizontal dashed line or wave graphic)
- Purely visual — no effect on audio track selection
- Disappears when next scorable note approaches within highlight window

## 1.2 Scoring Defaults

| Setting | Default | Notes |
|---------|---------|-------|
| Difficulty | Medium | Per newly assigned singer |
| Line bonus | ON | Reserves 1000 of 10000 points |
| Duet | Supported | Swap parts: YES |
| Rap | Supported | Presence-based scoring |
| Freestyle | No scoring | `ScoreFactor = 0` |
| Video backgrounds | Supported | Toggleable in Settings |

---

# 2. Global Navigation and Input

Primary input is TV remote (DPAD + OK/Enter + Back).

## 2.1 Navigation Model

- The TV app uses a simple navigation stack.
  - Entering a full-screen screen **pushes** it onto the stack.
  - Pressing **Back** on a full-screen screen **pops** the current screen and returns to the previous screen.
- Overlays/modals (Advanced Search, Select Players, dialogs) do not affect the navigation stack; Back closes the overlay and returns to the underlying screen.

## 2.2 Back Behavior

| Context | Back Action |
|---------|-------------|
| Song List (filter active) | Clears the filter |
| Song List (no filter) | Exits app / returns to Android launcher |
| Settings (root) | Returns to previous screen in navigation stack |
| Settings sub-screens | Returns to Settings (root) |
| Modal dialogs/overlays | Closes overlay, returns to underlying screen |
| Singing | Opens Pause overlay (Resume / Restart Song / Quit to Song List) |
| Results | Returns to Song List |

**Special case — Settings entered from Select Players "No phones connected" action:** pressing Back on the Settings root MUST return to the Select Players modal (not Song List). Implementations MUST track this entry context explicitly; it cannot be inferred from the navigation stack alone, because modals do not push onto the navigation stack.

## 2.3 Selection and Long-Press

- **OK/Enter** selects highlighted item.
- **DPAD** navigates focus in lists and menus.
- **Long-press OK** is a press-and-hold of OK/Enter for **>= 500 ms**.
  - When a screen defines a long-press action, the long-press MUST trigger that secondary action.
  - When no long-press action is defined, long-press MUST behave the same as a normal OK.

---

# 3. Song Library

The TV's in-memory library index aggregates songs from all connected phones. It is rebuilt each session and not persisted. The TV holds no song files — all media is streamed directly from the phone's HTTP server on demand.

## 3.1 Library Lifecycle

**Catalog fetch triggers**

The TV rebuilds its library by fetching `GET /manifest.json` from each connected phone:

| Trigger | When |
|---------|------|
| Phone connection | After successful `hello`/`sessionState` handshake, before songs visible |
| Results screen | When displayed (after any song/medley), re-fetch all manifests |
| Manual refresh | Settings > Song Library → Refresh / Refresh all |

On fetch, TV replaces all songs attributed to that phone's `clientId` with fetched entries. **If fetch fails** (HTTP error, timeout, unreachable): retain previous catalog for that phone and show brief error toast.

**Phone disconnect**

When a phone's WebSocket drops, TV MUST immediately remove all songs attributed to that `clientId` from the library — songs become invisible and unselectable. Any in-progress playback from that phone handles per [§7.4](#74-pause-and-disconnect-handling).

## 3.2 Discovery Rules

The phone scans for **all `.txt` files recursively** under its configured songs folder. Each `.txt` is treated as a distinct song entry, even if multiple `.txt` files exist in the same folder.

## 3.3 Validation Rules

A song entry is accepted into the library if and only if all checks pass. Invalid songs are rejected with diagnostics.

**Required header tags**

- `#TITLE` and `#ARTIST`: MUST be present and non-empty
- `#BPM`: MUST be present and parseable as non-zero float
- Audio reference:
  - For `#VERSION >= 1.0.0`: at least one of `#AUDIO` or `#MP3` (if both, `#AUDIO` takes precedence)
  - For legacy format: `#MP3` required, `#AUDIO` ignored

**Required audio file**

- Audio file referenced MUST exist relative to the `.txt` directory

**Notes section**

- MUST parse without fatal errors
- Unknown tokens handled with warning (continue)
- Fatal numeric parse error → reject

**Track content**

- Each track MUST have at least one non-empty sentence after cleanup
- Empty sentences (zero note events) are removed before this check

**Missing optional files**

| File | Behavior |
|------|----------|
| Required audio | Load fails |
| Video | Logged; song loads (feature disabled) |
| Instrumental | Logged; song loads (feature disabled) |

No audio format validation at scan time — format compatibility determined at playback.

## 3.4 Index Fields

**Identity / storage**

| Field | Description |
|-------|-------------|
| `phoneClientId` | `clientId` of the phone that provided this song |
| `relativeTxtPath` | Normalized relative path of `.txt` (separators `/`, no leading `/`, no `.`/`..`, case preserved) |
| `songId` | `phoneClientId + "::" + relativeTxtPath` |
| `modifiedTimeMs` | Last-modified timestamp at scan time |

**Display fields**

| Field | Required |
|-------|----------|
| `artist`, `title` | Yes |
| `album` | No |

**Flags**

| Flag | Derivation |
|------|------------|
| `isDuet` | True if song is duet |
| `hasRap` | True if any `R` or `G` notes exist |
| `hasVideo` | True if video reference exists and file present |
| `hasInstrumental` | True if `#INSTRUMENTAL` exists and file present |
| `canMedley` | True if medley-eligible (see [§4.6](#46-medley-eligibility)) |
| `medleySource` | `null` or `"tag"` |
| `medleyStartBeat`, `medleyEndBeat` | Required if `medleySource != null` |

**Preview/seek metadata**

| Field | Computation |
|-------|-------------|
| `startSec` | From `#START`, default 0.0 |
| `previewStartSec` | `#PREVIEWSTART` if >0, else `timeFromBeat(medleyStartBeat)` if medley, else 0.0 |

**Asset URLs** (from `/manifest.json`)

| Field | Description |
|-------|-------------|
| `txtUrl` | URL to `.txt` file (required for valid songs) |
| `audioUrl` | Primary audio file (null if absent) |
| `videoUrl` | Local video file (null for YouTube refs / absent) |
| `coverUrl` | Cover image for song grid |
| `backgroundUrl` | Background image |
| `instrumentalUrl` | Instrumental audio file |
| `vocalsUrl` | Vocals audio file |

---

# 4. Song List (Landing Screen)

The Song List is always the landing screen (even if library is empty). Songs are displayed sorted by **Artist → Album → Title**. Only one song (or one medley segment) is played at a time.

## 4.1 Header Actions and Pairing

**Header actions**

| Element | Position | Action |
|---------|----------|--------|
| Search field | Top row | Primary top-level re-entry point for focus |
| Join button | Top row | Opens pairing UI for current session |
| ⚙ Settings button | Top row | Opens Settings screen |
| Join code (text) | Top row | Shows current join code (e.g., `Code: ABCD-EFGH`) |

**Pairing behavior**

- The Song List MUST expose session joining from the landing screen via the **Join** button.
- Activating **Join** MUST open a TV-side pairing overlay showing:
  - the session **QR code**
  - the **join code**
- The QR payload MUST encode the full WebSocket endpoint URL (including the `token` query parameter).
- The Song List MUST NOT show a connected-device roster (management is in [Settings > Connect Phones](#61-connect-phones)).

**QR sizing requirements**

| Aspect | Requirement |
|--------|-------------|
| Minimum size | 320 dp × 320 dp |
| Recommended size | 360–420 dp square on 1080p |
| Quiet zone | At least 4 modules on all sides |
| Contrast | High contrast (dark on light), no transparency or gradients |
| Position | Centered within the modal, not occluded by UI chrome |
| Join code text | Below QR, minimum 24 sp, sufficient character spacing |
| Animation | QR MUST remain static |

## 4.2 Layout and Preview Pane

**Two-column layout**

- **Left panel**: Preview pane, Medley playlist, Play Medley / Random Medley actions
- **Right panel**: Search field, Random Song / Random Duet actions, song grid

**Preview pane**

- Positioned in the left panel above the Medley playlist.
- MUST use a **16:9** aspect ratio.
- **Display-only and non-focusable** — MUST NOT participate in the DPAD focus graph.
- Driven entirely by the currently focused song tile in the grid.

**Preview playback**

A preview MAY start only when:
- A song tile is focused, AND
- Focus remains on the same song for **500 ms** (debounce), AND
- Preview Volume is non-zero ([Settings > Audio](#63-audio)).

Preview MUST stop immediately when:
- Focus moves to a different song tile
- Focus leaves the song grid
- Any overlay/modal opens (Advanced Search, Select Players, Settings)
- Singing starts or screen loses focus

**What plays**

- Preview uses the song's `audioUrl` from the cached manifest.
- Start position from `previewStartSec` in the song's index entry; fallback: `min(audioLength/4, 60.0)` seconds.
- Playback continues until stopped by the rules above (no fixed duration limit).
- If `audioUrl` is null or HTTP fails, suppress preview silently (no error shown).
- Volume controlled by **Settings > Audio > Preview Volume** (0 = silence/disabled).

**Empty states**

| Condition | Message | Hint |
|-----------|---------|------|
| No phones connected | "No phones connected." | "Connect a phone to see songs. Open the karaoke app on your phone and scan the QR code." |
| Phones connected, no valid songs | "No songs found." | "Open the karaoke app on your phone and make sure the songs folder is set." |

## 4.3 Song Grid and Search

**Song card display**

Each song tile shows:
- Cover image (or placeholder)
- Title + Artist
- Bottom-right tag overlays (single-letter chips):
  - `D` = duet (`isDuet=true`)
  - `R` = rap (`hasRap=true`)
  - `V` = video (`hasVideo=true`)
  - `I` = instrumental (`hasInstrumental=true`)
  - `M` = medley-eligible (`canMedley=true`)

**Grid column count**: 3 columns at 1080p, 4 columns at 4K. Column count MUST NOT change while screen is displayed.

**Search behavior**

- **Case-insensitive substring** match across artist, album, title.
- Input MUST be debounced by **150 ms**.
- Filtering preserves underlying sort order (Artist → Album → Title).
- **OK** on Search field opens the Android TV system text input dialog.

**Primary actions**

| Input | Action |
|-------|--------|
| OK on song tile | Opens [Select Players](#5-select-players-modal) modal |
| Long-press OK on song tile | Add to Medley (if `canMedley=true`) |
| Long-press OK on non-medley song | Blocking modal: "This song can't be used in a medley. Look for songs with an M tag in the lower right corner" |

**Random actions**

| Action | Behavior |
|--------|----------|
| Sing Random Song | Selects random valid song from filtered set, opens Select Players |
| Sing Random Duet | Selects random valid duet from filtered set, opens Select Players |
| Sing Random Medley | Selects 5 random medley-eligible songs (or all if fewer), opens Select Players. Requires ≥2 songs. |

Random buttons MUST be disabled (not focusable) when no eligible songs exist in the filtered set.

## 4.4 Medley Playlist

The Medley playlist is a **transient in-memory list** of songs to be played back-to-back in medley mode.

**Lifecycle**

- Initialized empty each time Song List is shown.
- Cleared when leaving for a non-modal screen (Settings, starting a song/medley, Results).
- Opening/closing modal overlays MUST NOT clear it.

**Display**

- Fixed-height list: **lesser of 7 lines or 25% of screen height** (minimum 3 lines visible).
- Row format: `<Artist>  <Title>` (no row number).
- Scrolls when content exceeds visible height.

**Playlist actions**

| Action | Behavior |
|--------|----------|
| Play Medley | Opens [Select Players](#5-select-players-modal) for the entire medley run. Disabled if playlist empty. |
| OK on playlist row | Enters **Reorder mode**: Up/Down moves item; OK confirms; Back cancels. Left/Right do nothing. |
| Long-press OK on playlist row | Deletes row immediately (no confirmation) |

**Reorder mode hints**: `Up/Down=Move  OK=Accept  Back=Cancel`

## 4.5 Focus and Navigation

**Focus allocation**

- Preview pane: non-focusable
- Focusable in left panel: Medley playlist rows, Play Medley, Random Medley
- Focusable in top/right: Search field, Random Song, Random Duet, Join, Settings, song grid tiles

**Initial focus**

On entering Song List (including app launch and return from Singing/Results):
- First tile in song grid (top-left), OR
- Search field if grid is empty

**DPAD navigation**

| Current Focus | Up | Down | Left | Right |
|---------------|-----|------|------|-------|
| Search field | — | First grid tile | Join button | Settings button |
| Join button | — | First grid tile | — | Search field |
| Settings button | — | First grid tile | Search field | — |
| Grid tile (top row) | Search field | Tile below | Left panel entry | Tile right |
| Grid tile (other) | Tile above | Tile below | Left panel entry | Tile right |
| Medley playlist row | Previous row / Play Medley | Next row / Random Medley | — | Search field |
| Play Medley | Last playlist row | Random Medley | — | Search field |

**Left-panel entry priority** (from leftmost grid column):
1. First Medley playlist row, if present
2. Play Medley button, if playlist empty
3. Random Medley button, as fallback

**Back behavior**

- Modal/overlay open: Close it per [§2](#2-global-navigation-and-input)
- Focus in grid or left panel: Move focus to Search field
- Focus in top controls with active filter: Clear the filter
- Focus in top controls without filter: Exit app

## 4.6 Medley Eligibility

`canMedley` is computed at scan/index time. A song is medley-eligible iff:
- `isDuet = false`, AND
- `#MEDLEYSTARTBEAT` and `#MEDLEYENDBEAT` are both present, parse as integers, and `startBeat < endBeat`

**Note**: Automatic medley calculation (`#CALCMEDLEY`) is deferred for MVP. Only explicit medley tags enable eligibility.

## 4.7 Wireframe

```text
+--------------------------------------------------------------------------------------------------+
|  Code: ABCD-EFGH   Search: [______________________________]     [ JOIN ]   [ ⚙ SETTINGS ]       |
+--------------------------------------------------------------------------------------------------+
|                [ Random Song ]   [ Random Duet ]   [Random Medley]                               |
+--------------------------------------------------------------------------------------------------+
|  +--------------------------------------+     +----------------------------------------------+   |
|  | PREVIEW PANE (16:9)                  |     | SONG GRID                                    |   |
|  | (display-only; non-focusable)        |     |  +---------+ +---------+ +---------+ +-----+ |   |
|  |                                      |     |  | Cover   | | Cover   | | Cover   | | ... | |   |
|  +--------------------------------------+     |  | Title   | | Title   | | Title   | |     | |   |
|  | Title                                |     |  | Artist  | | Artist  | | Artist  | |     | |   |
|  | Artist                               |     |  | [V]     | | [D]     | | [I][M]  | |     | |   |
|  | [V] [D] [R] [I] [M]                  |     |  +---------+ +---------+ +---------+ +-----+ |   |
|  +--------------------------------------+     |                                              |   |
|  | MEDLEY PLAYLIST                      |     |  Tags: [D]=Duet  [R]=Rap  [V]=Video          |   |
|  | (max 7 lines or 25% height; scrolls) |     |        [I]=Inst  [M]=Medley                  |   |
|  |  +-------------------------------+   |     +----------------------------------------------+   |
|  |  | <artist>  <song>              |   |                                                        |
|  |  | <artist>  <song>              |   |                                                        |
|  |  | <artist>  <song>              |   |                                                        |
|  |  +-------------------------------+   |                                                        |
|  |         [ PLAY MEDLEY ]          |   |                                                        |
|  |                                  |   |                                                        |
|  +--------------------------------------+                                                        |
+--------------------------------------------------------------------------------------------------+
| Contextual help:                                                                                 |
|  - Song grid: OK = Sing   Long-Press OK = Add to Medley                                          |
|  - Medley playlist: OK = Reorder   Long-Press OK = Delete                                        |
+--------------------------------------------------------------------------------------------------+
```

---

# 5. Select Players Modal

The Select Players modal is the handoff point between song selection and active singing. It defines player assignment and playback-start rules.

## 5.1 Purpose and Presentation

**Purpose**

- On starting a song (including via Random actions) and on starting a medley run, select which connected phone(s) sing.
- For medley playback, selected players MUST remain assigned for the entire medley run (no prompts between segments).

**Presentation**

- Modal overlay
- Title: `SELECT PLAYERS`
- Subtitle:
  - Single-song: `<Artist> — <Title>`
  - Medley: `Medley — <n> songs` (playlist count at open time)

## 5.2 Fields and Selection

| Field | Description |
|-------|-------------|
| Player 1 device | Required; dropdown of connected phones |
| Player 2 device | Present but may be disabled/hidden by song type |
| Difficulty (per player) | Easy / Medium / Hard |

## 5.3 Gating Rules by Song Type

**Duet songs**

- Player 1: required
- Player 2: optional
- Two players selected: Player 1 sings P1, Player 2 sings P2; provide **Swap Parts**
- One player selected: allow selecting which duet part (P1 or P2)

**Non-duet songs**

- Player 1: required
- Player 2 selector: visible but **disabled** (cannot be selected)
- Player 2 Difficulty: **hidden** when Player 2 is `(none)`

**Medley play**

- All medley songs are non-duet (`canMedley` requires `isDuet=false`)
- Player 2 section (phone selector and difficulty) MUST be **hidden entirely**

## 5.4 Start Flow and Error Handling

**No phones connected**

Show blocking message `No phones connected` with primary action to open [Settings > Connect Phones](#61-connect-phones).

**Song start**

- **Single-song**: When user presses **Start**, TV fetches `txtUrl` synchronously, parses it, hands `audioUrl`/`videoUrl` to ExoPlayer. Playback starts within 1–2 seconds.
- **Medley**: Same as single-song. Segment `txtUrl` values MAY be fetched eagerly in background (optional, MUST NOT block Start).

**Missing audio**

If `audioUrl` is null (file unavailable on phone), show error before starting:
> `Cannot load song — audio file is unavailable on the phone.`

**Playback start failure**

If playback fails after **Start** (URL unreachable, phone disconnected):
- Abort start
- Return to Song List
- Show blocking error modal (`OK` action, default focus):
  - Title: `ERROR`
  - Body: `This song can't be played.` / `Check Settings > Song Library — the song's phone may be disconnected.`

## 5.5 Actions and Protocol Effects

**Actions**

| Action | Effect |
|--------|--------|
| Start | Begins countdown then singing (single) or medley run |
| Cancel/Back | Closes modal, returns to Song List |

**Protocol effects on Start**

- TV sends `assignSinger` to each selected phone (one per singer):
  - Non-duet: Player 1 → `P1`
  - Duet with two players: Player 1 → `P1`, Player 2 → `P2` (swapped if Swap Parts selected)
  - Duet with one player: `P1` or `P2` based on user's selection
- TV MUST NOT send `assignSinger` to non-selected devices

**Countdown mapping** (from [Settings > Gameplay](#65-gameplay)):
- Ready countdown ON: `startMode="countdown"`, `countdownMs = countdownSeconds*1000`
- Ready countdown OFF: `startMode="live"`, omit `countdownMs`

## 5.6 Wireframes

**Non-duet song**
```text
+--------------------------------------------------------------------------------+
| SELECT PLAYERS                                              <Artist> — <Title> |
+--------------------------------------------------------------------------------+
| Player 1 (required)                                                            |
|  Phone:      [ Pixel-7 ▾ ]                                                     |
|  Difficulty: [ Medium ▾ ]                                                      |
+--------------------------------------------------------------------------------+
| Player 2                                                                       |
|  Phone:      [ (disabled) ]                                                    |
+--------------------------------------------------------------------------------+
| [Start]   [Cancel]                                                             |
+--------------------------------------------------------------------------------+
| Hints: OK=Select   Back=Cancel                                                 |
+--------------------------------------------------------------------------------+
```

**Duet song**
```text
+--------------------------------------------------------------------------------+
| SELECT PLAYERS (DUET)                                       <Artist> — <Title> |
+--------------------------------------------------------------------------------+
| Player 1 (P1)                                Player 2 (P2)                     |
|  Phone: [ Pixel-7 ▾ ]                        Phone: [ (none) ▾ ] (optional)   |
|  Difficulty: [ Medium ▾ ]                    Difficulty: [ Medium ▾ ]         |
|                                                                               |
| If Player 2 is (none):  Solo duet part:  (• P1) (  P2)                        |
| If both players selected:  [Swap Parts]                                       |
+--------------------------------------------------------------------------------+
| [Start]   [Cancel]                                                             |
+--------------------------------------------------------------------------------+
```

**No phones connected**
```text
+--------------------------------------------------------------------------------+
| SELECT PLAYERS                                                                 |
+--------------------------------------------------------------------------------+
| ⚠ No phones connected.                                                        |
|   Connect phones in Settings to sing.                                          |
|                                                                               |
| [Open Settings > Connect Phones]   [Cancel]                                    |
+--------------------------------------------------------------------------------+
```

---

# 6. Settings Screen

Settings is the TV-side navigation shell for app configuration. The root screen routes into specialized subsections; shared edit behaviors defined here apply to child screens unless overridden.

**Root menu**

| Item | Description |
|------|-------------|
| Connect Phones | Pairing and device management |
| Song Library | Song sources from connected phones |
| Audio | Preview volume, vocals volume |
| Scoring Timing | Manual mic delay calibration |
| Gameplay | Line bonus, countdown, note lines |
| Video | Video playback toggle |

**Wireframe (Settings root)**
```text
+--------------------------------------+
| SETTINGS                             |
|  > Connect Phones                    |
|    Song Library                      |
|    Audio                             |
|    Scoring Timing                    |
|    Gameplay                          |
|    Video                             |
+--------------------------------------+
| Hints: OK=Open   Back=Return         |
+--------------------------------------+
```

**Numeric setting edit**

- Boolean settings: OK toggles immediately
- Numeric settings: OK opens modal numeric keypad dialog
  - Shows setting name and current value
  - Digits 0–9; first digit replaces entire value, subsequent digits append
  - **Del**: deletes last digit; long-press clears entire input
  - **Cancel** (default focus) / **OK** actions
  - OK validates input; on failure, dialog remains open with error

## 6.1 Connect Phones

**Purpose**: Allow phones to connect via QR/code; show list of connected devices.

**UI elements**

- QR code + join code (must satisfy QR sizing from [§4.1](#41-header-actions-and-pairing))
- Device roster list: display name (editable), connection status, optional latency indicator

**Actions**

| Action | Effect |
|--------|--------|
| End session | Invalidates token, disconnects all phones, clears assignments, creates new Open session |
| Rename | Opens rename dialog with TV on-screen keyboard |
| Kick | Confirm, then disconnect device |
| Forget | Confirm, then remove stored label and disconnect |

**Navigation**

- Default focus: first roster row (if present)
- Up/Down: navigate roster
- Down from last row: action buttons (default: Rename)
- Left/Right on action row: cycle Rename / Kick / Forget
- Down from action row: End session
- OK: trigger focused action

**Wireframe (Connect Phones)**
```text
+--------------------------------------------------------------------------------+
| SETTINGS > CONNECT PHONES                                                      |
+--------------------------------------------------------------------------------+
| Join this session:                                                             |
|   [   QR CODE   ]             Code: ABCD-EFGH                                  |
|                                                                                |
| Connected devices (up to 10):                                                  |
|  > Pixel-7        Connected                                                    |
|    iPhone-13      Connected                                                    |
|                                                                                |
| Actions on selected device:  [Rename] [Kick] [Forget]                          |
| Session: [End session] (confirm)                                               |
+--------------------------------------------------------------------------------+
```

## 6.2 Song Library

Shows song contribution status of all connected phones. Any connected phone automatically contributes its songs.

**Connected sources list**

For each phone:
- Device name (from `hello.deviceName`)
- Song count (valid songs from last manifest fetch)
- Invalid song count (if any): `2 invalid`
- Per-row action: **Refresh** (fetches `/manifest.json`)

**Actions**: **Refresh all** fetches manifests from all connected phones.

**Navigation**

- Default focus: first row (if phones connected), else Refresh all
- Up/Down: navigate rows
- Right from row: Refresh action for that row
- Down from last row: Refresh all

**Wireframe**
```text
+--------------------------------------------------------------------------------+
| SETTINGS > SONG LIBRARY                                                        |
+--------------------------------------------------------------------------------+
| Connected phones:                                                              |
|                                                                                |
|  > Alice's Pixel 7    songs: 423                           [Refresh]          |
|    Bob's Galaxy S24   songs: 198   2 invalid               [Refresh]          |
|                                                                                |
| [Refresh all]                                                                  |
+--------------------------------------------------------------------------------+
```

## 6.3 Audio

| Setting | Range | Description |
|---------|-------|-------------|
| Preview Volume | 0–100 | Song List preview playback volume. 0 = silence (disables preview). |
| Vocals Volume | 0–100 (default 50) | Mix volume of `#VOCALS` track when both instrumental and vocals provided. 0 = pure instrumental. |

**Slider interaction**: Left/Right adjusts ±1; long-press adjusts ±10. OK opens numeric keypad for direct entry.

**Implementation note**: TV plays instrumental and vocals tracks simultaneously with independent volume control. Vocals track at `vocalsVolume / 100.0`.

**Wireframe**
```text
+--------------------------------------+
| SETTINGS > AUDIO                     |
+--------------------------------------+
| Preview Volume:  [=====|-----]  60   |
| Vocals Volume:   [==|------]    50   |
+--------------------------------------+
```

## 6.4 Scoring Timing

| Setting | Range | Description |
|---------|-------|-------------|
| Manual mic delay (ms) | 0–400 | Compensates for hardware audio pipeline latency. One-time calibration per phone model. |

**Effect**: Mic delay shifts pitch lane rendering and scoring windows only. Lyrics highlight timing is unaffected (tracks audio playback).

OK on setting opens numeric keypad dialog.

**Wireframe**
```text
+--------------------------------------+
| SETTINGS > SCORING TIMING            |
+--------------------------------------+
| Manual mic delay (ms):   0           |
+--------------------------------------+
```

## 6.5 Gameplay

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Line bonus | ON/OFF | ON | Line bonus scoring |
| Ready countdown | ON/OFF | ON | Countdown before song start |
| Countdown seconds | 1–10 | 3 | Countdown displays at 1 Hz: N, N-1, ..., 1 |
| Show note lines | ON/OFF | ON | Visual note lines (USDX: Ini.NoteLines) |

Boolean settings: OK toggles. Countdown seconds: OK opens numeric keypad (validates 1–10).

**Wireframe**
```text
+--------------------------------------+
| SETTINGS > GAMEPLAY                  |
+--------------------------------------+
| Line bonus:             ON           |
| Ready countdown:        ON           |
| Countdown seconds:      3            |
| Show note lines:        ON           |
+--------------------------------------+
```

## 6.6 Video

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Video enabled | ON/OFF | ON | Suppresses video playback when OFF |

**Background fallback** (when video disabled or unavailable):
1. Song's `#BACKGROUND` image file (if valid)
2. App-shipped default background image (final fallback, also used on Song List when no cover available)

**Wireframe**
```text
+--------------------------------------+
| SETTINGS > VIDEO                     |
+--------------------------------------+
| Video enabled:          ON           |
+--------------------------------------+
```

---

# 7. Singing Screen

The Singing Screen is the TV singing phase as both a visible screen and runtime mode.

## 7.1 Layout and Overlays

**Minimum layout**

- Lyrics line with progressive highlight
- Pitch bars for each active singer
- Per-singer score (current total, optionally note/golden breakdown)
- Elapsed time (bottom-right, `MM:SS` format)
- Instrumental gap indicator (animated rest indicator during silent regions)

**Layout variants**

| Singers | Layout |
|---------|--------|
| Single | Pitch lane vertically centered, full width. Score box at right of lane. |
| Two | Two pitch lanes stacked vertically, one per singer. |

**Wireframe (two singers)**
```text
+--------------------------------------------------------------------------------+
|                          (FULLSCREEN VIDEO / BACKGROUND)                       |
|                                                                                |
| P1 [badge]                                                                     |
|  ───────────────────────────────────────────────────────────────────────────   |
|   [note bars / pitch lane P1]                                                  |
|                                                                +--------+      |
|                                                                | 00710  |      |
|                                                                +--------+      |
|                                                                  Great         |
|                                                                                |
| P2 [badge]                                                                     |
|  ───────────────────────────────────────────────────────────────────────────   |
|   [note bars / pitch lane P2]                                                  |
|                                                                +--------+      |
|                                                                | 00720  |      |
|                                                                +--------+      |
|                                                                  Perfect!      |
|                                                                                |
+--------------------------------------------------------------------------------+
| Lyrics (USDX style: active syllables highlighted)                              |
|   CUz this life is too short                                                   |
|   to live it just for you                                                      |
+--------------------------------------------------------------------------------+
|                                                                      00:35     |
+--------------------------------------------------------------------------------+
```

**Wireframe (single singer)**
```text
+--------------------------------------------------------------------------------+
|                          (FULLSCREEN VIDEO / BACKGROUND)                       |
|                                                                                |
| P1 [badge]                                                                     |
|  ───────────────────────────────────────────────────────────────────────────   |
|   [note bars / pitch lane P1 — vertically centered]                            |
|                                                                +--------+      |
|                                                                | 00710  |      |
|                                                                +--------+      |
|                                                                  Perfect!      |
|                                                                                |
+--------------------------------------------------------------------------------+
| Lyrics                                                                         |
|   CUz this life is too short                                                   |
+--------------------------------------------------------------------------------+
|                                                                      00:35     |
+--------------------------------------------------------------------------------+
```

## 7.2 Lyrics and Sentence Rating

**Lyrics rendering**

- Lyrics MUST remain spatially stable during a sentence (no continuous scrolling)
- Sentence-based paging: current sentence stays in place while highlight progresses
- Page to next sentence when lyrics beat position reaches `startBeat` of first note in next sentence
- During instrumental gaps: completed sentence remains displayed at 100% highlight (no pre-paging)
- Typography MUST prioritize readability at TV viewing distance

**Sentence rating** (after each sentence ends, ~800ms display)

| LinePerfection | Label |
|----------------|-------|
| 1.00 | `Perfect!` |
| ≥ 0.80 | `Great` |
| ≥ 0.60 | `Good` |
| ≥ 0.40 | `Cool` |
| ≥ 0.20 | `Okay` |
| < 0.20 | `Poor` |

Animation: simple opacity fade. No layout-affecting animation during singing.

## 7.3 Countdown and Start

**Countdown** (from [Settings > Gameplay](#65-gameplay))

- Ready countdown ON: show N-second countdown at 1 Hz, then begin playback/scoring
- Ready countdown OFF: begin immediately

**Countdown disconnect**

If required singer disconnects during countdown:
- Cancel start
- Return to Select Players
- Show blocking modal:
  - Title: `DISCONNECTED`
  - Body: `A required singer disconnected during countdown. Please reconnect and start again.`
  - Action: `OK` (default focus)

## 7.4 Pause and Disconnect Handling

**Pause overlay** (Back key)
```text
+--------------------------------------+
| PAUSED                               |
|  > Resume                            |
|    Restart Song                      |
|    Quit to Song List                 |
+--------------------------------------+
```

| Action | Effect |
|--------|--------|
| Resume | Resumes playback and scoring |
| Restart Song | Confirm dialog (default: Cancel). Resets scores, seeks to start, re-sends `assignSinger`. In medley: restarts full medley from segment 1. |
| Quit to Song List | Confirm dialog (default: Cancel). Stops playback, returns to Song List. |

**Disconnect auto-pause**

When a **required** singer (P1 or P2) disconnects mid-song:
```text
+--------------------------------------+
| PAUSED — PLAYER DISCONNECTED         |
| <PhoneName> has disconnected.        |
|                                      |
|  > Wait for reconnect                |
|    Continue without them             |
|    Quit to Song List                 |
+--------------------------------------+
```

| Action | Effect |
|--------|--------|
| Wait for reconnect | Song stays paused. On reconnect: re-sends `assignSinger`, resumes from paused position. |
| Continue without them | Resumes. Player contributes no further score. |
| Quit to Song List | Normal quit behavior. |

Spectator disconnects (non-singers) MUST NOT trigger auto-pause.

## 7.5 Song End Behavior

**Stop point**

- `stopAtLyricsTimeMs` is the authoritative stop point for each singer (lyrics-time milliseconds)
- Normal song: `stopAtLyricsTimeMs = songAbsoluteEndMs` (from `#END` if present, else audio duration)
- Medley: end of final segment's `medleyEndSec` (including fade-out)

**Phone behavior at stop**

- Stop audio capture and pitch detection
- Stop transmitting `pitchFrame` datagrams for that `songInstanceSeq`
- Transition to Waiting/Connected screen

**TV behavior at stop**

- Ignore pitch frames beyond `stopAtLyricsTimeMs`
- Finalize scoring and transition to [Results](#10-results-screen)

**Playback error**

If ExoPlayer reports non-recoverable error:
1. Stop playback/scoring immediately
2. Return to Song List
3. Show blocking error modal:
   - Title: `ERROR`
   - Body: `This song can't be played.` / ExoPlayer error (truncated 120 chars)
   - Action: `OK`

Session MUST return to Open state (no crash, no corruption).

## 7.6 Medley Mode

**Medley run context**

- Create immutable **medley run snapshot** from playlist at start
- Preserves playlist order
- Selected players remain assigned for entire run (no prompts between segments)

**Medley window playback**

Constants:
- `MEDLEY_FADE_IN_SEC = 8`
- `MEDLEY_FADE_OUT_SEC = 2`

Computed times:
- `medleyStartSec = max(0, timeFromBeat(startBeat) - MEDLEY_FADE_IN_SEC)`
- `medleyEndSec = timeFromBeat(endBeat) + MEDLEY_FADE_OUT_SEC`

Audio MUST fade in over `MEDLEY_FADE_IN_SEC` at segment start. Video position: `videoGapSec + medleyStartSec`.

**Segment transitions**

- Fade out current segment over `MEDLEY_FADE_OUT_SEC`
- Fade in next segment over `MEDLEY_FADE_IN_SEC`
- Crossfade acceptable if audio mixing available

**Segment failure**

- `audioUrl` null: skip segment, show error toast, proceed to next
- Audio unreachable mid-segment: abort medley, return to Song List with error modal

**Scoring scope**

Only notes within medley window `[startBeat, endBeat)` contribute to score (notes outside treated as Freestyle with `ScoreFactor=0`).

**Header text** (medley mode, n>1)
```text
| 2/5: Daft Punk — Get Lucky          P1 [badge]
|  ─────────────────────────────────────────────
```

Segment progress indicator in top-left alongside label.

---

# 8. Scoring System

Note-based scoring normalized to 10000 total. Line bonus ON reserves 1000 for line bonus; remaining 9000 distributed via note value normalization.

## 8.1 Scoring Model

**Per-note scoring**

When a note is finalized, compute:
- `samplesInNote` = qualifying pitch frames collected for this note
- `N = |samplesInNote|`

If `N = 0` (no frames): `note_score = 0`

If `N > 0`:
- `hits = |{ s ∈ samplesInNote : isPitchMatch(s, note) }|`
- `max_note_score = (MaxSongPoints / TrackScoreValue) × ScoreFactor[noteType] × durationBeats`
- `note_score = max_note_score × (hits / N)` (IEEE 754 double-precision)

**Score accumulation**

| Note Type | Accumulates To |
|-----------|----------------|
| Normal (`:`) | `Player.Score` |
| Rap (`R`) | `Player.Score` |
| Golden (`*`) | `Player.ScoreGolden` |
| RapGolden (`G`) | `Player.ScoreGolden` |
| Freestyle (`F`) | Nothing (`ScoreFactor = 0`) |

**Sentence finalization**

When last scorable note in sentence is finalized:
- Line bonus evaluation runs ([§8.5](#85-line-bonus))
- `Player.ScoreLast` updated

## 8.2 Note Types

**Note tokens**

| Token | Type | Description |
|-------|------|-------------|
| `F` | Freestyle | No scoring |
| `:` | Normal | Standard pitch matching |
| `*` | Golden | 2× score factor |
| `R` | Rap | Presence-only (pitch ignored) |
| `G` | RapGolden | Presence-only, 2× score factor |

**Hit detection (`isPitchMatch`)**

| Type | Condition |
|------|-----------|
| Freestyle | Never evaluated |
| Normal, Golden | `toneValid = true` AND pitch within tolerance after octave normalization |
| Rap, RapGolden | `toneValid = true` (presence-only) |

**ScoreFactor constants**

| Type | ScoreFactor |
|------|-------------|
| Freestyle | 0 |
| Normal | 1 |
| Golden | 2 |
| Rap | 1 |
| RapGolden | 2 |

## 8.3 Difficulty and Tolerance

Each singer has a Difficulty setting: Easy, Medium, or Hard.

| Difficulty | Tolerance (semitones) |
|------------|----------------------|
| Easy | ±2 |
| Medium | ±1 |
| Hard | ±0 (exact pitch) |

Tolerance applies only to Normal and Golden notes. Rap notes ignore pitch difference. Default: **Medium**.

## 8.4 Octave Normalization

Before comparing to target note, normalize detected pitch to closest octave:

```
while (Tone - TargetTone > 6) Tone := Tone - 12
while (Tone - TargetTone < -6) Tone := Tone + 12
```

- `Tone = midiNote - 36` (C2=36 maps to Tone=0, matching USDX's C2=0 pitch base)
- Do NOT reduce to pitch class (`mod 12`) before the loop

## 8.5 Line Bonus

**Line bonus mode** (when `LineBonusEnabled = ON`, default):
- `MaxSongPoints = 9000` (notes+golden budget)
- `MaxLineBonusPool = 1000`

**Line score calculation**

- `TrackScoreValue = sum(Note.Duration × ScoreFactor)` over all notes in track
- `LineScoreValue = sum(Note.Duration × ScoreFactor)` over notes in sentence
- `MaxLineScore = MaxSongPoints × (LineScoreValue / TrackScoreValue)`

**Line perfection**

At sentence completion:
- `LineScore = (Player.Score + Player.ScoreGolden) - Player.ScoreLast`
- If `MaxLineScore <= 2`: `LinePerfection = 1` (forgiveness)
- Else: `LinePerfection = clamp(LineScore / (MaxLineScore - 2), 0, 1)`

**Line bonus distribution**

- Empty lines (`LineScoreValue = 0`) receive no line bonus
- `LineBonusPerLine = MaxLineBonusPool / NonEmptyLines` (float division)
- `Player.ScoreLine += LineBonusPerLine × LinePerfection`

**Medley exception**: `TrackScoreValue` only sums notes within `[medleyStartBeat, medleyEndBeat)`. Notes outside treated as Freestyle for this computation.

## 8.6 Rounding and Display

**Per-note scoring**

- `max_note_score = (MaxSongPoints / TrackScoreValue) × ScoreFactor × durationBeats`
- `note_score = max_note_score × (hits / N)` (if N=0, note_score=0)

**Line score rounding**

`ScoreLineInt = floor(round(ScoreLine) / 10) × 10`

**Tens rounding** (intentional asymmetry)

- `ScoreInt = round(Score / 10) × 10`
- `ScoreGoldenInt`:
  - If `ScoreInt < Score`: `ceil(ScoreGolden / 10) × 10`
  - Else: `floor(ScoreGolden / 10) × 10`

**Total**

`ScoreTotalInt = ScoreInt + ScoreGoldenInt + ScoreLineInt`

The opposite-rounding for Golden ensures sum never exceeds 10000 due to .5 rounding.

---

# 9. Session Lifecycle

## 9.1 Session States

| State | Description |
|-------|-------------|
| **Open** | Phones may join and appear in roster |
| **Locked** | Song in progress; new joins rejected (existing phones may reconnect) |
| **Ended** | Session token invalid; phones must join new session |

**State transitions**

| Trigger | Transition |
|---------|------------|
| App launch | → Open (new session created) |
| Start singing (TV sends `assignSinger`) | → Locked |
| Return to Song List after song end/quit | → Open |
| End session (Settings) or app close | → Ended |

Navigation between Song List, Settings, and overlays does NOT change session state.

**Pairing rules**

- Reconnect-within-session supported
- Persistent singer assignment across sessions NOT supported (phones join as spectators until assigned)

## 9.2 Join and Admission

**Join capacity**

- Maximum 10 devices per session
- Phones MAY join while session is **Open** until roster full
- Additional phones rejected with `error(code="session_full")`
- During **Locked** state, new joins rejected with `error(code="session_locked")`

**Roster actions**

| Action | Effect |
|--------|--------|
| Rename | Changes display label stored by `clientId` |
| Kick | Disconnects immediately; roster entry removed |
| Forget | Removes stored label, disconnects; future join treated as new device |

## 9.3 Disconnect and Reconnect

**Mid-song disconnect**

| Device Role | Behavior |
|-------------|----------|
| Required singer (P1/P2) | Auto-pause with disconnect overlay ([§7.4](#74-pause-and-disconnect-handling)) |
| Spectator/song-source-only | No pause; songs removed from library. If active song streams from that phone, playback error handling applies. |

**Reconnect behavior**

| Disconnect Cause | Reconnect Behavior |
|------------------|-------------------|
| Transport disconnect (network drop, app backgrounded) | Auto-reconnect attempt; show "Reconnecting" |
| User-initiated leave | Return to Join screen; no auto-reconnect |
| Host kick/forget | Return to Join screen; no auto-reconnect |

**Reconnect mechanics**

- Same `clientId` in `hello` reclaims prior identity
- TV assigns new `connectionId`; old frames silently dropped
- TV fetches `/manifest.json` from reconnected phone to refresh library
- If phone was assigned as Singer, it resumes that role; TV re-sends `assignSinger` with updated `stopAtLyricsTimeMs`
- If roster full and `clientId` not found, reject with `code="session_full"`

---

# 10. Results Screen

## 10.1 Post-Song Results

**Per-singer display**

- Notes score
- Golden score  
- Line bonus
- **Song Total** (tens-rounded per USDX rules)

**Actions**

- **Back to Song List** (only action; restarting via Pause menu)
- MVP has no persistent song queue

**Back key**: Returns to Song List.

**Wireframe**
```text
+--------------------------------------------------------------------------------+
| Song Score                                                                     |
| <Artist> — <Title>                                                             |
+--------------------------------------------------------------------------------+
| P1: <PhoneName>                                  | Comparison |  P2: <PhoneName>|
|                                                                                |
| Notes score        00000                         |█████       |  Notes score    00000 |
| Golden score       00000                         |███████     |  Golden score   00000 |
| Line bonus         00000                         |████        |  Line bonus     00000 |
|                                                                                |
| Song Total        00000                          |██████      |  Song Total    00000 |
|                                                                                |
+--------------------------------------------------------------------------------+
| [Back to Song List]                                                            |
+--------------------------------------------------------------------------------+
```

## 10.2 Post-Medley Results

After medley run finishes, show single results screen with static score table.

**Aggregation**

- Medley Total = **mean** of per-song `scoreTotalInt` values across segments
- `MedleyTotal.scoreTotalInt = round( sum(segment.scoreTotalInt) / nSegments )`
- Result MAY be non-multiple-of-10 (USDX parity)

**Display**

- Each segment as row: `<i>. <Artist> — <Title>   P1: <score>   P2: <score>`
- Final row: Medley Total per player
- No navigation between rounds
- Only action: **Back to Song List**

**Back key**: Returns to Song List.

**Wireframe**
```text
+--------------------------------------------------------------------------------+
| Medley Results                                                                 |
+--------------------------------------------------------------------------------+
| P1: <PhoneName>                                          P2: <PhoneName>       |
+--------------------------------------------------------------------------------+
|  1. PSY — Gangnam Style                          01840         07200          |
|  2. Daft Punk — Get Lucky                        07200         04100          |
|  3. Queen — Bohemian Rhapsody                    06100         08300          |
|  ──────────────────────────────────────────────────────────────────────────   |
|  Medley Total                                    05047         06533          |
+--------------------------------------------------------------------------------+
| [Back to Song List]                                                            |
+--------------------------------------------------------------------------------+
```
