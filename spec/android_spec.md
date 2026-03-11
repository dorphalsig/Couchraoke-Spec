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

## 3.1 Storage Access
Each phone app has a single configured songs folder — a directory on the phone's local storage that contains all song subdirectories. The user sets this folder once in the phone app settings. The phone scans this folder recursively for `.txt` files and makes them available to the TV.
### 3.1.1 Scan implementation
#### 3.1.1.1 Android (SAF — Kotlin):*
The songs folder is selected via `ActivityResultContracts.OpenDocumentTree()` and represented as a persisted SAF tree URI (`content://...`). `java.io.File` cannot traverse SAF URIs. Recursive listing MUST use `DocumentFile.fromTreeUri(context, uri).listFiles()` directly (the `DocumentFile` API is part of `androidx.documentfile:documentfile`, already a transitive dependency of `androidx.core`). Recursion depth is bounded by the songs folder structure; no artificial depth limit is required.
For each `.txt` file found: read its content via `contentResolver.openInputStream(uri)`, parse the header tags, resolve asset filenames to their SAF URIs via `DocumentFile.findFile(name)`, check file availability via `DocumentFile.exists()`, and build `coverUrl`/`audioUrl`/etc. from the HTTP server's URL scheme (Section 8.6).
### 3.1.2 Song file delivery
The phone runs a lightweight read-only HTTP server for the duration of its session connection (see Section 8.6). Song files are served directly from the phone's songs folder via HTTP. The TV fetches files on demand using URLs provided in `songListUpdate`. No ZIP building, no extraction, and no temporary storage on the TV are required.

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

## 5.2 Pitch Frame Timing, Jitter, and Mic Delay

This section defines how phone pitch frames are mapped into the TV time domain, how the TV selects frames for scoring, and how microphone delay is applied.

### 5.2.1 Pitch frame rate and missing frames

- Phone pitch frames MUST be sent at the rate requested by `assignSinger.expectedPitchFps`. The **default is 50 fps** (20ms interval).
  - Phones that support 100 fps MAY advertise `"pitchFps":100` in `hello.capabilities`. The TV MAY then set `expectedPitchFps=100` in `assignSinger` for those phones.
  - If a phone cannot sustain the requested rate, it SHOULD reduce to 50 fps and the TV MUST tolerate the difference.
- Missing or invalid frames MUST be treated as `toneValid=false` (no scoring; rap also requires `toneValid=true`).

### 5.2.5 Mic Capture and FFT-YIN Pitch Detection Pipeline
This section defines the normative implementation for the on-device pitch detector. Both Android and iOS companion apps MUST implement a custom Fast YIN (FFT-YIN) pipeline.
To ensure low latency and eliminate Garbage Collection (GC) pauses during gameplay, the implementation MUST use primitive arrays exclusively and strictly prohibit object allocation within the audio processing loop.

