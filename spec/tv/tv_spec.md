Android Karaoke Game
USDX Parity MVP Functional Specification
Version: 4.20
Date: 2026-03-08
Owner: SpecBot
Status: Draft



# How to Use This Spec
This document defines the functional behavior required to implement a minimal Android karaoke game that behaves like UltraStar Deluxe (USDX) for the agreed MVP scope. It is designed to be sufficiently explicit for AI-driven implementation.
Conventions:
- TBD = decision or detail not yet specified.
- Paritiy-critical = must match USDX behavior for compatibility.
- Defaults are explicitly stated; if not, behavior is unspecified and must be decided.

# Table of Contents
- 1. Product Contract
  - 1.1 Locked Product Decisions
  - 1.2 Definition of Done
- 2. Architecture Overview
  - 2.1 Components
  - 2.2 Data Responsibilities
- 3. Songs and Library
  - 3.1 Storage Access
  - 3.2 Discovery and Validation Rules
  - 3.3 Index Fields (Functional)
  - 3.4 Song List (Landing Screen)
  - 3.5 Advanced Search (Overlay) [POST-MVP]
- 4. USDX TXT Format Support
  - 4.1 Supported Note Tokens
  - 4.2 Supported Header Tags and Semantics
  - 4.3 Error Handling
  - 4.4 Header Tags Reference
  - 4.5 Body Token Reference
- 5. Timing and Beat Model
  - 5.1 Authoritative Beat Definitions
  - 5.2 Pitch Frame Timing, Jitter, and Mic Delay
  - 5.3 Beat-Time Conversion
  - 5.4 START/END
- 6. Scoring
  - 6.1 Scoring Overview
  - 6.2 Note Types
  - 6.2.1 ScoreFactor constants
  - 6.3 Player Level / Tolerance
  - 6.4 Octave Normalization
  - 6.5 Line Bonus
  - 6.6 Rounding and Display
- 7. Multiplayer, Pairing, and Session Lifecycle
  - 7.1 Session States
  - 7.2 Pairing UX (TV)
  - 7.3 Pairing UX (Phone)
  - 7.4 Disconnect/Reconnect
- 8. Network Protocol
  - 8.1 Transport
  - 8.2 Control Messages
  - 8.3 Pitch Stream Messages
  - 8.4 Versioning and Compatibility
  - 8.5 Authentication
- 9. Time Sync and Jitter Handling
  - 9.1 Defaults
- 10. UI Screens and Flows
  - 10.1 Global navigation and input
  - 10.2 Song preview playback
  - 10.3 Select Players modal
  - 10.4 Settings Screen
  - 10.5 Singing Screen
    - 10.5.1 Singing Screen (Medley mode)
  - 10.6 Results
    - 10.6.1 Results (post-song)
    - 10.6.2 Results (post-medley)
- Appendix A: Library Dependency Reference
- Appendix B: Protocol Schemas
- Appendix C: Parsed Song Model
- Appendix D: ParsedSongModel Fixture Serialization
- Appendix E: Worked Examples

# 1. Product Contract
- Goal: USDX-like karaoke gameplay (parity for parsing, timing, duet, rap, scoring, results).
- Platforms: Android TV host app (Kotlin) + native companion apps (Kotlin on Android, Swift on iOS) acting as mic client / song source.
- Connectivity: same-subnet Wi-Fi only; offline operation.
- Players: 2.
- Out of scope: online song store, party modes other than Medley, editors, esports-grade calibration.

## 1.1 Locked Product Decisions
- Default per-player difficulty: **Medium**.
- Line bonus: ON.
- Duet: YES; swap duet parts: YES.
- Rap: YES (presence-based); Freestyle: no scoring.
- Video backgrounds: YES.
- Instrumental (full-song) via `#INSTRUMENTAL`: YES.
- **#INSTRUMENTAL playback semantics (normative):** `#INSTRUMENTAL` specifies an audio file containing only the instruments (no vocals). When present and the file exists in the song folder on the phone, the TV MUST use the `#INSTRUMENTAL` file as the sole backing track for the entire song, replacing `#AUDIO`/`#MP3`. There is no gap-based track switching; the instrumental track plays from start to end, uninterrupted.
  `#VOCALS` specifies the complementary acapella file. When present alongside `#INSTRUMENTAL`, the TV MUST mix the vocals track at a user-configurable volume (default: 50%, adjustable via **Settings > Audio > Vocals Volume**). This allows players to use the original singer as a pitch guide. If `#INSTRUMENTAL` is absent, `#VOCALS` is ignored.
  If `#INSTRUMENTAL` is absent, `#AUDIO`/`#MP3` plays throughout as normal.
- **Instrumental gap indicator (visual only):** An "instrumental gap" is a region of the chart where no scorable note (Normal, Golden, Rap, RapGolden) is active for the current player's track for more than **2 continuous seconds**. During such a region, the pitch lane for that player MUST display a pulsing animated rest indicator (e.g., a horizontal dashed line or wave graphic). This indicator is purely visual — it has no effect on audio track selection. The indicator disappears as soon as the next scorable note approaches within the highlight window.
- Songs stored on connected phones in a single songs folder per phone; TV aggregates library from all connected phones. Each phone runs a lightweight read-only HTTP server for the duration of the session; the TV fetches song files directly over HTTP on demand (Section 8.6). No temporary storage on the TV is required.

## 1.2 Definition of Done
Parity MVP PASS requires all parity-critical behaviors in this spec to be met, plus functional pairing and play flows operating reliably on typical home Wi-Fi.

# 2. Architecture Overview

## 2.1 Components
- **TV Host App**: song library (aggregated from phones), chart parsing, audio/video playback, timing/beat computation, scoring, session management, UI.
- **Phone Mic Client**: song storage (single songs folder on the phone), song metadata scanning, lightweight read-only HTTP file server for song asset delivery, mic capture + DSP (pitch), toneValid thresholding, pitch frame streaming.

## 2.2 Data Responsibilities
**Songs live on the phones.** Each phone has a single songs folder. The TV does not store or own song files. When a phone connects, the TV requests its song list; the phone scans its folder and returns song metadata. The TV aggregates the library from all connected phones.
When a song is needed for playback or preview, the TV uses the HTTP URLs provided in `songListUpdate` to fetch files directly from the phone's HTTP server. The TV passes audio and video URLs directly to ExoPlayer, which streams and buffers them progressively. No ZIP building, no extraction, no temporary storage on the TV.
TV is authoritative for: song timeline, beats, scoring, rendering, session state.
Phone is authoritative for: song file storage, song metadata scanning, song HTTP file serving, mic capture and pitch extraction.
**Consequence**: a phone must be connected for its songs to appear in the TV library. Songs from a disconnected phone are removed from the active library until that phone reconnects.

# 3. Songs and Library

### 3.1.3 TV-Side Library and Lifecycle
The TV aggregates song metadata received from all currently connected phones into an in-memory library index. The library index is never persisted between sessions. When a phone disconnects, its songs MUST be removed from the library index immediately — they become invisible and unselectable in the UI.

The TV holds no song files. All media is streamed directly from the phone's HTTP server on demand. When a phone disconnects, its song URLs become unreachable; any in-progress playback must be handled per Section 7.4. No cleanup of downloaded files is required.

## 3.2 Discovery and Validation Rules
### 3.2.1 Phone-side discovery (normative)
The phone scans for **all `.txt` files recursively** under its configured songs folder. Each `.txt` is treated as a distinct song entry, even if multiple `.txt` files exist in the same folder.
### 3.2.2 Validation (song acceptance)**
A song entry is accepted into the library if and only if all of the following checks pass. If any check fails, the song entry MUST be rejected and a diagnostic MUST be emitted (see Section 4.3).
1) Required header tags present
- `#TITLE` and `#ARTIST` MUST be present and non-empty.
- `#BPM` MUST be present and parseable as a **non-zero** floating-point number (USDX accepts any non-zero value).
- A required audio reference tag MUST be present:
  - For `#VERSION >= 1.0.0`: at least one of `#AUDIO` or `#MP3` MUST be present and non-empty. If both are present, `#AUDIO` takes precedence (Section 4.2).
  - For legacy format (`#VERSION` absent or `< 1.0.0`): `#MP3` MUST be present and non-empty. `#AUDIO` (if present) MUST be ignored for audio resolution (USDX behavior).
2) Required audio file exists
- The audio reference resolved by Section 4.2 MUST resolve to an existing file when interpreted relative to the `.txt` directory (subpaths are allowed), unless the resolved value is an absolute URI supported by the platform (if absolute URIs are not supported in MVP, treat them as missing).
3) Notes section parses without fatal errors
- The notes/body section MUST be parsed according to Section 4.1 and Section 4.3.
- Unknown tokens and recoverable grammar issues MUST be handled per Section 4.3 (warn and continue).
- Any fatal numeric parse error for a recognized token MUST reject the song entry.
4) Each track has at least one non-empty sentence after cleanup
After body parsing completes, validation MUST ensure each parsed track (single track, or both tracks for duet) contains singable structure:
- The track MAY omit sentence delimiters (`-`). If the body contains note events but no `-`, the parser MUST still construct at least one sentence/line container (USDX behavior).
  - `ERROR_CORRUPT_SONG_NO_BREAKS` is **reserved** for the invariant failure where the implementation cannot construct any sentence/line container after parsing.
- Empty sentences MUST be removed. An "empty sentence" is a sentence/line with zero note events after parsing (i.e., no `:`, `*`, `F`, `R`, `G` notes).
  - This cleanup is performed before the "no notes" check.
- After removing empty sentences, the track MUST contain at least one remaining sentence/line.
  - If a track contains zero sentences after cleanup, reject with reason `ERROR_CORRUPT_SONG_NO_NOTES`.

**Missing files**
Audio/video/instrumental files are validated for existence at load time:
- Missing required audio file -> load fails.
- Missing optional video/instrumental -> logged; song can still load (but feature disabled).

**MVP parity requirements**
- Mirror the recursive `.txt` discovery behavior.
- Reject songs missing the required header fields or required audio file.
- Keep invalid song diagnostics (error line number + reason) for export/troubleshooting.

## 3.3 Index Fields (Functional)
The TV's in-memory library index MUST store enough information to render Song Select and Search. The index is rebuilt from connected phones each session; it is not persisted between sessions.
Normative minimum index record (per song)
- Identity / storage
  - `phoneClientId`: the `clientId` of the phone that provided this song entry.
  - `relativeTxtPath`: the normalized relative path of the `.txt` within the phone's songs folder.
    - Normalization rules (normative):
      - Path separators MUST be `/`.
      - MUST NOT start with `/`.
      - MUST NOT contain `.` or `..` segments.
      - Case MUST be preserved.
  - `songId`: stable identifier derived from `phoneClientId` and `relativeTxtPath`.
    - Normative form: `songId = phoneClientId + "::" + relativeTxtPath`.
  - `modifiedTimeMs`: last-modified timestamp of the TXT file at scan time (provided by phone).
- Validation
  - `isValid`: boolean.
  - `invalidReasonCode`: required if `isValid=false` (short stable string; see Section 4.3).
  - `invalidLineNumber`: required if `isValid=false` and the failure is associated with a specific TXT line (1-based).
- Display fields
  - `artist`, `title` (required by validation rules).
  - `album` (optional).
- Flags (derived from parse)
  - `isDuet` (true if song is duet).
  - `hasRap` (true if any `R` or `G` notes exist).
  - `hasVideo` (true if a video reference exists and the file is present).
  - `hasInstrumental` (true if `#INSTRUMENTAL` exists and the file is present).
  - Medley eligibility (derived from parse; parity-aligned)
    - `canMedley` (true iff the song can be added to the Medley playlist; see Section 3.4)
    - `medleySource` (enum: `null` | `"tag"`)
    - `medleyStartBeat` (int; required if `medleySource != null`)
    - `medleyEndBeat` (int; required if `medleySource != null`)
    - `calcMedleyEnabled` (boolean; default true; false iff `#CALCMEDLEY:OFF`)
- Preview/seek metadata
  - `startSec` (from `#START`, default 0.0).
  - `previewStartSec` (computed as: `#PREVIEWSTART` if present and >0; else if `medleySource!=null` use `timeFromBeat(medleyStartBeat)`; else 0.0; see Section 3.4 and Section 10.2).
- Asset URLs (populated from `songListUpdate`; stored as-received; null if file absent on phone)
  - `txtUrl` (string): URL to the `.txt` file. Required for valid songs.
  - `audioUrl` (string|null): URL to the primary audio file.
  - `videoUrl` (string|null): URL to a local video file; null for YouTube references and absent files.
  - `coverUrl` (string|null): URL to the cover image. Used directly by song grid tile image loader (Coil) — no separate fetch step.
  - `backgroundUrl` (string|null): URL to the background image.
  - `instrumentalUrl` (string|null): URL to the instrumental audio file.
  - `vocalsUrl` (string|null): URL to the vocals audio file.
Implementations MAY store additional fields (e.g., genre, year, videoGapSec) but the above is the minimum required for MVP behavior.

## 3.4 Song List (Landing Screen) - TV
**Purpose**
- Always the landing screen (even if library is empty).
- Displays songs sorted by **Artist -> Album -> Title**.
- Only one song (or one medley segment) is played at a time.
- The screen maintains a **transient Medley playlist** (a short, in-memory list of songs to be played back-to-back in medley mode).
  - The Medley playlist is **initialized empty** each time this screen is shown.
  - The Medley playlist is **cleared** when leaving this screen for a non-modal screen (e.g., Settings, starting a song, starting a medley, Results).
  - Opening/closing modal overlays (Advanced Search, Select Players, error dialogs) MUST NOT clear it.
**Header actions**
- **⚙ Settings** button (gear icon): left side of header, opens Settings screen. This is the primary entry point to Settings from the Song List.
- **Back** button: behaves like the TV remote Back key (see Back key behavior below).
- **Join code** (text-only): top-right of header, shows the current session join code (e.g., `Code: ABCD-EFGH`) as a quick-glance alternative to scanning the QR in the left panel.
**Pairing (on landing)**
- The landing screen left panel MUST show a compact session join widget: **QR code + join code** for the current session endpoint (Section 8.1). The QR is positioned in the left panel below the video preview area and above the Medley playlist.
- The QR payload MUST encode the full WebSocket endpoint URL (including the `token` query parameter), so the phone can join without relying on LAN discovery.
- The landing screen MUST NOT show a connected-device roster.
- Device roster management (Rename/Kick/Forget) is available only in Settings -> Connect Phones (Section 10.4.1).
**QR sizing (normative; TV usability)**
- QR code MUST be scannable at typical living-room TV distance.
- Render requirements (implementation MUST satisfy all):
  - QR visible size MUST be at least **16% of screen height** (square), and MUST NOT be less than **280 px** on a 1080p surface.
  - Quiet zone MUST be at least **4 modules** on each side.
  - Join code text MUST be readable at the same distance: character height MUST be at least **3.5% of screen height** (approx. 38 px at 1080p).
**Empty state**
- If no phones are connected:
  - Message: `No phones connected.`
  - Hint: `Connect a phone to see songs. Open the karaoke app on your phone and scan the QR code.`
- If phones are connected but none have returned any valid songs:
  - Message: `No songs found.`
  - Hint: `Open the karaoke app on your phone and make sure the songs folder is set.`
**Song card display (grid)**
- Each visible song is shown as a **cover tile** with:
  - Cover image (if present; otherwise placeholder)
  - Title + Artist
  - Bottom-right tag overlays (single-letter chips):
    - `D` = duet (`isDuet=true`)
    - `R` = rap (`hasRap=true`)
    - `V` = video (`hasVideo=true`)
    - `I` = instrumental (`hasInstrumental=true`)
    - `M` = medley-eligible (`canMedley=true`)
**Default inline search (grid filter; normative)**
- The screen MUST provide a Search text field.
- Matching is **case-insensitive substring** match.
- Default search scope is fixed to `Everywhere` (matches if any of {artist, album, title} match).
- Filtering MUST preserve the underlying ordering (Artist -> Album -> Title) and simply hides non-matching songs.
- Input MUST be debounced by **150 ms**.
- Pressing **OK** on the Search field MUST open the **Android TV system text input dialog** (same mechanism as advanced search would use). On confirming the system dialog, focus returns to the Search field with the entered text applied and the grid filters immediately (150 ms debounce).
**Back key behavior (normative)**
- If a filter is active (from inline search), Back MUST **clear the filter** and keep the user on the Song List.
- Otherwise, Back exits the app (or returns to Android launcher).
**Primary actions (normative)**
- OK on a focused song tile opens **Select Players** modal (Section 10.3).
- Long-press OK on a focused song tile attempts **Add to Medley**.
  - If the focused song has `canMedley=false`, show a blocking modal:
    - Text (exact): `This song can't be used in a medley. Look for songs with an M tag in the lower right corner`
    - Single action: `OK` (default focus), closes the modal.
  - If `canMedley=true`, append the song to the end of the Medley playlist.
**Random actions (normative)**
- The screen MUST provide:
  - **Sing Random Song**: selects a random **valid** song from the currently visible (filtered) set, then opens Select Players.
  - **Sing Random Duet**: selects a random **valid duet** song from the currently visible (filtered) set, then opens Select Players.
- If the currently visible (filtered) set is empty (no grid results), the Random action buttons MUST be disabled (not focusable).
- If no eligible songs exist for the chosen action, show a blocking modal with a single `OK` action and keep focus unchanged.
**Medley playlist behavior (normative)**
- The Medley playlist is a fixed-height list area on the Song List screen.
- Fixed height = **the lesser of 7 lines or 25% of screen height**, with a minimum of 3 lines always visible. The playlist scrolls when it exceeds the visible height.
- Playlist row rendering: `<Artist>  <Title>` (no row number prefix).
Playlist actions:
- **Play Medley**:
  - If the playlist is empty, this action MUST be disabled.
  - Otherwise, it MUST open **Select Players** (Section 10.3) once for the entire medley run.
  - On **Start**, it starts medley playback using the playlist order.
- **Auto Medley (Random 5)**: replaces the playlist with up to **5** randomly selected songs from the currently visible (filtered) set where `canMedley=true`.
  - If the currently visible (filtered) set is empty (no grid results), this action MUST be disabled (not focusable).
  - If fewer than 5 eligible songs exist, use all eligible songs.
  - If zero eligible songs exist, show a blocking modal with `OK` and do not change the playlist.
Playlist edit interactions:
- Focus can move into the playlist.
- OK on a playlist row enters **Reorder mode** for that row.
  - In Reorder mode: Up/Down moves the item within the playlist; OK confirms; Back cancels and restores the prior order.
  - While in Reorder mode, DPAD Left and DPAD Right MUST do nothing (focus does not leave the playlist).
  - Navigating focus out of the playlist via any other mechanism (e.g., system focus change) MUST implicitly cancel the reorder and restore the original order.
  - While in Reorder mode, the bottom-of-screen context hints MUST include `Up/Down=Move  OK=Accept  Back=Cancel`.
