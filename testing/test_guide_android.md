# Couchraoke — Testing Guide (Android Phone) v4.19
**Spec**: 4.19 | **Coverage target**: 80% overall, ≥60% per file | **Stack**: Kotlin (Android Phone companion)
---
## Module 1 — Phone-side Song Scanner (Android)
> Produces `songListUpdate` entries from header-only `.txt` scan via SAF.

### 1.1 Validation [U]
| # | What | Fixture | Expected |
|---|---|---|---|
| 1.1.1 | Missing `#ARTIST` | F01/`a/invalid_missing_required_header` | `isValid=false`, code `ERROR_CORRUPT_SONG_MISSING_REQUIRED_HEADER` |
| 1.1.2 | `#AUDIO` missing on disk | F01/`b/invalid_missing_audio` | `isValid=false`, code `ERROR_CORRUPT_SONG_FILE_NOT_FOUND`, `invalidLineNumber=4` |
| 1.1.3 | v1.0.0: `#AUDIO` beats `#MP3` | F01/`c/v1_audio_precedence` | `isValid=true`, `resolvedAudio=audio.ogg` |
| 1.1.4 | Legacy: `#MP3` required, `#AUDIO` ignored | F01/`c/legacy_mp3_preferred` | `isValid=true`, `resolvedAudio=audio.mp3` |
| 1.1.5 | Legacy: no `#MP3` | F01/`c/legacy_missing_mp3_invalid` | `isValid=false`, code `ERROR_CORRUPT_SONG_MISSING_REQUIRED_HEADER` |
| 1.1.6 | Missing optional `#VIDEO` | F01/`c/v1_missing_optional_video` | `isValid=true`, `hasVideo=false` |
| 1.1.7 | `#BPM:0` | S04 | `isValid=false`, code `ERROR_CORRUPT_SONG_MALFORMED_HEADER` |
| 1.1.8 | Non-numeric `#BPM` | F02/`b/invalid_malformed_bpm` | `isValid=false`, code `ERROR_CORRUPT_SONG_MALFORMED_HEADER`, `invalidLineNumber=5` |

### 1.2 Header parsing [U]
| # | What | Fixture | Expected |
|---|---|---|---|
| 1.2.1 | Duplicate tags → last wins | F02/`a/dup_bpm_last_wins` | `bpmFile=120.0` |
| 1.2.2 | Unknown tags preserved | F02/`a/unknown_tags_variants` | `customTags=[{FOO,bar},{EMPTY,""},{"",.JUSTTEXT}]` ordered |
| 1.2.3 | `#VERSION:1.0.0` ignores `#ENCODING` | F02/`c/encoding_utf8_forced` | `title="Tést ✓ UTF8"` |
| 1.2.4 | `previewStartSec` from `#PREVIEWSTART` | F02/`d/preview_from_previewstart` | `previewStartSec=12.5` |
| 1.2.5 | `previewStartSec` medley fallback | F02/`d/preview_from_medley` | `previewStartSec=2.0` (`timeFromBeat(16)=2.0s`) |
| 1.2.6 | `previewStartSec` → 0 when no medley, no previewstart | F02/`d/preview_from_start` | `previewStartSec=0.0` |

### 1.3 Metadata flags [U]
| # | What | Input | Expected |
|---|---|---|---|
| 1.3.1 | `isDuet` detected from `P1`/`P2` in body | S11 | `isDuet=true` |
| 1.3.2 | `hasRap` detected from `R`/`G` notes | inline: body with `R 0 4 0 ra` | `hasRap=true` |
| 1.3.3 | `canMedley=false` for duet | `isDuet=true`, any `medleySource` | `canMedley=false` |
| 1.3.4 | `canMedley=true` via tags | `#MEDLEYSTARTBEAT:10`, `#MEDLEYENDBEAT:80`, `isDuet=false` | `canMedley=true`, `medleySource="tag"` |
| 1.3.5 | `canMedley=false` — no medley tags | no medley headers | `canMedley=false`, `medleySource=null` |

