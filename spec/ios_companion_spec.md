# Couchraoke iOS Companion Specification
Version 4.20 (iOS Companion)
Status: Draft

## Table of Contents
1. Introduction & Product Contract
  1.1 Locked Product Decisions (Legacy §1.1)
  1.2 Definition of Done (Legacy §1.2)
2. Architecture & Connection Model
  2.1 Components (Legacy §2.1)
  2.2 Data Responsibilities (Legacy §2.2)
3. Song Storage & Discovery
  3.1 Storage Access (Legacy §3.1)
    3.1.1 Scan implementation (Legacy §3.1.1)
      3.1.1.1 iOS (NSFileCoordinator — Swift)
    3.1.2 Song file delivery (Legacy §3.1.2)
    3.1.3 Phone-side state (Legacy §3.1.3)
  3.2 Discovery and Validation Rules (Legacy §3.2)
    3.2.1 Phone-side discovery (Legacy §3.2.1)
    3.2.2 Validation (song acceptance) (Legacy §3.2.2)
    3.2.3 Missing files (Legacy §3.2.3)
    3.2.4 MVP parity requirements (Legacy §3.2.4)
4. Parsing Rules & Validation (Legacy §4)
  4.1 Supported Note Tokens (Legacy §4.1)
  4.2 Supported Header Tags and Semantics (Legacy §4.2)
  4.3 Error Handling (Legacy §4.3)
  4.4 Header Tags Reference (Legacy §4.4)
  4.5 Body Token Reference (Legacy §4.5)
5. DSP Pipeline & Pitch Streaming (Legacy §5.2.5)
  5.1 Primitive Memory Management (Normative)
  5.2 Algorithm Pipeline (Normative)
  5.3 Consolidated Sensitivity Table (Normative)
6. Session Lifecycle & Pairing UX (Legacy §7)
  6.1 Phone Pairing UX (Legacy §7.3)
  6.2 Phone App Settings (Normative)
  6.3 Scan QR UX (Normative)
  6.4 Join Resolution (Normative)
  6.5 Leave Session UX (Normative)
  6.6 Disconnect/Reconnect (Legacy §7.4)
7. Network Protocol & HTTP Server (Legacy §8)
  7.1 Transport (Legacy §8.1)
  7.2 Control Messages (Legacy §8.2)
  7.3 Pitch Stream Messages (Legacy §8.3)
  7.4 Song File HTTP Server (Legacy §8.6)
8. Appendices
  A.1 iOS Companion App (Swift) Dependencies
  A.2 Prohibited Patterns

## 1. Introduction & Product Contract (Legacy §1)
- Goal: USDX-like karaoke gameplay (parity for parsing, timing, duet, rap, scoring, results).
- Platforms: Android TV host app (Kotlin) + iOS companion app (Swift) acting as mic client / song source alongside Android (see separate spec).
- Connectivity: same-subnet Wi-Fi only; offline operation.
- Players: 2.
- Out of scope: online song store, party modes other than Medley, editors, esports-grade calibration.

### 1.1 Locked Product Decisions (Legacy §1.1)
- Default per-player difficulty: **Medium** (communicated by TV via `assignSinger`).
- Line bonus: ON (TV scoring). Phones surface difficulty but do not calculate scores.
- Duet: YES; swap duet parts: YES (phones obey `assignSinger.playerIndex`).
- Rap: YES (presence-based); Freestyle: no scoring.
- Video backgrounds: YES (TV-only; phone does not render video).
- Instrumental (full-song) via `#INSTRUMENTAL`: YES. Phone must expose instrumental availability via `songListUpdate.instrumentalUrl` and include `hasInstrumental` flag in discovery metadata.
- **#INSTRUMENTAL / #VOCALS handling (normative for phone metadata):** When `#INSTRUMENTAL` is present and the referenced file exists under the songs folder, the iOS app MUST resolve its file URL (see §3.1.1.1) and expose it through the HTTP server + metadata payload. `#VOCALS` is emitted only if both the tag exists and file exists. Missing files are logged (see §4.3) and omitted from URLs.
- **Instrumental gap indicator data:** The phone does not render UI but MUST set `hasInstrumental` accurately so the TV can render the gap indicator semantics.
- Songs stored on connected phones in a single songs folder per phone; TV aggregates library from all connected phones. The iOS phone runs a lightweight read-only HTTP server for the duration of the session; the TV fetches song files directly over HTTP on demand (Section 7). No temporary storage or background syncing on the TV is required.