- Long-press OK on a playlist row deletes that row immediately (no confirm).
**Layout / focus (normative; TV remote)**
The Song List uses a two-column layout. The **left panel** contains the video preview, QR/join code widget, and Medley playlist. The **right panel** contains the Search field, action buttons, and song grid.
Focus allocation:
- The video preview and QR/join code widget are **display-only and non-focusable**. The remote cannot focus them.
- The Medley playlist rows, Play Medley button, and Auto Medley button are focusable within the left panel.
- The Search field, Random Song button, Random Duet button, and song grid tiles are focusable within the right panel.
Grid column count (normative):
- Grid column count MUST be fixed: **3 columns** at 1080p, **4 columns** at 4K.
- The column count MUST NOT change while the screen is displayed.
Initial focus (normative):
- On entering the Song List (including on app launch and on return from Singing/Results), initial focus MUST be placed on the **first tile in the song grid** (top-left). If the grid is empty (no songs visible), initial focus MUST be placed on the **Search field**.
DPAD navigation map (normative):
| Current focus | DPAD Up | DPAD Down | DPAD Left | DPAD Right |
|---|---|---|---|---|
| Search field | — (no action) | First grid tile | — (no action) | — (no action) |
| Random Song / Random Duet button | Search field | First grid tile | — (no action) | — (no action) |
| Grid tile (top row) | Search field | Tile below (or no action if last row) | Tile to the left, or Medley playlist if at leftmost column | Tile to the right; no action if at rightmost column |
| Grid tile (non-top row) | Tile above | Tile below (or no action if last row) | Tile to the left, or Medley playlist if at leftmost column | Tile to the right; no action if at rightmost column |
| Medley playlist row | Previous playlist row (or Play Medley if at top) | Next playlist row (or Auto Medley if at bottom) | — (no action) | Search field |
| Play Medley button | Last playlist row (or no action if empty) | Auto Medley button | — (no action) | Search field |
| Auto Medley button | Play Medley button | — (no action) | — (no action) | Search field |
**Wireframe (spec interactions; TV)**
```text
+--------------------------------------------------------------------------------------------------+
|  ⚙ Settings   ◀ Back                                                             Code: ABCD-EFGH      |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  +--------------------------------------+     +----------------------------------------------+   |
|  | VIDEO PREVIEW (focused song)         |     | Search: [______________________________]      |   |
|  | (uses Preview Volume)                |     | [Random Song]  [Random Duet]                  |   |
|  |                                      |     |   (disabled when filtered set is empty)       |   |
|  |  +------------------------------+    |     |                                              |   |
|  |  |          16:9 video          |    |     |  SONG GRID (right half)                        |   |
|  |  |          preview             |    |     |  +---------+ +---------+ +---------+ +-----+   |   |
|  |  |                              |    |     |  | Cover   | | Cover   | | Cover   | | ... |   |   |
|  |  |                              |    |     |  | Title   | | Title   | | Title   | |     |   |   |
|  |  +------------------------------+    |     |  | Artist  | | Artist  | | Artist  | |     |   |   |
|  |                                      |     |  | [D][V][M]| | [R]     | | [D]     | |     |   |   |
|  |  +------------------------------+    |     |  +---------+ +---------+ +---------+ +-----+   |   |
|  |  | JOIN SESSION                 |    |     |  +---------+ +---------+ +---------+ +-----+   |   |
|  |  | [   QR CODE   ]              |    |     |  | Cover   | | Cover   | | Cover   | | ... |   |   |
|  |  | Code: ABCD-EFGH              |    |     |  | Title   | | Title   | | Title   | |     |   |   |
|  |  +------------------------------+    |     |  | Artist  | | Artist  | | Artist  | |     |   |   |
|  +--------------------------------------+     |  | [V]     | | [D]     | | [I][M]  | |     |   |   |
|                                               |  +---------+ +---------+ +---------+ +-----+   |   |
|  +--------------------------------------+     |                                              |   |
|  | MEDLEY PLAYLIST                      |     |  Tags: [D]=Duet  [R]=Rap  [V]=Video         |   |
|  | (max 7 lines or 25% height; scrolls) |     |         [I]=Inst  [M]=Medley                |   |
|  |  +-------------------------------+   |     +----------------------------------------------+   |
|  |  | <artist>  <song>              |   |                                                      |
|  |  | <artist>  <song>              |   |                                                      |
|  |  | <artist>  <song>              |   |                                                      |
|  |  | <artist>  <song>              |   |                                                      |
|  |  | <artist>  <song>              |   |                                                      |
|  |  +-------------------------------+   |                                                      |
|  |    [ PLAY MEDLEY ]  [ AUTO MEDLEY (RANDOM 5) ]                                               |
|  +--------------------------------------+                                                      |
+--------------------------------------------------------------------------------------------------+
| Contextual help:                                                                                |
|  - Song grid: OK = Sing   Long-Press OK = Add to Medley                                         |
|  - Medley playlist: OK = Reorder   Long-Press OK = Delete                                       |
+--------------------------------------------------------------------------------------------------+
```
**Medley eligibility: `canMedley` (normative; parity-aligned)**
`canMedley` MUST be computed and stored in the in-memory song list built on scan/index.
A song is medley-eligible iff all are true:
- `isDuet = false`, AND
- Valid medley tags exist (`medleySource="tag"`).
Definition details (USDX parity):
- Valid medley tags exist iff:
  - `#MEDLEYSTARTBEAT` and `#MEDLEYENDBEAT` are both present, both parse as integers, and `startBeat < endBeat`.
  - If valid tags exist, `medleySource="tag"` and those beats are used.
  - If valid tags do not exist, `medleySource=null` and `canMedley=false`.
**Note — medley auto-calc deferred:** USDX supports a refrain-finding algorithm (`#CALCMEDLEY`) that produces `medleySource="calculated"` when no explicit tags exist. This algorithm is not specified for MVP. `medleySource="calculated"` is therefore not a valid value in this implementation. Only songs with explicit `#MEDLEYSTARTBEAT`/`#MEDLEYENDBEAT` tags are medley-eligible.

# 4. USDX TXT Format Support

## 4.1 Supported Note Tokens

### Note/body line tokens (USDX parser)
USDX reads the song body line-by-line and interprets the first character token.
Supported tokens:
- `:` Normal note
- `*` Golden note
- `F` Freestyle note (scored as 0)
- `R` Rap note
- `G` RapGolden note
- `-` Line break / new sentence
- `E` End of song data
- `P1`, `P2` Duet part delimiters (body markers; must appear on their own line, starting with `P`)

### Per-note fields
For note tokens (`:`, `*`, `F`, `R`, `G`) USDX parses:
`<token> <startBeat> <duration> <tone> <lyricText...>`
- `startBeat` and `duration` are integers in chart beat units. They are not scaled by BPM; BPM affects only the beat->time conversion (Section 5.1). Any legacy relative-mode shift (format < 1.0.0) is applied separately (Section 4.2).
- `tone` is an integer note tone as stored in the file.
- `lyricText` is the remainder of the line after the numeric fields.

### Duet structure
- If the first non-empty body line begins with `P`, USDX marks the song as duet (`isDuet = true`) and creates two tracks.
- A `P1`/`P2` marker sets the active track (0/1).
- Notes and `-` sentence breaks are assigned to the current active track.
- The file ends with a single `E` after all notes.

## 4.2 Supported Header Tags and Semantics

### Required tags
- `#TITLE:` song title (UTF-8 for format >= 1.0.0).
- `#ARTIST:` song artist.
- `#BPM:` base BPM. USDX loads as `BPM_internal = BPM_file * 4`. BPM values using a comma as decimal separator (e.g., `120,5`) MUST have the comma replaced with a period before parsing. Parsing MUST be locale-independent (i.e., always use `.` as decimal separator regardless of device locale).
- Audio filename:
 - For `#VERSION >= 1.0.0`: at least one of `#AUDIO:` or `#MP3:` MUST be present and non-empty. If `#AUDIO:` is present, it takes precedence over `#MP3:` (USDX behavior).
 - For legacy format (`#VERSION` absent or `< 1.0.0`): `#MP3:` MUST be present and non-empty. `#AUDIO:` (if present) MUST be ignored for audio resolution (USDX behavior).
 - The resolved audio file MUST exist, otherwise load fails.

### Timing/alignment tags
- `#GAP:` millisecond offset used as the lyrics/audio time origin for beat/time conversions (see Section 5.1). Parsed as a float (fractional ms allowed).
- `#START:` seconds; initial playback/lyrics time offset.
- `#END:` milliseconds; sets lyrics total time if present.
- `#PREVIEWSTART:` seconds; used by editor and can be used for song preview.

### Media tags
- `#VIDEO:` video filename or external reference. Optional; missing file is non-fatal (warn and continue without video).
  A `#VIDEO` value is treated as an **external/YouTube reference** and `videoUrl` MUST be `null` if it matches any of:
  - starts with `v=` (YouTube video-ID shorthand, e.g. `v=9bZkp7q19f0`)
  - starts with `http://`, `https://`, or `www.`
  - contains `youtube.com` or `youtu.be`
  For all other `#VIDEO` values, treat as a relative local filename. If the file does not exist on the phone, `videoUrl` MUST be `null` and a warn diagnostic MUST be emitted.
- `#VIDEOGAP:` seconds offset added to audio position when positioning video.
- `#INSTRUMENTAL:` instruments-only audio file. When present and the file exists, replaces `#AUDIO`/`#MP3` as the sole backing track for the entire song. See Section 1.1 for full semantics.
- `#VOCALS:` acapella audio file. When present alongside `#INSTRUMENTAL`, mixed at a user-configurable volume as a singing guide. Ignored if `#INSTRUMENTAL` is absent. See Section 1.1 for full semantics.
- `#COVER:` image; `#BACKGROUND:` image. Fallback filenames `*[CO].jpg` and `*[BG].jpg` (glob: any file in the song directory ending with `[CO].jpg` or `[BG].jpg` respectively) MUST be resolved by the phone at scan time if the explicit tag is absent or the named file does not exist. If a fallback file is found, it MUST be used to populate `coverUrl`/`backgroundUrl` in `songListUpdate`. If no fallback is found, the corresponding URL is `null`. The TV does NOT perform filename glob resolution — it only uses URLs supplied by the phone.

### Duet tags
Singer labels (stored and available via `ParsedSong.header.p1Name` / `p2Name`; not displayed in singing screen UI — device names are shown instead):
- `#P1:` and `#P2:` set duet singer names for internal use.

### In-song BPM changes
Variable-BPM charts (body `B` lines) are **not supported**. If any `B` line is present, the song MUST be rejected as invalid (use `ERROR_CORRUPT_SONG_UNSUPPORTED_VARIABLE_BPM`).

## 4.3 Error Handling
**Implementation requirements (MVP, parity-aligned)**
**Header tags**
Header processing is best-effort and MUST continue past unknown or non-fatal issues.
- Header lines are read from the top of the file while the first character of the line is `#`. Any other line (including an empty line) ends header parsing (USDX behavior).
- Tag names are case-insensitive; matching MUST be performed on `Uppercase(Trim(TagName))`.
- Duplicate known tags: if the same known tag appears multiple times, the **last** successfully parsed value wins (earlier values are overwritten).
- Each header line is classified into exactly one of:
  - **Well-formed tag**: `#NAME:VALUE` where `NAME` is non-empty.
  - **No separator**: a line starting with `#` that contains no `:`.
  - **Empty value**: `#NAME:` (value is empty string after trimming).
For each header line:
- **Well-formed known tag**: parse according to its definition.
  - If the value is malformed:
    - If the tag is **required for validity** (TITLE/ARTIST/AUDIO-or-MP3/BPM): mark the song **invalid**.
    - If the tag is **optional** (VIDEO, COVER, BACKGROUND, INSTRUMENTAL, etc.): **warn** and treat as absent.
- **Well-formed unknown tag**: **warn** and preserve it in `CustomTags` as `(NAME, VALUE)`.
- **Empty value** (`#NAME:`): **info/warn** and preserve it in `CustomTags` as `(NAME, "")`.
- **No separator** (no `:`): **warn** and preserve it in `CustomTags` as `("", CONTENT)` where `CONTENT` is the original line without the leading `#`.
`CustomTags` representation (MVP):
- `CustomTags` is an ordered list of `(TagName, Content)` pairs.
- `TagName` may be empty only for the "no separator" case above.
- The stored strings MUST be exactly the trimmed forms described above (do not reformat).
**Media files**
- Missing/unresolvable required audio file: **invalid**.
- Missing optional assets (video/images/instrumental): **warn** and continue without that asset.
- If video fails to open/decode at runtime: fall back to background/visualization without interrupting scoring/playback.
**Body grammar (notes section)**
Body parsing is best-effort and MUST continue past unknown or non-fatal issues. The goal is to load as much as possible while preserving deterministic behavior.
Recognized leading tokens (first non-whitespace character of the line):
- `E` end of song
- `P` duet track marker (`P1` or `P2`)
- Note tokens: `:` normal, `*` golden, `F` freestyle, `R` rap, `G` rap-golden
- Sentence marker: `-`
Rules:
- If the token is unrecognized: **warn** with line number and ignore the line.
- If the token is recognized but required numeric fields cannot be parsed as integers/floats: **invalid** (fatal for that song).
Token-specific behavior:
- `E`: stop reading the body; the song load continues with validation.
- `P`:
  - Accept only `P1` or `P2` (after the `P`).
  - Any other `P` value: **invalid** (fatal for that song).
- Note tokens (`:`, `*`, `F`, `R`, `G`):
  - Parse required fields as integers:
    - `startBeat` (int)
    - `duration` (int)
    - `tone` (int)
    - `lyricText` is the remainder of the line (may be empty).
  - Auto-fix: if `duration == 0`, then:
    - **warn** with line number: "found note with length zero -> converted to FreeStyle"
    - convert the note token to `F` (freestyle) and keep `duration` unchanged (still zero).
  - Hardcoded conversion flags (not user-configurable in MVP):
    - `RapToFreestyle = false`: Rap notes are kept as Rap.
    - `OutOfBoundsToFreestyle = false`: notes outside audio bounds are kept as-is (not converted to freestyle).
- `-` (sentence): parse required integer `startBeat`. If parsing fails, or if an extra numeric parameter is present (the legacy RELATIVE beat-delta format), the song is **invalid** (`ERROR_CORRUPT_SONG_UNSUPPORTED_RELATIVE`).
- `B` (BPM change): variable BPM is **not supported**; if present, the song is **invalid** (`ERROR_CORRUPT_SONG_UNSUPPORTED_VARIABLE_BPM`). On encountering a `B` token, the parser MUST record the diagnostic and MAY stop body parsing immediately or continue parsing for additional diagnostics — both behaviours are conformant.
**Version/encoding**
- If `#VERSION` is absent, treat the song as legacy format `0.3.0`.
- If `#VERSION` is present, it MUST parse as a dotted numeric version (e.g., `1.0.0`). If it fails to parse: **invalid**.
- Supported versions are `< 2.0.0`. If `#VERSION >= 2.0.0`: **invalid**.
- All files are treated as UTF-8. The tags `#ENCODING`, `#RESOLUTION`, `#NOTESGAP`, `#DUETSINGERP1`, and `#DUETSINGERP2` are treated as **unknown tags** regardless of version — they are preserved in `CustomTags` and no version-conditional processing is applied.
**Logging**
All invalidation MUST include a concise reason string suitable for display in a debug invalid songs listing.
Diagnostics record schema (normative)
- Implementations MUST produce a structured diagnostics list per song load attempt, where each entry has:
  - `severity`: one of `info` | `warn` | `invalid`.
  - `code`: short stable string (see the minimum code set below).
  - `message`: human-readable description.
  - `txtUri`: song TXT identifier.
  - `lineNumber`: optional 1-based line number within the TXT file, present whenever a specific line caused the issue.
- For any `isValid=false` song (Section 3.3), there MUST be at least one diagnostics entry with `severity=invalid`, and the song's `invalidReasonCode` MUST equal that entry's `code`.
Minimum invalidation codes (parity-aligned)
- `ERROR_CORRUPT_SONG_FILE_NOT_FOUND`: required audio file missing/unresolvable.
- `ERROR_CORRUPT_SONG_NO_NOTES`: after sentence cleanup, no remaining sentences.
- `ERROR_CORRUPT_SONG_NO_BREAKS`: reserved — implementation could not construct any sentence/line container after parsing (USDX typically does not reject songs solely for missing `-`).
- `ERROR_CORRUPT_SONG_MISSING_REQUIRED_HEADER`: missing TITLE/ARTIST/AUDIO-or-MP3/BPM.
- `ERROR_CORRUPT_SONG_MALFORMED_HEADER`: required header present but malformed/unparseable.
- `ERROR_CORRUPT_SONG_MALFORMED_BODY`: recognized body token but numeric field parse fails.
- `ERROR_CORRUPT_SONG_UNSUPPORTED_VARIABLE_BPM`: a `B` (BPM change) body line is present; variable BPM is not supported by this implementation.
- `ERROR_CORRUPT_SONG_UNSUPPORTED_RELATIVE`: a sentence (`-`) body line includes the legacy extra numeric beat-delta parameter (the RELATIVE format). Note: `#RELATIVE` as a header tag is treated as an unknown tag (stored in `customTags`; no semantic effect) and does NOT trigger this error — but songs originally authored with `#RELATIVE` will be parsed as if they are absolute-beat format, which may produce incorrect note timing.
- `ERROR_CORRUPT_SONG_INVALID_VERSION`: VERSION exists but fails to parse, or VERSION >= 2.0.0.
- `ERROR_CORRUPT_SONG_INVALID_DUET_MARKER`: `P` token present with value other than P1/P2.

