# Couchraoke Phone Companion App

**Version**: 1.2
**Date**: 2026-04-26  
**Scope**: Android Phone Companion (iOS follows same architecture)  
---

## Table of Contents

- [1. Non-Functional Requirements](#1-non-functional-requirements)
- [2. Top-Level Components](#2-top-level-components)
  - [2.1 SongScanner](#21-songscanner)
  - [2.2 HttpFileServer](#22-httpfileserver)
  - [2.3 PitchDetector](#23-pitchdetector)
  - [2.4 NetworkClient](#24-networkclient)
  - [2.5 ClockSync](#25-clocksync)
  - [2.6 SessionCoordinator](#26-sessioncoordinator)
- [3. Component APIs](#3-component-apis)
- [4. SLAs](#4-slas)
- [5. Resolved Blockers](#5-resolved-blockers)
- [6. Project Plan](#6-project-plan)
- [Appendix A: Mock TV Specification](#appendix-a-mock-tv-specification)

---

# 1. Non-Functional Requirements

Ordered by priority.

## 1.1 Pitch Latency (Critical)

**Why**: Frames arriving >150ms late are dropped by TV jitter buffer. Dropped frames = broken scoring.

| Requirement | Implementation |
|-------------|----------------|
| Frame generation ≤20ms | Process in AudioRecord callback thread |
| `tvTimeMs` accuracy ±5ms | Clock sync best-of-5 selection |
| No GC during pitch loop | Pre-allocated primitive arrays only |

**Tradeoff**: Pitch processing takes priority over HTTP serving. HTTP may briefly stall (~50ms) during heavy pitch activity. The TV player's 2–4s audio buffer absorbs this.

## 1.2 Reliability (High)

**Why**: A 3-minute song interrupted by disconnect ruins the experience.

| Requirement | Implementation |
|-------------|----------------|
| Auto-reconnect on disconnect | 5x immediate retry at 500ms, then exponential backoff to 30s cap |
| No silent failures | All errors surface to UI or logs |
| Frame delivery best-effort | UDP fire-and-forget, TV handles missing frames |

## 1.3 HTTP Throughput (High)

**Why**: The TV playback stack needs responsive seeks and sustained streaming.

| Requirement | Implementation |
|-------------|----------------|
| First byte ≤100ms P95 | Ktor CIO async I/O |
| Sustained ≥2 Mbps | Direct SAF stream, no buffering |
| Range requests | Ktor partial-content plugin |

## 1.4 Scan Performance (Medium)

**Why**: Large libraries should scan in reasonable time with progress feedback.

| Requirement | Implementation |
|-------------|----------------|
| Parse rate ≥100 TXT/sec | Pure Kotlin parser, no regex |
| Progress updates | Callback every 100ms or 10 songs |
| Unbounded library | No artificial limits |

## 1.5 Memory Efficiency (Medium)

**Why**: Leave headroom for other apps on 6-8GB device.

| Requirement | Implementation |
|-------------|----------------|
| Total app ≤300MB | Lean allocations, no caching |
| Pitch buffers fixed 50KB | Pre-allocated at init |
| Manifest ≤2MB for 500 songs | ~4KB per SongEntry |

## 1.6 Battery (Low)

**Why**: Songs are 3-5 minutes. Hot is acceptable for accuracy.

| Requirement | Implementation |
|-------------|----------------|
| No thermal throttling mitigation | Run at full speed |
| Idle mode minimal drain | Stop pitch detection when not singing |

---

# 2. Top-Level Components

Six components in a layered monolith (single `:app` module with package boundaries).

```
┌─────────────────────────────────────────────────────────────────┐
│                        SessionCoordinator                        │
│  (orchestrates state, routes messages, coordinates lifecycle)   │
└─────────────────────────────────────────────────────────────────┘
        │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  Song    │ │   HTTP   │ │  Pitch   │ │ Network  │ │  Clock   │
│ Scanner  │ │  Server  │ │ Detector │ │  Client  │ │   Sync   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
     │              │           │           │           │
     ▼              │           │           │           │
┌──────────┐        │           └─────┬─────┘           │
│  Cloud/  │        │                 │                 │
│  Local   │        │           ┌─────▼─────┐           │
│  Storage │        │           │ WebSocket │           │
│ (SAF/    │        │           │    +      │◄──────────┘
│  iCloud) │        │           │   UDP TX  │
└──────────┘        │           └─────┬─────┘
     │   manifest   │                 │
     └──────────────┤                 │
        + file URIs │                 │
                    ▼                 ▼
              ┌─────────────────────────────────────────┐
              │              TV (Black Box)              │
              │  ◄── HTTP GET /manifest.json            │
              │  ◄── HTTP GET /songs/<path>             │
              │  ◄── UDP pitch frames                   │
              │  ──► WebSocket control messages         │
              └─────────────────────────────────────────┘
```

---

## 2.1 SongScanner

**Responsibility**: Discover, validate, and index songs from user's configured folder.

**Lifecycle**: 
- Initialized at app start
- Runs on: app launch, folder change, manual rescan
- Produces: in-memory `SongIndex` + serialized `manifest.json` byte array

**Functional Boundary**:
- SAF tree URI persistence (Android) / security-scoped bookmark (iOS)
- Recursive `.txt` discovery
- Header parsing and validation (§2.1)
- Asset existence checks
- Builds `SongEntry` list with effective HTTP URLs

**L2 Visible Shapes**:
- `FolderAccessor` — platform abstraction for SAF/security-scoped
- `TxtParser` — header + body parsing (shared with TV)
- `ValidationEngine` — applies §2.1 acceptance rules

### Scan Implementation (Normative)

#### Android (SAF — Kotlin)

The songs folder is selected via `ActivityResultContracts.OpenDocumentTree()`. The chosen tree URI MUST be persisted using `takePersistableUriPermission()` + SharedPreferences. On subsequent launches, check permission; prompt if revoked.

Recursive enumeration uses `DocumentFile.fromTreeUri()` with `listFiles()`. For each `.txt` file found: read its content via `contentResolver.openInputStream(uri)`, parse the header tags, resolve asset filenames relative to the `.txt` directory using the segment-by-segment rules below, check file availability via `DocumentFile.exists()`, and record normalized relative asset paths plus scan metadata. Full `txtUrl`/`audioUrl`/`coverUrl`/etc. MUST NOT be constructed during scan; they are materialized later when `/manifest.json` is serialized (§2.2).

#### iOS (Security-Scoped Bookmarks — Swift)

The songs folder is selected via `UIDocumentPickerViewController(forOpeningContentTypes: [.folder])`. The chosen URL MUST be persisted as a security-scoped bookmark (`url.bookmarkData(options: .minimalBookmark)`). On subsequent launches, resolve the bookmark with `URL(resolvingBookmarkData:)` and call `url.startAccessingSecurityScopedResource()` before any file operation. Recursive enumeration uses `FileManager.default.enumerator(at: folderUrl, includingPropertiesForKeys: [.isRegularFileKey, .contentModificationDateKey])`. File reads for `.txt` content use `Data(contentsOf: fileUrl)`. Asset file availability checks use `FileManager.default.fileExists(atPath:)`. Call `url.stopAccessingSecurityScopedResource()` when scanning is complete.

### Validation Rules (Normative)

A song is accepted if and only if:

1. **Required headers present**:
   - `#TITLE` and `#ARTIST` non-empty
   - `#BPM` parseable as non-zero float
   - Audio tag: `#AUDIO` or `#MP3` (v1.0.0+: `#AUDIO` precedence; legacy: `#MP3` required)

2. **Required audio file exists**: resolved relative to `.txt` directory

3. **Notes parse without fatal errors**: unknown tokens warn, fatal numeric errors reject

4. **Each track has ≥1 non-empty sentence after cleanup**

### Header Parsing Behavior (Normative)

Header processing is best-effort and MUST continue past unknown or non-fatal issues.

- Header lines are read from the top of the file while the first character of the line is `#`. Any other line (including an empty line) ends header parsing (USDX behavior).
- Tag names are case-insensitive; matching MUST be performed on `Uppercase(Trim(TagName))`.
- Duplicate known tags: if the same known tag appears multiple times, the **last** successfully parsed value wins (earlier values are overwritten).
- Each header line is classified into exactly one of:
  - **Well-formed tag**: `#NAME:VALUE` where `NAME` is non-empty.
  - **No separator**: a line starting with `#` that contains no `:`.
  - **Empty value**: `#NAME:` (value is empty string after trimming).

For each header line:
- **Well-formed known tag**: parse according to its definition. If the value is malformed: if the tag is **required** (TITLE/ARTIST/AUDIO-or-MP3/BPM) → mark the song **invalid**; if the tag is **optional** (VIDEO, COVER, etc.) → **warn** and treat as absent.
- **Well-formed unknown tag**: **warn** and preserve in `CustomTags` as `(NAME, VALUE)`.
- **Empty value** (`#NAME:`): **info/warn** and preserve in `CustomTags` as `(NAME, "")`.
- **No separator** (no `:`): **warn** and preserve in `CustomTags` as `("", CONTENT)` where `CONTENT` is the original line without the leading `#`.

`CustomTags` is an ordered list of `(TagName, Content)` pairs. `TagName` may be empty only for the "no separator" case. The stored strings MUST be exactly the trimmed forms described above.

### BPM Parsing (Normative)

`#BPM` values using a comma as decimal separator (e.g., `120,5`) MUST have the comma replaced with a period before parsing. Parsing MUST be locale-independent (always use `.` as decimal separator regardless of device locale). Internal BPM: `BPM_internal = BPM_file × 4`.

### Version Handling (Normative)

- If `#VERSION` is absent, treat the song as legacy format `0.3.0`.
- If `#VERSION` is present, it MUST parse as a dotted numeric version (e.g., `1.0.0`). If it fails to parse: **invalid** (`ERROR_CORRUPT_SONG_INVALID_VERSION`).
- Supported versions are `< 2.0.0`. If `#VERSION >= 2.0.0`: **invalid**.
- All files are treated as UTF-8. The tags `#ENCODING`, `#RESOLUTION`, `#NOTESGAP`, `#DUETSINGERP1`, `#DUETSINGERP2`, and `#CALCMEDLEY` are treated as **unknown tags** regardless of version — preserved in `CustomTags`, no version-conditional processing.

### Supported Header Tags (Normative)

| Tag | Required | Type | Semantics |
|-----|----------|------|-----------|
| `#TITLE` | yes | string | Song title |
| `#ARTIST` | yes | string | Song artist |
| `#BPM` | yes | float | Beats per minute (file BPM; internal = ×4) |
| `#GAP` | no | float | Delay from audio start to first beat (ms) |
| `#MP3` / `#AUDIO` | yes (one) | string | Relative path to audio file |
| `#VIDEO` | no | string | Relative path to video file |
| `#VIDEOGAP` | no | float | Video offset in seconds |
| `#COVER` | no | string | Relative path to cover image |
| `#BACKGROUND` | no | string | Relative path to background image |
| `#INSTRUMENTAL` | no | string | Instrumental audio track (≥ 1.1.0) |
| `#VOCALS` | no | string | Acapella track (ignored if `#INSTRUMENTAL` absent; ≥ 1.1.0) |
| `#START` | no | float | Skip to this second on playback start |
| `#END` | no | int | Stop playback at this millisecond |
| `#PREVIEWSTART` | no | float | Preview start position in seconds |
| `#VERSION` | no | string | File format version (e.g., `1.0.0`) |
| `#MEDLEYSTARTBEAT` | no | int | Medley window start (file beats) |
| `#MEDLEYENDBEAT` | no | int | Medley window end (file beats) |
| `#P1` | no | string | Duet singer name for Player 1 (stored only) |
| `#P2` | no | string | Duet singer name for Player 2 (stored only) |
| `#YEAR` | no | int | Metadata year |
| `#GENRE` | no | string | Metadata genre |

All other tags (including `#ENCODING`, `#RESOLUTION`, `#NOTESGAP`, `#CALCMEDLEY`, and any unknown tags) MUST be preserved as `CustomHeaderTag` entries in encounter order.

### Relative Asset Resolution (Normative)

All asset header values (`#AUDIO`, `#MP3`, `#VIDEO`, `#COVER`, `#BACKGROUND`, `#INSTRUMENTAL`, `#VOCALS`) are resolved relative to the directory containing the `.txt` file.

Before lookup, the relative asset path MUST:
- use `/` as the normalized separator
- MUST NOT be empty
- MUST NOT start with `/`
- MUST NOT contain `.` or `..` path segments
- preserve case exactly as written in the chart

Android SAF resolution MUST traverse one path segment at a time from the `.txt` file's parent directory. `DocumentFile.findFile()` MUST be applied only to a single immediate-child name; it MUST NOT be used with a multi-segment relative path.

If any segment lookup fails, the asset is treated as absent.

### VIDEO External Reference Detection (Normative)

A `#VIDEO` value is treated as an **external/YouTube reference** and `videoUrl` MUST be `null` if it matches any of:
- starts with `v=` (YouTube video-ID shorthand, e.g. `v=9bZkp7q19f0`)
- starts with `http://`, `https://`, or `www.`
- contains `youtube.com` or `youtu.be`

For all other `#VIDEO` values, treat as a relative local filename. If the file does not exist on the phone, `videoUrl` MUST be `null` and a warn diagnostic MUST be emitted.

### Audio Resolution Rules (Normative)

- For `#VERSION >= 1.0.0`: at least one of `#AUDIO` or `#MP3` MUST be present and non-empty. If both are present, `#AUDIO` takes precedence.
- For legacy format (`#VERSION` absent or `< 1.0.0`): `#MP3` MUST be present and non-empty. `#AUDIO` (if present) MUST be ignored for audio resolution (USDX behavior).
- `#AUDIO` / `#MP3` identifies the song's base audio asset. It is the fallback playback source when no phone-side mixing path is active.
- `#INSTRUMENTAL` and `#VOCALS` are source assets for phone-side mixing only. They MUST NOT be exposed to the TV as independent playback URLs.
- If `#INSTRUMENTAL` resolves to a local file, the phone MUST expose exactly one effective `audioUrl` for the song. That effective `audioUrl` MUST represent the phone's chosen playback source for the song: either the unchanged base audio asset or a phone-generated mixed audio resource under `/songs/generated/`.
- `#VOCALS` without a valid `#INSTRUMENTAL` source MUST be ignored for playback resolution and MUST emit a warn diagnostic.

### Phone-Side Mixing Policy (Normative)

- MVP scope: phone-side mixing applies only when `#INSTRUMENTAL` resolves to a local file and `#VOCALS` also resolves to a local file.
- MVP scope: the `#INSTRUMENTAL` and `#VOCALS` source pair MUST have the same decoded sample rate and the same channel count. Differing compressed bitrates are allowed and do not affect validity.
- If the source pair differs in decoded sample rate or channel count, the phone MUST NOT attempt resampling or channel remixing in MVP. The song MUST fall back to the base `#AUDIO` / `#MP3` asset for `audioUrl`, and a warn diagnostic MUST be emitted.
- If the source pair is accepted for mixing, the phone MUST expose exactly one generated playback URL for the song under `/songs/generated/`. The generated relative path MUST equal `generated/<relativeTxtPath-with-.txt-suffix-replaced-by-.wav>`.
- The mixed playback resource MUST be pre-rendered before playback begins and MUST be served as RIFF/WAV containing PCM16LE samples.
- The mixed playback resource MUST preserve the accepted source pair's decoded sample rate and channel count. Original compressed bitrate MUST NOT be preserved or reported as a playback invariant.
- The mixed playback resource MUST be deterministic for a given song scan result and fixed MVP mix parameters.
- MVP mix parameters are fixed by the phone implementation. The TV-side vocals-volume control does not alter the mix in MVP.
- The effective playback duration of the mixed resource MUST equal the shorter decoded duration of the accepted source pair.
- If a song is accepted for mixing, `hasInstrumental` remains `true` whether the phone stores the pre-rendered WAV in memory, a temporary file, or another internal server-backed representation.

### Supported Note Tokens (Normative)

| Token | Name | Fields | Semantics |
|-------|------|--------|-----------|
| `:` | Normal | `startBeat duration tone lyric` | Standard scored note |
| `*` | Golden | `startBeat duration tone lyric` | Scored at 2× weight |
| `F` | Freestyle | `startBeat duration tone lyric` | Always scores max (tone ignored) |
| `R` | Rap | `startBeat duration tone lyric` | Scored on voicing only (tone ignored) |
| `G` | RapGolden | `startBeat duration tone lyric` | Rap at 2× weight |
| `-` | Sentence break | `startBeat` | Ends current sentence/line |
| `E` | End | (none) | Terminates body parsing |
| `P1`/`P2` | Player marker | (none) | Sets active track for duet |

Notes with `duration = 0` MUST be converted to Freestyle type. Unknown body tokens MUST be silently skipped (warn, don't reject).

### Duet Structure (Normative)

- If the first non-empty body line begins with `P`, the song is duet (`isDuet = true`) with two tracks.
- `P1`/`P2` markers set the active track (0/1). Notes and `-` breaks are assigned to the current active track.
- A `P` token with value other than `P1`/`P2` MUST reject the song with `ERROR_CORRUPT_SONG_INVALID_DUET_MARKER`.
- A single `E` ends the file after all notes.

### Variable BPM Rejection (Normative)

Variable-BPM charts (body `B` lines) are **not supported**. If any `B` line is present, the song MUST be rejected as invalid (`ERROR_CORRUPT_SONG_UNSUPPORTED_VARIABLE_BPM`).

### Sentence Cleanup (Normative)

After body parsing, each track MUST contain singable structure:
- If the body contains note events but no `-`, the parser MUST construct at least one sentence/line container.
- Empty sentences (zero note events) MUST be removed before the "no notes" check.
- After cleanup, if zero sentences remain: reject with `ERROR_CORRUPT_SONG_NO_NOTES`.

### previewStartSec Computation (Normative)

Fallback chain: (1) `#PREVIEWSTART` if present → (2) medley start beat if valid tags exist → (3) `0.0`.

### Medley Eligibility: `canMedley` (Normative)

A song is medley-eligible iff: `isDuet = false` AND valid medley tags exist. Valid medley tags: `#MEDLEYSTARTBEAT` and `#MEDLEYENDBEAT` both present, both parse as integers, and `startBeat < endBeat`. If valid, `medleySource = "tag"`; otherwise `medleySource = null` and `canMedley = false`.

### Derived Index Flags (Normative)

- `isDuet`: true if `P1`/`P2` markers detected in body.
- `hasRap`: true if any `R` or `G` note tokens present in body.
- `hasVideo`: true if `videoUrl != null` (local video file exists and is not an external reference).
- `hasInstrumental`: true if a valid `#INSTRUMENTAL` source tag resolves to a local file, regardless of whether the phone ultimately serves the base audio asset or a mixed playback resource.

### Path Normalization Rules (Normative)

`relativeTxtPath` in `SongEntry`: separators MUST be `/`, MUST NOT start with `/`, MUST NOT contain `.` or `..` segments, case MUST be preserved.

### URL Construction (Normative)

The scan result stores normalized relative asset paths and asset-resolution metadata only. Full manifest URLs are materialized only when serializing `/manifest.json` after the HTTP server has bound its actual port and after the phone has determined the local address of the active WebSocket connection to the TV.

```
http://<phone-ip>:<httpPort>/songs/<percent-encoded-relative-path>
```

`<phone-ip>` MUST be the local IP address of the socket used for the current WebSocket connection to the TV. The phone MUST NOT choose the published host by enumerating interfaces heuristically.

If the phone binds a different port on restart or fallback, it MUST regenerate the in-memory manifest before sending `hello` so all published URLs use the bound port. If the active TV connection changes and therefore the local socket address changes, the phone MUST regenerate the in-memory manifest before publishing any new URLs for that connection. Session-owned generated playback resources also publish a server-owned relative path under `/songs/generated/`; their `audioUrl` MUST be included in the manifest published to the active TV session before playback begins.

### Diagnostics Record Schema (Normative)

Each entry: `severity` (`info`|`warn`|`invalid`), `code`, `message`, `txtUri`, `lineNumber` (optional 1-based). Invalid songs MUST have at least one `severity=invalid` entry and are not published in `/manifest.json`.

### Parsed Song Model (Normative — Appendix C)

**SongHeader**: `title`, `artist`, `bpmFile` (raw, before ×4), `gapMs`, `videoGapSec`, `startSec`, `endMs`, `isDuet`, `previewStartSec`, custom tags (ordered list).

**SongTiming**: `bpmFile` (sole BPM). `BPM_internal = BPM_file × 4`.

**Track**: `trackIndex` (0 for P1/solo, 1 for P2), `lines` (ordered).

**Line**: `lineIndex` (0-based), `notes` (ordered by `startBeatFile`).

**NoteEvent**: `noteType` (enum), `startBeatFile`, `durationBeats`, `toneSemitone` (C2=0), `lyric`, `endBeatFileExclusive = startBeatFile + durationBeats`.

**Beat convention**: `noteActive if startBeat <= beat < endBeat` (start inclusive, end exclusive).

### Error Codes (Normative)

- `ERROR_CORRUPT_SONG_MISSING_REQUIRED_HEADER`
- `ERROR_CORRUPT_SONG_FILE_NOT_FOUND`
- `ERROR_CORRUPT_SONG_MALFORMED_HEADER`
- `ERROR_CORRUPT_SONG_MALFORMED_BODY`
- `ERROR_CORRUPT_SONG_NO_NOTES`
- `ERROR_CORRUPT_SONG_NO_BREAKS` (reserved)
- `ERROR_CORRUPT_SONG_UNSUPPORTED_VARIABLE_BPM`
- `ERROR_CORRUPT_SONG_UNSUPPORTED_RELATIVE`
- `ERROR_CORRUPT_SONG_INVALID_VERSION`
- `ERROR_CORRUPT_SONG_INVALID_DUET_MARKER`

### Tests (Normative)

| ID | What | Fixture | Expected |
|---|---|---|---|
| T3.2.1 | Missing `#ARTIST` tag | F01/`a/invalid_missing_required_header` | `isValid=false`, `ERROR_CORRUPT_SONG_MISSING_REQUIRED_HEADER` |
| T3.2.2 | `#AUDIO` file missing on disk | F01/`b/invalid_missing_audio` | `isValid=false`, `ERROR_CORRUPT_SONG_FILE_NOT_FOUND`, `invalidLineNumber=4` |
| T3.2.3 | v1.0.0: `#AUDIO` beats `#MP3` | F01/`c/v1_audio_precedence` | `isValid=true`, `resolvedAudio=audio.ogg` |
| T3.2.4 | Legacy: `#MP3` required, `#AUDIO` ignored | F01/`c/legacy_mp3_preferred` | `isValid=true`, `resolvedAudio=audio.mp3` |
| T3.2.5 | Legacy: no `#MP3` | F01/`c/legacy_missing_mp3_invalid` | `isValid=false`, `ERROR_CORRUPT_SONG_MISSING_REQUIRED_HEADER` |
| T3.2.6 | Missing optional `#VIDEO` | F01/`c/v1_missing_optional_video` | `isValid=true`, `hasVideo=false` |
| T3.2.7 | `#BPM:0` | `inline` | `isValid=false`, `ERROR_CORRUPT_SONG_MALFORMED_HEADER` |
| T3.2.8 | Non-numeric `#BPM` | F02/`b/invalid_malformed_bpm` | `isValid=false`, `ERROR_CORRUPT_SONG_MALFORMED_HEADER`, `invalidLineNumber=5` |
| T3.2.9 | Recursive scan finds all `.txt` | F01/`songs_root/` | All entries discovered |
| T3.2.9a | Nested relative asset path resolves segment-by-segment | F01/`c/nested_relative_asset_path` | `isValid=true`, asset present when each path segment exists |
| T3.2.10 | `#VOCALS` without `#INSTRUMENTAL` | F01/`d/vocals_without_instrumental` | `isValid=true`, `audioUrl` resolves from base audio asset, warn diagnostic emitted |
| T3.2.11 | Accepted mixing pair publishes one effective audio URL | F01/`d/mix_pair_same_rate_channels` | `isValid=true`, `hasInstrumental=true`, manifest contains single `audioUrl`, no `instrumentalUrl`/`vocalsUrl` fields |
| T3.2.12 | Mixing pair with mismatched sample rate falls back to base audio | F01/`d/mix_pair_mismatched_sample_rate` | `isValid=true`, `hasInstrumental=true`, `audioUrl` resolves from base audio asset, warn diagnostic emitted |
| T3.2.13 | Mixing pair with mismatched channel count falls back to base audio | F01/`d/mix_pair_mismatched_channels` | `isValid=true`, `hasInstrumental=true`, `audioUrl` resolves from base audio asset, warn diagnostic emitted |
| T4.1.1 | P1/P2 track routing | F04/`a/valid_duet_interleaved` | 2 tracks, notes assigned per track |
| T4.1.2 | Invalid `P3` marker | F04/`b/invalid_duet_marker_p3` | `isValid=false`, `ERROR_CORRUPT_SONG_INVALID_DUET_MARKER`, `invalidLineNumber=6` |
| T4.2.1 | Duplicate tags → last wins | F02/`a/dup_bpm_last_wins` | `bpmFile=120.0` |
| T4.2.2 | Unknown tags preserved and ordered | F02/`a/unknown_tags_variants` | `customTags=[{FOO,bar},{EMPTY,""},{"",.JUSTTEXT}]` |
| T4.2.3 | `#VERSION:1.0.0` forces UTF-8 | F02/`c/encoding_utf8_forced` | `title="Tést ✓ UTF8"` |
| T4.2.4 | `previewStartSec` from `#PREVIEWSTART` | F02/`d/preview_from_previewstart` | `previewStartSec=12.5` |
| T4.2.5 | `previewStartSec` medley fallback | F02/`d/preview_from_medley` | `previewStartSec=2.0` |
| T4.2.6 | `previewStartSec` defaults to 0 | F02/`d/preview_from_start` | `previewStartSec=0.0` |
| T4.2.7 | `#VOCALS` without `#INSTRUMENTAL` | F01/`d/vocals_without_instrumental` | `isValid=true`, `audioUrl` resolves from base audio asset, warn diagnostic emitted |
| T4.2.8 | Accepted mixing pair publishes one effective audio URL | F01/`d/mix_pair_same_rate_channels` | `isValid=true`, `hasInstrumental=true`, manifest contains single `audioUrl`, no `instrumentalUrl`/`vocalsUrl` fields |
| T4.2.9 | Mixing pair with mismatched sample rate falls back to base audio | F01/`d/mix_pair_mismatched_sample_rate` | `isValid=true`, `hasInstrumental=true`, `audioUrl` resolves from base audio asset, warn diagnostic emitted |
| T4.2.10 | Mixing pair with mismatched channel count falls back to base audio | F01/`d/mix_pair_mismatched_channels` | `isValid=true`, `hasInstrumental=true`, `audioUrl` resolves from base audio asset, warn diagnostic emitted |
| T4.3.1 | Unknown body token ignored | F03/`a/unknown_token_ignored` | `isValid=true` |
| T4.3.2 | Malformed numeric in body | F03/`b/invalid_malformed_numeric` | `isValid=false`, `ERROR_CORRUPT_SONG_MALFORMED_BODY`, `invalidLineNumber=7` |
| T4.3.3 | `duration=0` converts to Freestyle | F03/`c/duration_zero_converts_to_freestyle` | Note stored as `Freestyle` |
| T4.3.6 | `B` token rejected | F03/`d/variable_bpm_rejected` | `isValid=false`, `ERROR_CORRUPT_SONG_UNSUPPORTED_VARIABLE_BPM` |
| T4.3.7 | `#RELATIVE:YES` as custom tag | F03/`e/relative_header_as_custom_tag` | `isValid=true`, `customTags` contains `{RELATIVE, YES}` |
| T4.3.8 | RELATIVE body rejected | F03/`f/relative_body_rejected` | `isValid=false`, `ERROR_CORRUPT_SONG_UNSUPPORTED_RELATIVE` |

**Source**: §2.1, §4.1–§4.5, Appendix C

**NFRs**: 1.4 (scan performance), 1.5 (memory)

**Acceptance**: F01, F02, F03, F04, F05

---

## 2.2 HttpFileServer

**Responsibility**: Serve song files, effective playback audio, and manifest to TV over HTTP.

**Lifecycle**:
- Starts before the `hello` handshake
- Runs for session duration
- Stops on session end

**Functional Boundary**:
- `GET /manifest.json` from in-memory byte array (Cache-Control: no-cache)
- `GET /songs/<path>` with range request support for scanned static assets
- `GET /songs/<path>` MAY also resolve to a phone-generated mixed playback resource when the requested relative path identifies the song's effective playback resource
- Generated playback resources use a reserved `/songs/generated/<path>.wav` namespace and are served as `audio/wav`
- Resolves request paths through scan-owned metadata or session-owned generated-resource state
- 404 for missing, 416 for invalid ranges

**L2 Visible Shapes**:
- `KtorServer` — Ktor CIO + partial-content plugin
- `HummingbirdServer` — Hummingbird HTTP/1.1 server for iOS embedding
- `AssetResolver` — resolves request path to static asset or generated playback resource
- `RangeHandler` — parses Range header, streams bytes

### Libraries (Pinned)

| Platform | Library | Version |
|----------|---------|---------|
| Android | `io.ktor:ktor-server-cio` | 3.4.3 |
| Android | `io.ktor:ktor-server-partial-content` | 3.4.3 |
| iOS | Hummingbird | 2.22.0 |

### Server Configuration

- Default port: `34781` (fallback to ephemeral if busy)
- Report actual port in `hello.httpPort`

### Manifest Endpoint (Normative)

The phone MUST serve its catalog at `GET /manifest.json`. Response: `200 OK`, `Content-Type: application/json`, body is a JSON array of `SongEntry` objects.

The endpoint MUST be served from an in-memory JSON byte array rebuilt on each scan. It MUST NOT read from disk on each request. The phone MUST set `Cache-Control: no-cache` on manifest responses.

### Song Asset Endpoint (Normative)

URL form: `http://<phone-ip>:<httpPort>/songs/<percent-encoded-relative-path>`.

Range requests MUST be supported for all audio and video responses, including phone-generated mixed playback resources:
- `Accept-Ranges: bytes` on all audio/video responses.
- `206 Partial Content` with correct `Content-Range` when `Range` is received.
- `Content-Length` MUST be set on all responses.

Path traversal attempts (e.g., `../etc/passwd`) MUST return 404.

### Internal Asset Resolution (Normative)

The HTTP server maintains scan-owned metadata for static assets and session-owned metadata for any generated playback resources. Request-path resolution MUST map a requested relative path to exactly one of:
- a scanned static asset (`relativePath → platformURI`), or
- a generated playback resource owned by the current session.

Generated playback resources MUST be addressed only through the reserved `generated/` relative-path namespace. A generated request path MUST NOT alias any scanned static asset path.

`java.io.File(path)` MUST NOT be used on Android 10+ scoped storage.

### SAF File Reads (Android)

```kotlin
// File reads via ContentResolver (not java.io.File)
contentResolver.openAssetFileDescriptor(uri, "r")
contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), ...)

// Cloud file check: if SIZE=0 or null, treat as absent
```

Ktor's `ktor-server-partial-content` plugin handles `Accept-Ranges` / `206 Partial Content` automatically when the response body is a `ByteReadChannel`.

### Security-Scoped Reads (iOS)

```swift
url.startAccessingSecurityScopedResource()
NSFileCoordinator().coordinate(readingItemAt: fileURL, options: .withoutChanges) { ... }
url.stopAccessingSecurityScopedResource()

// iCloud check: ubiquitousItemDownloadingStatus == .current
```

All file reads MUST go through `NSFileCoordinator` to prevent conflicts with the iCloud sync daemon. Range requests: parse `Range: bytes=X-Y` manually, open `FileHandle`, `seek(toOffset: offset)`, `read(upToCount: length)`.

### iCloud Drive Files (iOS — Normative)

Before including a file URL in `SongEntry`, check:
```swift
(try? fileURL.resourceValues(forKeys: [.ubiquitousItemDownloadingStatusKey]))?
    .ubiquitousItemDownloadingStatus == .current
```
If not `.current`, treat as absent. Call `FileManager.default.startDownloadingUbiquitousItem(at:)` as background hint only — do not block.

### iOS Idle Timer (Normative)

`UIApplication.shared.isIdleTimerDisabled` MUST be set to `true` for the session duration. Reset to `false` on session end.

### iOS Backgrounding Limitation (Normative)

iOS may suspend the process ~30 seconds after backgrounding, terminating the HTTP server socket. Users must keep the phone app in the foreground during a song. Show "Keep app in foreground" banner when singing or serving.

### Phone-Side Audio Mixing (Normative)

When a song has both `#INSTRUMENTAL` and `#VOCALS` files with matching decoded sample rate and channel count, the phone MUST generate a single mixed WAV playback resource and expose it as the effective `audioUrl`.

#### Mix Decision Rules

A song is eligible for mixing if and only if:
1. `#INSTRUMENTAL` resolves to a local file
2. `#VOCALS` resolves to a local file
3. Both files decode to the **same sample rate** (e.g., 44100 Hz or 48000 Hz)
4. Both files have the **same channel count** (1 = mono, 2 = stereo)

Differing compressed bitrates (e.g., 128 kbps vs 320 kbps) are allowed and do not affect eligibility.

If any condition fails, fall back to the base `#AUDIO` or `#MP3` asset and emit a warn diagnostic.

#### Generated Resource Lifecycle

1. **Scan time**: Store relative paths for `#INSTRUMENTAL` and `#VOCALS`; determine eligibility; record in scan metadata
2. **Manifest construction**: If eligible, set `audioUrl` to `/songs/generated/<relativeTxtPath-with-.txt-replaced-by-.wav>`
3. **First GET request**: Decode both MP3s, mix to WAV, cache in memory
4. **Subsequent requests**: Serve from cache
5. **Song end or session leave**: Discard cached WAV

#### Android Mixing Implementation

**Decoding library**: `MediaCodec` + `MediaExtractor` (Android SDK, API 21+)

**Algorithm**:
```kotlin
// 1. Extract metadata
val instrumentalExtractor = MediaExtractor().apply { setDataSource(context, instrumentalUri, null) }
val vocalsExtractor = MediaExtractor().apply { setDataSource(context, vocalsUri, null) }

val format1 = instrumentalExtractor.getTrackFormat(0)
val format2 = vocalsExtractor.getTrackFormat(0)

val sampleRate = format1.getInteger(MediaFormat.KEY_SAMPLE_RATE)
val channels = format1.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
val durationUs = min(format1.getLong(MediaFormat.KEY_DURATION), format2.getLong(MediaFormat.KEY_DURATION))

// Eligibility check
if (sampleRate != format2.getInteger(MediaFormat.KEY_SAMPLE_RATE) ||
    channels != format2.getInteger(MediaFormat.KEY_CHANNEL_COUNT)) {
    // Fall back to base audio
}

// 2. Decode to PCM
val decoder1 = MediaCodec.createDecoderByType(format1.getString(MediaFormat.KEY_MIME)!!)
val decoder2 = MediaCodec.createDecoderByType(format2.getString(MediaFormat.KEY_MIME)!!)

decoder1.configure(format1, null, null, 0)
decoder2.configure(format2, null, null, 0)

decoder1.start()
decoder2.start()

val pcm1 = mutableListOf<ShortArray>()
val pcm2 = mutableListOf<ShortArray>()

// Decode loop (standard MediaCodec pattern, omitted for brevity)
// Output: List<ShortArray> of PCM16 samples

// 3. Mix: sample-by-sample addition with clipping
val mixed = ShortArray(pcm1.sumOf { it.size })
var writeIdx = 0
for (chunkIdx in pcm1.indices) {
    val chunk1 = pcm1[chunkIdx]
    val chunk2 = pcm2.getOrNull(chunkIdx) ?: ShortArray(chunk1.size) // pad if unequal
    for (i in chunk1.indices) {
        val sum = chunk1[i].toInt() + chunk2[i].toInt()
        mixed[writeIdx++] = sum.coerceIn(Short.MIN_VALUE.toInt(), Short.MAX_VALUE.toInt()).toShort()
    }
}

// 4. Write WAV header + PCM data
val wavBytes = buildWavFile(mixed, sampleRate, channels)
```

**WAV Header Format** (RIFF/WAV PCM16LE, 44 bytes):
```
Offset | Bytes | Value
-------|-------|------
0      | 4     | "RIFF" (0x52494646)
4      | 4     | fileSize - 8 (little-endian uint32)
8      | 4     | "WAVE" (0x57415645)
12     | 4     | "fmt " (0x666d7420)
16     | 4     | 16 (subchunk1 size, LE uint32)
20     | 2     | 1 (audio format = PCM, LE uint16)
22     | 2     | channels (1 or 2, LE uint16)
24     | 4     | sampleRate (LE uint32)
28     | 4     | sampleRate * channels * 2 (byte rate, LE uint32)
32     | 2     | channels * 2 (block align, LE uint16)
34     | 2     | 16 (bits per sample, LE uint16)
36     | 4     | "data" (0x64617461)
40     | 4     | pcmDataSize in bytes (LE uint32)
44     | N     | PCM samples (shorts in LE byte order)
```

**Caching**: LRU in-memory cache, max 3 songs (~90 MB for three 3-minute stereo 48kHz WAVs). Evict least-recently-used on 4th song.

**Timing**: First request decodes both files (~2-3s on mid-tier 2022 hardware), subsequent requests <100ms from cache.

#### iOS Mixing Implementation

**Decoding library**: `AVAssetReader` + `AVAssetReaderTrackOutput` (iOS SDK)

**Algorithm**:
```swift
let asset1 = AVURLAsset(url: instrumentalURL)
let asset2 = AVURLAsset(url: vocalsURL)

let track1 = asset1.tracks(withMediaType: .audio)[0]
let track2 = asset2.tracks(withMediaType: .audio)[0]

let format1 = track1.formatDescriptions[0] as! CMAudioFormatDescription
let format2 = track2.formatDescriptions[0] as! CMAudioFormatDescription

let asbd1 = CMAudioFormatDescriptionGetStreamBasicDescription(format1)!.pointee
let asbd2 = CMAudioFormatDescriptionGetStreamBasicDescription(format2)!.pointee

// Eligibility check
guard asbd1.mSampleRate == asbd2.mSampleRate,
      asbd1.mChannelsPerFrame == asbd2.mChannelsPerFrame else {
    // Fall back
}

let reader1 = try AVAssetReader(asset: asset1)
let reader2 = try AVAssetReader(asset: asset2)

let outputSettings: [String: Any] = [
    AVFormatIDKey: kAudioFormatLinearPCM,
    AVLinearPCMBitDepthKey: 16,
    AVLinearPCMIsNonInterleaved: false,
    AVLinearPCMIsFloatKey: false,
    AVLinearPCMIsBigEndianKey: false
]

let output1 = AVAssetReaderTrackOutput(track: track1, outputSettings: outputSettings)
let output2 = AVAssetReaderTrackOutput(track: track2, outputSettings: outputSettings)

reader1.add(output1)
reader2.add(output2)

reader1.startReading()
reader2.startReading()

var pcm1: [Int16] = []
var pcm2: [Int16] = []

while reader1.status == .reading {
    if let buffer = output1.copyNextSampleBuffer() {
        let blockBuffer = CMSampleBufferGetDataBuffer(buffer)!
        var length: Int = 0
        var dataPtr: UnsafeMutablePointer<Int8>?
        CMBlockBufferGetDataPointer(blockBuffer, atOffset: 0, lengthAtOffsetOut: nil, totalLengthOut: &length, dataPointerOut: &dataPtr)
        let shorts = dataPtr!.withMemoryRebound(to: Int16.self, capacity: length / 2) { Array(UnsafeBufferPointer(start: $0, count: length / 2)) }
        pcm1.append(contentsOf: shorts)
    }
}

// Same for pcm2

// Mix
var mixed: [Int16] = []
for i in 0..<min(pcm1.count, pcm2.count) {
    let sum = Int32(pcm1[i]) + Int32(pcm2[i])
    mixed.append(Int16(clamping: sum))
}

// Write WAV (same header format as Android)
```

**Caching**: Same LRU strategy as Android.

#### Range Request Support

Generated WAV responses MUST support HTTP Range requests. The cached WAV byte array includes the 44-byte header + PCM data. For a range request:

```
Range: bytes=100000-200000

1. Validate range against total WAV size
2. If valid, respond with:
   Status: 206 Partial Content
   Content-Range: bytes 100000-200000/<totalSize>
   Content-Length: 100001
   Body: wavBytes[100000..200000]
```

#### Determinism Requirement

For a given `#INSTRUMENTAL` + `#VOCALS` pair and fixed mix parameters, the generated WAV MUST be byte-identical across requests. This ensures correct `Content-Length` and allows LibVLC to cache byte ranges.

#### SLA Update

| Metric | Limit | Test |
|--------|-------|------|
| First byte (uncached mix) | ≤3s | F18 + timing wrapper |
| First byte (cached) | ≤100ms | F18 |
| Mix determinism | Exact byte identity | F01/`d/mix_pair_same_rate_channels` repeated GET |

### Tests (Normative)

| ID | What | Fixture | Expected |
|---|---|---|---|
| T8.7.1 | Full file request (no `Range`) | F18 | 200, `Content-Length` set |
| T8.7.2 | Partial range `bytes=0-99` | F18 | 206, correct `Content-Range`, 100 bytes |
| T8.7.3 | Open-ended range `bytes=9500-` | F18 | 206, bytes from offset to EOF |
| T8.7.4 | `Accept-Ranges: bytes` header | F18 | Header present |
| T8.7.5 | Unsatisfiable range | `inline` | 416 |
| T8.7.7 | Percent-encoded path decoded | `inline` | 200 |
| T8.7.8 | Path traversal blocked | `inline` | 404 |
| T8.7.9 | Server starts before `hello` | `inline` [I] | `httpPort` reachable |
| T8.7.10 | Default port busy → ephemeral fallback | `inline` [I] | Actual bound port reported |
| T8.7.10a | Manifest rebuilt after bound-port change | `inline` [I] | Published `audioUrl`/`txtUrl` use actual bound port |
| T8.7.10b | Published host uses active WebSocket local address | `inline` [I] | Published manifest URLs use the local socket address of the TV connection |
| T8.7.10c | Generated playback path is reserved and ends in `.wav` | F01/`d/mix_pair_same_rate_channels` | `audioUrl` path is under `/songs/generated/` and ends in `.wav` |
| T8.7.11 | iCloud evicted file → `audioUrl=null` (iOS) | F19 | `audioUrl=null`, `coverUrl` present |
| T8.7.12 | Mix with matching sample rate/channels | F01/`d/mix_pair_same_rate_channels` | Generates WAV, serves under `/songs/generated/` |
| T8.7.13 | Mix with mismatched sample rate | F01/`d/mix_pair_mismatched_sample_rate` | Falls back to base audio, warn emitted |
| T8.7.14 | Mix with mismatched channels | F01/`d/mix_pair_mismatched_channels` | Falls back to base audio, warn emitted |
| T8.7.15 | Generated WAV has correct RIFF header | F01/`d/mix_pair_same_rate_channels` | Bytes 0-3 = "RIFF", 8-11 = "WAVE", format = PCM16LE |
| T8.7.16 | Generated WAV Range request | F01/`d/mix_pair_same_rate_channels` | Subsequent Range request returns correct subset |
| T8.7.17 | Cache eviction (4th song) | `inline` [I] | LRU evicted, 4th song decoded fresh |

**Source**: §8.7.1, §8.7.2, §8.7.3

**NFRs**: 1.3 (HTTP throughput), 1.2 (reliability)

**Acceptance**: F18, F19, F01

---

## 2.3 PitchDetector

**Responsibility**: Capture mic audio and extract MIDI pitch at 50fps.

**Lifecycle**:
- Warms up on `assignSinger`
- Active during countdown (no frames sent) and singing (frames sent)
- Stops on `playbackState.stopped`

**Functional Boundary**:
- Mic capture at 44100Hz, 1024 samples/window (~23ms)
- FFT-YIN pitch detection (§5.2.5)
- Voicing gate + sensitivity presets (0-7)
- 3-frame median filter
- Outputs `midiNote` (0-127 or 255)

**L2 Visible Shapes**:
- `MicCapture` — AudioRecord (Android) / AVAudioEngine (iOS)
- `FftYinPipeline` — zero-allocation FFT, autocorrelation, d' computation
- `MedianFilter` — 3-byte circular buffer
- `SensitivityTable` — 8 presets from §5.2.5.3

### Pre-Allocated Buffers (Normative)

All buffers allocated once at init, reused every frame (zero GC):

| Buffer | Size | Purpose |
|--------|------|---------|
| `audioBuffer` | 1024 floats | Raw PCM input |
| `paddedBuffer` | 2048 floats | Zero-padded FFT input |
| `fftComplexBuffer` | 4096 floats | In-place FFT (interleaved real/imag) |
| `diffBuffer` | 1024 floats | d_t difference function |
| `normBuffer` | 1024 floats | d' normalized function |
| `medianHistory` | 3 bytes | Temporal smoothing |

### Algorithm Pipeline (Normative)

**Step 1: Voicing Gate**
```
maxAmp = max(abs(audioBuffer[i])) for i in 0..1023
if maxAmp < sensitivityTable[index].maxAmpCutoff:
    rawMidiNote = 255  // skip Steps 2-4
```

**Step 2: Linear Autocorrelation via FFT**
1. Zero-pad: copy audioBuffer to paddedBuffer[0..1023], fill [1024..2047] with 0
2. Forward FFT in-place
3. Power spectrum: `Re² + Im²`, zero imaginary
4. Inverse FFT: first 1024 reals = `r_t(tau)`

**Step 3: Squared Difference and Normalization**
```
d_t(tau) = E_start + E_shift(tau) - 2 * r_t(tau)
d'(0) = 1.0
d'(tau) = d_t(tau) / ((1/tau) * sum(d_t(1..tau)))
```

**Step 4: Candidate Selection**
- Find first local minimum where `d'(tau) < dPrimeCutoff`
- If none, use absolute minimum
- If `d'(tau) > 0.40`: unvoiced
- Else: `hz = 44100 / tau`, `rawMidiNote = clamp(round(69 + 12*log2(hz/440)), 0, 127)`

**Step 5: Temporal Smoothing**
- 3-frame rolling median
- If any of 3 frames is 255: output 255 (silence breaks combo)

### maxAmp Normalization (Normative)

- 16-bit signed PCM input: `maxAmp = clamp(max(abs(sample_i)) / 32768.0, 0, 1)`
- Float PCM input in [−1..1]: `maxAmp = clamp(max(abs(sample_i)), 0, 1)`

### Sensitivity Table

| Index | maxAmpCutoff | dPrimeCutoff | Environment |
|-------|--------------|--------------|-------------|
| 0 | 0.01 | 0.10 | Whisper/Studio |
| 1 | 0.02 | 0.15 | High Sensitivity |
| 2 | 0.04 | 0.20 | Medium-High |
| **3** | **0.06** | **0.25** | **Default (Karaoke Room)** |
| 4 | 0.09 | 0.30 | Noisy Room |
| 5 | 0.13 | 0.35 | Low |
| 6 | 0.18 | 0.40 | Loud Party |
| 7 | 0.25 | 0.45 | Extreme Noise |

The `sensitivityIndex` (0–7) is sourced from the phone Settings **Mic Sensitivity** control (§7.3.5).

### Frame Rate (Normative)

Pitch frames MUST be sent at **50 fps** (20 ms). Frames MUST NOT be batched.

### Frame Drop Rules (Normative)

- Do not send frames with decreasing `seq`.
- When `startMode == "countdown"`: do not send frames until the countdown completes. The phone MAY warm up pitch detection locally during this period.
- The phone MUST NOT send `pitchFrame` datagrams unless current-session `clockOffsetMs` is available.

### Mute Behavior (Normative)

When mute is enabled, continue capturing audio (for VU meter display) but set `midiNote = 255` in all transmitted frames.

### Phone Authority Boundary (Normative)

Phones MUST NOT send any computed scoring, judgement, combo, or rating values. Phones send only DSP-derived observations. `toneValid` is implicit: `toneValid = (midiNote != 255)`.

### Tests (Normative)

| ID | What | Fixture | Expected |
|---|---|---|---|
| T5.2.5.1 | Pure A4 sine → MIDI 69 | F17/`A4_Pure_Sine` | `midiNote=69` |
| T5.2.5.2 | Amplitude below index=3 → unvoiced | F17/`Below_Threshold_Index_3` | `midiNote=255` |
| T5.2.5.3 | Median filter: silence interrupts combo | F17/`Median_Filter_Stabilization` | `midiNote=255` |
| T5.2.5.4 | Zero-padded FFT produces linear autocorrelation | `inline` | paddedBuffer second half zeros |
| T5.2.5.5 | `d'(0) = 1.0` always | `inline` | normBuffer[0] == 1.0 |

**Source**: §5.2.5, §8.6.2

**NFRs**: 1.1 (pitch latency - CRITICAL), 1.6 (battery)

**Acceptance**: F17

---

## 2.4 NetworkClient

**Responsibility**: All network communication with TV.

**Lifecycle**:
- Starts on join (QR or code)
- Maintains WebSocket for session
- Handles reconnect

**Functional Boundary**:
- mDNS/NSD discovery for manual code
- QR payload parsing
- WebSocket client (hello, sessionState, ping/pong, assignSinger, playbackState, error)
- UDP sender (20-byte pitch frames)

**L2 Visible Shapes**:
- `ServiceDiscovery` — NSD (Android) / NWBrowser (iOS)
- `WebSocketClient` — OkHttp (Android) / URLSessionWebSocketTask (iOS)
- `UdpSender` — DatagramSocket (Android) / NWConnection (iOS)
- `MessageCodec` — JSON serialization
- `PitchFrameEncoder` — 20-byte binary encoding

### Transport Channels (Normative)

- **WebSocket** (control): `ws://<host-ip>:<port>/?token=<sessionToken>`. Messages: `hello`, `sessionState`, `ping`, `pong`, `clockAck`, `assignSinger`, `playbackState`, `error`.
- **HTTP** (song delivery): phone runs read-only HTTP server on `httpPort`. See §2.2.
- **UDP** (pitch): `pitchFrame` datagrams to `<tv-ip>:<udpPort>`. Port from `assignSinger.udpPort`.

### Pitch Frame Wire Format (20 bytes, little-endian)

```
Offset  Size  Type     Field
  0      4    uint32   seq              — frame counter
  4      8    int64    tvTimeMs         — phone's estimate of TV monotonic ms
 12      4    uint32   songInstanceSeq  — from assignSinger
 16      1    uint8    playerId         — 0=P1, 1=P2
 17      1    uint8    midiNote         — 0-127 voiced, 255=unvoiced
 18      2    uint16   connectionId     — from sessionState
```

Struct format: `<IqIBBH`.

### Session Token / Join Code (Normative)

Two random English words (Adjective-Noun) drawn from bundled TV-side wordlists, uppercase hyphen-separated: e.g. `SWIFT-PANDA`. Provides ~18 bits of entropy — sufficient for accidental-join prevention on a LAN. Generated by the TV per session; the phone receives and displays it.

Phone normalization for manual entry: strip hyphens, case-insensitive (`SWIFT-PANDA` = `swiftpanda` = `swift-panda`).

### QR Payload Format (Normative)

Encodes the full WebSocket endpoint URL: `ws://<tv-ip>:<ws-port>/?token=SWIFT-PANDA`.

### mDNS Discovery (Manual Code Entry)

1. Normalize input: strip hyphens, uppercase
2. Browse `_karaoke._tcp`
3. Match TXT field `code` against normalized input
4. Connect to matching service's host:port
5. Timeout: 5 seconds → "TV not found"

If two TVs advertise the same code, prompt user to select by instance name.

**Android**: Acquire `WifiManager.MulticastLock` during browse.

**iOS**: No explicit multicast lock required. OS handles multicast via `Network.framework` (`NWBrowser`).

### connectionId Semantics (Normative)

- Assigned at `hello` via `sessionState`, stored by the phone.
- Embedded in every UDP `pitchFrame` (bytes 18–19).
- `connectionId` is **absent** from `assignSinger` — delivered only via `sessionState`.
- On reconnect: TV assigns a **new** `connectionId`. Phone MUST use new value; old frames silently dropped.

### Control Message Schemas (Normative)

All messages: JSON objects, `type` (string), `protocolVersion` (int, MUST be `1`), `tsTvMs` (optional).

**`hello`** (Phone → TV): `clientId` (stable UUID, min 8 chars), `deviceName`, `appVersion`, `httpPort` (1024–65535).
- `clientId` is the phone's stable protocol identity and authority key across rejoins. Any identity comparison for reconnect, source-phone selection, or session ownership MUST use `clientId`, never `deviceName`.
- `deviceName` is the phone's persisted human-readable label for TV display. It MUST be generated locally on first launch, kept stable across rejoins, and MAY use a bundled funny/geeky adjective-name scheme such as `jumping-gazelle` or `recursive-octopus`.
- `deviceName` is display-only. It is not required to be globally unique and MUST NOT be used as a protocol identity key.

**`sessionState`** (TV → Phone): `sessionId`, `slots { P1: { connected, deviceName }, P2: { connected, deviceName } }`, `inSong`, `songTimeSec` (float|null), `connectionId` (present only in initial response to hello; null in broadcasts).
- `sessionState.inSong=false` is the authoritative session-level signal that the phone MUST leave singing mode, clear active-song UI/state, and release any runtime-only source-phone indicators even if the last `playbackState` was `countdown`, `playing`, `paused`, or `stopped`.

**`assignSinger`** (TV → Phone): `sessionId`, `songInstanceSeq` (uint32), `playerId` (`"P1"`/`"P2"`), `difficulty` (`"Easy"`/`"Medium"`/`"Hard"`), `startMode` (`"countdown"`/`"live"`), `countdownMs` (int|null), `stopAtLyricsTimeMs` (int), `udpPort` (int), `songTitle`, `songArtist`.

**`stopAtLyricsTimeMs` computation**: normal song: if `#END` present and > 0, use `endMs`; otherwise `audioDurationMs`. Medley: lyrics-time ms at end of final segment fade-out. MUST be recomputed on Restart or reconnect.

**`playbackState`** (TV → Phone): `sessionId`, `songInstanceSeq`, `revision` (monotonically increasing per songInstanceSeq), `state` (`"countdown"`/`"playing"`/`"paused"`/`"stopped"`), `lyricsTimeMs`, `stopAtLyricsTimeMs`, `countdownRemainingMs` (int|null, present only when `state="countdown"`; omitted otherwise), `reason` (`""`/`"user_pause"`/`"singer_disconnected"`/`"song_end"`/`"user_quit"`/`"restart"`/`"segment_transition"`/`"medley_source"`/`"medley_end"`), `tsTvMs`.

Phones MUST ignore any `playbackState` with a lower `revision` than the last accepted message for the same `songInstanceSeq`. Once received for current `songInstanceSeq`, `playbackState` is authoritative for phone UI state.

**`error`** (TV → Phone): `code`, `message`. Codes: `invalid_token`, `protocol_mismatch`, `session_full`, `session_locked`. Unknown codes displayed as generic error.

### Message Validation Rules (Normative)

- Unknown `type`: ignore and warn. Exception: during handshake, unexpected type is fatal.
- `protocolVersion` mismatch: TV sends `error(code="protocol_mismatch")` and closes.

### Required Permissions (Android)

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />
<uses-permission android:name="android.permission.NEARBY_WIFI_DEVICES" android:usesPermissionFlags="neverForLocation" />
```

### Required Network Security Config (Android)

MVP transport uses LAN-local cleartext `http://` and `ws://` endpoints between phone and TV. Android builds MUST opt in explicitly for this traffic class; loopback-only exceptions are not sufficient for LAN device IPs.

Minimum requirement:
- declare `android:networkSecurityConfig="@xml/network_security_config"` on the application
- permit cleartext traffic for the LAN endpoints used by the TV during MVP
- do not rely on localhost-only behavior for `192.168.x.x` / `10.x.x.x` / `.local` device targets

### Required Plist (iOS)

```xml
<key>NSLocalNetworkUsageDescription</key>
<key>NSBonjourServices</key><array><string>_karaoke._tcp</string></array>
<key>NSCameraUsageDescription</key>
<key>NSMicrophoneUsageDescription</key>
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsLocalNetworking</key>
    <true/>
</dict>
```

`NSAllowsLocalNetworking` covers MVP LAN-local `http://` / `ws://` access to `.local`, unqualified, and local IP-address endpoints without broadly disabling ATS.

**Source**: §8.1, §8.2, §8.3, §8.5, §8.6

**NFRs**: 1.1 (pitch latency), 1.2 (reliability)

**Acceptance**: F12v2, F15, F20

---

## 2.5 ClockSync

**Responsibility**: Compute and maintain `clockOffsetMs` to estimate TV time.

**Lifecycle**:
- 5 exchanges on connect (100ms apart)
- Suspend during singing
- Resume on song end or reconnect
- Provides offset for frame `tvTimeMs`

**Functional Boundary**:
- Responds to `ping` with `pong`
- Processes `clockAck` to compute offset
- Best-of-N selection (smallest RTT)
- `toTvTime()` conversion

**L2 Visible Shapes**:
- `ClockSample` — t1, t2, t3, t4, RTT, offset
- `SampleBuffer` — 5-sample ring
- `BestOfNSelector` — picks lowest RTT

### Clock Model (Normative)

Phone and TV clocks are independent monotonic timers. The phone maintains:

```
tvTimeEstMs = phoneMonotonicMs + clockOffsetMs
```

Clock sync is always **TV-initiated**. The phone does not initiate sync. `clockAck` closes the loop — without it, the phone cannot compute `clockOffsetMs`.

`clockOffsetMs` is valid only for the phone's current TV session and active control connection. The phone MUST discard cached `clockOffsetMs` on reconnect, on any observed `sessionId` change, and whenever it returns to Join after leave, kick, or token rejection.

### Clock Sync Protocol

```
TV ──ping(pingId, tTvSendMs)──► Phone
              │
              ▼
         record t2 = phoneMonotonicMs at receipt
         record t3 = phoneMonotonicMs at send
              │
Phone ──pong(pingId, tTvSendMs, tPhoneRecvMs, tPhoneSendMs)──► TV
              │
              ▼
TV ──clockAck(pingId, tTvRecvMs)──► Phone
```

### Per-Sample Computation (Phone)

```
t1 = tTvSendMs      (from ping, echoed)
t2 = tPhoneRecvMs   (phone's record)
t3 = tPhoneSendMs   (phone's record)
t4 = tTvRecvMs      (from clockAck)

RTT = (t4 - t1) - (t3 - t2)
clockOffsetMs = ((t2 - t1) + (t3 - t4)) / 2
```

### Sample Selection

- Keep last 5 samples
- Discard if `RTT < 0` or `RTT > 2000`
- Use sample with smallest RTT

### TV Time Estimation

```kotlin
fun toTvTime(phoneMonotonicMs: Long): Long = phoneMonotonicMs + clockOffsetMs
```

### Tests (Normative)

| ID | What | Fixture | Expected |
|---|---|---|---|
| T8.8.1 | Per-sample computation | F14v2 | All 3 samples match to 0.5ms |
| T8.8.2 | Best-of-N: smallest RTT | F14v2 | `chosen.pingId="a3"` (RTT=30) |
| T8.8.3 | Invalid RTT discarded | `inline` | Not chosen |
| T8.8.4 | `tvTimeMs` estimation | `inline` | `clockOffsetMs=-500`, `phoneMonotonicMs=2000` → `tvTimeMs=1500` |

**Source**: §8.8

**NFRs**: 1.1 (pitch latency)

**Acceptance**: F14v2

---

## 2.6 SessionCoordinator

**Responsibility**: Orchestrate phone state and coordinate components.

**Lifecycle**: App lifetime.

**Functional Boundary**:
- Phone state FSM: Disconnected → Connecting → Connected(Spectator|Singer)
- Routes incoming messages
- Triggers scan on folder change when the session is not currently serving current-song media and the phone is not active in-song
- Starts/stops pitch detection on assignSinger/playbackState
- Materializes and publishes generated mixed playback resources on first request, or earlier if already known locally, when the current song's effective `audioUrl` requires phone-side mixing
- Discards session-owned generated playback resources when the song ends, restarts, or the session is left
- Exposes `StateFlow<PhoneState>` for UI

**L2 Visible Shapes**:
- `PhoneStateMachine` — transitions + guards
- `MessageRouter` — dispatches WebSocket messages
- `ReconnectPolicy` — 5x immediate + exponential backoff

### Phone Screen States (Normative)

1. **Join screen**: not connected.
2. **Waiting/Connected screen**: connected as Spectator, or after song end.
3. **Active Mic screen**: assigned as Singer, during countdown and singing.

### Join Screen (Normative)

Two ways to join: **Scan QR** (camera-based) and manual **enter code** (mDNS-based). Exposes **Settings** and connection status.

If camera permission denied (including "Don't ask again"), return to Join and show blocking error modal.

Manual code entry uses mDNS: browse `_karaoke._tcp`, match `code` TXT field, connect. 5s timeout → `TV not found. Make sure your phone is on the same Wi-Fi network.`

**Wireframe (Join screen)**
```text
+----------------------------------+
| JOIN SESSION                      |
+----------------------------------+
| [Scan QR]                         |
| or enter code: [ SWIFT-PANDA ] [Join]|
|                                  |
| Status: Disconnected              |
| [Settings]                        |
+----------------------------------+
```

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
|    (to connect to the TV on LAN)  |
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

### Waiting/Connected Screen (Normative)

Displays: connection state, assigned role (Singer/Spectator + P1/P2), live VU meter, **Mute** toggle, **Leave session**, **Settings**.

Medley-source indicator: when `playbackState(state="playing", reason="medley_source")` is received, show `Your songs are in use — keep app open`. Visible until `state="stopped"` or `sessionState.inSong=false`.

When current-session state indicates that the phone is serving current-song media, **Rescan now** and **Change folder** controls MUST be disabled.

After song end, phone returns here automatically. No score displayed on phone; results are TV-only.

**Wireframe (Waiting/Connected — Spectator)**
```text
+----------------------------------+
| CONNECTED                         |
+----------------------------------+
| Role: Spectator                   |
| Input level:  |||||||             |
| Mute: [OFF]                       |
|                                  |
| [Settings]   [Leave session]      |
+----------------------------------+
```

### Active Mic Screen (Normative)

Shown on `assignSinger`. Phone MUST trigger a short haptic vibration (~200ms). Displays: role badge (Singer P1/P2), large countdown number during countdown, live VU meter, **Mute** toggle.

Mic warms up during countdown but no frames are sent until countdown completes and current-session clock sync is available.

When `stopAtLyricsTimeMs` reached or `playbackState.state == "stopped"`, phone stops pitch detection and transitions to Waiting/Connected.

**Active Mic exit policy**: MUST NOT display Leave/Back during active song. Hardware Back key MUST be suppressed. Users must background the app to exit.

**Wireframe (Active Mic — countdown)**
```text
+----------------------------------+
| SINGER P1                         |
+----------------------------------+
|                                  |
|              3                    |
|                                  |
| Input level:  |||||||||           |
| Mute: [OFF]                       |
+----------------------------------+
```

**Wireframe (Active Mic — singing)**
```text
+----------------------------------+
| SINGER P1                         |
+----------------------------------+
| Input level:  |||||||||           |
| Mute: [OFF]                       |
+----------------------------------+
```

### Phone Settings Screen (Normative)

Accessible from Join screen and Waiting/Connected screen.

- **Songs folder**: current path; change triggers rescan and manifest update when allowed.
- **Rescan now**: manual rescan when allowed.
- **Mic Sensitivity**: range 0–7, source for pitch detector.
- **Song count**: read-only (valid / invalid).

Songs folder SHOULD default to a well-known location (e.g., `Downloads/Songs/`).

Rescan and folder-change operations are allowed while disconnected or connected-idle. They MUST be blocked while the phone is actively serving current-song media or while the phone is in the Active Mic screen. "Actively serving current-song media" means the current session has not yet emitted authoritative exit via `sessionState.inSong=false` and the phone is serving HTTP requests for song assets needed by the current song or medley run. The UI MUST disable those controls in blocked states, and any attempted programmatic call to `rescan()` or `setFolder()` in a blocked state MUST fail without mutating the current scan snapshot.

**Wireframe (Settings)**
```text
+----------------------------------+
| SETTINGS                          |
+----------------------------------+
| Songs folder:                     |
|   /storage/Downloads/Songs        |
|   [Change folder]                 |
|                                   |
| Mic Sensitivity: [==|------]  2   |
| Song count:  423 valid / 2 invalid|
| [Rescan now]                      |
+----------------------------------+
```

### Leave Session (Normative)

MUST: close WebSocket, return to Join screen, clear cached endpoint. No auto-reconnect after leave. Phone SHOULD reuse `clientId` on rejoin.

### Join Rejection UX (Normative)

Show blocking error message and return to Join screen.

**Wireframe (phone join rejected)**
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

### Disconnect/Reconnect Mechanics (Normative)

- **Transport disconnect** (network drop, backgrounded): auto-reconnect with same `clientId`. Show `Reconnecting`. No QR/code rescan.
- **User-initiated leave**: return to Join, clear endpoint, no auto-reconnect.
- **Host kick/forget**: return to Join, clear endpoint.

On reconnect: send same `clientId`, clear cached `clockOffsetMs`, TV assigns new `connectionId`, re-sends `assignSinger` with recomputed `stopAtLyricsTimeMs`, sends current `playbackState`, and performs a fresh clock-sync exchange.

If phone was Singer when disconnected, it resumes that role only after fresh clock sync completes (unless TV has kicked/forgotten).

### Song End Behavior — Phone (Normative)

When `stopAtLyricsTimeMs` reached or `playbackState.state == "stopped"`, the phone MUST: stop audio capture and pitch detection, stop transmitting `pitchFrame` datagrams for that `songInstanceSeq`, transition to Waiting/Connected screen.

**Source**: §7.1–§7.4, §9.5

**NFRs**: 1.2 (reliability)

**Acceptance**: F15

---

## 2.7 UI Layer

**Responsibility**: All screens, navigation, theme. Observes state from other components. Emits user intents.

**Lifecycle**: Standard platform app lifecycle (Android Activity/iOS UIViewController).

### Entry Point and Wiring (Normative)

**Android Entry Point**: `MainActivity` is the single Activity. Uses Jetpack Compose.

```kotlin
@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            CouchraokePhoneTheme {
                AppNavHost()
            }
        }
    }
}
```

**iOS Entry Point**: SwiftUI `App` with single `WindowGroup`.

```swift
@main
struct CouchraokePhoneApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
```

**Theme**: Material Design 3 (Android) / iOS Human Interface Guidelines (iOS).

**Navigation**: 
- Android: `androidx.navigation:navigation-compose`
- iOS: NavigationStack

**Dependency injection**:
- Android: Hilt (`@HiltAndroidApp`, `@AndroidEntryPoint`)
- iOS: Environment Objects or manual DI

**Library versions** (Android):

| Artifact | Version |
|---|---|
| `androidx.navigation:navigation-compose` | `2.8.x` |
| `com.google.dagger:hilt-android` | `2.51.x` |
| `androidx.compose.material3:material3` | `1.3.x` |
| `androidx.camera:camera-camera2` | `1.4.x` |
| `com.google.mlkit:barcode-scanning` | `17.3.x` |

**Library versions** (iOS):

| Artifact | Version |
|---|---|
| Swifter | `1.5.0` |
| SwiftUI | Built-in (iOS 15+) |

### 2.7.1 Design System

#### Color Scheme

**Android** (Material Design 3 Dynamic Color):
- Primary: `Color(0xFF6750A4)` light / `Color(0xFFD0BCFF)` dark
- Surface: `Color(0xFFFFFBFE)` light / `Color(0xFF1C1B1F)` dark
- Error: `Color(0xFFB3261E)` light / `Color(0xFFF2B8B5)` dark

**iOS** (System colors):
- Primary: `.accent`
- Background: `.systemBackground`
- Error: `.systemRed`

#### Typography

**Android**:
- Headline Large: 32sp bold
- Title Large: 22sp semibold
- Body Large: 16sp regular
- Label Large: 14sp medium

**iOS**:
- Large Title: 34pt bold
- Title: 28pt semibold
- Body: 17pt regular
- Caption: 12pt regular

#### Spacing

8pt grid: `4dp`, `8dp`, `16dp`, `24dp` (screen padding), `32dp`

#### Components

- **Buttons**: Filled (primary), Outlined (secondary), Text
- **Text fields**: OutlinedTextField (Android) / TextField with border (iOS)
- **Cards**: 12dp/pt corner radius, elevation 1
- **VU Meter**: 8dp/pt height horizontal bar, primary color, animated

### 2.7.2 Screen Specifications

#### Join Screen

**State**: Disconnected

**Layout**:
```
┌────────────────────────┐
│  Couchraoke            │
│                        │
│  [Scan QR Code]        │
│                        │
│  — or —                │
│                        │
│  Enter code:           │
│  [SWIFT-PANDA ] [Join]│
│                        │
│  [Settings]            │
└────────────────────────┘
```

**Behavior**:
- **Scan QR**: Opens camera, parses `ws://...` payload, connects
- **Manual code**: mDNS browse for 5s → connect or "TV not found" error
- **Settings**: Navigate to Settings screen

**Camera**: CameraX + MLKit (Android) / AVCaptureSession + Vision (iOS)

#### Waiting/Connected Screen

**State**: Connected as Spectator or Singer (not singing)

**Layout**:
```
┌────────────────────────┐
│  Connected             │
│  Role: Spectator       │
│                        │
│  Input level:          │
│  ████████░░░░░░        │
│                        │
│  [ ] Mute              │
│                        │
│  [Leave Session]       │
│  [Settings]            │
└────────────────────────┘
```

**Behavior**:
- **VU meter**: Realtime amplitude from pitch detector
- **Mute**: When ON, sends `midiNote=255`
- **Medley source**: If `playbackState.reason="medley_source"`, show "Your songs in use — keep app open"

**Screen wake**: `FLAG_KEEP_SCREEN_ON` (Android) / `isIdleTimerDisabled=true` (iOS)

#### Active Mic Screen

**State**: Assigned Singer, countdown or singing

**Entry**: On `assignSinger`. Trigger 200ms haptic.

**Layout (Countdown)**:
```
┌────────────────────────┐
│     SINGER P1          │
│                        │
│         3              │
│                        │
│  Input: ████████░░░░   │
│  [ ] Mute              │
└────────────────────────┘
```

**Layout (Singing)**:
```
┌────────────────────────┐
│  SINGER P1             │
│                        │
│  Input: █████████░░░   │
│  [ ] Mute              │
└────────────────────────┘
```

**Behavior**:
- **Countdown**: Display 3, 2, 1. Mic warms, no frames sent
- **Singing**: Stream 50fps UDP pitch frames
- **Back**: SUPPRESSED (must background to exit)
- **Exit**: On `stopAtLyricsTimeMs` or `playbackState.stopped` → Waiting

**iOS banner**: "Keep app in foreground" shown during Active Mic

#### Settings Screen

**Accessible from**: Join, Waiting (disabled if serving song)

**Layout**:
```
┌────────────────────────┐
│  Settings              │
│                        │
│  Songs folder:         │
│  /Downloads/Songs      │
│  [Change Folder]       │
│                        │
│  Mic Sensitivity:      │
│  [====|====] 3         │
│  0   3   5   7         │
│                        │
│  423 valid, 2 invalid  │
│  [Rescan Now]          │
│                        │
│  [Back]                │
└────────────────────────┘
```

**Behavior**:
- **Change Folder**: SAF picker (Android) / security-scoped bookmark picker (iOS), triggers rescan
- **Mic Sensitivity**: 0-7 slider, updates `PitchDetector.setSensitivity()`
- **Rescan**: Disabled if `inSong=true` and phone serves current song
- **Default folder**: `Downloads/Songs/` (Android) / Documents (iOS)

#### Error Modals

**Permission denied**:
```
Permission Required

Enable:
• Camera (scan QR)
• Microphone (pitch)
• Local Network (TV)

Android: Settings → Apps
iOS: Settings → Privacy

[OK]
```

**Session locked**: "A song is in progress. Try again in a moment."

**Session full**: "Maximum players reached."

**Protocol mismatch**: "App version incompatible. Please update."

### 2.7.3 Navigation Flow

```
Join ──[connect]──► Waiting ──[assignSinger]──► ActiveMic
 ▲                     │                            │
 └─────[leave]─────────┴──[playbackState.stopped]──┘

Settings: accessible from Join or Waiting
```

**Back handling**:
- Join: Exit app
- Waiting: Confirm → Join
- ActiveMic: SUPPRESSED
- Settings: Previous screen

### 2.7.4 Platform Notes

**Android**:
- Permissions: Runtime request for `CAMERA`, `RECORD_AUDIO`, `NEARBY_WIFI_DEVICES`
- Network: `network_security_config.xml` with `cleartextTrafficPermitted=true`
- Background: Mic + HTTP continue when backgrounded

**iOS**:
- Permissions: Info.plist descriptions required
- Background: Suspended after ~30s → HTTP socket closed
- AVAudioSession: `.record` category, `.measurement` mode
- Security-scoped bookmarks: Call `startAccessingSecurityScopedResource()` before serving

---

# 3. Component APIs

## 3.1 SongScanner

```kotlin
interface SongScanner {
    val scanState: StateFlow<ScanState>
    val songIndex: StateFlow<SongIndex>
    
    suspend fun rescan(): ScanResult
    suspend fun setFolder(uri: Uri): ScanResult
    fun getFolder(): Uri?
}

data class ScanState(
    val phase: ScanPhase,        // IDLE, SCANNING, VALIDATING, COMPLETE, ERROR
    val songsDiscovered: Int,
    val songsValidated: Int,
    val songsInvalid: Int,
    val currentFile: String?
)

data class SongIndex(
    val entries: List<SongEntry>,
    val invalidEntries: List<InvalidSong>,
    val staticAssets: Map<String, Uri>,
    val generatedPlaybackCandidates: Map<String, GeneratedPlaybackCandidate>
)

data class GeneratedPlaybackCandidate(
    val relativeTxtPath: String,
    val sourceUris: List<Uri>
)
```

`SongIndex.entries` contains manifest-ready song metadata but not finalized full URLs. `staticAssets` is keyed by normalized relative path for scanned static assets. `generatedPlaybackCandidates` identifies songs whose effective `audioUrl` may later resolve to a session-owned generated playback resource under the reserved `generated/` namespace.

## 3.2 HttpFileServer

```kotlin
interface HttpFileServer {
    val serverState: StateFlow<ServerState>
    
    suspend fun start(staticAssets: Map<String, Uri>, manifestJson: ByteArray): Int
    fun stop()
    fun updateManifest(manifestJson: ByteArray, staticAssets: Map<String, Uri>)
    fun publishGeneratedPlaybackResource(path: String, resource: GeneratedPlaybackResource)
    fun discardGeneratedPlaybackResources()
}

`path` for `publishGeneratedPlaybackResource()` MUST be a normalized relative path under `generated/` ending in `.wav`.

data class ServerState(
    val running: Boolean,
    val port: Int,
    val activeRequests: Int,
    val totalBytesServed: Long
)

interface GeneratedPlaybackResource

Generated playback resources MUST expose deterministic byte content, total content length, and support byte-range reads over the pre-rendered WAV payload.
```

## 3.3 PitchDetector

```kotlin
interface PitchDetector {
    val detectorState: StateFlow<DetectorState>
    
    fun start()
    fun stop()
    fun setSensitivity(index: Int)
    fun setMuted(muted: Boolean)
    fun onPitchFrame(callback: (PitchFrame) -> Unit)
}

data class DetectorState(
    val active: Boolean,
    val muted: Boolean,
    val currentAmplitude: Float,
    val sensitivityIndex: Int
)

data class PitchFrame(
    val midiNote: UByte,
    val maxAmp: Float,
    val phoneMonotonicMs: Long
)
```

## 3.4 NetworkClient

```kotlin
interface NetworkClient {
    val connectionState: StateFlow<ConnectionState>
    val serverMessages: SharedFlow<ServerMessage>
    
    suspend fun connectViaQr(payload: String): ConnectResult
    suspend fun connectViaCode(code: String): ConnectResult
    fun disconnect()
    fun sendPitchFrame(frame: PitchFrameWire)
}

data class ConnectionState(
    val phase: ConnectionPhase,
    val sessionId: String?,
    val connectionId: UShort?,
    val tvEndpoint: String?,
    val udpPort: Int?,
    val tvIpAddress: String?,
    val localPublishedIpAddress: String?
)

sealed class ServerMessage {
    data class SessionState(...) : ServerMessage()
    data class Ping(...) : ServerMessage()
    data class ClockAck(...) : ServerMessage()
    data class AssignSinger(...) : ServerMessage()
    data class PlaybackState(...) : ServerMessage()
    data class Error(...) : ServerMessage()
}

data class PitchFrameWire(
    val seq: UInt,
    val tvTimeMs: Long,
    val songInstanceSeq: UInt,
    val playerId: UByte,
    val midiNote: UByte,
    val connectionId: UShort
)
```

## 3.5 ClockSync

```kotlin
interface ClockSync {
    val clockOffsetMs: StateFlow<Long?>
    val syncQuality: StateFlow<SyncQuality>
    
    fun handlePing(ping: ServerMessage.Ping): ClientMessage.Pong
    fun handleClockAck(ack: ServerMessage.ClockAck)
    fun toTvTime(phoneMonotonicMs: Long): Long
    fun reset()
}

data class SyncQuality(
    val samplesCollected: Int,
    val bestRttMs: Long?,
    val synchronized: Boolean
)
```

## 3.6 SessionCoordinator

```kotlin
interface SessionCoordinator {
    val phoneState: StateFlow<PhoneState>
    
    suspend fun joinViaQr(payload: String): JoinResult
    suspend fun joinViaCode(code: String): JoinResult
    fun leave()
    fun setMuted(muted: Boolean)
    suspend fun rescanLibrary(): ScanResult
    suspend fun setLibraryFolder(uri: Uri): ScanResult
}

`rescanLibrary()` and `setLibraryFolder()` MUST reject calls while the phone is actively serving current-song media or while the phone is in the Active Mic screen.

sealed class PhoneState {
    object Disconnected : PhoneState()
    data class Connecting(val method: String) : PhoneState()
    data class Connected(
        val role: Role,
        val playerId: String?,
        val sessionId: String,
        val servingCurrentSongMedia: Boolean
    ) : PhoneState()
    data class Reconnecting(val attempt: Int) : PhoneState()
}
```

## 3.7 SongEntry (manifest.json schema)

```kotlin
@Serializable
data class SongEntry(
    val relativeTxtPath: String,
    val modifiedTimeMs: Long,
    val title: String,
    val artist: String,
    val album: String? = null,
    val year: Int? = null,
    val genre: String? = null,
    val isDuet: Boolean,
    val hasRap: Boolean,
    val hasVideo: Boolean,
    val hasInstrumental: Boolean,
    val canMedley: Boolean,
    val medleySource: String? = null,
    val medleyStartBeat: Int? = null,
    val medleyEndBeat: Int? = null,
    val startSec: Float,
    val previewStartSec: Float,
    val txtUrl: String?,
    val audioUrl: String?,
    val videoUrl: String? = null,
    val coverUrl: String? = null,
    val backgroundUrl: String? = null
)
```

Required fields: `relativeTxtPath`, `modifiedTimeMs`, `title`, `artist`, `isDuet`, `hasRap`, `hasVideo`, `hasInstrumental`, `canMedley`, `startSec`, `previewStartSec`, `txtUrl`, `audioUrl`. URL fields are `null` when absent/unavailable. The `/manifest.json` response is a JSON array of these objects.

`audioUrl` is the song's single TV-facing playback URL. It MUST identify the effective playback resource chosen by the phone for the song: either the unchanged base audio asset or a phone-generated mixed playback resource. For accepted phone-side mixing, `audioUrl` MUST point to the deterministic generated WAV resource under `/songs/generated/` for that song. That generated resource MAY be materialized on first request or earlier if already known locally, but once published it MUST remain deterministic for the lifetime of the active song/session use. `instrumentalUrl` and `vocalsUrl` MUST NOT appear in the manifest schema.

---

# 4. SLAs

All tests are JVM-only unless noted.

## 4.1 Pitch Frame Latency

| Metric | Limit | Test |
|--------|-------|------|
| FFT-YIN computation | ≤10ms | F17 + timing wrapper |
| `tvTimeMs` accuracy | ±5ms | F14v2 clock math |

## 4.2 HTTP Range Response

| Metric | Limit | Test |
|--------|-------|------|
| First byte (static assets) | ≤100ms | F18 with Ktor testApplication |
| First byte (generated mix, uncached) | ≤3s | F18 + timing wrapper |
| First byte (generated mix, cached) | ≤100ms | F18 |
| Range correctness | Exact boundaries | F18 |
| Generated mixed `audioUrl` content length | Present on full and range responses | F01/`d/mix_pair_same_rate_channels` |
| Generated mixed `audioUrl` repeatability | Exact byte identity for repeated GETs of the same path/range | F01/`d/mix_pair_same_rate_channels` |
| Generated mixed `audioUrl` media type | `audio/wav` with PCM16LE payload | F01/`d/mix_pair_same_rate_channels` |

## 4.3 Scan Performance

| Metric | Limit | Test |
|--------|-------|------|
| Parse rate | ≥100 TXT/sec | F01-F05 batch timing |

## 4.4 Reconnect Timing

| Metric | Limit | Test |
|--------|-------|------|
| First retry | ≤500ms | F15 with fake clock |
| Backoff cap | 30s | F15 |

## 4.5 Clock Sync

| Metric | Limit | Test |
|--------|-------|------|
| 5-sample sync | ≤3s | F14v2 |
| Invalid RTT rejection | ≥2000ms discarded | F14v2 |

---

# 5. Resolved Blockers

## 5.1 Pitch Pipeline Threading

**Resolution**: Process in AudioRecord callback thread. FFT-YIN ≤10ms fits in 23ms window. UDP send is non-blocking.

## 5.2 HTTP vs Pitch Priority

**Resolution**: OS scheduling. AudioRecord has real-time priority; Ktor runs on Dispatchers.IO. No explicit management needed.

## 5.3 SAF URI Persistence

**Resolution**: `takePersistableUriPermission()` + SharedPreferences. Check permission on app start; prompt if revoked.

## 5.4 Mute Toggle

**Resolution**: Keep capturing, send `midiNote=255`. VU meter still works.

## 5.5 Clock Sync During Countdown

**Resolution**: No sync during countdown or singing. Sync on: connect (5 samples), song end, reconnect.

## 5.6 Manifest URL Construction

**Resolution**: Store normalized relative asset paths plus resolution metadata in scan output. Build full manifest URLs only at manifest serialization time using the server's bound address and current session-owned generated-resource state.

## 5.7 iOS Backgrounding

**Resolution**: Document as limitation. Show "Keep app in foreground" banner when singing or serving.

## 5.8 Phone-Side Audio Mixing Scope

**Resolution**: MVP mixing accepts differing compressed bitrates but requires matching decoded sample rate and channel count for `#INSTRUMENTAL`/`#VOCALS`. Unsupported pairs fall back to the base `#AUDIO`/`#MP3` asset and emit a warn diagnostic.

---

# 6. Project Plan

Aligned with TV iterations. Phone always uses Mock TV.

## 6.1 Iteration Overview

| Iter | TV Iter | Phone Goal | Mock TV Needed |
|------|---------|------------|----------------|
| 0 | 0 | Song scanning | No |
| 1 | 1 | HTTP server + Session join | Yes |
| 2 | 2 | Clock sync + Pitch detection | Yes |
| 3 | 3 | Full singing flow | Yes |
| 4 | 4 | Polish + iOS | Yes |

## 6.2 Iter 0 — Song Scanning (Week 1)

**Goal**: Parse and validate songs. No network.

| Deliverable | Fixtures |
|-------------|----------|
| SAF folder picker | — |
| TxtParser (shared with TV) | F01-F05 |
| Validation engine | F01 |
| Settings screen | — |
| Local song list UI | — |

**DOD**:
- [ ] F01–F05 pass (JVM)
- [ ] Select folder → songs scanned
- [ ] No Android deps in parser

## 6.3 Iter 1 — HTTP Server + Session Join (Week 2)

**Goal**: Serve manifest, join session.

| Deliverable | Fixtures |
|-------------|----------|
| Ktor HTTP server (Android) / Hummingbird server (iOS) | F18 |
| `/manifest.json` + `/songs/<path>` | F18 |
| mDNS discovery | — |
| QR scanner | — |
| WebSocket client | F15, F20 |
| Join + Waiting screens | — |

**DOD**:
- [ ] F15, F18, F20 pass (JVM)
- [ ] curl manifest works
- [ ] Handshake completes with mock TV

**Mock TV**: `handshake_only.json`

## 6.4 Iter 2 — Clock Sync + Pitch Detection (Week 3-4)

**Goal**: Sync clock, detect pitch, stream frames.

| Deliverable | Fixtures |
|-------------|----------|
| Clock sync | F14v2 |
| Mic capture | — |
| FFT-YIN pipeline | F17 |
| UDP sender | F12v2 |
| VU meter | — |

**DOD**:
- [ ] F12v2, F14v2, F17 pass (JVM)
- [ ] Sing A4 → midiNote=69
- [ ] Frames stream at 50fps

**Mock TV**: `sing_10s.json`

## 6.5 Iter 3 — Full Singing Flow (Week 5-6)

**Goal**: Complete assign → countdown → sing → stop cycle.

| Deliverable | Fixtures |
|-------------|----------|
| AssignSinger handling | — |
| PlaybackState handling | — |
| Phone-side audio mixing lifecycle | F01, F18 |
| Active Mic screen | — |
| Mute toggle | — |
| Reconnect logic | F15 |

**DOD**:
- [ ] Full sing cycle works
- [ ] Reconnect within 2.5s
- [ ] Mixed songs expose one effective `audioUrl` with deterministic HTTP behavior

**Mock TV**: `sing_10s.json`, `reconnect.json`

## 6.6 Iter 4 — Polish + iOS (Week 7-8)

**Goal**: Production quality, iOS port.

| Deliverable | Notes |
|-------------|-------|
| iOS song scanner | Security-scoped bookmarks |
| iOS HTTP server | Hummingbird |
| iOS pitch detection | AVAudioEngine + vDSP |
| Backgrounding warning | Both platforms |
| Error modals | — |
| Persistent settings | — |

**DOD**:
- [ ] Android polished
- [ ] iOS working
- [ ] F19 passes (iOS)

---

# Appendix A: Mock TV Specification

Simple JVM process. No REPL — runs scripted scenarios.

## A.1 Usage

```bash
# Basic handshake
./gradlew :mock-tv:run

# With scenario
./gradlew :mock-tv:run --args="--scenario=scenarios/sing_10s.json"
```

## A.2 Scenario Format

```json
{
  "joinCode": "TESTABCD",
  "wsPort": 8765,
  "udpPort": 34567,
  "steps": [
    { "action": "waitForHello" },
    { "action": "sendSessionState", "connectionId": 1 },
    { "action": "runClockSync", "samples": 5 },
    { "action": "wait", "ms": 1000 },
    { "action": "sendAssignSinger", "playerId": "P1", "countdown": 3000 },
    { "action": "wait", "ms": 3000 },
    { "action": "sendPlaybackState", "state": "playing" },
    { "action": "collectFrames", "durationMs": 10000 },
    { "action": "sendPlaybackState", "state": "stopped" },
    { "action": "printFrameStats" }
  ]
}
```

## A.3 Built-in Scenarios

| Scenario | Purpose |
|----------|---------|
| `handshake_only.json` | Connect + clock sync |
| `sing_10s.json` | P1 sings 10 seconds |
| `reconnect.json` | Disconnect after 5s, allow reconnect |
| `two_players.json` | Assign P1 and P2 |

## A.4 Output

```
[MockTV] Started on ws://192.168.1.10:8765, UDP :34567
[MockTV] Advertising _karaoke._tcp code=TESTABCD
[MockTV] Phone connected: clientId=abc123
[MockTV] Clock sync: offset=-42ms, RTT=28ms
[MockTV] Assigned P1
[MockTV] Received 487 frames (48.7 fps)
[MockTV] Done.
```

## A.5 Implementation

```
mock-tv/
├── src/main/kotlin/
│   ├── Main.kt
│   ├── MockTvServer.kt
│   ├── ScenarioRunner.kt
│   └── FrameCollector.kt
└── scenarios/
    ├── handshake_only.json
    ├── sing_10s.json
    └── reconnect.json
```