#### 5.2.5.1 Primitive Memory Management (Normative)
The following buffers MUST be pre-allocated once during initialization and reused for every frame:
- `audioBuffer`: 1024 floats (for the raw PCM input)
- `paddedBuffer`: 2048 floats (for zero-padded FFT input)
- `fftComplexBuffer`: 4096 floats (for in-place FFT interleaved real/imaginary parts, or split-complex equivalent on iOS)
- `diffBuffer`: 1024 floats (for the d_t difference function)
- `normBuffer`: 1024 floats (for the d' normalized function)
- `medianHistory`: 3-byte circular buffer (for temporal smoothing)

#### 5.2.5.2 Algorithm Pipeline (Normative)
The audio capture window is 1024 samples at 44100 Hz (~23 ms). For each window, the phone MUST execute the following pipeline synchronously:
**Step 1: Voicing Gate (maxAmp)**
Compute the peak amplitude of the window using a primitive loop:
`maxAmp = max(abs(audioBuffer[i]))` for i in 0..1023.
If `maxAmp < thresholdTable[thresholdIndex].maxAmpCutoff`, the frame is considered unvoiced. The pipeline MUST immediately set `rawMidiNote = 255`, skip Steps 2-4 to conserve battery, and proceed to Step 5.
**Step 2: Linear Autocorrelation via FFT**
To avoid circular correlation artifacts, the signal MUST be zero-padded.
1. Copy `audioBuffer` into the first half of `paddedBuffer`. Fill the second half with 0.0f.
2. Compute the forward FFT of `paddedBuffer` in-place.
3. Compute the Power Spectrum in-place: multiply each complex number by its conjugate (Real^2 + Imaginary^2), zeroing out the imaginary component.
4. Compute the inverse FFT in-place. The first 1024 real elements represent the linear autocorrelation `r_t(tau)`.
**Step 3: Squared Difference (d_t) and Normalization (d')**
1. Compute `d_t(tau) = E_start + E_shift(tau) - 2 * r_t(tau)`, where `E_start` and `E_shift` are the window energy and shifted window energy, respectively.
2. Compute the Cumulative Mean Normalized Difference `d'(tau)`:
   - `d'(0) = 1.0`
   - For `tau > 0`: `d'(tau) = d_t(tau) / ((1 / tau) * sum(d_t(1..tau)))`
**Step 4: Candidate Selection**
Iterate through `d'(tau)` to find local minima. Select the **first** local minimum where `d'(tau) < thresholdTable[thresholdIndex].dPrimeCutoff`. 
- If no local minimum meets the cutoff, select the absolute minimum.
- If the selected `d'(tau) > 0.40` (the hard limit for human vocal periodicity), the frame is unvoiced; set `rawMidiNote = 255`.
- Otherwise, compute frequency: `hz = 44100.0 / tau`.
- Compute MIDI note: `rawMidiNote = clamp(round(69 + 12 * log2(hz / 440.0)), 0, 127)`.
**Step 5: Temporal Smoothing**
To prevent erratic octave jumping in noisy environments, the phone MUST maintain a 3-frame rolling median filter. 
- Push `rawMidiNote` into the `medianHistory` buffer.
- The `midiNote` transmitted in the 16-byte UDP `pitchFrame` MUST be the median of these 3 values. 
- If any of the 3 frames in the history buffer are unvoiced (255), the transmitted `midiNote` MUST be 255 (silence interrupts the combo immediately).

#### 5.2.5.3 Consolidated Sensitivity Table
The `thresholdIndex` (0–7) from `assignSinger` determines both the volume required to open the noise gate (`maxAmpCutoff`) and the strictness of the pitch detection (`dPrimeCutoff`). 
| Index | maxAmpCutoff | dPrimeCutoff | Environment Profile |
|---|---|---|---|
| 0 | 0.01 | 0.10 | Very High Sensitivity (Whisper/Studio) |
| 1 | 0.02 | 0.15 | High Sensitivity |
| 2 | 0.04 | 0.20 | Medium-High |
| 3 | 0.06 | 0.25 | **Medium (Default Karaoke Room)** |
| 4 | 0.09 | 0.30 | Medium-Low (Noisy Room) |
| 5 | 0.13 | 0.35 | Low |
| 6 | 0.18 | 0.40 | Very Low (Loud Party) |
| 7 | 0.25 | 0.45 | Lowest (Extreme Noise) |
---

# 7. Multiplayer, Pairing, and Session Lifecycle

## 7.3 Pairing UX (Phone)
- Phone joins by scanning the TV QR code or entering the join code.
**Phone screen states**
The phone app has three primary screen states:
1. **Join screen**: shown when not connected to any session.
2. **Waiting/Connected screen**: shown when connected as Spectator, or after song end.
3. **Active Mic screen**: shown when assigned as Singer, both during countdown and during singing.
**Waiting/Connected screen**
- Connection state (Connecting / Connected / Reconnecting / Disconnected)
- Current assigned role (Singer / Spectator); if Singer, show playerId (P1/P2)
- Live input level meter (VU meter, always active for audio monitoring)
- Mute toggle: when enabled, the phone MUST continue to stay connected but MUST stream frames as unvoiced (equivalent to `toneValid=false` and `midiNote=255`) so the TV scores silence.
- Leave session action (see below)
**Active Mic screen (during countdown and singing)**
- Shown immediately when the phone receives `assignSinger`. The phone MUST trigger a short haptic vibration (~200ms) on receiving `assignSinger` to alert the player.
- Role badge: Singer P1 / Singer P2
- Large countdown number during countdown phase (mirrors TV countdown; derived from `countdownMs`)
- Live VU meter (real-time input level from active mic capture)
- Mute toggle
- Mic warms up locally during countdown but no frames are sent until countdown completes (`startMode="countdown"`)
- When `tvNowMs >= endTimeTvMs`, the phone transitions back to the Waiting/Connected screen automatically
**Post-song state**
- After song end, the phone returns to the Waiting/Connected screen. Role label still shows the last assigned role until a new `assignSinger` or session change. No score is displayed on the phone; results are TV-only.
**Song Library management from phone (normative)**
- Song folder management is accessed via the phone app **Settings screen** (see below). There is no separate Song Library menu item.
- When the TV requests a song list (via `requestSongList`), the phone MUST scan its configured songs folder, build the metadata list, and reply with a `songListUpdate` message (see Section 8.2).
- The TV sends `requestSongList` to all connected phones on connection and whenever the library needs refreshing (e.g., when the TV screen is focused after being away).
- The phone's songs folder SHOULD default to a well-known location (e.g., `Downloads/Songs/` or `Music/KaraokeApp/`) to minimize initial setup friction.
- **Cloud/remote storage**: songs stored in cloud-synced folders (e.g., Google Drive Offline, iCloud Drive) are supported, but require platform-level file access APIs — they are NOT transparently accessible as regular filesystem paths. See §8.6 for the normative SAF (Android) and NSFileCoordinator (iOS) access model and cloud-evicted file handling. Users must ensure songs are downloaded locally before starting a session.
- **Songs folder picker**: on Android, opening the folder picker uses `ActivityResultContracts.OpenDocumentTree()`. On iOS, it uses `UIDocumentPickerViewController(forOpeningContentTypes: [.folder])`. Both platforms persist the selection for future scans (SAF persistent permission on Android; security-scoped bookmark on iOS).
**Wireframes (phone app, spec-only interactions)**
```text
Join screen
+----------------------------------+
| JOIN SESSION                      |
+----------------------------------+
| [Scan QR]                         |
| or enter code: [ ABCD-EFGH ] [Join]|
|                                  |
| Status: Disconnected              |
| [Settings]                        |
+----------------------------------+
Waiting/Connected (Spectator)
+----------------------------------+
| CONNECTED                         |
+----------------------------------+
| Role: Spectator                   |
| Input level:  |||||||             |
| Mute: [OFF]                       |
|                                  |
| [Settings]   [Leave session]      |
+----------------------------------+
Active Mic (during countdown — 3 seconds shown)
+----------------------------------+
| SINGER P1                         |
+----------------------------------+
|                                  |
|              3                    |
|                                  |
| Input level:  |||||||||           |
| Mute: [OFF]                       |
+----------------------------------+
Active Mic (during singing)
+----------------------------------+
| SINGER P1                         |
+----------------------------------+
| Input level:  |||||||||           |
| Mute: [OFF]                       |
+----------------------------------+
```
**Active Mic exit policy (normative):** The Active Mic screen MUST NOT display a Leave session or Back action during an active song. The hardware Back key MUST be suppressed (do nothing) during Active Mic. Users wishing to exit must use the device's OS navigation to background the app. This is expected MVP behaviour — session control is TV-side only.
**Phone app settings (normative)**
The phone app has a Settings screen accessible from the Join screen and from the Waiting/Connected screen. Settings MUST include:
- **Songs folder**: displays the currently configured songs folder path; pressing OK opens the platform folder picker (`ActivityResultContracts.OpenDocumentTree()` on Android, `UIDocumentPickerViewController` on iOS) to change it. On selection, the phone immediately triggers a rescan and sends `songListUpdate` to the TV if connected.
- **Rescan now**: manually triggers a rescan of the current songs folder. If connected to a TV session, the phone sends `songListUpdate` on completion.
- **Song count**: read-only display of the number of valid songs found in the last scan.
**Phone wireframe (Settings — unpaired or connected)**
```text
+----------------------------------+
| SETTINGS                          |
+----------------------------------+
| Songs folder:                     |
|   /storage/Downloads/Songs        |
|   [Change folder]                 |
|                                   |
| Song count:  423 valid / 2 invalid|
| [Rescan now]                      |
+----------------------------------+
```
**Scan QR UX (normative)**
- Tapping **Scan QR** MUST open the camera-based QR scanner.
- If camera permission is not granted, the phone MUST request it.
- If camera permission is denied (including "Don't ask again"), the phone MUST:
 - Return to the Join screen.
 - Show a blocking error modal (see below).
**Join resolution (normative)**
- The QR payload encodes the full WebSocket endpoint URL as specified in Section 8.1, including the `token` query parameter.
- On successful QR scan, the phone connects directly to that endpoint.
- After a successful QR scan, the phone SHOULD additionally start LAN discovery (NSD/mDNS) to confirm the user is on the correct LAN and display a friendly session name if discovered.
- When the user enters the join code manually, the phone MUST use mDNS to locate the matching TV session per the normative resolution algorithm in Section 8.1: browse `_karaoke._tcp`, filter discovered services by the `code` TXT field matching the normalized typed input, connect to the matching service's host/port with the join code as the session token. If no match is found within 5 seconds, show: `TV not found. Make sure your phone is on the same Wi-Fi network.`
- If two TVs on the LAN advertise the same join code (extremely unlikely), the phone MUST prompt the user to select by instance name (Section 8.1).
**Wireframe (phone select TV session; used when multiple sessions are discovered)**
```text
+----------------------------------+
| SELECT TV SESSION                 |
+----------------------------------+
|  > Living Room TV                 |
|    Bedroom TV                     |
|                                  |
| [Back]                            |
+----------------------------------+
```
**LAN discovery permission UX (normative)**
- **Android**: if LAN discovery (NSD/mDNS) is used, the phone MUST request the required Android runtime permission(s). If denied (including "Don't ask again"), the phone MUST return to the Join screen and show the blocking error modal below, instructing the user to open Android Settings → Apps → (this app) → Permissions.
- **iOS**: local network access is gated by the system-level `NSLocalNetworkUsageDescription` prompt (iOS 14+), which is shown automatically on the first connection attempt. If the user denies it, the phone MUST return to the Join screen and show the blocking error modal below, instructing the user to open iOS Settings → Privacy → Local Network → (this app) and enable access.
**Wireframe (phone permission denied; shared modal)**
```text
+----------------------------------+
| ERROR                             |
+----------------------------------+
| Permission required.              |
|                                  |
| Enable:                           |
|  - Camera (to scan QR)            |
|  - Local Network access           |
|    (to discover the TV on LAN)    |
|                                  |
| Android: Settings -> Apps ->      |
| (this app) -> Permissions         |
|                                  |
| iOS: Settings -> Privacy ->       |
| Local Network -> (this app)       |
|                                  |
| [OK]                              |
+----------------------------------+
```
**Leave session UX (normative)**
- Tapping **Leave session** MUST:
 - Close the network connection to the TV host (WebSocket).
 - Return the phone UI to the Join screen.
 - Clear any cached session endpoint so the user MUST rejoin explicitly (Scan QR or enter code).
- After leaving, automatic reconnect MUST NOT occur in MVP.
- Rejoining the same session is done via the Join screen (Scan QR or enter code). The phone SHOULD reuse the same `clientId` so the TV can reclaim identity/assignment per Section 7.4.
**Join rejection UX (normative)**
- If the TV rejects a join with an `error`, the phone MUST show a blocking error message and return to the Join screen.
- Minimum user action is `OK` (dismiss) or Back.
**Wireframes (phone join rejected; spec-only interactions)**
```text
Session locked
+----------------------------------+
| ERROR                             |
+----------------------------------+
| Session is locked.                |
| (A song is in progress.)          |
|                                  |
| [OK]                              |
+----------------------------------+
Session full
+----------------------------------+
| ERROR                             |
+----------------------------------+
| Session is full.                  |
|                                  |
| [OK]                              |
+----------------------------------+
Protocol mismatch
+----------------------------------+
| ERROR                             |
+----------------------------------+
| Protocol mismatch.                |
|                                  |
| [OK]                              |
+----------------------------------+
```

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

### 8.2.2 Service Discovery — Phone (Android & iOS)

When the user enters a join code manually:

1. Phone normalizes input: strip spaces/hyphens, uppercase.
2. Phone performs mDNS browse for `_karaoke._tcp`.
3. For each discovered service, the phone resolves TXT records and compares the `code` field against the normalized input.
4. If exactly one match: connect directly to that service's host/port with the token.
5. If multiple matches (two TVs with the same code — extremely unlikely): prompt the user to select by instance name.
6. If no match after 5 seconds: show `TV not found. Make sure your phone is on the same Wi-Fi network.`

**Android phone — multicast lock**
The phone app MUST acquire a `WifiManager.MulticastLock` (tag: `"karaoke_multicast"`) when performing mDNS browsing and release it when discovery completes. See §8.7.5 for the required `CHANGE_WIFI_MULTICAST_STATE` permission declaration.

**iOS phone — multicast lock**
The iOS phone app does not require an explicit multicast lock. The OS handles multicast internally; no additional permission or lock is required for mDNS browsing via `Network.framework` (`NWBrowser`).

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

### 8.5.2 connectionId Usage — Phone

- The phone MUST include its assigned `connectionId` in every `pitchFrame` datagram (bytes 14–15; see §8.6.1).

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

### 8.6.2 Frame Generation & Transmission (Phone — Android & iOS)

**Normative rule:** Phones MUST NOT send any computed scoring, judgement, combo, or rating values. Phones send only DSP-derived observations. The TV is the single source of truth for timeline alignment, note matching, and scoring.

**Rate:**
- Default **50 fps** (one frame every 20 ms).
- Phones capable of 100 fps MAY advertise `"pitchFps": 100` in `capabilities` and send at 100 fps if the TV requests it via `expectedPitchFps` in `assignSinger`.
- Frames MUST NOT be batched.

**Phone-side pitch derivation (non-normative):** Implementation-defined. The protocol carries only `midiNote` and the implicit `toneValid`.

**Voicing / noise thresholding (normative):**

The TV selects a noise gate threshold via `thresholdIndex` (0..7) and delivers it to the phone in `assignSinger`. The phone applies it locally before deciding whether a frame is voiced.

`maxAmp` definition (normative): normalized peak amplitude of the audio window that produced the pitch estimate for this frame.
- 16-bit signed PCM input: `maxAmp = clamp(max(abs(sample_i)) / 32768.0, 0, 1)`
- Float PCM input in [−1..1]: `maxAmp = clamp(max(abs(sample_i)), 0, 1)`

Threshold table:
```
thresholdValueByIndex = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.60]
```

Decision rule:
```
toneValid = (maxAmp >= thresholdValueByIndex[thresholdIndex]) AND (pitch_estimate_succeeded)
```

When `toneValid = false`, the phone MUST set `midiNote = 255`.

**Frame drop rules (normative):**
- Do not send frames with decreasing `seq`.
- When `startMode == "countdown"`: do not send frames until the countdown completes. The phone MAY warm up pitch detection locally during this period.

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

### 8.7.2 HTTP File Server — Android Phone

**Library**

| Library | Pinned Version | Justification |
|---|---|---|
| `io.ktor:ktor-server-cio` + `io.ktor:ktor-server-partial-content` | `2.3.12` | CIO engine; `ktor-server-partial-content` handles `Accept-Ranges` / `206 Partial Content` automatically. |

**Server lifecycle (normative):**
- The HTTP server MUST start before the phone sends `hello` to the TV, so `httpPort` is valid when `hello` is sent.
- The server MUST remain running for the duration of the session connection.
- Default port: `34781`. If unavailable, the phone MUST bind to any available ephemeral port and report the actual port in `hello.httpPort`.

**Storage access and SAF reads (normative):**

The HTTP server maintains an **internal URI map** (`relativePath → platformURI`) built at scan time. When a request arrives, the handler looks up the `relativePath` in this map and opens the file via the Android ContentResolver — `java.io.File(path)` MUST NOT be used on Android 10+ scoped storage.

- File reads: `contentResolver.openAssetFileDescriptor(uri, "r")`. File size: `contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), ...)`.
- Range reads: open the `AssetFileDescriptor`, obtain a `FileInputStream`, skip to `offset`, read `length` bytes. If the underlying provider does not support `seek`, skip by sequential read.
- **Cloud file availability**: if `contentResolver.query()` returns null or `SIZE = 0`, treat the file as absent and return `null` for the corresponding URL in `SongEntry`. The handler MUST NOT trigger cloud downloads from within the HTTP request handler.
- Ktor's `ktor-server-partial-content` plugin handles `Accept-Ranges` / `206 Partial Content` automatically when the response body is a `ByteReadChannel`. Provide the channel from the `AssetFileDescriptor` input stream and set `Content-Length` from the queried file size.

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

### 8.8.3 Per-Sample Computation — Phone

Computed by the phone after receiving `clockAck`:

Let:
- `t1 = tTvSendMs` (from `ping`, echoed in `pong`)
- `t2 = tPhoneRecvMs` (phone's own record)
- `t3 = tPhoneSendMs` (phone's own record)
- `t4 = tTvRecvMs` (from `clockAck`)

Round-trip time (subtracting phone processing time):
```
RTT = (t4 - t1) - (t3 - t2)
```

Clock offset (TV time minus phone time):
```
clockOffsetMs = ((t2 - t1) + (t3 - t4)) / 2
```

**Sample selection and smoothing (normative):**
- Keep the last 5 samples.
- Discard samples with `RTT < 0` or `RTT > 2000`.
- Choose the sample with the smallest `RTT` as the active `clockOffsetMs` (best-of-N reduces Wi-Fi jitter).

The TV does NOT need to compute `clockOffsetMs`; it uses `tvTimeMs` from each binary pitch frame directly.

Pitch-frame time mapping, jitter buffer behavior, scoring sample selection, and mic delay application are defined in §5.2.

# Appendix A: Library Dependency Reference
This appendix is **normative**. Implementations MUST use the pinned libraries below for the designated concerns. Using alternative libraries for these concerns is not permitted without a spec revision, because the choice of library directly affects wire compatibility, audio behavior, or performance on the target hardware.

## A.2 Android Companion App (Kotlin)
| Concern | Library | Pinned Version | Justification |
|---|---|---|---|
| WebSocket client | `com.squareup.okhttp3:okhttp` | `4.12.0` | Same OkHttp already used by TV host (transitive via ExoPlayer). `WebSocket` API built-in. No additional dependency. |
| QR code scanning | `com.google.mlkit:barcode-scanning` + `androidx.camera:camera-camera2` + `androidx.camera:camera-lifecycle` + `androidx.camera:camera-view` | `barcode-scanning: 17.3.0`, `camera-*: 1.3.4` | ML Kit barcode scanning on CameraX. GPU-accelerated on all target hardware. |
| LAN discovery (NSD/mDNS) | `android.net.nsd.NsdManager` (platform API) | n/a — SDK built-in (API 16+) | No third-party dependency required. Browse `_karaoke._tcp` using `NsdManager.discoverServices`. |
| HTTP file server | `io.ktor:ktor-server-cio` + `io.ktor:ktor-server-partial-content` | `2.3.12` | Same Ktor version as TV host. `ktor-server-partial-content` handles `Accept-Ranges` / `206 Partial Content` automatically. |
| SAF directory listing | `androidx.documentfile:documentfile` | `1.0.1` | Transitive dependency of `androidx.core`. `DocumentFile.fromTreeUri()` for SAF tree traversal. No additional library needed. |
| FFT Operations | `com.github.wendykierp:JTransforms`| 3.2 | Fast, GC-free primitive float array FFT implementations for Java/Kotlin.|
| Haptic feedback (200ms on assignSinger) | `android.os.VibrationEffect` (platform API) | n/a — SDK built-in (API 26+) | `VibrationEffect.createOneShot(200, DEFAULT_AMPLITUDE)`. No third-party library. |
| Settings persistence | `androidx.datastore:datastore-preferences` | `1.1.1` | Same as TV host. |

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