### 1.2 Definition of Done (Legacy §1.2)
Parity MVP PASS requires all parity-critical behaviors in this spec to be met, plus reliable pairing, discovery, HTTP serving, and pitch streaming on typical home Wi-Fi.

## 2. Architecture & Connection Model (Legacy §2)

### 2.1 Components (Legacy §2.1)
**Tests:** F18, F15

- **iOS Companion App**: song storage (single songs folder on the phone), song metadata scanning, lightweight read-only HTTP file server for song asset delivery, mic capture + FFT-YIN DSP (pitch), toneValid thresholding, pitch frame streaming, connection UX.
- **TV Host App** (reference only): aggregates libraries from phones, parses charts, handles audio/video playback, timing, scoring, UI, and session authority.

### 2.2 Data Responsibilities (Legacy §2.2)
**Tests:** F18, F15

**Songs live on the phones.** The iOS companion owns access to its configured songs folder. The TV does not store or own song files. When the phone connects, it waits for `requestSongList`, scans its folder, and returns metadata. The TV aggregates the library across all phones.

When a song is needed, the iOS app's HTTP server streams files directly from file URLs (see Section 7). The phone MUST provide stable URLs per connection and keep the HTTP server running until disconnect.

Authority split:
- Phone: song file storage, metadata scanning, diagnostic logging, HTTP file serving, mic capture, pitch extraction, tone validity flags, network transport of frames.
- TV: song timeline, beats, scoring, rendering, session state, user flows.

**Consequence**: If the iOS phone disconnects, all songs it provided disappear from the TV library until it reconnects and re-advertises them. The iOS app MUST tear down its HTTP server on disconnect to release file coordinator resources.

## 3. Song Storage & Discovery (Legacy §3)

### 3.1 Storage Access (Legacy §3.1)
**Tests:** F01, F02

Each phone app has a single configured songs folder — a directory on device storage that contains all song subdirectories. The user sets this folder once in the iOS app settings. The phone scans this folder recursively for `.txt` files and makes them available to the TV.

#### 3.1.1 Scan implementation (Legacy §3.1.1)
Scanning requires platform-specific file enumeration.

##### 3.1.1.1 iOS (NSFileCoordinator — Swift)
The songs folder is selected via `UIDocumentPickerViewController(forOpeningContentTypes: [.folder])` and represented as a security-scoped bookmark (`Data`). `FileManager` alone cannot access files outside the app sandbox without user-granted permissions. Recursive listing MUST use `FileManager.contentsOfDirectory(at:includingPropertiesForKeys:options:)` with `.skipsHiddenFiles` option. Recursion depth is bounded by folder structure; no artificial limit is required.

For each `.txt` file found:
- Read contents via `Data(contentsOf: url, options: .mappedIfSafe)`.
- Parse header tags, resolve asset filenames to file URLs via `FileManager.contentsOfDirectory`.
- Check file availability via `FileManager.fileExists(atPath:)`.
- Build HTTP URLs (`coverUrl`, `audioUrl`, etc.) from the on-device HTTP server scheme (see Section 7).
- Preserve modified timestamp via `url.resourceValues(forKeys: [.contentModificationDateKey])` for `modifiedTimeMs`.

**iCloud Drive files (normative):**
Before including a file URL in `SongEntry`, check:
```swift
let values = try fileURL.resourceValues(forKeys: [.ubiquitousItemDownloadingStatusKey])
if values.ubiquitousItemDownloadingStatus != .current {
    // File is not downloaded - treat as missing
    return null
}
```
Call `FileManager.default.startDownloadingUbiquitousItem(at:)` as a background hint only — do not block on it.

#### 3.1.2 Song file delivery (Legacy §3.1.2)
The iOS app runs a lightweight read-only HTTP server for the duration of its session connection (see Section 7). Song files are served directly from file URLs via `FileHandle` streams; no copying to app-private storage. The TV fetches files on demand using URLs provided in `songListUpdate`. The iOS app MUST keep the HTTP server alive while connected and stop it on disconnect to release file coordinator grants.