## 4.4 Header Tags Reference
This section consolidates the supported UltraStar `.txt` header tags and their semantics. Tags are introduced here so that later timing (Chapter 5) and scoring (Chapter 6) rules can reference them directly.
Legend:
- Req: required for song validity
- Since/Until: format version applicability. Missing `#VERSION` is treated as legacy `0.3.0`.
- Gameplay impact: whether it changes timing/scoring (vs metadata only)
| Tag | Req | Type | Units | Since/Until | Default | Gameplay impact | Normative behavior |
|---|---:|---|---|---|---|---|---|
| `#VERSION` | no | string | - | all | (absent → `0.3.0`) | none | If present, MUST parse as dotted numeric version (e.g., `1.0.0`) or song is invalid. Supported versions are `< 2.0.0`; if `>= 2.0.0` song is invalid (Section 4.3). |
| `#TITLE` | yes | string | - | all | - | display only | Required; missing/empty invalidates song. |
| `#ARTIST` | yes | string | - | all | - | display only | Required; missing/empty invalidates song. |
| `#AUDIO` | yes (preferred) | string | relative path | `>= 1.0.0` | - | timing (playback clock) | If present, takes precedence over `#MP3`. Referenced file MUST exist or song invalid (Sections 3.2/4.3). |
| `#MP3` | yes (fallback) | string | relative path | all | - | timing (playback clock) | Used for legacy (`#VERSION` absent or `< 1.0.0`) and as fallback when `#AUDIO` is absent for `#VERSION >= 1.0.0`. Referenced file MUST exist or song invalid. |
| `#BPM` | yes | float | file BPM | all | - | timing/scoring | Required and MUST be non-zero. Internal BPM = `BPM_file * 4` (Section 5.3). |
| `#GAP` | no | float | ms | all | `0` | timing/scoring | Shifts highlight/scoring cursors (Section 5.1). |
| `#START` | no | float | sec | all | `0` | timing (trim) | Audio start trim (Section 5.4). |
| `#END` | no | int | ms | all | `0` | timing (trim) | Audio end trim (Section 5.4). |
| `#PREVIEWSTART` | no | float | sec | all | `0` | none | Optional preview cue point (UI). |
| `#VIDEO` | no | string | relative path | all | unset | none | Optional video filename. Missing file is non-fatal. |
| `#VIDEOGAP` | no | float | sec | all | `0` | A/V sync only | Video offset relative to audio (rendering). |
| `#COVER` | no | string | relative path | all | unset | none | Optional cover image. |
| `#BACKGROUND` | no | string | relative path | all | unset | none | Optional background image. |
| `#INSTRUMENTAL` | no | string | relative path | `>= 1.1.0` | unset | audio (full-track) | When present and file exists, replaces `#AUDIO`/`#MP3` as the sole backing track for the entire song. See Section 1.1. |
| `#VOCALS` | no | string | relative path | `>= 1.1.0` | unset | audio (mix) | Acapella track. Mixed with `#INSTRUMENTAL` at configurable volume. Ignored if `#INSTRUMENTAL` is absent. See Section 1.1. |
| `#YEAR` | no | int | year | all | `0` | none | Optional metadata year. |
| `#GENRE` | no | string (multi) | - | all | empty | none | Optional multi-valued metadata used for filtering/sorting. |
| `#EDITION` | no | string (multi) | - | all | empty | none | Optional multi-valued metadata used for filtering/sorting. |
| `#CREATOR` | no | string (multi) | - | all | empty | none | Optional multi-valued metadata used for filtering/sorting. |
| `#LANGUAGE` | no | string (multi) | - | all | empty | none | Optional multi-valued metadata used for filtering/sorting. |
| `#TAGS` | no | string (multi) | - | `>= 1.0.0` | empty | none | Optional multi-valued metadata parsed only for `>= 1.0.0`. |
| `#MEDLEYSTARTBEAT` | no | int | beats | all | unset | none | Medley window start beat (file beats). |
| `#MEDLEYENDBEAT` | no | int | beats | all | unset | none | Medley window end beat (file beats). |
| `#CALCMEDLEY` | no | OFF/ON | - | all | ON | none | Controls medley auto-calc. |
| `#P1` | no | string | - | all | unset | none | Duet singer name for Player 1 (stored only; not shown in singing UI). |
| `#P2` | no | string | - | all | unset | none | Duet singer name for Player 2 (stored only; not shown in singing UI). |
All other tags (including `#ENCODING`, `#RESOLUTION`, `#NOTESGAP`, `#DUETSINGERP1`, `#DUETSINGERP2`, and any unknown tags) MUST be treated as unknown tags: preserved in `ParsedSong.header.customTags` in encounter order (Section 4.3).

## 4.5 Body Token Reference
All body lines are tokenized by the first non-space character. Unknown tokens MUST be ignored with a warning diagnostic unless they cause numeric-parse failure for a recognized token (Section 4.3).
| Token | Grammar | Meaning |
|---|---|---|
| `E` | `E` | End of song data. Parsing stops. |
| `P1` / `P2` | `P <n>` where `n ∈ {1,2}` | Switch active track. If `n` is not 1 or 2, song is invalid (`ERROR_CORRUPT_SONG_INVALID_DUET_MARKER`). |
| `-` | `- <startBeat>` | Sentence ends; new line begins at `startBeat`. |
Note tokens:
| Token | Grammar | NoteType |
|---|---|---|
| `:` | `: <startBeat> <duration> <tone> <lyric>` | Normal |
| `*` | `* <startBeat> <duration> <tone> <lyric>` | Golden |
| `F` | `F <startBeat> <duration> <tone> <lyric>` | Freestyle |
| `R` | `R <startBeat> <duration> <tone> <lyric>` | Rap |
| `G` | `G <startBeat> <duration> <tone> <lyric>` | RapGolden |

# 5. Timing and Beat Model

## 5.1 Authoritative Beat Definitions
The chart is authored in beats, while DSP frames and playback run in time. The TV MUST convert between time and beats deterministically using the rules below.
Definitions:
- `GAPms`: the float value of `#GAP:` in milliseconds (fractional ms allowed).
- `lyricsTimeSec`: the current lyrics/playback clock time in seconds, where `lyricsTimeSec = 0` corresponds to the start of the audio file.
- `micDelayMs`: the per-phone (or per-player) microphone delay setting in milliseconds.
Two beat cursors are used:
1) Highlight beat cursor (UI timing)
- `highlightTimeSec = lyricsTimeSec - (GAPms / 1000.0)`
- `CurrentBeat = floor(TimeSecToMidBeatInternal(highlightTimeSec))`
2) Note scoring windows (judgement timing)

Scoring operates per **note**, not per beat. Each note defines a time window during which pitch frames are collected and evaluated.

For a note with `startBeat` and `durationBeats` in the current track, the scoring window in TV monotonic time is:

- `noteStartTvMs = songStartTvMs + (startBeat × 15000 / BPM_file) + GAPms + micDelayMs`
- `noteEndTvMs   = songStartTvMs + ((startBeat + durationBeats) × 15000 / BPM_file) + GAPms + micDelayMs`

Where:
- `songStartTvMs` is defined in Section 5.2.2.
- `BPM_file` is the raw `#BPM` value from the header (before ×4).
- `GAPms` is the `#GAP` value in milliseconds.
- `micDelayMs` is the effective mic delay (Section 5.2.4). Adding it shifts the collection window later to account for hardware audio pipeline latency.

A pitch frame with timestamp `tvTimeMs` falls within a note's scoring window if:
`noteStartTvMs <= tvTimeMs < noteEndTvMs`

This uses the same start-inclusive, end-exclusive boundary convention as Section 5.3.

Invalid or missing frames MUST be treated as `toneValid=false` (no scoring; rap also requires `toneValid=true`).

## 5.2 Pitch Frame Timing, Jitter, and Mic Delay

This section defines how phone pitch frames are mapped into the TV time domain, how the TV selects frames for scoring, and how microphone delay is applied.

### 5.2.2 Pitch-frame timestamps in TV time

**`songStartTvMs` (normative):**
The TV MUST record the TV monotonic clock value at the moment `lyricsTimeSec = 0` begins playing (i.e., when ExoPlayer starts audio playback for the current song, before any `#START` offset is applied). This value is used throughout scoring to convert audio positions to TV time.

- `songStartTvMs`: TV monotonic ms at audio position 0 for the current song.

When a `pitchFrame` arrives:
- `frameTimestampTvMs` = the `tvTimeMs` field from the binary frame header.
- `arrivalTimeTvMs` = TV monotonic ms at receipt.
- `latenessMs = arrivalTimeTvMs - frameTimestampTvMs`

### 5.2.3 TV jitter buffer and scoring sample selection

Jitter buffer (TV):
- Target playout delay: **220 ms** — frames are expected to arrive no later than 220 ms after their `tvTimeMs` timestamp in real TV-wall time.
- Max playout delay cap: **450 ms** — frames arriving where `latenessMs > 450` MUST be dropped (treated as if never received).

**Note-level frame collection (normative):**

`NOTE_FINALIZATION_DELAY_MS = 450` (constant; matches max playout delay cap).

A note is **finalized** when the TV monotonic clock reaches `noteEndTvMs + NOTE_FINALIZATION_DELAY_MS`. This delay ensures that late-arriving frames for the tail of the note have been received before scoring is computed.