### 1.4 Recursive discovery [I]
| # | What | Fixture | Expected |
|---|---|---|---|
| 1.4.1 | Recursive scan finds all `.txt` | F01/`songs_root/` tree | All 8 entries discovered |

---
## Module 2 — Binary PitchFrame Codec (Phone/Kotlin) [SHARED]
### 2.1 Codec correctness [U]
| # | What | Expected |
|---|---|---|
| 2.1.1 | encode(decode(frame)) round-trip | Identical bytes |

---
## Module 3 — Clock Sync (NTP-lite, Phone-side) [FLAG: SPLIT]
### 3.1 Per-sample math [U]
`RTT = (t4-t1)-(t3-t2)` | `offset = ((t2-t1)+(t3-t4))/2`.
### 3.2 Best-of-N selection [U]
- Choose sample with smallest RTT → a3.
- RTT < 0 or RTT > 2000 → discard.
### 3.3 tvTimeMs estimation [U]
- `clockOffsetMs=-500`, `phoneMonotonicMs=2000` → `tvTimeMs=1500`.

---
## Module 4 — Control Message Protocol (Phone-side) [FLAG: SPLIT]
### 4.1 Hello handshake [U]
| # | What | Expected |
|---|---|---|
| 4.1.1 | `hello` without `httpPort` | TV rejects; schema validation failure |
| 4.1.2 | Wrong `protocolVersion` | `error(code="protocol_mismatch")` |
| 4.1.3 | Wrong token | `error(code="invalid_token")` |

### 4.2 songListUpdate handling [U]
| # | What | Expected |
|---|---|---|
| 4.2.1 | Phone A sends songs | library updated on TV |
| 4.2.2 | Phone A disconnects | All songs for `clientId=A` removed immediately |
| 4.2.3 | Rescan: phone sends new `songListUpdate` | Replaces all prior entries for that `clientId` |

---
## Module 5 — HTTP File Server (Phone-side / Android)
### 5.1 Range requests [U]
| # | What | Input | Expected |
|---|---|---|---|
| 5.1.1 | Full file | No `Range` header | 200, full bytes |
| 5.1.2 | Partial range | `Range: bytes=0-99` | 206, 100 bytes |
| 5.1.3 | Open-ended range | `Range: bytes=500-` | 206, bytes from 500 to EOF |
| 5.1.4 | All audio/video responses | Any request | `Accept-Ranges: bytes` header present |
| 5.1.5 | Unsatisfiable range | `Range: bytes=9999-9999` on 100-byte file | 416 |

### 5.2 Routing and security [U]
| # | What | Expected |
|---|---|---|
| 5.2.1 | `/songs/Artist/Song/audio.ogg` | 200 |
| 5.2.2 | Percent-encoded path | `Queen/Bohemian%20Rhapsody/` correctly decoded |
| 5.2.3 | Path traversal `../etc/passwd` | 404 |

### 5.3 Server lifecycle [I]
| # | What | Expected |
|---|---|---|
| 5.3.1 | Server starts before `hello` is sent | `httpPort` in `hello` is reachable |
| 5.3.2 | Default port 34781 busy → ephemeral fallback | `httpPort` in `hello` reflects bound port |

### 5.4 SAF cloud-evicted file handling [U]
| # | What | Expected |
|---|---|---|
| 5.4.1 | `ContentResolver.query()` returns `SIZE=0` | URL is `null` in `SongEntry` |
| 5.4.2 | SAF URI path not used directly | Verify no `uri.path` → `File()` call exists |

---
## Module 6 — Key UI Invariants (Phone)
### 6.1 Phone — Android [U widget]
| # | What | Expected |
|---|---|---|
| 6.1.1 | Hardware Back during Active Mic | Suppressed (no-op) |
| 6.1.2 | `tvNowMs >= endTimeTvMs` | Screen transitions to Waiting/Connected |
| 6.1.3 | Leave session | Returns to Join screen; cached endpoint cleared |