#### 3.1.3 Phone-side state (Legacy §3.1.3)
The iOS app maintains in-memory metadata for songs it has scanned during the current session. This cache is invalidated when:
- The TV issues `requestSongList` (full rescan).
- The user changes the songs folder (clear cache, rescan new folder).
- The app disconnects from the session (cache discarded; will rescan on next join when requested).
No persistence is required between app launches; scans always reflect the filesystem state at request time.

### 3.2 Discovery and Validation Rules (Legacy §3.2)
**Tests:** F01, F02, F04

#### 3.2.1 Phone-side discovery (normative) (Legacy §3.2.1)
The iOS app scans for **all `.txt` files recursively** under its configured songs folder. Each `.txt` produces one song entry, even if multiple `.txt` files exist per directory. Duplicate titles are allowed; identity is `clientId + relativeTxtPath`.

#### 3.2.2 Validation (song acceptance) (Legacy §3.2.2)
A song entry is accepted into the library if and only if all of the following checks pass. If any check fails, the song entry MUST be rejected and a diagnostic MUST be emitted (see Section 4.3).
1) Required header tags present
- `#TITLE` and `#ARTIST` MUST be present and non-empty.
- `#BPM` MUST be present and parseable as a **non-zero** floating-point number.
- A required audio reference tag MUST be present:
  - For `#VERSION >= 1.0.0`: at least one of `#AUDIO` or `#MP3` MUST be present and non-empty. If both are present, `#AUDIO` takes precedence (Section 4.2).
  - For legacy format (`#VERSION` absent or `< 1.0.0`): `#MP3` MUST be present and non-empty. `#AUDIO` (if present) MUST be ignored for audio resolution.
2) Required audio file exists
- The audio reference resolved by Section 4.2 MUST resolve to an existing file relative to the `.txt` directory (subpaths allowed). Absolute URLs unsupported by the HTTP server count as missing.
3) Notes section parses without fatal errors
- Parse body per Section 4.1 / 4.3.
- Unknown tokens and recoverable grammar issues MUST be logged (warn) and skipped.
- Fatal numeric parse errors for recognized tokens MUST reject the song entry.
4) Each track has at least one non-empty sentence after cleanup
- Tracks MAY omit sentence delimiters (`-`). If notes exist but no `-`, construct at least one sentence/line (USDX behavior).
- `ERROR_CORRUPT_SONG_NO_BREAKS` reserved for inability to construct any sentence container.
- Remove empty sentences (no `:`, `*`, `F`, `R`, `G`). Perform cleanup before "no notes" check.
- If a track contains zero sentences after cleanup, reject with `ERROR_CORRUPT_SONG_NO_NOTES`.

#### 3.2.3 Missing files (Legacy §3.2.3)
Audio/video/instrumental files are validated for existence at scan time:
- Missing required audio file -> load fails (song omitted with invalid diagnostic).
- Missing optional assets (video/images/instrumental) -> log warn, continue.
- For cloud-only placeholders (file URL without local bytes, e.g., iCloud Drive file not downloaded), the iOS app MUST check `ubiquitousItemDownloadingStatus`. If not `.current`, count as missing.

#### 3.2.4 MVP parity requirements (Legacy §3.2.4)
- Mirror the recursive `.txt` discovery behavior exactly.
- Reject songs missing required header fields or required audio file.
- Keep invalid song diagnostics (error line number + reason) for export/troubleshooting via developer UI/os_log.

## 4. Parsing Rules & Validation (Legacy §4)

### 4.1 Supported Note Tokens (Legacy §4.1)
**Tests:** F03, F04


#### Note/body line tokens (USDX parser)
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

#### Per-note fields
For note tokens (`:`, `*`, `F`, `R`, `G`) USDX parses:
`<token> <startBeat> <duration> <tone> <lyricText...>`
- `startBeat` and `duration` are integers in chart beat units. They are not scaled by BPM; BPM affects only the beat->time conversion (Section 5.1). Any legacy relative-mode shift (format < 1.0.0) is applied separately (Section 4.2).
- `tone` is an integer note tone as stored in the file.
- `lyricText` is the remainder of the line after the numeric fields.