At finalization, the TV collects all frames in the jitter buffer satisfying both:
1. `noteStartTvMs <= frame.tvTimeMs < noteEndTvMs` (within the note's scoring window; Section 5.1).
2. `frame.arrivalTimeTvMs - frame.tvTimeMs <= 450` (frame was not excessively late; same max playout cap).

Frames that fail condition (2) MUST be excluded (treated as if never received).

The resulting set of qualifying frames is `samplesInNote`. Scoring proceeds per Section 6.1.

### 5.2.4 Effective mic delay (manual)

The scoring beat cursor (Section 5.1) uses a mic delay to compensate for hardware audio pipeline latency:
- `effectiveMicDelayMs = micDelayMs`

Where `micDelayMs` is the user-configured per-session setting (Settings > Scoring Timing). Hardware audio latency (microphone → digital → network) is essentially constant for a given phone model and does not drift during a song, so adaptive adjustment adds complexity without benefit. Manual calibration before singing is sufficient.

Default: `micDelayMs = 0` (adjustable in Settings > Scoring Timing; valid range 0–400 ms).

## 5.3 Beat-Time Conversion (TV/Host)
USDX treats the beat numbers written in UltraStar `.txt` files as the authoritative beat grid (quarter-beat resolution). There is no additional beat scaling.

**Internal beat unit**
- File beats: the integers stored in note lines (`startBeat`, `duration`) and sentence lines (`- startBeat`) in the `.txt`.
- Internal beats: identical to file beats (no scaling): `internalBeat = fileBeat`.
Parsing rule:
- Parsed beat values (note `startBeat`, note `duration`, sentence `startBeat`) MUST be used as-is (no `*4`).

**Internal BPM**
- The `.txt` header `#BPM:` is expressed in file beats per minute.
- The internal BPM is: `BPM_internal = BPM_file * 4`

**TimeSecToMidBeatInternal**
`TimeSecToMidBeatInternal(tSec)` converts a time offset (seconds) into an internal beat position (float).
Input:
- `tSec` is measured relative to the chart origin (i.e., `lyricsTimeSec - GAPms/1000.0`), and MAY be negative.
Output:
- A floating-point internal beat position.
Static BPM:
- `MidBeat_internal = tSec * (BPM_internal / 60.0)`

**BeatInternalToTimeSec**
`BeatInternalToTimeSec(beatInt)` converts an internal beat index to a time offset in seconds, relative to the chart origin (i.e., `lyricsTimeSec - GAPms/1000.0`).
Static BPM:
- `tSec = beatInt * (60.0 / BPM_internal)`
To convert this chart-relative time back to `lyricsTimeSec` (audio-start relative), add `GAPms/1000.0`.
Boundary conventions:
- When comparing a time to a note window converted from beats, implementations MUST use: `noteActive if startBeat <= beat < endBeat` (start inclusive, end exclusive).

## 5.4 START/END
This section defines how the optional TXT headers `#START` and `#END` affect playback.
START (normative)
- `#START:` is parsed as a float seconds value `startSec`.
- When entering the Singing screen in normal play, the song timeline `songTimeSec` and audio playback position MUST be initialized to `startSec`.
- If a video is present, its playback position MUST be initialized to `videoGapSec + startSec` (see Section 4.2 for `videoGapSec`).
END (normative)
- `#END:` is parsed as an integer milliseconds value `endMs`.
- If `endMs > 0`, the song MUST end when `songTimeSec >= endMs/1000.0` (after applying the same start initialization above).
- If `endMs <= 0` or missing, the song duration is determined by the audio track length.
Gameplay behaviors that depend on START/END (normative)
- Restart song: resets per-player scores/state and seeks playback back to `startSec` (and video to `videoGapSec + startSec`).

# 6. Scoring

## 6.1 Scoring Overview

Note-based scoring, normalized to 10000 total. Line bonus ON reserves 1000 for line bonus and distributes remaining 9000 via note value normalization.

**Scoring coroutine (normative)**

Scoring evaluation MUST run on a **dedicated scoring coroutine**, independent of the UI render loop. The coroutine MUST:
1. Poll `ExoPlayer.getCurrentPosition()` every **10 ms** (100 Hz) to track song progress and detect note finalization times.
2. Maintain the jitter buffer of incoming pitch frames (Section 5.2.3).
3. Finalize notes in chronological order within each track when the TV monotonic clock reaches `noteEndTvMs + NOTE_FINALIZATION_DELAY_MS` (Section 5.2.3).

This decouples scoring accuracy from UI frame rate — render load, frame drops, or 30/60/120 Hz display differences MUST NOT affect scoring.

Score state MUST be exposed via `StateFlow<PlayerScore>` and observed by the Compose UI.

**Per-note scoring (normative)**

When a note is finalized, its score is computed as follows:

Let:
- `samplesInNote` = the set of qualifying pitch frames collected for this note (Section 5.2.3).
- `N = |samplesInNote|` (number of qualifying frames).

If `N = 0` (no frames received during the note window — e.g., network drop or silence):
- `note_score = 0`

If `N > 0`:
- Count hits: `hits = |{ s ∈ samplesInNote : isPitchMatch(s, note) }|`
  - `isPitchMatch` is defined per note type in Section 6.2.
- Compute maximum possible score for this note:
  - `max_note_score = (MaxSongPoints / TrackScoreValue) × ScoreFactor[noteType] × durationBeats`
  - Where `MaxSongPoints` and `TrackScoreValue` are defined in Section 6.5, and `ScoreFactor` in Section 6.2.1.
- Compute the note's earned score:
  - `note_score = max_note_score × (hits / N)`
  - `hits / N` MUST use IEEE 754 double-precision float division.

**Score accumulation (normative)**

After computing `note_score`:
- If `noteType` is Normal (`:`) or Rap (`R`): add `note_score` to `Player.Score`.
- If `noteType` is Golden (`*`) or RapGolden (`G`): add `note_score` to `Player.ScoreGolden`.
- Freestyle (`F`) notes: `ScoreFactor = 0`, so `max_note_score = 0`; no accumulation occurs.

**Normalization check:** For a perfect performance (all frames are hits for every note), the total across all notes equals:
`sum(max_note_score) = sum((MaxSongPoints / TrackScoreValue) × ScoreFactor × duration) = MaxSongPoints × (TrackScoreValue / TrackScoreValue) = MaxSongPoints` ✓

**Sentence finalization (normative)**

A sentence/line is considered complete when its last scorable note has been finalized. At that point, line bonus evaluation (Section 6.5) MUST run for that sentence. `Player.ScoreLast` MUST be updated after each sentence's line bonus is applied, as in the current spec.

## 6.2 Note Types
Note-type tokens in the TXT file:
- Freestyle: `F`
- Normal: `:`
- Golden: `*`
- Rap: `R`
- RapGolden: `G`
**Per-sample hit detection (`isPitchMatch`):**

For each pitch frame `s` in `samplesInNote`, `isPitchMatch(s, note)` is defined as:
- Freestyle (`F`): never evaluated — Freestyle notes are excluded from scoring entirely (`ScoreFactor = 0`).
- Normal (`:`) and Golden (`*`): `s.toneValid = true` AND the detected pitch is within the tolerance Range of the target tone after octave normalization (Sections 6.3–6.4).
  - Specifically: `abs(octaveNormalized(s.tone, note.toneSemitone) − note.toneSemitone) <= Range`
- Rap (`R`) and RapGolden (`G`): `s.toneValid = true` (presence-only; pitch difference is ignored).

Where `s.tone = s.midiNote − 36` (Section 6.4), `octaveNormalized` is the shift-by-12 loop in Section 6.4, and `Range` is the player's difficulty tolerance in Section 6.3.

Definition of `toneValid` and how it is produced/transported is normative in Section 8.3 (Pitch Stream Messages).

## 6.2.1 ScoreFactor constants
ScoreFactor is used to weight note durations for score normalization and line bonus calculations.
Normative constants:
- Freestyle (`F`): ScoreFactor=0
- Normal (`:`): ScoreFactor=1
- Golden (`*`): ScoreFactor=2
- Rap (`R`): ScoreFactor=1
- RapGolden (`G`): ScoreFactor=2

## 6.3 Player Level / Tolerance
Each singer/player has a Difficulty setting: Easy, Medium, or Hard.
Define the pitch tolerance Range (in semitones) as:
- Easy: Range = 2
- Medium: Range = 1
- Hard: Range = 0
Range is applied only for Normal and Golden notes (Section 6.2). Rap notes ignore pitch difference.
Default Difficulty is **Medium** for each newly assigned singer.
**Parity requirement**
Implement the exact Range mapping above, per player.

## 6.4 Octave Normalization
Before comparing to the target note, USDX normalizes the detected pitch **to the closest octave of the target note**, but it does so using the detected pitch-class (`Tone`) and shifting it by 12:
```
while (Tone - TargetTone > 6) Tone := Tone - 12
while (Tone - TargetTone < -6) Tone := Tone + 12
```
**Notes**
- Phones send `midiNote` (integer semitone index, MIDI note number). The TV derives the USDX-compatible semitone value:
  - `Tone = midiNote - 36` (so C2=36 maps to `Tone=0`, matching USDX's C2=0 pitch base)
  - Do NOT reduce to pitch class (`mod 12`) before the octave normalization loop. The loop operates on the full semitone value and shifts by 12 until the distance to `TargetTone` is within ±6. Reducing first would corrupt the loop for notes more than one octave from the target.
- After octave normalization, the value compared/scored is the shifted `Tone`.
**Parity requirement**
Implement octave normalization exactly as above (shift detected `tone` by 12 until it is within 6 semitones of the target note).

## 6.5 Line Bonus
Line bonus is a scoring mode that reserves 1000 points of the 10000-point total for sentence/line completion.
Enable/disable (normative):
- Setting `LineBonusEnabled` (boolean), default ON.
- If OFF: `MaxSongPoints = 10000` and `MaxLineBonusPool = 0`.
- If ON: `MaxSongPoints = 9000` (notes+golden budget) and `MaxLineBonusPool = 1000`.
Per-line max score (normative):
- Each track computes `TrackScoreValue = sum(Note.Duration * ScoreFactor[noteType])` over all notes in the track (Section 6.2.1).
  - **Medley exception**: when computing `TrackScoreValue` for a medley segment, only notes within `[medleyStartBeat, medleyEndBeat)` MUST be included. Notes outside the medley window MUST be treated as Freestyle (ScoreFactor=0) for this computation, consistent with USDX's internal conversion. This does not require modifying the parsed chart structure; apply the window filter only when summing.
- Each line/sentence computes `LineScoreValue = sum(Note.Duration * ScoreFactor[noteType])` over its notes.
- For a line, define the note-score budget available to that line as:
  `MaxLineScore = MaxSongPoints * (LineScoreValue / TrackScoreValue)`
Line perfection (normative):
At sentence completion (when the last scorable note in the sentence has been finalized; Section 6.1):
- `LineScore = (Player.Score + Player.ScoreGolden) - Player.ScoreLast`
- If `MaxLineScore <= 2` then `LinePerfection = 1`
- Else `LinePerfection = clamp(LineScore / (MaxLineScore - 2), 0, 1)`
Line bonus distribution (normative, when LineBonusEnabled=ON):
- A line is empty if `LineScoreValue = 0`. Empty lines do not receive line bonus.
- Let `NonEmptyLines = NumLines - NumEmptyLines`. Then:
  - `LineBonusPerLine = MaxLineBonusPool / NonEmptyLines` (float division; do not integer-divide)
  - `Player.ScoreLine += LineBonusPerLine * LinePerfection`
Rounding: see Section 6.6.
**Parity requirement**
Implement sentence-end scoring and line bonus exactly as above, including the `-2` forgiveness term.

## 6.6 Rounding and Display
Per-note scoring (normative):
- Let `MaxSongPoints` be as defined in Section 6.5 (10000 if LineBonusEnabled=OFF; 9000 if ON).
- Let `TrackScoreValue` be as defined in Section 6.5.
- For each finalized note (Section 6.1):
  - `max_note_score = (MaxSongPoints / TrackScoreValue) × ScoreFactor[noteType] × durationBeats`
  - `note_score = max_note_score × (hits / N)` where `hits` and `N` are defined in Section 6.1. If `N = 0`, `note_score = 0`.
  - If noteType is Normal or Rap: add `note_score` to `Player.Score`
  - If noteType is Golden or RapGolden: add `note_score` to `Player.ScoreGolden`
Line score rounding (normative):
- `Player.ScoreLineInt = floor(round(Player.ScoreLine) / 10) * 10`
Tens rounding (normative):
- `ScoreInt = round(Player.Score/10) * 10`
- `ScoreGoldenInt` is rounded to tens in the opposite direction to ensure the sum cannot exceed 10000 due to .5 rounding:
  - If `ScoreInt < Player.Score` then `ScoreGoldenInt = ceil(Player.ScoreGolden/10) * 10`
  - Else `ScoreGoldenInt = floor(Player.ScoreGolden/10) * 10`
- `ScoreTotalInt = ScoreInt + ScoreGoldenInt + Player.ScoreLineInt`
Parity requirement:
Use the exact rounding rules above and compute total as shown.
**Normative note — intentional rounding asymmetry:** `ScoreLineInt` uses `floor(round(x)/10)*10` (round to integer first, then floor-truncate to tens), while `ScoreInt` and `ScoreGoldenInt` use `round(x/10)*10` (round directly to tens). This asymmetry matches USDX behavior and MUST NOT be normalized — do not apply the same formula to all three fields.

# 7. Multiplayer, Pairing, and Session Lifecycle

## 7.1 Session States
Session state is owned by the TV host app.
**States (normative)**
- **Open**: phones may join and appear in the connected-roster.
- **Locked**: a song is in progress; new joins are rejected (existing phones may reconnect).
- **Ended**: the current session token is invalid; all phones must join a new session.
**Lifecycle (normative)**
- On TV app launch, the host MUST create a new session in state **Open** and display pairing info.
- The session MUST enter **Locked** at the moment the TV sends `assignSinger` to the first assigned singer phone (i.e., when the user confirms Start in Select Players and the TV begins the song start sequence). Any `hello` join attempt received after this point MUST be rejected with `error(code="session_locked")`.
- When the user returns to Song List after song end/quit, the session returns to **Open**.
- The session enters **Ended** only when the host explicitly ends it via Settings > Connect Phones (**End session**) or when the app is closed.
- **Navigation does not change session state**: navigating between Song List, Settings, and any overlay or sub-screen on the TV MUST NOT change the session state. The session remains Open (or Locked, if a song is in progress) regardless of TV-side navigation.
**Pairing across sessions (normative for MVP)**
- Reconnect-within-session is supported (Section 7.4).
- Persistent singer assignment across sessions is NOT supported: on a new session, all phones join as spectators until assigned for a song (Section 10.3).

## 7.2 Pairing UX (TV)
**Join UI placement (normative)**
- The TV host MUST display the session join QR code and join code (token) representing the current session endpoint (Section 8.1).
- The QR payload MUST encode the full WebSocket endpoint URL (including the `token` query parameter). It MUST NOT be an NSD/service-discovery identifier.
- The Song List landing screen (Section 3.4) MUST show a compact join widget (QR + code) and MUST NOT show the connected-device roster.
- Settings -> Connect Phones (Section 10.4.1) MUST show the join QR/code plus the connected-device roster and management actions.
**Join admission (normative)**
- Phones MAY join while the session is **Open** until the roster reaches 10 devices.
- Additional phones MUST be rejected with an `error` (e.g., `code="session_full"`).
- During **Locked** state, new joins MUST be rejected with an `error` (e.g., `code="session_locked"`).
**Roster actions (normative)**
- **Rename device**: changes the display label shown on TV and stored by `clientId` for future use within the same session.
- **Kick device**: disconnects the device immediately; the roster entry is removed.
- **Forget device**: removes the stored display label for that `clientId` and disconnects the device; a future join is treated as a fresh device with default name.
- Kick/Forget MUST use a confirm dialog with default focus on Cancel.
**Wireframes**
- Join widget: see Section 3.4 (Song List).
- Roster management: see Section 10.4.1 (Settings > Connect Phones).

## 7.4 Disconnect/Reconnect
**Mid-song disconnect (normative)**
- When a **required singer** (a phone assigned as P1 or P2) disconnects while a song is in progress, the TV MUST automatically pause the song and show the disconnect overlay defined in Section 10.5. The three available responses are: wait for reconnect, continue without them, or quit to Song List.
- When a **spectator** or **song-source-only** phone disconnects mid-song, the TV MUST NOT pause or alter gameplay. The phone's songs are removed from the library immediately. **However**, if the active song's audio or video is being streamed from that phone's HTTP server, the stream will break immediately on disconnect — ExoPlayer will stall and eventually report a playback error. The TV MUST handle this as a non-fatal playback error: show a brief error toast and continue (silent fallback) rather than aborting the session. This is a known limitation of the HTTP streaming architecture.
**Reconnect mechanics (normative)**
- Disconnect cause determines reconnect behaviour:
  - **Transport disconnect** (network drop, app backgrounded, temporary WiFi loss — not initiated by the user): the phone SHOULD automatically attempt to reconnect to the last session endpoint. While attempting, the phone MUST show `Reconnecting`. No QR/code rescan is required.
  - **User-initiated leave** (tap **Leave session**): return to Join screen and clear cached endpoint. Automatic reconnect MUST NOT occur.
  - **Host kick/forget**: the TV closes the connection. The phone MUST return to the Join screen and clear any cached endpoint (same behaviour as Leave session).
- If the same phone reconnects within the same session, it MUST reclaim its prior identity by sending the same `clientId` in `hello` (Section 8.2).
- **`connectionId` on reconnect (normative):** A reconnect follows the same `hello` handshake path as an initial connection. The TV MUST assign a **new** `connectionId` to the reconnecting phone (Section 8.5) and deliver it in the `sessionState` response to the reconnect `hello`. The phone MUST use this new `connectionId` in all subsequent `pitchFrame` datagrams. Any frames still in-flight with the old `connectionId` MUST be silently dropped by the TV (Section 8.5 validation).
- On reconnect, the TV MUST send `requestSongList` to refresh the song index. On receiving a `songListUpdate` during **Locked** state, the TV MUST update its in-memory library index immediately (replacing songs from that phone's `clientId`). The updated library will be visible on the Song List screen when the session returns to Open. Any in-progress playback from that phone's HTTP server is interrupted; assets become unreachable until the phone reconnects and the HTTP server restarts.
- If the phone was assigned as a Singer when it disconnected, it MUST resume that singer role on reconnect (unless the TV has removed the device via Settings > Connect Phones — Kick or Forget — in which case the device must re-join and will be treated as a new, unapproved spectator). The TV re-sends `assignSinger` with an updated `endTimeTvMs` reflecting the **remaining** song duration: for a regular song, `endTimeTvMs = tvMonotonicNowMs + remainingSongDurationMs`; for a medley, `endTimeTvMs = tvMonotonicNowMs + remainingMedleyDurationMs` (i.e., duration from the current playback position to the end of the final medley segment).
- If the session roster is full and the reconnect cannot be matched to an existing `clientId`, the reconnect MUST be rejected with `code="session_full"`.

# 8. Network Protocol

---

## 8.1 Transport Channels (Common)

This system uses three transports:

- **WebSocket** (control channel): all control messages (`hello`, `sessionState`, `ping`, `pong`, `clockAck`, `assignSinger`, `error`, `requestSongList`, `songListUpdate`). The TV host exposes a single path:
  - `ws://<host-ip>:<port>/` — requires `?token=<sessionToken>`
- **HTTP** (song file delivery): the phone runs a read-only HTTP file server on `httpPort` (reported in `hello`). The TV fetches song assets directly from `http://<phone-ip>:<httpPort>/...` using URLs provided in `songListUpdate`. See §8.7.
- **UDP** (pitch channel): all `pitchFrame` datagrams. The TV MUST bind a `DatagramSocket` on a fixed port at session start (before any phone connects), so `udpPort` is stable for the session lifetime. This port MUST be included in the `assignSinger` message as the required field `udpPort` (int). The phone targets `<tv-ip>:<udpPort>` for all pitch datagrams. Frames MUST NOT be batched.

**Song source policy (normative)**
Any phone that successfully joins a session (presents a valid session token) MUST be sent a `requestSongList` message immediately after the `hello` handshake. The phone's songs appear in the TV library for the duration of the connection. No separate pairing or trust approval is required. The session token already gates who can join.

**Session token / join code (normative)**
- Random token to prevent accidental joins on the LAN; minimum 32 bits entropy (recommended 64+).
- The same token MUST be shown to the user as the join code and MUST be the value of the `token` query parameter.
- The join code MUST be human-enterable: implementations SHOULD use a case-insensitive alphabet and MAY display the code in groups (e.g., `ABCD-EFGH`).
- When the user types the join code, the phone MUST normalize it by removing spaces/hyphens and applying case-insensitive comparison.
- Generated per session start; invalidated when the session ends.
- Reuse across sessions is NOT allowed.
- The TV MUST reject WebSocket connections with a missing or incorrect session token and send `error(code="invalid_token")` before closing.

---

## 8.2 Session Discovery

### 8.2.1 Service Advertisement — Android TV

The TV MUST advertise itself via mDNS for the duration of the session so phones can locate it by typed join code without knowing the TV's IP address.

- Service type: `_karaoke._tcp`
- Instance name: `KaraokeTV-<last4>` where `<last4>` is the last 4 characters of the normalized join code (e.g., `KaraokeTV-EFGH` for code `ABCDEFGH`). Instance names MUST be unique on the LAN.
- Port: the WebSocket server port.
- TXT record (normative; all fields required):
  - `code=<normalizedJoinCode>` — the full join code, uppercase, no hyphens or spaces (e.g., `code=ABCDEFGH`). This is what the phone matches against.
  - `v=1` — protocol version.

**jmDNS library (normative)**
Add `jmdns:3.5.9` to the TV app's dependencies. This is the only mature, pure-Java mDNS implementation suitable for Android TV. NSD Manager on Android TV has known unreliability on some OEM firmware.

**Multicast lock (normative)**
Android's Wi-Fi hardware filters multicast packets by default to save battery. The TV app MUST:
1. Declare `<uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />` in `AndroidManifest.xml`.
2. Acquire a `WifiManager.MulticastLock` (tag: `"jmdns_lock"`) on session start, before starting jmDNS.
3. Release the lock on session end.

Without this lock, incoming multicast packets are silently dropped by the Wi-Fi driver on many Android TV devices, making the mDNS advertisement invisible to phones.

---

## 8.3 Control Messages

### 8.3.1 Message Envelope (Common)

All messages are JSON objects. Every message carries:
- `type` (string) — message type identifier.
- `protocolVersion` (int) — see §8.4.
- `tsTvMs` (int, optional) — TV may include its monotonic timestamp for diagnostics.

---

### 8.3.2 Message Definitions (Common)

Sender direction is noted per message. Both sides MUST understand all messages; unknown `type` values MUST be ignored with a warning (except during handshake — see §8.3.3).

---

#### Handshake

**`hello`** (Phone → TV)

Fields: `clientId` (stable UUID), `deviceName`, `appVersion`, `protocolVersion`, `capabilities` (e.g., `{"pitchFps":100}`), `httpPort` (int; the port on which the phone's HTTP file server is listening).

**`sessionState`** (TV → Phone; optional Phone → TV ack)

Fields: `sessionId`, `slots` (`{"P1":{connected, deviceName}, "P2":{...}}`), `inSong` (bool), `songTimeSec` (float, optional), `connectionId` (uint16; assigned by TV per connection; **present only in the initial `sessionState` sent in response to `hello`**; see §8.5).

**`error`** (TV → Phone)

Fields: `code` (string), `message` (string). After sending, the TV MAY close the connection.

Normative error codes (snake_case):
- `invalid_token` — join token is missing or incorrect.
- `protocol_mismatch` — `protocolVersion` mismatch.
- `session_full` — session roster is full.
- `session_locked` — session is in Locked state.

Implementations MAY add additional codes in the future; unknown codes MUST be displayed as a generic error.

---

#### Song Library

**`requestSongList`** (TV → Phone)

Fields: `sessionId` (string).

Semantics: TV requests the phone to scan its songs folder and reply with a `songListUpdate`. Sent on connection and whenever the TV needs a library refresh.

**`songListUpdate`** (Phone → TV)

Fields:
- `sessionId` (string)
- `songs` (array of `SongEntry`; may be empty)

`SongEntry` fields:
- `relativeTxtPath` (string): path to the `.txt` file relative to the songs folder root.
- `isValid` (bool)
- `invalidReasonCode` (string|null): present when `isValid=false`; stable code from §4.3.
- `modifiedTimeMs` (int): last-modified timestamp of the `.txt` file.
- `title`, `artist` (string): required display fields.
- `isDuet` (bool), `hasRap` (bool), `hasVideo` (bool), `hasInstrumental` (bool): derived flags.
- `canMedley` (bool), `medleySource` (`null` | `"tag"`), `medleyStartBeat` (int|null), `medleyEndBeat` (int|null): medley eligibility fields.
- `startSec` (float), `previewStartSec` (float): timing metadata.
- Optional display fields: `album` (string|null), `year` (int|null), `genre` (string|null).
- Asset URLs (all are full `http://` URLs; `null` if the file does not exist locally on the phone at scan time):
  - `txtUrl` (string): URL to the `.txt` file. Required if `isValid=true`.
  - `audioUrl` (string|null)
  - `videoUrl` (string|null): local video file only; YouTube references are `null`.
  - `coverUrl` (string|null)
  - `backgroundUrl` (string|null)
  - `instrumentalUrl` (string|null)
  - `vocalsUrl` (string|null)

Semantics: the phone responds to `requestSongList` with the complete list of songs in its songs folder (including invalid entries for diagnostics). The TV replaces all songs attributed to this phone's `clientId` with the contents of this message. The phone MUST also send an unsolicited `songListUpdate` when a manual rescan triggered by the user in the phone app completes.

---

#### Singing

**`assignSinger`** (TV → Phone)

Sent to phones assigned to sing (one message per singer) when the user starts a song (Select Players modal), and on reconnect while a song is in progress.

Fields:
- `sessionId` (string)
- `songInstanceSeq` (uint32; increments by 1 on every song start, including Restart; used in binary `pitchFrame` to identify the active song)
- `playerId` (`"P1"` or `"P2"`)
- `difficulty` (`"Easy" | "Medium" | "Hard"`)
- `thresholdIndex` (0..7; derived from Settings > Audio > Mic sensitivity)
- `effectiveMicDelayMs` (int; informational; mic delay applied by TV when selecting scoring sample timing)
- `expectedPitchFps` (int; default 50)
- `startMode` (`"countdown"` or `"live"`)
- `countdownMs` (int; required if `startMode == "countdown"`)
- `endTimeTvMs` (int; TV monotonic ms when the song or medley ends)
- `udpPort` (int; the TV's UDP listener port for `pitchFrame` datagrams)
- `connectionId` (uint16; the sender ID the phone MUST include in every `pitchFrame` datagram; matches the value from the initial `sessionState`)
- `songTitle` (string; informational display on phone)
- `songArtist` (string; informational display on phone)

**`endTimeTvMs` computation (normative):** `endTimeTvMs = songStartTvMs + effectiveSongDurationMs`, where `songStartTvMs` is the TV monotonic ms at audio position `startSec`. For `#END`-bounded songs: `effectiveSongDurationMs = (endMs/1000.0 - startSec) * 1000`. Otherwise: audio file duration minus `startSec`, in ms. For medley runs: `endTimeTvMs` is the TV monotonic ms at the end of the final segment's fade-out (`medleyEndSec` of the last segment). When re-sending `assignSinger` after Restart or reconnect, `endTimeTvMs` MUST be recomputed from `tvMonotonicNowMs` plus the remaining duration.

**`assignSinger` semantics:** this message instructs the phone to begin the Active Mic screen, warm up pitch detection, and stream binary `pitchFrame` UDP datagrams tagged with the given `playerId` and `songInstanceSeq` to `<tv-ip>:<udpPort>`.
- If `startMode == "countdown"`: the phone MUST delay sending frames until the countdown completes (after `countdownMs`). The phone MAY warm up pitch detection locally during countdown, but MUST NOT send frames.
- If `startMode == "live"`: begin sending frames immediately.
- The phone MUST treat `effectiveMicDelayMs` as informational only and MUST NOT offset `tvTimeMs` based on it.
- End-of-song behavior is defined in §10.5.

---

#### Clock Sync

**`ping`** (TV → Phone), **`pong`** (Phone → TV), **`clockAck`** (TV → Phone)

These messages are part of the NTP-lite clock synchronization protocol. Fields and per-sample computation are defined in §8.8.

---

### 8.3.3 Validation Rules (Common)

- **Unknown `type`**: ignore and warn. Exception: during the handshake sequence, an unexpected message type is a fatal error.
- **`protocolVersion` mismatch**: send `error(code="protocol_mismatch")` and close.

---

## 8.4 Versioning & Compatibility (Common)

- Define `protocolVersion = 1` for this MVP.
- TV host MUST reject clients whose `hello.protocolVersion != 1` with `error(code="protocol_mismatch")` and close.
- Backward/forward compatibility is out of scope for MVP; future versions must increment `protocolVersion` and maintain a compatibility table.

---

## 8.5 Sender Identification

Purpose: identify which phone a `pitchFrame` UDP datagram came from, so the TV can route it to the correct player slot and discard datagrams from unknown sources.

### 8.5.1 connectionId Assignment — TV

- The TV assigns a `connectionId` (uint16) to each phone when it successfully completes the `hello` handshake. The value MUST be unique among currently active connections. A simple incrementing counter starting at 1 is sufficient.
- The TV delivers `connectionId` to the phone as an integer in the initial `sessionState` message sent in response to `hello`.
- If a phone disconnects and reconnects, the reconnect follows the full `hello` handshake path. The TV MUST assign a **new** `connectionId` and deliver it in the `sessionState` response to the reconnect `hello`. See §7.4 for the full reconnect flow.

### 8.5.3 Datagram Validation — TV

- On receipt of a UDP datagram, the TV looks up the `connectionId` (bytes 14–15) in its active connection table.
- If the `connectionId` does not match any active connection, or does not match the expected connection for the `playerId` in byte 12, the datagram MUST be silently dropped.
- This is a best-effort routing mechanism, not a security control. Datagrams from misconfigured or stale senders are discarded without error.

---

## 8.6 Pitch Stream

### 8.6.1 Wire Format (Common)

`pitchFrame` is a **16-byte fixed-size binary UDP datagram**. All multi-byte integers are **little-endian**:

```
Offset  Size  Type     Field
  0      4    uint32   seq              — frame counter, increments by 1 per frame
  4      4    int32    tvTimeMs         — phone's estimate of TV monotonic ms for this frame
  8      4    uint32   songInstanceSeq  — matches `songInstanceSeq` from assignSinger
 12      1    uint8    playerId         — 0=P1, 1=P2
 13      1    uint8    midiNote         — 0..127 (voiced); 255 = unvoiced / toneValid=false
 14      2    uint16   connectionId     — assigned by TV at hello handshake; identifies the sender
```

Total: **16 bytes per frame**.

`toneValid` is implicit: `toneValid = (midiNote != 255)`. There is no separate `toneValid` field.

**MIDI numbering (common):** `midiNote` uses standard MIDI note numbers [0..127].

---

### 8.6.3 Frame Ingestion & Validation (TV)

**Datagram validation (normative):**
- Any datagram that is not exactly 16 bytes MUST be silently dropped.
- On receipt, the TV MUST check `connectionId` (bytes 14–15) against the registered value for the `playerId` in byte 12. Mismatches MUST be silently dropped. See §8.5.3.
- Datagrams whose `songInstanceSeq` does not match the active song MUST be silently dropped.
- If no registration is found for the `playerId`, the datagram MUST be silently dropped.
- Drop frames with `tvTimeMs` regressions > 200 ms relative to the previous accepted frame for that player.
- If no valid frame exists for a scoring beat window, treat as `toneValid = false` (silence).

**MIDI-to-scoring conversion (normative):**
The TV converts `midiNote` to the USDX semitone scale via:
```
Tone = midiNote - 36    (C2=36 → Tone=0)
```
This value is used directly as input to the octave normalization loop in §6.4.

---

## 8.7 Song File Delivery

Purpose: serve song asset files from the phone to the TV over HTTP so ExoPlayer can stream them progressively without ZIP building, extraction, or temporary storage.

### 8.7.1 URL Scheme (Common)

Song asset URLs are constructed by the phone at scan time and included in each `SongEntry` in `songListUpdate`. URL form:

```
http://<phone-ip>:<httpPort>/songs/<percent-encoded-relative-path>
```

Where `<relative-path>` is the asset file's path relative to the phone's songs folder root (e.g., `Queen/Bohemian%20Rhapsody/bohemian.ogg`). The phone's IP is inferred by the TV from the WebSocket connection's remote address.

**Range requests (normative):**
The server MUST support HTTP `Range` requests for all audio and video files. ExoPlayer requires range support for seeking without re-downloading from the start. The server MUST respond with:
- `Accept-Ranges: bytes` on all audio/video responses.
- `206 Partial Content` with a correct `Content-Range` header when a `Range` request is received.
- `Content-Length` MUST be set on all responses.

---

### 8.7.4 Asset Consumption — TV

- The TV constructs the phone's base URL as `http://<ws-remote-ip>:<hello.httpPort>`.
- Song asset URLs from `songListUpdate` are handed directly to ExoPlayer (`MediaItem.fromUri(audioUrl)`) or to Coil for cover/background images. No intermediate storage step.
- ExoPlayer begins buffering and playback after approximately 2–4 seconds of audio is buffered. Playback MUST NOT wait for the full file to download.
- If an HTTP request to the phone fails (connection refused, 404, timeout), the TV MUST treat it the same as a missing optional asset: suppress for images, show a recoverable error for audio.

---

### 8.7.5 Platform Configuration

#### Android TV — `network_security_config.xml`

The TV app MUST include the following file at `res/xml/network_security_config.xml` and reference it in `AndroidManifest.xml` via `android:networkSecurityConfig="@xml/network_security_config"`. Without it, all `http://` requests to phone IPs throw `CLEARTEXT_NOT_PERMITTED` on API 28+:

```xml
<!-- res/xml/network_security_config.xml -->
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <!-- RFC-1918 class C: 192.168.x.x -->
        <domain includeSubdomains="false">192.168.0.0</domain>
        <!-- RFC-1918 class A: 10.x.x.x — Android domain-config does not support CIDR.
             Enumerate common home subnets explicitly: -->
        <domain includeSubdomains="false">10.0.0.0</domain>
        <domain includeSubdomains="false">10.0.1.0</domain>
        <!-- RFC-1918 class B: 172.16.x.x – 172.31.x.x -->
        <domain includeSubdomains="false">172.16.0.0</domain>
        <domain includeSubdomains="false">172.20.0.0</domain>
        <domain includeSubdomains="false">172.24.0.0</domain>
        <domain includeSubdomains="false">172.28.0.0</domain>
    </domain-config>
</network-security-config>
```

> **Implementation note:** Android `<domain>` entries match by host string, not CIDR and cannot express subnet ranges. The entries above cover the most common home and corporate Wi-Fi subnets. For a production release, use the `<base-config cleartextTrafficPermitted="false">` pattern with a debug-only override. A simpler but less secure alternative acceptable for MVP LAN-only play is `<base-config cleartextTrafficPermitted="true">` restricted via Play Store internal track instead.

#### Android Phone — `AndroidManifest.xml`

Required permissions (normative):

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />
<!-- Android 12+ (API 31+) for NSD/mDNS browsing -->
<uses-permission android:name="android.permission.NEARBY_WIFI_DEVICES"
    android:usesPermissionFlags="neverForLocation" />
```

`CAMERA` is required at runtime for QR scanning — request it before opening the scanner.

#### iOS Phone — `Info.plist`

Four entries are mandatory. Without them the phone app cannot function:

```xml
<!-- App Transport Security: permit cleartext HTTP to LAN hosts -->
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsLocalNetworking</key>
    <true/>
</dict>
<!-- Local Network permission prompt (iOS 14+) -->
<key>NSLocalNetworkUsageDescription</key>
<string>Used to connect to your TV for karaoke playback and scoring.</string>
<key>NSBonjourServices</key>
<array>
    <string>_karaoke._tcp</string>
</array>
<!-- Camera access for QR code scanning -->
<key>NSCameraUsageDescription</key>
<string>The camera is used to scan the QR code displayed on your TV.</string>
<!-- Microphone access for pitch detection -->
<key>NSMicrophoneUsageDescription</key>
<string>The microphone is used to detect your singing pitch for scoring.</string>
```

`NSAllowsLocalNetworking` permits cleartext HTTP to RFC-1918 addresses without opening ATS globally. `NSLocalNetworkUsageDescription` triggers the one-time system permission prompt (iOS 14+) that gates all LAN TCP connections; without it, connections to TV IPs are silently blocked. iOS triggers this prompt automatically on the first connection attempt — the app cannot control the exact moment it appears.

---

## 8.8 Clock Sync

Goal: calibrate each phone's estimate of TV monotonic time so that each pitch frame can include a valid `tvTimeMs`.

### 8.8.1 Clock Model & Sync Schedule (Common)

Phone and TV clocks are independent monotonic timers. The phone maintains an offset (`clockOffsetMs`) that maps its own monotonic time to estimated TV monotonic time:

```
tvTimeEstMs = phoneMonotonicMs + clockOffsetMs
```

**Sync schedule (normative):**
- Run **5 exchanges in rapid succession** (100 ms apart) on connection to establish the initial `clockOffsetMs`.
- **Suspend** during active singing. LAN clock drift over a 3-minute song is negligible (<1 ms) once the offset is established.
- Resume with a single exchange on song end or disconnect/reconnect.

---

### 8.8.2 Message Flow (Common)

Clock sync is always **TV-initiated**.

**`ping`** (TV → Phone)
- `pingId` (string; random per sample; echoed by all subsequent messages)
- `tTvSendMs` (TV monotonic ms at send)

**`pong`** (Phone → TV)
- `pingId` (echo)
- `tTvSendMs` (echo)
- `tPhoneRecvMs` (phone monotonic ms at receipt of `ping`)
- `tPhoneSendMs` (phone monotonic ms at send of `pong`)

**`clockAck`** (TV → Phone) — sent **immediately** after receiving `pong`
- `pingId` (echo)
- `tTvRecvMs` (TV monotonic ms at receipt of `pong`)

`clockAck` closes the loop for the phone. Without it, the phone has only `t1, t2, t3` and cannot compute `clockOffsetMs`.

---

# 9. UI Screens and Flows - TV
This section is normative for MVP UI and navigation on Android TV.

## 9.1 Global navigation and input
- Primary input is TV remote (DPAD + OK/Enter + Back).
**Navigation model (normative)**
- The TV app uses a simple navigation stack.
 - Entering a full-screen screen **pushes** it onto the stack.
 - Pressing **Back** on a full-screen screen **pops** the current screen and returns to the previous screen.
- Overlays/modals (Advanced Search, Select Players, dialogs) do not affect the navigation stack; Back closes the overlay and returns to the underlying screen.
**Back behavior (normative)**
- From Song List: if a song filter is active, Back clears the filter; otherwise exits app (or returns to Android launcher).
- From Settings (root): returns to the previous screen in the navigation stack.
 - If Settings was entered from Song List (via ⚙ gear button), previous is Song List.
 - If Settings was entered from Select Players (via the "No phones connected" modal), previous is Select Players.
- From Settings sub-screens: returns to Settings (root).
- From modal dialogs/overlays:
 - Back closes the overlay/dialog and returns to the underlying screen.
- From Singing: opens Pause overlay (Resume / Restart Song / Quit to Song List).
- From Results: returns to Song List.
- **Special case — Settings entered from Select Players "No phones connected" action:** pressing Back on the Settings root MUST return to the Select Players modal (not Song List). Implementations MUST track this entry context explicitly; it cannot be inferred from the navigation stack alone, because modals do not push onto the navigation stack.
- **OK/Enter** selects highlighted item.
- DPAD navigates focus in lists and menus.
**Long-press OK (normative)**
- A long-press OK is a press-and-hold of OK/Enter for **>= 500 ms**.
- When a screen defines a long-press action, the long-press MUST trigger that secondary action.
- When no long-press action is defined, long-press MUST behave the same as a normal OK.

## 9.2 Song preview playback
This section defines the behavior for Song List preview playback (Section 3.4) and the related Preview Volume setting (10.4.3).
**When preview plays (normative; USDX-aligned)**
- A preview MAY start only when:
  - A song tile is focused, AND
  - Focus remains on the same song for **500 ms** (debounce), AND
  - Preview Volume is non-zero.
- Preview MUST stop immediately when:
  - Focus moves to a different song tile
  - Focus leaves the song grid (e.g., moves to Search field, buttons, Medley playlist)
  - Advanced Search overlay opens
  - Select Players modal opens
  - Settings opens
  - Singing starts
  - The Song List screen is hidden (screen loses focus)
**What plays (normative; USDX-aligned)**
- Preview uses the song's `audioUrl` from `songListUpdate`.
- Preview start position is taken from `previewStartSec` in the song's index entry (always available; computed at scan time per §3.3).
- If `previewStartSec > 0.0`, use `previewStartSec`.
  - Otherwise, use a fallback position computed from the audio length:
    - `pos = audioLengthSec / 4`
    - If `pos > 120.0`, clamp to `60.0` seconds.
- `audioUrl` is handed directly to ExoPlayer with a seek to the preview position. Playback begins once ExoPlayer has buffered a small initial segment (typically < 500 ms on LAN).
- Preview plays from the start position and continues until stopped by the rules above (no fixed 10s limit).
- If `audioUrl` is null or the HTTP request fails, the TV MUST suppress preview silently (no error shown).
**Video preview (normative; USDX-aligned)**
- If video preview is enabled in settings and the focused song has a valid video file, the preview pane MUST play video.
- Video position MUST be synchronized to audio preview position:
  - `videoPositionSec = videoGapSec + audioPreviewPositionSec` (i.e., applies `#VIDEOGAP` like USDX).
- If video preview is stopped (focus change or screen hide), the preview pane MUST stop video and show a blank/black area.
**Audio routing (normative)**
- Preview volume uses **Settings > Audio > Preview Volume**.
- A value of 0 MUST result in silence (disables preview).

## 9.3 Select Players modal
**Purpose**
- On starting a song (including via Random actions) and on starting a medley run, select which connected phone(s) sing.
- For medley playback, the selected players MUST remain assigned for the entire medley run (no additional prompts between segments).
**Presentation (normative)**
- This is a modal overlay.
- Title: `SELECT PLAYERS`
- Subtitle:
  - For single-song play: `<Artist> — <Title>`
  - For medley play: `Medley — <n> songs` (where `n` is the playlist count at the time Select Players opens; no cap)
**Fields**
- Player 1 device: required (dropdown list of connected phones).
- Player 2 device: present but may be disabled or hidden depending on song/mode type.
- Difficulty per player: Easy / Medium / Hard.
**Gating rules (normative)**
- Duet songs:
 - Player 1 required.
 - Player 2 optional.
 - If two players are selected: Player 1 sings P1 and Player 2 sings P2; provide **Swap Parts**.
 - If only one player is selected: allow selecting which duet part is sung (P1 or P2).
- Non-duet songs:
 - Player 1 required.
 - Player 2 selector MUST be visible but **disabled** (cannot be selected).
 - Player 2 Difficulty selector MUST be **hidden** when Player 2 is `(none)`.
- Medley play:
 - All medley songs are non-duet (`canMedley` requires `isDuet=false`).
 - The Player 2 section (phone selector and difficulty) MUST be **hidden entirely** in the Select Players modal when opened for medley play.
**Empty/error states (normative)**
- If no phones are connected, show a blocking message `No phones connected` and a primary action to open Settings > Connect Phones.
**Song start (normative)**
- For **single-song play**: asset URLs are already available in `songListUpdate`. When the user presses **Start**, the TV fetches `txtUrl` (the chart file, typically < 200 KB) synchronously, parses it, then hands `audioUrl` and `videoUrl` directly to ExoPlayer. No pre-fetch loading gate is required; ExoPlayer begins buffering immediately and playback starts within 1–2 seconds.
- For **medley play**: same as single-song. All segment `txtUrl` values MAY be fetched eagerly in the background once the medley playlist is confirmed, to reduce per-segment parse latency. This is optional and MUST NOT block the Start button.
- If `audioUrl` is null for a selected song (file missing or not locally available on the phone), the TV MUST show an error before starting: `Cannot load song — audio file is unavailable on the phone.`
**Song start failure (normative; used by medley too)**
- If starting playback fails after the user selects **Start** (e.g., audio URL is unreachable or the phone disconnected between Select Players and playback start), the app MUST:
  - Abort start,
  - Return to Song List, and
  - Show a blocking error modal with a single `OK` action (default focus):
    - Title: `ERROR`
    - Body line 1 (exact): `This song can't be played.`
    - Body line 2: `Check Settings > Song Library — the song's phone may be disconnected.`
**Actions**
- Start: begins countdown then singing (single-song) or begins the medley run (medley play).
- Cancel/Back: closes the modal and returns to the underlying screen (typically Song List).
**Select Players wireframes (TV modal; spec-only interactions)**
Loading state (single-song; txt fetch in progress):
```text
+--------------------------------------------------------------------------------+
| SELECT PLAYERS                                              <Artist> — <Title> |
+--------------------------------------------------------------------------------+
| Player 1 (required)                                                             |
|  Phone:      [ Pixel-7 ▾ ]                                                      |
|  Difficulty: [ Medium  ▾ ]                                                      |
|                                                                                |
|                                     > Cancel    [Start]                         |
+--------------------------------------------------------------------------------+
```
Non-duet song (ready to start):
```text
Non-duet song
+--------------------------------------------------------------------------------+
| SELECT PLAYERS                                                   <Artist> — <Title> |
+--------------------------------------------------------------------------------+
| Player 1 (required)                                                             |
|  Phone:      [ Pixel-7 ▾ ]                                                      |
|  Difficulty: [ Medium ▾ ]                                                       |
+--------------------------------------------------------------------------------+
| Player 2                                                                        |
|  Phone:      [ (disabled) ]                                                     |
+--------------------------------------------------------------------------------+
| [Start]   [Cancel]                                                              |
+--------------------------------------------------------------------------------+
| Hints: OK=Select   Back=Cancel                                                  |
+--------------------------------------------------------------------------------+
Duet song
+--------------------------------------------------------------------------------+
| SELECT PLAYERS (DUET)                                           <Artist> — <Title> |
+--------------------------------------------------------------------------------+
| Player 1 (P1)                                Player 2 (P2)                      |
|  Phone: [ Pixel-7 ▾ ]                        Phone: [ (none) ▾ ] (optional)    |
|  Difficulty: [ Medium ▾ ]                    Difficulty: [ Medium ▾ ]          |
|                                                                                |
| If Player 2 is (none):  Solo duet part:  (• P1) (  P2)                         |
| If both players selected:  [Swap Parts]                                        |
+--------------------------------------------------------------------------------+
| [Start]   [Cancel]                                                              |
+--------------------------------------------------------------------------------+
| Hints: OK=Select   Back=Cancel                                                  |
+--------------------------------------------------------------------------------+
Blocking state (no phones connected)
+--------------------------------------------------------------------------------+
| SELECT PLAYERS                                                                  |
+--------------------------------------------------------------------------------+
| ⚠ No phones connected.                                                         |
|   Connect phones in Settings to sing.                                           |
|                                                                                |
| [Open Settings > Connect Phones]   [Cancel]                                     |
+--------------------------------------------------------------------------------+
```
**Protocol side effects (normative)**
- On Start, TV sends `assignSinger` to each selected singer phone (one message per singer):
 - Selected device(s) receive an `assignSinger` with `playerId`:
  - Non-duet: Player 1 -> `P1`.
  - Duet:
   - If two players selected: Player 1 -> `P1`, Player 2 -> `P2` (swapped if the user selects Swap Parts).
   - If one player selected: `P1` or `P2` based on the user's duet-part selection.
- The TV MUST NOT send `assignSinger` to non-selected devices.
- When a song ends, phones stop streaming based on `endTimeTvMs` (Section 10.5). When the user quits early, the TV MUST stop scoring and SHOULD transition phones out of Singing via `sessionState.inSong=false` and/or closing the session.
- Countdown mapping (from Settings > Gameplay):
 - If Ready countdown is ON: send `startMode="countdown"` and `countdownMs = countdownSeconds*1000`.
 - If OFF: send `startMode="live"` and omit `countdownMs`.

## 9.4 Settings Screen
Settings is a simple list of items; selecting one opens a sub-screen.
- Connect Phones
- Song Library
- Audio
- Scoring Timing
- Gameplay
- Video
**Wireframe (TV Settings root)**
```text
+--------------------------------------+
| SETTINGS                              |
|  > Connect Phones                     |
|    Song Library                       |
|    Audio                              |
|    Scoring Timing                     |
|    Gameplay                           |
|    Video                              |
+--------------------------------------+
| Hints: OK=Open   Back=Return          |
+--------------------------------------+
```
**Numeric setting edit (normative)**
- For boolean settings, OK MUST toggle the value immediately.
- For numeric settings, OK MUST open a modal numeric keypad dialog.
- The numeric keypad dialog MUST:
 - Show the setting name and current value.
 - Allow entering digits 0-9.
 - First digit entered MUST **replace** the entire current value (replace-on-first-digit). Subsequent digits MUST append.
 - **Del** MUST delete the last entered digit (if any). If no digits remain, the value becomes empty.
 - Long-pressing **Del** (or equivalent Clear gesture) MUST clear the entire input.
 - Provide **Cancel** and **OK** actions.
 - Cancel (or Back) MUST close the dialog without applying changes.
 - OK MUST validate input; on success, apply immediately and return to the settings screen.
 - On validation failure, the dialog MUST remain open and show an error.
- Default focus MUST be **Cancel**.
**Wireframe (numeric keypad dialog; default focus Cancel)**
```text
+--------------------------------------+
| EDIT VALUE                            |
| Setting: <SettingName>                |
|                                      |
| Value: [ 123 ]                        |
|                                      |
|  [1] [2] [3]                          |
|  [4] [5] [6]                          |
|  [7] [8] [9]                          |
|  [Del] [0]                            |
|                                      |
|  > Cancel     OK                      |
+--------------------------------------+
```

### 9.4.1 Settings > Connect Phones
**Purpose**
- Allow phones to connect via QR/code.
- Show list of connected devices.
**UI**
- QR code + short code.
  - The QR code and join code text MUST satisfy the **QR sizing** requirements from Section 3.4 (Song List).
- Device roster list:
 - display name (editable label), connection status.
 - Optional: latency indicator.
**Actions**
- End session (confirm): invalidates the current session token, disconnects all phones, clears slot assignments, and immediately creates a new session in state Open.
- Rename device: opens a rename dialog (TV on-screen keyboard), updates the stored label for that `clientId`.
- Kick device: confirm then disconnect.
- Forget device: confirm then remove the stored label for that `clientId` and disconnect.
**Focus and activation (normative; TV remote)**
- Default focus on entry: the connected-devices roster list (first row if present).
- DPAD Up/Down: moves focus within the roster list.
- DPAD Down from the roster list when focus is on the **last** row: moves focus to the action-button row (default focused button **Rename**).
- DPAD Left/Right while on the action-button row: cycles **Rename** / **Kick** / **Forget**.
- DPAD Down from the action-button row: moves focus to **End session**.
- DPAD Up from **End session**: returns focus to the action-button row (keeping the currently focused action button).
- OK/Enter triggers the currently focused action (Rename/Kick/Forget/End session).
**Rename dialog (normative)**
- Selecting **Rename** MUST open a modal rename dialog using the TV on-screen keyboard.
- The input field MUST be pre-filled with the current display name.
- The user MAY change the name to any non-empty trimmed string.
 - If the resulting trimmed string is empty, OK MUST be disabled (or a validation error MUST be shown and the rename MUST NOT be applied).
- Cancel (or Back) MUST close the dialog without applying changes.
- OK MUST apply the change immediately, store the new name for that `clientId`, and update the roster display.
- Default focus MUST be **Cancel**.
**Wireframe (rename dialog; default focus Cancel)**
```text
+--------------------------------------+
| RENAME DEVICE                         |
| Device: <DeviceName>                  |
|                                      |
| Name: [ Pixel-7__________ ]           |
|                                      |
| [On-screen keyboard]                  |
|                                      |
|  > Cancel     OK                      |
+--------------------------------------+
```
**Wireframe (Connect Phones)**
```text
+--------------------------------------------------------------------------------+
| SETTINGS > CONNECT PHONES                                                      |
+--------------------------------------------------------------------------------+
| Join this session:                                                             |
|   [   QR CODE   ]             Code: ABCD-EFGH                                       |
|                                                                                |
| Connected devices (up to 10):                                                  |
|  > Pixel-7        Connected                                                    |
|    iPhone-13      Connected                                                    |
|    ...                                                                         |
|                                                                                |
| Actions on selected device:  [Rename] [Kick] [Forget]                           |
| Session: [End session] (confirm)                                               |
+--------------------------------------------------------------------------------+
| Hints: OK=Select/Action   Back=Return                                          |
+--------------------------------------------------------------------------------+
```
**Wireframe (confirm dialog; default focus Cancel)**
```text
+--------------------------------------+
| CONFIRM                              |
| Kick <DeviceName>?                   |
|                                      |
|  > Cancel     OK                     |
+--------------------------------------+
+--------------------------------------+
| CONFIRM                              |
| Forget <DeviceName>?                 |
|                                      |
|  > Cancel     OK                     |
+--------------------------------------+
+--------------------------------------+
| CONFIRM                              |
| End session?                         |
|                                      |
|  > Cancel     OK                     |
+--------------------------------------+
```

### 9.4.2 Settings > Song Library (TV)
This screen shows the song contribution status of all currently connected phones. There is no persistent trust list or pairing — any connected phone automatically contributes its songs (see §8.1).
**Connected sources list (normative)**
For each connected phone the TV MUST show:
- Device name (from `hello.deviceName`)
- Song count: number of valid songs from the last `songListUpdate`
- Invalid song count (if any), shown as `2 invalid` alongside the valid count
- Per-row action: **Refresh** (sends `requestSongList` to that phone)
**Actions**
- **Refresh all**: sends `requestSongList` to all currently connected phones.
**DPAD navigation (normative)**
- Default focus on entry: first row if any phones are connected; **Refresh all** button otherwise.
- DPAD Up/Down: navigates phone rows.
- DPAD Right from a row: moves focus to the **Refresh** action for that row.
- DPAD Down from the last row: moves to **Refresh all**.
- OK triggers the focused action.
**Wireframe**
```text
+--------------------------------------------------------------------------------+
| SETTINGS > SONG LIBRARY                                                        |
+--------------------------------------------------------------------------------+
| Connected phones:                                                               |
|                                                                                |
|  > Alice's Pixel 7    songs: 423                           [Refresh]           |
|    Bob's Galaxy S24   songs: 198   2 invalid               [Refresh]           |
|                                                                                |
| [Refresh all]                                                                  |
+--------------------------------------------------------------------------------+
| Hints: OK=Action  Back=Return                                                  |
+--------------------------------------------------------------------------------+
```

### 9.4.3 Settings > Audio
- **Preview Volume** (normative):
 - Slider 0–100.
 - Controls only Song List preview playback volume (Section 10.2). TV/music playback volume during singing uses Android system volume and is not controlled by this app.
 - A value of 0 results in silence (disables preview).
 - **Slider DPAD interaction**: Left/Right adjusts value by ±1 per press; long-press Left/Right adjusts by ±10 per repeat. OK on the slider opens the numeric keypad dialog for direct value entry.
- **Vocals Volume** (normative):
 - Slider 0–100. Default: 50.
 - Controls the mix volume of the `#VOCALS` acapella track when a song provides both `#INSTRUMENTAL` and `#VOCALS` (Section 1.1). Has no effect when `#VOCALS` is absent.
 - A value of 0 silences the vocal guide entirely (pure instrumental karaoke mode). A value of 100 plays the acapella at full volume.
 - **Slider DPAD interaction**: same as Preview Volume slider.
 - **Implementation (TV, normative)**: The TV MUST combine the instrumental and vocals tracks using `MergingMediaSource` (Media3), merging one `ProgressiveMediaSource` per track. Vocals volume MUST be applied by wrapping the vocals `ProgressiveMediaSource` in a `DefaultMediaSourceFactory` that inserts a `ScalingAudioProcessor` into the audio pipeline with a gain factor of `vocalsVolume / 100.0`. The `ScalingAudioProcessor` MUST be applied only to the vocals track; the instrumental track plays at full gain. `player.setVolume()` MUST NOT be used for this purpose (it controls master output, not per-track gain). If the two tracks have different durations, the player MUST stop when the shorter track ends (Media3 default). Track sync differences due to HTTP buffering are tolerated as best-effort on LAN.
- **Mic sensitivity** (normative):
 - Slider 0–7 mapping to `thresholdIndex` (Section 8.3).
 - Display labels: 0=Low, 1=Med-Low, 2=Medium, 3=Med-High, 4=High, 5=Higher, 6=Very High, 7=Max.
 - Default: 2 (threshold value 0.15; suitable for typical room noise).
 - This global setting is used by the TV when populating the `thresholdIndex` field of `assignSinger`. No per-phone override in MVP.
 - **Slider DPAD interaction**: same as Preview Volume slider.
**Wireframe (Audio)**
```text
+--------------------------------------+
| SETTINGS > AUDIO                      |
+--------------------------------------+
| Preview Volume:  [=====|-----]  60    |
| Vocals Volume:   [==|------]    50    |
| Mic sensitivity: [==|------]  Medium  |
+--------------------------------------+
| Hints: Left/Right=Adjust  OK=Enter value  Back=Return |
+--------------------------------------+
```

### 9.4.4 Settings > Scoring Timing
- Manual mic delay baseline (ms). This value compensates for hardware audio pipeline latency (microphone → digital → network). Hardware latency is constant for a given phone model, so a one-time manual calibration is sufficient. See §5.2.4.
**Interaction rules (normative)**
- Selecting **Manual mic delay** and pressing OK MUST open the numeric keypad dialog (see "Numeric setting edit" in Section 10.4).
 - The manual mic delay value MUST be an integer number of milliseconds (>= 0, <= 400).
**Wireframe (Scoring Timing)**
```text
+--------------------------------------+
| SETTINGS > SCORING TIMING             |
+--------------------------------------+
| Manual mic delay (ms):   0            |
+--------------------------------------+
| Hints: OK=Edit  Back=Return           |
+--------------------------------------+
```

### 9.4.5 Settings > Gameplay
- Line bonus ON/OFF (default ON).
- Ready countdown before song start: ON/OFF (default ON).
- Countdown length (seconds): integer 1-10 (default 3). Countdown displays at 1 Hz: N, N-1, ... , 1. After displaying `1`, playback and scoring start.
- Optional: show note lines ON/OFF (visual only; USDX: Ini.NoteLines).
**Interaction rules (normative)**
- Selecting **Countdown seconds** and pressing OK MUST open the numeric keypad dialog (see "Numeric setting edit" in Section 10.4).
 - Validation MUST enforce the range 1-10.
- Selecting **Line bonus**, **Ready countdown**, or **Show note lines** and pressing OK MUST toggle ON/OFF.
**Wireframe (Gameplay)**
```text
+--------------------------------------+
| SETTINGS > GAMEPLAY                   |
+--------------------------------------+
| Line bonus:             ON            |
| Ready countdown:        ON            |
| Countdown seconds:      3             |
| Show note lines:        ON            |
+--------------------------------------+
| Hints: OK=Toggle/Keypad  Back=Return  |
+--------------------------------------+
```

### 9.4.6 Settings > Video
- Video enabled ON/OFF (if disabled, video playback is suppressed and the background fallback is used instead).
**Background fallback order (normative)**
When video is disabled or unavailable, the singing screen background is determined as follows:
1. If the song has a valid `#BACKGROUND` image file: use it as full-screen background.
2. If no background image is available: use the **app-shipped default background image** (a single static image bundled with the app at build time and always available as the final fallback). This same image is also used as the fallback on the Song List screen when no song cover is available.
**Wireframe (Video)**
```text
+--------------------------------------+
| SETTINGS > VIDEO                      |
+--------------------------------------+
| Video enabled:          ON            |
+--------------------------------------+
| Hints: OK=Toggle  Back=Return         |
+--------------------------------------+
```

## 9.5 Singing Screen
**Minimum layout**
- Lyrics line with progressive highlight.
- Pitch bars (or equivalent) for each active singer.
- Per-singer score: current total (and optionally note/golden breakdown).
- **Single singer layout**: when only one singer is active, the single pitch lane is **vertically centered** on screen (occupying the full width, centered vertically). The lyrics strip remains at the bottom. The score box appears at the right of the lane.
- **Two singer layout**: two pitch lanes, one per singer, stacked vertically.
- **Elapsed time**: displayed bottom-right of the singing screen, formatted as `MM:SS` (always two digits each, zero-padded; e.g., `00:35`, `01:23`). This is elapsed time from the start of the song.
- **Instrumental gap indicator**: shown in the pitch lane per the rule in Section 1.1 (animated rest indicator during extended silent regions).
**Sentence rating (USDX parity)**
After each sentence ends, a brief rating label is displayed for the corresponding singer's lane. The label is derived from `LinePerfection` (Section 6.5) and is shown for approximately 800ms then fades:
| LinePerfection | Label |
|---|---|
| 1.00 | `Perfect!` |
| ≥ 0.80 | `Great` |
| ≥ 0.60 | `Good` |
| ≥ 0.40 | `Cool` |
| ≥ 0.20 | `Okay` |
| < 0.20 | `Poor` |
**Countdown**
- Countdown before playback and scoring begin is controlled by Settings > Gameplay:
 - If Ready countdown is ON: show N-second countdown at 1 Hz (N from setting) then begin playback and scoring.
 - If OFF: begin playback and scoring immediately.
- If a required singer disconnects during countdown: cancel start and return to Select Players with a blocking error modal.
**Countdown disconnect error modal (normative)**
- The modal MUST appear immediately after returning to Select Players.
- The modal MUST be blocking (no background interaction until dismissed).
- Modal content:
 - Title: `DISCONNECTED`
 - Body: `A required singer disconnected during countdown. Please reconnect and start again.`
 - Single action: `OK`
- Default focus MUST be on `OK`.
- On `OK`, the modal MUST close and the user remains on Select Players.
**Wireframe (countdown disconnect modal; TV)**
```text
+--------------------------------------+
| DISCONNECTED                          |
| A required singer disconnected         |
| during countdown.                      |
| Please reconnect and start again.      |
|                                      |
|  > OK                                 |
+--------------------------------------+
```
**Pause**
- Back opens Pause overlay:
```text
+--------------------------------------+
| PAUSED                               |
|  > Resume                            |
|    Restart Song                      |
|    Quit to Song List                 |
+--------------------------------------+
```
 - **Resume**: resumes playback and scoring from the current position.
 - **Restart Song**: opens a confirm dialog (default focus Cancel). On OK: resets all per-player scores and state, seeks audio to `startSec` (and video to `videoGapSec + startSec`), resets beat cursors, and re-sends `assignSinger` to assigned phones with a new `songInstanceSeq`. In medley mode, **Restart Song restarts the full medley from segment 1** — scores for all segments are cleared, and `endTimeTvMs` MUST be recomputed as: `endTimeTvMs = tvMonotonicNowMs + totalMedleyDurationMs`, where `totalMedleyDurationMs = sum over all medley segments of (medleyEndSec[i] - medleyStartSec[i])`, using the `medleyStartSec`/`medleyEndSec` computed per segment per §10.5.1.
 - **Quit to Song List**: confirm dialog (default focus Cancel). On OK: stops playback, returns to Song List.
**Disconnect auto-pause (normative)**
- When a **required** singer (a phone assigned as P1 or P2) disconnects mid-song, the TV MUST **automatically pause** the song and show the following overlay:
```text
+--------------------------------------+
| PAUSED — PLAYER DISCONNECTED         |
| <PhoneName> has disconnected.         |
|                                      |
|  > Wait for reconnect                |
|    Continue without them             |
|    Quit to Song List                 |
+--------------------------------------+
```
 - **Wait for reconnect**: song stays paused. If the phone reconnects (Section 7.4), the TV re-sends `assignSinger` with an updated `endTimeTvMs` reflecting the remaining song duration, and the song resumes from the paused position.
 - **Continue without them**: song resumes. No pitch frames will arrive for that player; they contribute no further score.
 - **Quit to Song List**: same as normal Quit behavior.
- Spectator disconnects (phones not assigned as singers) MUST NOT trigger auto-pause.
**Song end (normative)**
Definition:
- `endTimeTvMs` is the authoritative song end time for each assigned singer, expressed in TV monotonic milliseconds.
  - For a normal song: `endTimeTvMs = songStartTvMs + effectiveSongDurationMs`. Where `effectiveSongDurationMs`: if `#END` is present and `endMs > 0`, use `(endMs/1000.0 - startSec) * 1000`; otherwise use audio file duration minus `startSec`, in ms.
  - For a medley: `endTimeTvMs` is the TV monotonic ms at the end of the final segment's `medleyEndSec` (including `MEDLEY_FADE_OUT_SEC`).
Phone behavior:
- When `tvNowMs >= endTimeTvMs`, the phone MUST:
  - stop audio capture and pitch detection
  - stop transmitting any further `pitchFrame` UDP datagrams for that `songInstanceSeq`
  - transition its UI state to the Waiting/Connected screen
TV behavior:
- The TV MUST ignore any `pitchFrame` with `tvTimeMs >= endTimeTvMs` for scoring.
- The TV MUST finalize scoring and transition to Results when playback reaches the chart/medley end.
**Wireframes (USDX-aligned, spec-only interactions)**
```text
Active singing screen — two singers
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
| Lyrics (USDX style: active syllables highlighted)                               |
|   CUz this life is too short                                                   |
|   to live it just for you                                                      |
+--------------------------------------------------------------------------------+
|                                                                      00:35     |
+--------------------------------------------------------------------------------+
Active singing screen — single singer (vertically centered lane)
+--------------------------------------------------------------------------------+
|                          (FULLSCREEN VIDEO / BACKGROUND)                       |
|                                                                                |
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
| Lyrics                                                                          |
|   CUz this life is too short                                                   |
+--------------------------------------------------------------------------------+
|                                                                      00:35     |
+--------------------------------------------------------------------------------+
Countdown overlay (before playback and scoring start; 1 Hz)
+--------------------------------------------------------------------------------+
|                                                                                |
|                                     3                                          |
|                                                                                |
+--------------------------------------------------------------------------------+
(then 2, 1; after showing 1, playback + scoring start)
Pause overlay (Back)
+--------------------------------------+
| PAUSED                               |
|  > Resume                            |
|    Restart Song                      |
|    Quit to Song List                 |
+--------------------------------------+
Restart confirm (default focus Cancel)
+--------------------------------------+
| CONFIRM                              |
| Restart song?                        |
|                                      |
|  > Cancel     OK                     |
+--------------------------------------+
Quit confirm (default focus Cancel)
+--------------------------------------+
| CONFIRM                              |
| Quit to Song List?                   |
|                                      |
|  > Cancel     OK                     |
+--------------------------------------+
Disconnect auto-pause overlay
+--------------------------------------+
| PAUSED — PLAYER DISCONNECTED         |
| <PhoneName> has disconnected.         |
|                                      |
|  > Wait for reconnect                |
|    Continue without them             |
|    Quit to Song List                 |
+--------------------------------------+
```

### 9.5.1 Singing Screen (Medley mode)
Medley mode plays a **sequence of songs** (the Medley playlist) back-to-back, but only the **medley window** of each song is played and scored.
**Medley run context (normative)**
- When starting medley playback, the implementation MUST create an immutable **medley run snapshot** from the current Medley playlist (Song List screen; Section 3.4).
  - This avoids coupling medley playback to the Song List screen lifecycle (the Song List playlist may be cleared when the user leaves that screen).
- The medley run snapshot MUST preserve the playlist order.
**Medley start flow (normative)**
- When the user starts a medley (Song List; **Play Medley**), the app MUST show **Select Players** once (Section 10.3) with subtitle `Medley — <n> songs`.
- On **Start**, apply countdown rules (Countdown subsection in Section 10.5) and then begin playback of segment 1.
- The selected players MUST remain assigned for the entire medley run; the app MUST NOT prompt again between segments.
- On segment end, automatically advance to the next song (or end medley if the last segment finished).
**Cancel behavior (normative)**
- If the user selects **Cancel** in Select Players before the medley begins, the medley start MUST be aborted and the app MUST return to the Song List without changing the current playlist.
**Medley window playback (parity-aligned; normative)**
- A song is only eligible for medley playback if `medleySource = "tag"` (Section 3.4; `canMedley`).
- The medley window is defined by the song's medley beats:
  - `startBeat = ParsedSong.medley.startBeat`
  - `endBeat = ParsedSong.medley.endBeat`
- The implementation MUST play and display lyrics starting at a **medley entry** time and stop at an **extended end** time.
  - `MEDLEY_FADE_IN_SEC = 8` (constant; not user-configurable)
  - `MEDLEY_FADE_OUT_SEC = 2` (constant; not user-configurable)
  - **Parity note (USDX):** these constants are the medley audio fade envelope durations and also extend the playback window before `startBeat` and after `endBeat`.
  - `medleyStartSec = max(0, timeFromBeat(startBeat) - MEDLEY_FADE_IN_SEC)`
  - `medleyEndSec = timeFromBeat(endBeat) + MEDLEY_FADE_OUT_SEC`
  - At the start of each segment (including segment 1), audio MUST begin with a fade-in over `MEDLEY_FADE_IN_SEC` to the normal playback volume.
- For video backgrounds (if present and enabled):
  - The video position MUST be initialized to `videoGapSec + medleyStartSec` (USDX behavior).
**Segment transitions (normative; TV UX)**
- Between segments, the implementation MUST perform an audio fade transition.
- Default behavior:
  - Fade out the current segment over `MEDLEY_FADE_OUT_SEC`.
  - Fade in the next segment over `MEDLEY_FADE_IN_SEC` starting at that segment's `medleyStartSec`.
- Implementations MAY overlap the tail of fade-out with the head of fade-in (crossfade) if audio mixing is available; if not, a sequential fade-out then fade-in is acceptable.
**Segment failure handling (normative)**
- If `audioUrl` is null for any segment when the medley reaches it, the TV MUST skip that segment and proceed to the next, showing a brief error toast.
- If a segment's audio URL becomes unreachable during playback (e.g., the source phone disconnected mid-segment), the current medley run MUST be aborted and the app MUST follow **Song start failure** behavior (Section 10.3): return to Song List and show the same blocking error modal.
**Scoring scope (parity-aligned; normative)**
- Only notes within the medley window contribute to score.
  - Parity note: in USDX, entering medley mode converts notes outside `[startBeat, endBeat)` to **Freestyle**; Freestyle has `ScoreFactor=0`, so those notes contribute 0 points.
**In-song header text and segment indicator (parity-aligned; normative)**
- While singing in medley mode and `n>1`, the in-song artist/title label MUST render as:
  - `<i>/<n>: <Artist> — <Title>`
- A segment progress indicator MUST be shown in the top-left corner of the singing screen alongside the label.
**Wireframe note (medley singing screen header area)**
```text
| 2/5: Daft Punk — Get Lucky          P1 [badge]
|  ─────────────────────────────────────────────
```

## 9.6 Results Screen (TV)

### Post-song results
Show per singer:
- Notes score, Golden score, Line bonus, **Song Total** (tens-rounded per USDX rules).
Actions:
- MVP has no persistent song queue; returning to Song List is required to start another song. The Song List screen may maintain a transient Medley playlist (Section 3.4) that is initialized when the screen is shown.
- **Back to Song List** (only action; restarting is done from the Pause menu)
**Back key (normative)**
- Pressing TV remote **Back** on the Results screen MUST behave the same as selecting **Back to Song List** (i.e., return to Song List).
**Wireframe (Song Score layout; spec-only actions)**
```text
+--------------------------------------------------------------------------------+
| Song Score                                                                     |
| <Artist> — <Title>                                                             |
+--------------------------------------------------------------------------------+
| P1: <PhoneName>                                  | Comparison |     P2: <PhoneName> |
|                                                                                |
| Notes score        00000                          |█████       |   Notes score        00000 |
| Golden score       00000                          |███████     |   Golden score       00000 |
| Line bonus         00000                          |████        |   Line bonus         00000 |
|                                                                                |
| Song Total        00000                           |██████      |   Song Total        00000 |
|                                                                                |
+--------------------------------------------------------------------------------+
| [Back to Song List]                                                            |
+--------------------------------------------------------------------------------+
```

### Post-medley results
After a medley run finishes, show a single results screen with a static score table listing each segment score and the aggregate Medley Total. No Left/Right navigation between rounds is required.
**Aggregation (parity-aligned; normative)**
- The Medley Total MUST be the **mean** (average) of the per-song `scoreTotalInt` values across segments for each player.
  - `MedleyTotal.scoreTotalInt = round( sum(segment.scoreTotalInt) / nSegments )`
  - `round()` uses the same primitive as §6.6. Note that the result MAY be a non-multiple-of-10 because it is produced by averaging (USDX parity).
**Display (normative)**
- List each segment as a row: `<i>. <Artist> — <Title>   P1: <scoreTotalInt>   P2: <scoreTotalInt>`
- Final row: Medley Total for each player.
- No navigation actions between rounds. Only action: **Back to Song List**.
**Back key (normative)**
- Pressing TV remote **Back** MUST return to Song List.
**Wireframe (medley results; TV)**
```text
+--------------------------------------------------------------------------------+
| Medley Results                                                                  |
+--------------------------------------------------------------------------------+
| P1: <PhoneName>                                          P2: <PhoneName>        |
+--------------------------------------------------------------------------------+
|  1. PSY — Gangnam Style                          01840         07200           |
|  2. Daft Punk — Get Lucky                        07200         04100           |
|  3. Queen — Bohemian Rhapsody                    06100         08300           |
|  ──────────────────────────────────────────────────────────────────────────   |
|  Medley Total                                    05047         06533           |
+--------------------------------------------------------------------------------+
| [Back to Song List]                                                            |
+--------------------------------------------------------------------------------+
| Hints: OK=Back to Song List   Back=Back to Song List                           |
+--------------------------------------------------------------------------------+
```

# Appendix A: Library Dependency Reference
This appendix is **normative**. Implementations MUST use the pinned libraries below for the designated concerns. Using alternative libraries for these concerns is not permitted without a spec revision, because the choice of library directly affects wire compatibility, audio behavior, or performance on the target hardware.

## A.1 Android TV Host App (Kotlin)
| Concern | Library | Pinned Version | Justification |
|---|---|---|---|
| WebSocket server | `io.ktor:ktor-server-cio` + `io.ktor:ktor-server-websockets` | `2.3.12` | CIO engine is coroutine-native, ~500 KB, zero native dependencies. Handles `/` WebSocket routing and token validation trivially. Netty is prohibited — it adds ~8 MB of native binaries and complex thread pool management. |
| JSON serialization (all control messages, hot path) | `org.jetbrains.kotlinx:kotlinx-serialization-json` | `1.7.3` | Compile-time code generation; no reflection. Mandatory on the scoring receive path. Gson and Moshi (reflection-based) are prohibited on any path that handles incoming WebSocket frames during gameplay. |
| Audio playback + VOCALS mixing | `androidx.media3:media3-exoplayer` + `androidx.media3:media3-datasource-okhttp` | `1.4.1` | `MergingMediaSource` for dual-track (#INSTRUMENTAL + #VOCALS) mixing with `ScalingAudioProcessor` for per-track volume control (§10.4.3). `ProgressiveMediaSource` for HTTP streaming. The OkHttp data source is required — the default `DefaultHttpDataSource` uses `HttpURLConnection` which does not handle concurrent range requests efficiently; without it seeking on LAN-served audio is noticeably slower on mid-tier hardware. |
| Image loading (cover/background art) | `io.coil-kt.coil3:coil-compose` + `io.coil-kt.coil3:coil-network-okhttp` | `3.4.0` | Coroutine-native, Compose-compatible image loader. `coil-network-okhttp` artifact required for HTTP URL loading (coil3's core no longer includes a network backend by default). Handles LRU memory cache and lazy loading of cover art tiles in the song grid. |
| QR code generation (session join code display) | `com.journeyapps:zxing-android-embedded` | `4.3.0` | Mature, widely used, no camera permission required for generation-only use. |
| Settings persistence (device names, audio prefs) | `androidx.datastore:datastore-preferences` | `1.1.1` | Idiomatic replacement for SharedPreferences on Android. Room is overkill for flat key-value preferences. |
| mDNS advertisement | `jmdns` | `3.5.9` | Pure-Java mDNS/DNS-SD implementation. Android TV's NSD Manager has known unreliability on several OEM firmware builds; jmDNS is the safe, deterministic alternative for advertising `_karaoke._tcp` service records. |

## A.4 Prohibited Patterns
- **Reflection-based JSON on the scoring path**: any library that uses runtime reflection is prohibited for decoding control messages received during an active song. Use `kotlinx.serialization` (Android/TV) and `Codable` with `JSONDecoder` (iOS) instead.
- **Netty engine for Ktor**: use CIO only.
- **ZIP-based song transfer**: §8.6 mandates direct HTTP streaming. No ZIP building, extraction, or WebSocket binary chunk framing for song files.
- **`shelf_static` or equivalent static file middleware for audio/video**: does not implement `Accept-Ranges`. Use a custom route handler that parses the `Range` header and returns the correct byte range.
- **Direct `file://` path access to SAF URIs on Android**: use `ContentResolver` exclusively. Calling `uri.path` and opening it as a `File` is broken on Android 10+ scoped storage and MUST NOT be used.
- **`NSNetServiceBrowser` on iOS**: deprecated since iOS 16. Use `NWBrowser` from `Network.framework` exclusively.

# Appendix B: Protocol Schemas
This appendix is **normative** and defines JSON Schemas for MVP protocol messages described in Section 8.
Schema notes:
- Schemas use JSON Schema Draft 2020-12.
- `additionalProperties` is set to `false` to keep fixtures deterministic for MVP.

## B.1 Common envelope
All messages are JSON objects and MUST include:
- `type` (string)
- `protocolVersion` (int; MUST be `1` in MVP)
- `tsTvMs` (optional; TV may include)

## B.2 Schemas

### B.2.1 `hello`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "hello",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "protocolVersion", "clientId", "deviceName", "appVersion", "capabilities", "httpPort"],
  "properties": {
    "type": {"const": "hello"},
    "protocolVersion": {"type": "integer", "const": 1},
    "clientId": {"type": "string", "minLength": 8},
    "deviceName": {"type": "string", "minLength": 1},
    "appVersion": {"type": "string", "minLength": 1},
    "httpPort": {"type": "integer", "minimum": 1024, "maximum": 65535, "description": "Port on which the phone's HTTP file server is listening"},
    "capabilities": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "pitchFps": {"type": "integer", "minimum": 1}
      }
    }
  }
}
```

### B.2.2 `sessionState`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "sessionState",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "protocolVersion", "sessionId", "slots", "inSong"],
  "properties": {
    "type": {"const": "sessionState"},
    "protocolVersion": {"type": "integer", "const": 1},
    "tsTvMs": {"type": "number"},
    "sessionId": {"type": "string", "minLength": 1},
    "slots": {
      "type": "object",
      "additionalProperties": false,
      "required": ["P1", "P2"],
      "properties": {
        "P1": {
          "type": "object",
          "additionalProperties": false,
          "required": ["connected", "deviceName"],
          "properties": {
            "connected": {"type": "boolean"},
            "deviceName": {"type": "string"}
          }
        },
        "P2": {
          "type": "object",
          "additionalProperties": false,
          "required": ["connected", "deviceName"],
          "properties": {
            "connected": {"type": "boolean"},
            "deviceName": {"type": "string"}
          }
        }
      }
    },
    "inSong": {"type": "boolean"},
    "songTimeSec": {"type": "number"},
    "connectionId": {"type": "integer", "description": "uint16 sender ID assigned by TV per connection; present only in the initial sessionState response to hello; included in every pitchFrame datagram"}
  }
}
```

### B.2.3 `ping` / `pong` (clock sync)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ping_or_pong",
  "oneOf": [
    {"$ref": "#/$defs/ping"},
    {"$ref": "#/$defs/pong"}
  ],
  "$defs": {
    "ping": {
      "title": "ping",
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "protocolVersion", "pingId", "tTvSendMs"],
      "properties": {
        "type": {"const": "ping"},
        "protocolVersion": {"type": "integer", "const": 1},
        "tsTvMs": {"type": "number"},
        "pingId": {"type": "string", "minLength": 1},
        "tTvSendMs": {"type": "integer"}
      }
    },
    "pong": {
      "title": "pong",
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "protocolVersion", "pingId", "tTvSendMs", "tPhoneRecvMs", "tPhoneSendMs"],
      "properties": {
        "type": {"const": "pong"},
        "protocolVersion": {"type": "integer", "const": 1},
        "tsTvMs": {"type": "number"},
        "pingId": {"type": "string", "minLength": 1},
        "tTvSendMs": {"type": "integer"},
        "tPhoneRecvMs": {"type": "integer"},
        "tPhoneSendMs": {"type": "integer"}
      }
    }
  }
}
```

### B.2.4 `clockAck` (TV → phone)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "clockAck",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "protocolVersion", "pingId", "tTvRecvMs"],
  "properties": {
    "type": {"const": "clockAck"},
    "protocolVersion": {"type": "integer", "const": 1},
    "tsTvMs": {"type": "number"},
    "pingId": {"type": "string", "minLength": 1},
    "tTvRecvMs": {"type": "integer"}
  }
}
```

### B.2.5 `error`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "error",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "protocolVersion", "code", "message"],
  "properties": {
    "type": {"const": "error"},
    "protocolVersion": {"type": "integer", "const": 1},
    "tsTvMs": {"type": "number"},
    "code": {"type": "string", "minLength": 1},
    "message": {"type": "string", "minLength": 1}
  }
}
```

### B.2.6 `assignSinger`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "assignSinger",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "protocolVersion", "sessionId", "songInstanceSeq", "playerId", "difficulty", "thresholdIndex", "effectiveMicDelayMs", "expectedPitchFps", "startMode", "endTimeTvMs", "udpPort"],
  "properties": {
    "type": {"const": "assignSinger"},
    "protocolVersion": {"type": "integer", "const": 1},
    "tsTvMs": {"type": "number"},
    "sessionId": {"type": "string", "minLength": 1},
    "songInstanceSeq": {"type": "integer", "minimum": 0, "description": "uint32 counter; increments on every song start including Restart"},
    "playerId": {"type": "string", "enum": ["P1", "P2"]},
    "difficulty": {"type": "string", "enum": ["Easy", "Medium", "Hard"]},
    "thresholdIndex": {"type": "integer", "minimum": 0, "maximum": 7},
    "effectiveMicDelayMs": {"type": "integer", "minimum": 0},
    "expectedPitchFps": {"type": "integer", "minimum": 1},
    "startMode": {"type": "string", "enum": ["countdown", "live"]},
    "countdownMs": {"type": "integer", "minimum": 0},
    "endTimeTvMs": {"type": "integer"},
    "udpPort": {"type": "integer", "minimum": 1024, "maximum": 65535},
    "songTitle": {"type": "string"},
    "songArtist": {"type": "string"}
  },
  "allOf": [
    {
      "if": {"properties": {"startMode": {"const": "countdown"}}},
      "then": {"required": ["countdownMs"]}
    }
  ]
}
```

### B.2.7 `pitchFrame` (binary; not JSON)
`pitchFrame` is a **binary UDP datagram**, not a JSON message. There is no JSON schema for it. See §8.3 for the full 16-byte layout. For reference:
```
Offset  Size  Type    Field
  0      4   uint32  seq
  4      4   int32   tvTimeMs
  8      4   uint32  songInstanceSeq  (matches assignSinger.songInstanceSeq)
 12      1   uint8   playerId     (0=P1, 1=P2)
 13      1   uint8   midiNote     (0-127 voiced; 255=unvoiced)
 14      2   uint16  connectionId (assigned by TV at hello handshake)
```

### B.2.8 `requestSongList`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "requestSongList",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "protocolVersion", "sessionId"],
  "properties": {
    "type": {"const": "requestSongList"},
    "protocolVersion": {"type": "integer", "const": 1},
    "tsTvMs": {"type": "number"},
    "sessionId": {"type": "string", "minLength": 1}
  }
}
```

### B.2.9 `songListUpdate`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "songListUpdate",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "protocolVersion", "sessionId", "songs"],
  "properties": {
    "type": {"const": "songListUpdate"},
    "protocolVersion": {"type": "integer", "const": 1},
    "sessionId": {"type": "string", "minLength": 1},
    "songs": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["relativeTxtPath", "isValid", "modifiedTimeMs", "title", "artist", "isDuet", "hasRap", "hasVideo", "hasInstrumental", "canMedley"],
        "properties": {
          "relativeTxtPath": {"type": "string", "minLength": 1},
          "isValid": {"type": "boolean"},
          "invalidReasonCode": {"type": ["string", "null"]},
          "invalidLineNumber": {"type": ["integer", "null"], "description": "1-based; present when isValid=false and error is line-associated; null otherwise"},
          "modifiedTimeMs": {"type": "integer"},
          "title": {"type": "string"},
          "artist": {"type": "string"},
          "album": {"type": ["string", "null"]},
          "year": {"type": ["integer", "null"]},
          "genre": {"type": ["string", "null"]},
          "isDuet": {"type": "boolean"},
          "hasRap": {"type": "boolean"},
          "hasVideo": {"type": "boolean"},
          "hasInstrumental": {"type": "boolean"},
          "canMedley": {"type": "boolean"},
          "medleySource": {"type": ["string", "null"], "enum": ["tag", null]},
          "medleyStartBeat": {"type": ["integer", "null"]},
          "medleyEndBeat": {"type": ["integer", "null"]},
          "startSec": {"type": "number"},
          "previewStartSec": {"type": "number"},
          "txtUrl": {"type": ["string", "null"], "format": "uri"},
          "audioUrl": {"type": ["string", "null"], "format": "uri"},
          "videoUrl": {"type": ["string", "null"], "format": "uri"},
          "coverUrl": {"type": ["string", "null"], "format": "uri"},
          "backgroundUrl": {"type": ["string", "null"], "format": "uri"},
          "instrumentalUrl": {"type": ["string", "null"], "format": "uri"},
          "vocalsUrl": {"type": ["string", "null"], "format": "uri"}
        }
      }
    }
  }
}
```