#### Duet structure
- If the first non-empty body line begins with `P`, USDX marks the song as duet (`isDuet = true`) and creates two tracks.
- A `P1`/`P2` marker sets the active track (0/1).
- Notes and `-` sentence breaks are assigned to the current active track.
- The file ends with a single `E` after all notes.

### 4.2 Supported Header Tags and Semantics (Legacy §4.2)
**Tests:** F02, F01


#### Required tags
- `#TITLE:` song title (UTF-8 for format >= 1.0.0).
- `#ARTIST:` song artist.
- `#BPM:` base BPM. USDX loads as `BPM_internal = BPM_file * 4`. BPM values using a comma as decimal separator (e.g., `120,5`) MUST have the comma replaced with a period before parsing. Parsing MUST be locale-independent (i.e., always use `.` as decimal separator regardless of device locale).
- Audio filename:
  - For `#VERSION >= 1.0.0`: at least one of `#AUDIO:` or `#MP3:` MUST be present and non-empty. If `#AUDIO:` is present, it takes precedence over `#MP3:` (USDX behavior).
  - For legacy format (`#VERSION` absent or `< 1.0.0`): `#MP3:` MUST be present and non-empty. `#AUDIO:` (if present) MUST be ignored for audio resolution (USDX behavior).
  - The resolved audio file MUST exist, otherwise load fails.

#### Timing/alignment tags
- `#GAP:` millisecond offset used as the lyrics/audio time origin for beat/time conversions (see Section 5.1). Parsed as a float (fractional ms allowed).
- `#START:` seconds; initial playback/lyrics time offset.
- `#END:` milliseconds; sets lyrics total time if present.
- `#PREVIEWSTART:` seconds; used by editor and can be used for song preview.

#### Media tags
- `#VIDEO:` video filename or external reference. Optional; missing file is non-fatal (warn and continue without video).
  A `#VIDEO` value is treated as an **external/YouTube reference** and `videoUrl` MUST be `null` if it matches any of:
  - starts with `v=` (YouTube video-ID shorthand, e.g., `v=9bZkp7q19f0`)
  - starts with `http://`, `https://`, or `www.`
  - contains `youtube.com` or `youtu.be`
  For all other `#VIDEO` values, treat as a relative local filename. If the file does not exist on the phone, `videoUrl` MUST be `null` and a warn diagnostic MUST be emitted.
- `#VIDEOGAP:` seconds offset added to audio position when positioning video.
- `#INSTRUMENTAL:` instruments-only audio file. When present and the file exists, replaces `#AUDIO`/`#MP3` as the sole backing track for the entire song. See Section 1.1 for full semantics.
- `#VOCALS:` acapella audio file. When present alongside `#INSTRUMENTAL`, mixed at a user-configurable volume as a singing guide. Ignored if `#INSTRUMENTAL` is absent. See Section 1.1 for full semantics.
- `#COVER:` image; `#BACKGROUND:` image. Fallback filenames `*[CO].jpg` and `*[BG].jpg` (glob: any file in the song directory ending with `[CO].jpg` or `[BG].jpg` respectively) MUST be resolved by the phone at scan time if the explicit tag is absent or the named file does not exist. If a fallback file is found, it MUST be used to populate `coverUrl`/`backgroundUrl` in `songListUpdate`. If no fallback is found, the corresponding URL is `null`. The TV does NOT perform filename glob resolution — it only uses URLs supplied by the phone.

#### Duet tags
Singer labels (stored and available via `ParsedSong.header.p1Name` / `p2Name`; not displayed in singing screen UI — device names are shown instead):
- `#P1:` and `#P2:` set duet singer names for internal use.

#### In-song BPM changes
Variable-BPM charts (body `B` lines) are **not supported**. If any `B` line is present, the song MUST be rejected as invalid (use `ERROR_CORRUPT_SONG_UNSUPPORTED_VARIABLE_BPM`).

### 4.3 Error Handling (Legacy §4.3)
**Tests:** F02, F03, F04


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
  - `txtUrl`: song TXT identifier.
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

### 4.4 Header Tags Reference (Legacy §4.4)
**Tests:** F02, F03, F04


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