# Appendix C: Parsed Song Model
This appendix defines the **normative in-memory representation** of a parsed USDX `.txt` song.
- Implementations MAY choose different class/type names.
- Implementations MUST preserve the fields, semantics, and invariants described here.
- All beats in this model are expressed in **file beats** (the beats used in `.txt` note lines). Conversion to internal beats is defined in Section 5.3.

## C.1 Core entities

### ParsedSong
Required fields:
- `songId` (string): stable identifier of the song instance in the library.
  - MUST match the index `songId` derivation in Section 3.3: `phoneClientId + "::" + relativeTxtPath`.
- `header` (SongHeader)
- `timing` (SongTiming)
- `tracks` (Track[1..2])
- `diagnostics` (DiagnosticEntry[]) : parse-time diagnostics; MUST include line numbers when available.
Invariants:
- `tracks.length` MUST be `2` if and only if duet mode is detected (Section 4.1: first non-empty body token begins with `P`). Otherwise `tracks.length` MUST be `1`.
- All note events in `tracks[*].lines[*].notes[*]` MUST satisfy `durationBeats >= 0` (duration=0 contributes 0 score; USDX converts the note token to `F` Freestyle; Section 4.3 / 4.5).

### SongHeader
Required fields (mirrors Section 4.2 semantics):
- `songPath` (string) : canonical path/URI to the song root (directory containing the `.txt` and assets)
- `title` (string)
- `artist` (string)
- `bpmFile` (float) : file BPM from `#BPM` (before internal conversion)
- `gapMs` (float) : from `#GAP` (milliseconds; fractional ms allowed)
- `audio` (string) : resolved audio filename (from `#AUDIO` when `#VERSION >= 1.0.0` and present; otherwise from `#MP3`, USDX behavior)
Optional fields:
- `video` (string|null)
- `cover` (string|null)
- `background` (string|null)
- `p1Name` (string|null) : from `#P1` (duet)
- `p2Name` (string|null) : from `#P2` (duet)
- `version` (string) : from `#VERSION` if present; otherwise treated as `0.3.0` for legacy behavior (Section 4.3)
- `customTags` (CustomHeaderTag[]) : unknown/malformed tags preserved per Section 4.3 in encounter order (including tags without `:` where `tag=""`). If represented as a map/dictionary internally, it MUST preserve insertion order and MUST NOT discard duplicates.
`CustomHeaderTag`:
- `tag` (string) : tag name without leading `#` (empty string when the header line had no `:`)
- `content` (string) : remainder of the header line (decoded per Section 4.3 rules)
Note: implementations MAY maintain a convenience map/dictionary view, but it MUST preserve insertion order. Fixtures MUST compare `customTags` by ordered list semantics.

### SongTiming
Required fields:
- `bpmFile` (float) : file BPM from `#BPM` (before the `×4` internal conversion). This is the sole BPM value for the song — variable-BPM songs are rejected at parse time (Section 4.3).
Optional/derived fields:
- `startSec` (float|null) : from `#START` if present (seconds)
- `endMs` (int|null) : from `#END` if present (milliseconds)

### Track
Required fields:
- `trackIndex` (int) : `0` for P1 (or solo), `1` for P2
- `lines` (Line[]) : ordered in encounter order

### Line
A "line" corresponds to a sentence/phrase separated by `-` tokens in the body.
Required fields:
- `lineIndex` (int) : 0-based within track
- `notes` (NoteEvent[]) : ordered by `startBeatFile` then encounter order
Optional/derived fields:
- `startBeatFile` (int) : the `startBeatFile` of the first note in the line (if any)
- `endBeatFileExclusive` (int) : `max(note.startBeatFile + note.durationBeats)` over notes in the line
Invariants:
- Lines MAY be empty (e.g., consecutive `-`), but empty lines MUST NOT affect scoring.

### NoteEvent
Required fields:
- `noteType` (enum) : one of:
  - `Normal`  (token `:`)
  - `Golden`  (token `*`)
  - `Rap`     (token `R`)
  - `RapGolden` (token `G`)
  - `Freestyle` (token `F`)