### 4.5 Body Token Reference (Legacy §4.5)
**Tests:** F03


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

## 5. DSP Pipeline & Pitch Streaming (Legacy §5.2.5)

This section defines the normative implementation for the on-device pitch detector. The iOS companion app MUST implement a custom Fast YIN (FFT-YIN) pipeline.

To ensure low latency and eliminate GC pauses during gameplay, the implementation MUST use primitive arrays exclusively (e.g., `UnsafeMutablePointer<Float>` or `Accelerate` vDSP buffers) and strictly prohibit object allocation within the audio processing loop.

### 5.1 Primitive Memory Management (Normative)
**Tests:** F06


The following buffers MUST be pre-allocated once during initialization and reused for every frame:
- `audioBuffer`: 1024 floats (for the raw PCM input)
- `paddedBuffer`: 2048 floats (for zero-padded FFT input)
- `fftComplexBuffer`: 4096 floats (for in-place FFT interleaved real/imaginary parts using Accelerate framework)
- `diffBuffer`: 1024 floats (for the d_t difference function)
- `normBuffer`: 1024 floats (for the d' normalized function)
- `medianHistory`: 3-byte circular buffer (for temporal smoothing)

### 5.2 Algorithm Pipeline (Normative)
**Tests:** F13, F14v2


The audio capture window is 1024 samples at 44100 Hz (~23 ms). For each window, the phone MUST execute the following pipeline synchronously:

**Step 1: Voicing Gate (maxAmp)**
Compute the peak amplitude of the window using a primitive loop:
`maxAmp = max(abs(audioBuffer[i]))` for i in 0..1023.
If `maxAmp < thresholdTable[thresholdIndex].maxAmpCutoff`, the frame is considered unvoiced. The pipeline MUST immediately set `rawMidiNote = 255`, skip Steps 2-4 to conserve battery, and proceed to Step 5.

**Step 2: Linear Autocorrelation via FFT**
To avoid circular correlation artifacts, the signal MUST be zero-padded.
1. Copy `audioBuffer` into the first half of `paddedBuffer`. Fill the second half with 0.0f.
2. Compute the forward FFT of `paddedBuffer` in-place using Accelerate/vDSP.
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

### 5.3 Consolidated Sensitivity Table (Normative)
**Tests:** F06


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

## 6. Session Lifecycle & Pairing UX (Legacy §7)

### 6.1 Phone Pairing UX (Legacy §7.3)
**Tests:** F08, F09


The phone app has three primary screen states:
1. **Join screen**: shown when not connected to any session.
2. **Waiting/Connected screen**: shown when connected as Spectator, or after song end.
3. **Active Mic screen**: shown when assigned as Singer, both during countdown and during singing.

#### Wireframes (phone app)

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

+----------------------------------+
| SETTINGS                          |
+----------------------------------+
| Songs folder:                     |
|   /storage/emulated/Downloads/Songs|
|   [Change folder]                 |
|                                   |
| Song count:  423 valid / 2 invalid|
| [Rescan now]                      |
+----------------------------------+

SELECT TV SESSION (when multiple sessions discovered)
+----------------------------------+
| SELECT TV SESSION                 |
+----------------------------------+
|  > Living Room TV                 |
|    Bedroom TV                     |
|                                  |
| [Back]                            |
+----------------------------------+

ERROR — Permission denied
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
| iOS: Settings -> Privacy ->       |
| Local Network -> (this app)       |
|                                  |
| [OK]                              |
+----------------------------------+

ERROR — Session locked
+----------------------------------+
| ERROR                             |
+----------------------------------+
| Session is locked.                |
| (A song is in progress.)          |
|                                  |
| [OK]                              |
+----------------------------------+

ERROR — Session full
+----------------------------------+
| ERROR                             |
+----------------------------------+
| Session is full.                  |
|                                  |
| [OK]                              |
+----------------------------------+

ERROR — Protocol mismatch
+----------------------------------+
| ERROR                             |
+----------------------------------+
| Protocol mismatch.                |
|                                  |
| [OK]                              |
+----------------------------------+
```

#### Waiting/Connected screen
- Connection state (Connecting / Connected / Reconnecting / Disconnected)
- Current assigned role (Singer / Spectator); if Singer, show playerId (P1/P2)
- Live input level meter (VU meter, always active for audio monitoring)
- Mute toggle: when enabled, the phone MUST continue to stay connected but MUST stream frames as unvoiced (equivalent to `toneValid=false` and `midiNote=255`) so the TV scores silence.
- Leave session action

#### Active Mic screen (during countdown and singing)
- Shown immediately when the phone receives `assignSinger`. The phone MUST trigger haptic feedback on receiving `assignSinger` to alert the player.
- Role badge: Singer P1 / Singer P2
- Large countdown number during countdown phase (mirrors TV countdown; derived from `countdownMs`)
- Live VU meter (real-time input level from active mic capture)
- Mute toggle
- Mic warms up locally during countdown but no frames are sent until countdown completes (`startMode="countdown"`)
- When `tvNowMs >= endTimeTvMs`, the phone transitions back to the Waiting/Connected screen automatically

#### Post-song state
- After song end, the phone returns to the Waiting/Connected screen. Role label still shows the last assigned role until a new `assignSinger` or session change. No score is displayed on the phone; results are TV-only.

#### Active Mic exit policy (normative)
The Active Mic screen MUST NOT display a Leave session or Back action during an active song. The hardware Back key MUST be suppressed (do nothing) during Active Mic. Users wishing to exit must use the device's OS navigation to background the app. This is expected MVP behaviour — session control is TV-side only.

### 6.2 Phone App Settings (Normative)
**Tests:** F03, F09


The phone app has a Settings screen accessible from the Join screen and from the Waiting/Connected screen. Settings MUST include:
- **Songs folder**: displays the currently configured songs folder path; pressing OK opens the platform folder picker (`UIDocumentPickerViewController(forOpeningContentTypes: [.folder])`) to change it. On selection, the phone immediately triggers a rescan and sends `songListUpdate` to the TV if connected.
- **Rescan now**: manually triggers a rescan of the current songs folder. If connected to a TV session, the phone sends `songListUpdate` on completion.
- **Song count**: read-only display of the number of valid songs found in the last scan.

### 6.3 Scan QR UX (Normative)
**Tests:** F09

- Tapping **Scan QR** MUST open the camera-based QR scanner using `AVFoundation`.
- If camera permission is not granted, the phone MUST request it.
- If camera permission is denied (including "Don't ask again"), the phone MUST return to the Join screen and show a blocking error modal.

### 6.4 Join Resolution (Normative)
**Tests:** F09

- The QR payload encodes the full WebSocket endpoint URL including the `token` query parameter.
- On successful QR scan, the phone connects directly to that endpoint.
- When the user enters the join code manually, the phone MUST use mDNS to locate the matching TV session per the normative resolution algorithm in Section 7.1.

### 6.5 Leave Session UX (Normative)
**Tests:** F11, F16

- Tapping **Leave session** MUST:
  - Close the network connection to the TV host (WebSocket).
  - Return the phone UI to the Join screen.
  - Clear any cached session endpoint so the user MUST rejoin explicitly.
- After leaving, automatic reconnect MUST NOT occur in MVP.

### 6.6 Disconnect/Reconnect (Legacy §7.4)
**Tests:** F11


#### Mid-song disconnect (normative)
- When a **required singer** (a phone assigned as P1 or P2) disconnects while a song is in progress, the TV pauses the song.
- When a **spectator** or **song-source-only** phone disconnects mid-song, the TV does NOT pause. The phone's songs are removed from the library immediately.

#### Reconnect mechanics (normative)
- **Transport disconnect** (network drop, app backgrounded, temporary WiFi loss): the phone SHOULD automatically attempt to reconnect to the last session endpoint.
- **User-initiated leave** (tap **Leave session**): return to Join screen and clear cached endpoint. Automatic reconnect MUST NOT occur.
- **Host kick/forget**: the TV closes the connection. The phone MUST return to the Join screen and clear any cached endpoint.
- If the same phone reconnects within the same session, it MUST reclaim its prior identity by sending the same `clientId` in `hello`.
- The TV assigns a **new** `connectionId` to the reconnecting phone.
- On reconnect, the TV MUST send `requestSongList` to refresh the song index.
- If the phone was assigned as a Singer when it disconnected, it MUST resume that singer role on reconnect.

## 7. Network Protocol & HTTP Server (Legacy §8)

### 7.1 Transport (Legacy §8.1)
**Tests:** F15


This system uses two transports:
- **WebSocket** (control channel): all control messages (`hello`, `sessionState`, `ping`, `pong`, `clockAck`, `assignSinger`, `error`, `requestSongList`, `songListUpdate`).
- **HTTP** (song file delivery): the phone runs a read-only HTTP file server. The TV fetches song assets directly using URLs provided in `songListUpdate`.
- **UDP** (pitch channel): all `pitchFrame` datagrams. The phone targets `<tv-ip>:<udpPort>` for all pitch UDP datagrams. Frames MUST NOT be batched.

#### Session token / join code (normative)
- Random token to prevent accidental joins on the LAN; minimum 32 bits entropy.
- The join code MUST be human-enterable: implementations SHOULD use a case-insensitive alphabet and MAY display the code in groups (e.g., `ABCD-EFGH`).
- When the user types the join code, the phone MUST normalize it by removing spaces/hyphens and applying case-insensitive comparison.

#### mDNS advertisement (normative)
The TV advertises via mDNS for the duration of the session.
- Service type: `_karaoke._tcp`
- Instance name: `KaraokeTV-<last4>` where `<last4>` is the last 4 characters of the normalized join code.
- TXT record fields: `code=<normalizedJoinCode>`, `v=1`

#### Phone join-code resolution (normative)
When the user enters a join code manually:
1. Phone normalizes input: strip spaces/hyphens, uppercase.
2. Phone performs mDNS browse for `_karaoke._tcp` using `Network.framework` (`NWBrowser`).
3. For each discovered service, phone resolves TXT records and compares `code` field against normalized input.
4. If exactly one match: connect directly to that service's host/port with the token.
5. If multiple matches: prompt user to select by instance name.
6. If no match after 5 seconds: show `TV not found. Make sure your phone is on the same Wi-Fi network.`

### 7.2 Control Messages (Legacy §8.2)
**Tests:** none


All messages are JSON objects with fields: `type` (string), `protocolVersion` (int), `tsTvMs` (optional).

#### Required control messages:

1) `hello` (phone -> TV)
- Fields: `clientId` (stable UUID), `deviceName`, `appVersion`, `protocolVersion`, `capabilities` (e.g., `{"pitchFps":100}`), `httpPort` (int)

2) `sessionState` (TV -> phone)
- Fields: `sessionId`, `slots`, `inSong` (bool), `connectionId` (uint16; assigned by TV per connection)

3) `ping` / `pong` / `clockAck` (clock sync)
- `ping` (TV -> phone): `pingId`, `tTvSendMs`
- `pong` (phone -> TV): `pingId` (echo), `tTvSendMs` (echo), `tPhoneRecvMs`, `tPhoneSendMs`
- `clockAck` (TV -> phone): `pingId` (echo), `tTvRecvMs`

4) `error` (TV -> phone)
- Fields: `code` (string), `message` (string)
- Codes: `invalid_token`, `protocol_mismatch`, `session_full`, `session_locked`

5) `assignSinger` (TV -> phone)
- Fields: `sessionId`, `songInstanceSeq`, `playerId`, `difficulty`, `thresholdIndex`, `effectiveMicDelayMs`, `expectedPitchFps`, `startMode`, `countdownMs` (if startMode=="countdown"), `endTimeTvMs`, `udpPort`, `connectionId`, `songTitle`, `songArtist`

6) `requestSongList` (TV -> phone)
- Fields: `sessionId`

7) `songListUpdate` (phone -> TV)
- Fields: `sessionId`, `songs` (array of `SongEntry`)

### 7.3 Pitch Stream Messages (Legacy §8.3)
**Tests:** none


Normative MVP rule: phones MUST NOT send any computed scoring, judgement, combo, or rating values. Phones send only DSP-derived observations.

#### pitchFrame (phone -> TV, via UDP — binary format)

Each frame is a **16-byte fixed-size binary datagram** with the following layout. All multi-byte integers are **little-endian**:

```
Offset  Size  Type     Field
  0      4    uint32   seq              — frame counter, increments by 1 per frame
  4      4    int32    tvTimeMs         — phone's estimate of TV monotonic ms for this frame
  8      4    uint32   songInstanceSeq  — matches `songInstanceSeq` from assignSinger
 12      1    uint8    playerId         — 0=P1, 1=P2
 13      1    uint8    midiNote         — 0..127 (voiced); 255 = unvoiced/toneValid=false
 14      2    uint16   connectionId     — assigned by TV at hello handshake
```

Total: **16 bytes per frame**.

`toneValid` is implicit: `toneValid = (midiNote != 255)`.

#### Rate
- Default **50 fps** (one frame every 20 ms). Phones capable of 100 fps MAY advertise `"pitchFps":100` in `capabilities`.
- Frames MUST NOT be batched.

### 7.4 Song File HTTP Server (Legacy §8.6)
**Tests:** F15


**Purpose**: serve song asset files from the phone to the TV over HTTP so ExoPlayer can stream them progressively.

#### Server lifecycle (normative)
- The HTTP server MUST start before the phone sends `hello` to the TV.
- The server MUST remain running for the duration of the session connection.
- Port `34781` is the default. If unavailable, the phone MUST bind to any available ephemeral port and report the actual port in `hello.httpPort`.
- **iOS**: `UIApplication.shared.isIdleTimerDisabled` MUST be set to `true` for the duration of the session to prevent the OS from dimming the screen. Reset to `false` on session end.

#### URL scheme (normative)
Song asset URLs are constructed by the phone at scan time:
```
http://<phone-ip>:<httpPort>/songs/<percent-encoded-relative-path>
```

#### Range requests (normative)
The server MUST support HTTP `Range` requests for all audio and video files. The server MUST respond with:
- `Accept-Ranges: bytes` on all audio/video responses.
- `206 Partial Content` with correct `Content-Range` header when a `Range` request is received.

#### iOS file reads (Swift)
- Files selected via `UIDocumentPickerViewController` are accessed via their bookmarked `URL`. Call `url.startAccessingSecurityScopedResource()` before opening the file and `url.stopAccessingSecurityScopedResource()` after the response is written.
- All file reads in the HTTP request handler MUST go through `NSFileCoordinator` to prevent conflicts with the iCloud sync daemon:
```swift
var error: NSError?
NSFileCoordinator().coordinate(readingItemAt: fileURL, options: .withoutChanges, error: &error) { url in
    // open FileHandle and read byte range here
}
```
- **Range requests**: parse the `Range: bytes=X-Y` header manually in the HTTP handler. Open a `FileHandle`, `seek(toFileOffset: offset)`, `readData(ofLength: length)`. Respond with `206 Partial Content`, `Content-Range: bytes X-Y/total`, and `Content-Length: length`.

#### iOS background HTTP server (known limitation)
If the user backgrounds the phone app during a song, iOS may suspend the process after approximately 30 seconds, terminating the HTTP server socket. ExoPlayer on the TV will then stall. `UIApplication.shared.isIdleTimerDisabled = true` (set for the session duration) prevents screen dimming but does not prevent backgrounding. MVP implementations MUST document this as a known limitation: users must keep the phone app in the foreground during a song.

## 8. Appendices

### A.1 iOS Companion App (Swift) Dependencies

| Library | Version | Purpose |
|---|---|---|
| `Network.framework` | built-in | mDNS browsing (NWBrowser) |
| `Accelerate` | built-in | FFT/YIN DSP pipeline |
| `AVFoundation` | built-in | QR code scanning |
| `Swifter` | 1.5.0 | HTTP server (via SPM) |

### A.2 Info.plist Entries (Normative)

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

`NSAllowsLocalNetworking` permits cleartext HTTP to RFC-1918 addresses without opening ATS globally. `NSLocalNetworkUsageDescription` triggers the one-time system permission prompt (iOS 14+) that gates all LAN TCP connections.

### A.3 Prohibited Patterns

- Do NOT use `URL(fileURLWithPath:)` with arbitrary strings — always use security-scoped URLs from the folder picker.
- Do NOT allocate objects in the audio processing loop.
- Do NOT use GC-heavy operations during pitch detection.
- Do NOT rely on background execution for the HTTP server — users must keep the app in foreground during songs.