- `startBeatFile` (int)
- `durationBeats` (int)
- `toneSemitone` (int) : semitone index in USDX scale (`C2 = 0`). This is the raw value from the `.txt` file, used directly as `TargetTone` in the §6.4 octave normalization loop.
- `lyric` (string) : as authored (may be empty)
Optional/derived fields:
- `endBeatFileExclusive` (int) : `startBeatFile + durationBeats`

# Appendix D: Fixture Types, Testing Policy, and Coverage Requirements
This appendix defines the fixture conventions, testing policy, and coverage requirements for this project.

## D.1 Testing Policy
**Approach**: Test-Driven Development (TDD). Tests for a feature MUST be written before or alongside the implementation, not after. No production code is merged without corresponding tests.
**Coverage targets (normative)**
- **Overall project coverage**: ≥ 80% line coverage.
- **Per-file minimum**: no file may fall below 60% line coverage, except:
  - Files with ≤ 30 lines of non-comment, non-blank code ("tiny files") are exempt from the per-file minimum.
  - Generated code files (e.g., protobuf stubs, schema-generated types) are exempt.
- Coverage is measured on the full test suite (unit + integration + acceptance); no partial-suite measurement satisfies the target.
- CI MUST fail the build if either the overall or any qualifying per-file threshold is not met.
**Test categories**
- **Unit tests**: test a single function or class in isolation; mock external dependencies (filesystem, network, clock).
- **Integration tests**: test interactions between two or more components (e.g., parser + scoring pipeline, protocol state machine + session manager).
- **Acceptance tests (fixture-driven)**: consume the fixture files described in D.2–D.5 and assert deterministic expected outputs. These are the primary regression guard for spec parity.

## D.2 Fixture Conventions
All fixtures live under `fixtures/` in the repository root. A machine-readable **manifest** at `fixtures/manifest.json` is the authoritative index.
**Manifest entry fields**
- `id`: stable fixture ID (e.g., `S01`, `F08`).
- `name`: short slug.
- `type`: fixture type (see D.3).
- `tags`: categories (`parser`, `timing`, `scoring`, `protocol`, `discovery`).
- `status`: `implemented` | `planned`.
- `covers`: list of spec section references (e.g., `["4.2", "5.3"]`).
- `paths`: file pointers relevant to the fixture type.
Test harnesses MUST discover fixtures via the manifest; hard-coding paths is not allowed.
**General rules**
- Fixtures MUST be deterministic. Dynamic values (timestamps, generated UUIDs, absolute paths) MUST NOT be asserted.
- Media files in fixtures MUST be stubs (empty or minimal valid files) unless the test requires real audio/video decoding.
- Fixtures MUST be small and self-contained.

## D.3 Fixture Types

### D.3.1 Parse-only fixture (`type: "parse"`)
Validates TXT parsing into the Parsed Song Model (Appendix C).
**Required files**
- `song.txt`: the song file under test.
- Any stub media files referenced by the header (`audio.ogg`, `audio.mp3`, etc.).
**Optional files**
- `expected.parsedSong.json`: expected `ParsedSong` output (structural schema in D.4). When present, the test MUST assert the parsed output matches this file field-by-field.
**Usage**: covers Section 4 (parsing rules, error codes, tag handling).

### D.3.2 Scoring fixture (`type: "scoring"`)
Validates the full pipeline: TXT parsing → timing/beat conversion → pitch frame evaluation → scoring output.
**Required files**
- `song.txt`: minimal chart.
- `pitchFrames.bin`: optional binary file containing a sequence of 16-byte `pitchFrame` datagrams (Section 8.3 / Appendix B.2.6). Each datagram is laid out exactly as specified in §8.3. `connectionId` MAY be set to 0 in fixture files unless routing logic is under test.
- `expected.score.json`: expected intermediate and final scoring values (see D.5).
**Usage**: covers Sections 5 (timing/beat conversion) and 6 (scoring normalization, line bonus, rounding). The worked examples in Appendix E are intended to be implemented as scoring fixtures.

### D.3.3 Discovery fixture (`type: "discovery"`)
Validates recursive song discovery and accept/reject validation across multiple songs.
**Required files**
- `songs_root/`: a directory tree with multiple song subdirectories, each containing a `song.txt` and any referenced stub media.
- `expected.discovery.json`: expected discovery result.
**`expected.discovery.json` schema (normative)**
```json
{
  "rootRel": "songs_root",
  "songs": [
    {
      "songDirRel": "a/valid_minimal",
      "songTxtRel": "a/valid_minimal/song.txt",
      "isValid": true,
      "invalidReasonCode": null,
      "invalidLineNumber": null
    }
  ]
}
```
Fields: `songDirRel` and `songTxtRel` are relative to `songs_root/`. `invalidReasonCode` and `invalidLineNumber` MUST be `null` when `isValid=true`.
**Usage**: covers Sections 3.2 and 4.3.

### D.3.4 Protocol/session fixture (`type: "protocol"`)
Validates control-message handling: pairing, assignment, reconnect, session state transitions.
**Required files**
- `transcript.jsonl`: one JSON object per line. Each object represents a message event:
  ```json
  { "direction": "phone_to_tv", "message": { "type": "hello", "clientId": "..." } }
  ```
  Valid `direction` values: `phone_to_tv`, `tv_to_phone`.
- `expected.session.json`: expected session state outcomes after replaying the transcript.
**Usage**: covers Sections 7 and 8.

## D.4 ParsedSong JSON Schema (structural)
When `expected.parsedSong.json` is present in a parse fixture, it MUST conform to the following structure (not a specific JSON-Schema draft; types are descriptive):
- `songId`: string
- `header`: object — `title` (string), `artist` (string), `bpmFile` (number), `gapMs` (number), `audio` (string), `video` (string|null), `cover` (string|null), `background` (string|null), `p1Name` (string|null), `p2Name` (string|null), `version` (string, optional), `customTags` (array of `{ tag:string, content:string }`, ordered)
- `timing`: object — `bpmFile` (number), `startSec` (number|null), `endMs` (integer|null)
- `tracks`: array of track objects (length 1 or 2):
  - `trackIndex` (int), `lines` (array of line objects):
    - `lineIndex` (int), `notes` (array of note objects):
      - `noteType` (string: `Normal|Golden|Rap|RapGolden|Freestyle`), `startBeatFile` (int), `durationBeats` (int), `toneSemitone` (int), `lyric` (string)
- `diagnostics`: array of `{ severity:string, code:string, message:string, lineNumber:int|null }`

## D.5 Expected Score JSON Schema
`expected.score.json` for scoring fixtures MUST include at minimum:
- `MaxSongPoints` (int)
- `MaxLineBonusPool` (int)
- `TrackScoreValue` (int or float)
- Per-note entries with `max_note_score`, `hits`, `N` (sample count), `note_score`
- Per-line entries with `LinePerfection`, `LineBonusAwarded`
- Final player fields: `Score` (float), `ScoreGolden` (float), `ScoreLine` (float), `ScoreInt` (int), `ScoreGoldenInt` (int), `ScoreLineInt` (int), `ScoreTotalInt` (int)
Fixtures MUST NOT assert unstable intermediate values that are not normatively defined by this spec.

# Appendix E: Worked Examples
This appendix provides worked numeric examples to remove ambiguity in:
- timing/beat conversion (Section 5)
- beat stepping and note-window boundaries (Sections 5.2, 6.1)
- scoring normalization, line bonus, and rounding (Sections 6.5–6.6)
These examples are intended to be copied into fixtures by providing:
- `song.txt` (minimal chart)
- optional `pitchFrames.jsonl` (MIDI-based detection stream)
- `expected.score.json` (authoritative intermediate values + expected totals)

## E.1 Static BPM — highlight cursor and note scoring windows

Given:
- `BPM_file = 120.0`
- `BPM_internal = BPM_file × 4 = 480.0`
- `beatsPerSec = BPM_internal / 60.0 = 8.0`
- `GAPms = 2000`
- `micDelayMs = 100`
- `songStartTvMs = 50000` (example TV monotonic value)
- `lyricsTimeSec = 5.0`

Highlight cursor (Section 5.1 — unchanged):
- `highlightTimeSec = lyricsTimeSec − (GAPms / 1000) = 5.0 − 2.0 = 3.0`
- `MidBeat_internal(highlight) = 3.0 × 8.0 = 24.0`
- `CurrentBeat = floor(24.0) = 24`

Note scoring window example (Section 5.1):

Consider a note with `startBeat = 20`, `durationBeats = 4`:
- `noteStartTvMs = 50000 + (20 × 15000 / 120) + 2000 + 100 = 50000 + 2500 + 2000 + 100 = 54600`
- `noteEndTvMs   = 50000 + (24 × 15000 / 120) + 2000 + 100 = 50000 + 3000 + 2000 + 100 = 55100`

All pitch frames with `54600 <= tvTimeMs < 55100` are collected for this note.
The note is finalized at TV clock `55100 + 450 = 55550` (Section 5.2.3).

## E.2 Beat-to-time and time-to-beat round-trip
Given:
- `BPM_file = 120.0`
- `BPM_internal = 480.0`
- `GAPms = 2000`
Convert beat 24 to `lyricsTimeSec` (Section 5.3):
- `chartSec = 24 * (60 / 480.0) = 24 * 0.125 = 3.0`
- `lyricsTimeSec = chartSec + GAPms/1000 = 3.0 + 2.0 = 5.0`
Round-trip: convert `lyricsTimeSec=5.0` back to internal beat (Section 5.3):
- `highlightTimeSec = 5.0 - 2.0 = 3.0`
- `MidBeat = 3.0 * (480.0 / 60.0) = 3.0 * 8.0 = 24.0`
- `CurrentBeat = floor(24.0) = 24` ✓

## E.3 Note-window boundary convention

If a note has:
- `startBeat = 11`
- `durationBeats = 2`
- `endBeat = startBeat + durationBeats = 13`

Then (Section 5.3 boundary convention):
- A pitch frame falls within this note's window if its corresponding beat position `b` satisfies `11 <= b < 13`.
- A frame at beat position `b = 13` belongs to the **next** note (end exclusive).

In TV time (given `songStartTvMs`, `BPM_file`, `GAPms`, `micDelayMs`):
- `noteStartTvMs = songStartTvMs + (11 × 15000 / BPM_file) + GAPms + micDelayMs`
- `noteEndTvMs   = songStartTvMs + (13 × 15000 / BPM_file) + GAPms + micDelayMs`
- Frame included if `noteStartTvMs <= frame.tvTimeMs < noteEndTvMs`.

## E.4 Scoring normalization and line bonus (fully-worked minimal song)

Assume:
- Line bonus: ON
- `MaxSongPoints = 9000`
- `MaxLineBonusPool = 1000`
- `BPM_file = 120.0`, `GAPms = 0`, `micDelayMs = 0`, `songStartTvMs = 10000`
- Pitch frame rate: 50 fps (one frame every 20 ms)

Create a minimal SOLO track (trackIndex=0) with two non-empty lines:

Line 1:
- `: 0 4 0 la`  (Normal, startBeat=0, duration=4, tone=0)
- `- 4`

Line 2:
- `* 4 4 0 la`  (Golden, startBeat=4, duration=4, tone=0)
- `- 8`
- `E`

Where (Section 6.2.1):
- Normal (`:`) has `ScoreFactor = 1`
- Golden (`*`) has `ScoreFactor = 2`

**Compute `TrackScoreValue` (Section 6.5):**
- Line1 ScoreValue = `4 × 1 = 4`
- Line2 ScoreValue = `4 × 2 = 8`
- `TrackScoreValue = 4 + 8 = 12`

**Note scoring windows (Section 5.1):**

Note 1 (Normal, beats 0–4):
- `noteStartTvMs = 10000 + (0 × 15000 / 120) + 0 + 0 = 10000`
- `noteEndTvMs   = 10000 + (4 × 15000 / 120) + 0 + 0 = 10000 + 500 = 10500`
- Window duration: 500 ms → at 50 fps, expect ~25 frames

Note 2 (Golden, beats 4–8):
- `noteStartTvMs = 10000 + (4 × 15000 / 120) = 10500`
- `noteEndTvMs   = 10000 + (8 × 15000 / 120) = 11000`
- Window duration: 500 ms → at 50 fps, expect ~25 frames

**Per-note max scores (Section 6.1):**
- Note 1 (Normal): `max_note_score = (9000 / 12) × 1 × 4 = 3000`
- Note 2 (Golden): `max_note_score = (9000 / 12) × 2 × 4 = 6000`
- Sum = 9000 ✓

**Perfect performance** (all frames have `toneValid=true` and pitch matching tone 0):

Note 1: N=25 frames, hits=25 → `note_score = 3000 × (25/25) = 3000` → added to `Player.Score`
Note 2: N=25 frames, hits=25 → `note_score = 6000 × (25/25) = 6000` → added to `Player.ScoreGolden`

Note totals: `Player.Score = 3000`, `Player.ScoreGolden = 6000`, sum = 9000

**Partial performance example** (Note 1: 20 of 25 hit; Note 2: 15 of 25 hit):

Note 1: `note_score = 3000 × (20/25) = 2400` → `Player.Score = 2400`
Note 2: `note_score = 6000 × (15/25) = 3600` → `Player.ScoreGolden = 3600`

Note totals: sum = 6000

**Line bonus (Section 6.5) — perfect performance case:**

- `NonEmptyLines = 2`
- `LineBonusPerLine = MaxLineBonusPool / NonEmptyLines = 1000 / 2 = 500`

Line 1 (at sentence completion):
- `MaxLineScore = MaxSongPoints × (Line1ScoreValue / TrackScoreValue) = 9000 × (4/12) = 3000`
- `LineScore = (Player.Score + Player.ScoreGolden) − Player.ScoreLast = 3000 − 0 = 3000`
- `LinePerfection = clamp(3000 / (3000 − 2), 0, 1) = clamp(3000 / 2998, 0, 1) = 1`
- `Player.ScoreLine += 500 × 1 = 500`

Line 2 (at sentence completion):
- `MaxLineScore = 9000 × (8/12) = 6000`
- `LineScore = (3000 + 6000) − 3000 = 6000`
- `LinePerfection = clamp(6000 / (6000 − 2), 0, 1) = clamp(6000 / 5998, 0, 1) = 1`
- `Player.ScoreLine += 500 × 1 = 500`

`Player.ScoreLine = 1000`

**Rounding (Section 6.6):**
- `Player.ScoreLineInt = floor(round(1000) / 10) × 10 = 1000`
- `ScoreInt = round(3000 / 10) × 10 = 3000`
- Since `ScoreInt < Player.Score` is FALSE, `ScoreGoldenInt = floor(6000 / 10) × 10 = 6000`
- `ScoreTotalInt = 3000 + 6000 + 1000 = 10000`

**Line bonus — partial performance case:**

Line 1:
- `LineScore = 2400 − 0 = 2400`
- `LinePerfection = clamp(2400 / 2998, 0, 1) = 0.8005...`
- `Player.ScoreLine += 500 × 0.8005 = 400.26...`

Line 2:
- `LineScore = (2400 + 3600) − 2400 = 3600`
- `LinePerfection = clamp(3600 / 5998, 0, 1) = 0.6002...`
- `Player.ScoreLine += 500 × 0.6002 = 300.10...`

`Player.ScoreLine = 700.36...`

## E.5 Golden rounding direction rule (fractional demonstration)
This example exists only to demonstrate the “golden rounds opposite” rule (Section 6.6).
Assume after accumulation:
- `Player.Score = 4090.909...`
- `Player.ScoreGolden = 100.909...`
Compute:
- `ScoreInt = round(4090.909/10)*10 = 4090`
- Since `ScoreInt < Player.Score` is TRUE, apply opposite rounding:
  - `ScoreGoldenInt = ceil(100.909/10)*10 = 110`

## E.6 Minimal fixture files for E.4 (reference layout)

Fixture directory example: `E4_score_linebonus_perfect/`
- `song.txt` contains the exact 2-line chart from E.4.
- `expected.score.json` contains at least:
  - `MaxSongPoints`, `MaxLineBonusPool`
  - `TrackScoreValue`
  - per-note `max_note_score`, `hits`, `N`, `note_score` values
  - `Score`, `ScoreGolden`, `ScoreLine`, and the tens-rounded ints
  - `ScoreTotalInt`
`pitchFrames.jsonl` is OPTIONAL for E.4 if the harness can inject per-note hit counts directly. If the fixture uses the full scoring pipeline, provide `pitchFrames.jsonl` with frames at 50 fps covering each note's time window, with `toneValid=true` and `midiNote` matching the target tone for hit frames, or `toneValid=false` / mismatched `midiNote` for miss frames.
