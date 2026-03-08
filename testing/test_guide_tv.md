# Couchraoke — Testing Guide (Android TV) v4.19
**Spec**: 4.19 | **Coverage target**: 80% overall, ≥60% per file | **Stack**: Kotlin (Android TV host)
---
## Module 1 — TV-side TXT Parser
> Full parse (header + body) when TV fetches a selected song's `.txt` over HTTP.

### 1.1 Body grammar [U]
| # | What | Fixture | Expected |
|---|---|---|---|
| 1.1.1 | Unknown body token ignored | F03/`a/unknown_token_ignored` | `isValid=true`, note type = Normal |
| 1.1.2 | Malformed numeric in body | F03/`b/invalid_malformed_numeric` | `isValid=false`, `ERROR_CORRUPT_SONG_MALFORMED_BODY` |
| 1.1.3 | `duration=0` → Freestyle | F03/`c/duration_zero_converts_to_freestyle` | note stored as `Freestyle` |
| 1.1.4 | No `-` lines → single implicit sentence | S09 | `isValid=true`, 1 line, 1 note |
| 1.1.5 | No notes after cleanup | S10 | `isValid=false`, `ERROR_CORRUPT_SONG_NO_NOTES` |
| 1.1.6 | Body contains `B` token (variable BPM) | F03/`d/variable_bpm_rejected` | `isValid=false`, `ERROR_CORRUPT_SONG_UNSUPPORTED_VARIABLE_BPM` |

### 1.2 RELATIVE tag and body format [U]
| # | What | Fixture | Expected |
|---|---|---|---|
| 1.2.1 | `#RELATIVE:YES` header treated as unknown tag | F03/`e/relative_header_as_custom_tag` | `isValid=true`, `customTags` contains `{tag:"RELATIVE", content:"YES"}` |
| 1.2.2 | RELATIVE body format: `-` line with extra beat-delta parameter | F03/`f/relative_body_rejected` | `isValid=false`, `ERROR_CORRUPT_SONG_UNSUPPORTED_RELATIVE` |

### 1.3 Duet parsing [U]
| # | What | Fixture | Expected |
|---|---|---|---|
| 1.3.1 | P1/P2 routing | F04/`a/valid_duet_interleaved` | 2 tracks, notes assigned per track |
| 1.3.2 | Invalid `P3` marker | F04/`b/invalid_duet_marker_p3` | `isValid=false`, `ERROR_CORRUPT_SONG_INVALID_DUET_MARKER` |

---
## Module 2 — Timing and Beat Model
### 2.1 Beat cursors — static BPM [U]
| Input | Computation | Expected |
|---|---|---|
| `lyricsTimeSec=5.0`, `GAPms=2000`, `micDelayMs=100`, `BPM_file=120` | `highlightTimeSec=3.0` → `midBeat=24.0` | `currentBeat=24` |
| Same | `scoringTimeSec=2.9` → `midBeat=23.2` → `-0.5=22.7` | `currentBeatD=22` |

### 2.2 Note window boundary [U]
- `startBeat=11`, `duration=2` → active at b=11, b=12.
- Scoring loop `(oldBeatD=10, currentBeatD=13]` → evaluates b=11,12,13 only.

---
## Module 3 — Scoring Engine
### 3.1 Beat stepping [U]
- Only beats in `(oldBeatD, currentBeatD]` scored.
### 3.2 Pitch tolerance + octave normalization [U]
| Subcase | Difficulty | midiNote | Target toneUsdx | Result |
|---|---|---|---|---|
| `easy_hit_diff1` | Easy (±2) | 47 | 0 | Hit |
| `medium_hit_diff1` | Medium (±1) | 47 | 0 | Hit |
| `medium_miss_diff2` | Medium (±1) | 38 | 0 | Miss |
| `hard_miss_diff1` | Hard (±0) | 47 | 0 | Miss |

### 3.3 Rap scoring | 3.4 Freestyle exclusion | 3.5 Line bonus [U]
- Rap: scores regardless of pitch if `toneValid=true`.
- Freestyle: `scoreDelta=0` even with `toneValid=true`.
- Line bonus: Perfect performance = `ScoreLineInt=1000`.

---
## Module 4 — Binary PitchFrame Codec
### 4.1 Codec correctness [U]
| # | What | Expected |
|---|---|---|
| 4.1.1 | Decode frame 0 | Fields match `expected.json` |
| 4.1.2 | `midiNote=255` → `toneValid=false` | Row 1: `toneValid=false` |
| 4.1.3 | `midiNote=0` → `toneValid=true` | 0 is valid MIDI note |

### 4.2 TV-side validation / drop rules [U]
| # | What | Expected |
|---|---|---|
| 4.2.1 | Datagram ≠ 16 bytes | Silently dropped |
| 4.2.2 | `connectionId` mismatch | Silently dropped |
| 4.2.3 | `songInstanceSeq` mismatch | Silently dropped |
| 4.2.4 | Unknown `playerId` | Silently dropped |

---
## Module 5 — Jitter Buffer 
| # | What | F13 sample | Expected |
|---|---|---|---|
| 5.1 | Most recent frame ≤ now | `tvNowMs=1060` | seq=2 (`tvTimeMs=1050`) |
| 5.2 | All eligible frames stale (>120ms) | `tvNowMs=1400` | `toneValid=false` |
| 5.3 | Frame arrives late (>450ms) | latenessMs=500 | `toneValid=false` |
| 5.4 | Decreasing `seq` | Inject seq=5 then seq=3 | seq=3 dropped |

---
## Module 6 — Control Message Protocol 
### 6.1 Hello handshake [U]
| # | What | Expected |
|---|---|---|
| 6.1.1 | Valid `hello` | TV responds with `sessionState` |
| 6.1.2 | TV sends `requestSongList` | Present in transcript immediately after hello |
| 6.1.3 | Join during Locked state | `error(code="session_locked")` |
| 6.1.4 | Roster full (>10) | `error(code="session_full")` |

### 6.2 Reconnect logic [U]
| # | What | Expected |
|---|---|---|
| 6.2.1 | First connection | `connectionId=1` assigned |
| 6.2.2 | Reconnect hello | new `connectionId=3` |
| 6.2.3 | `assignSinger` re-sent | Contains new `songInstanceSeq`; NO `connectionId` |

### 6.3 assignSinger fields [U]
Verify `assignSinger` contains: `sessionId`, `songInstanceSeq`, `playerId`, `difficulty`, `thresholdIndex`, `effectiveMicDelayMs`, `expectedPitchFps`, `startMode`, `endTimeTvMs`, `udpPort`.

---
## Module 7 — TV Library Aggregation
### 7.1 Library state [U]
- 7.1.1 `songId` derivation: `phoneClientId + "::" + relativeTxtPath`.
- 7.1.2 Phone disconnects: its songs removed immediately.
- 7.1.3 `medleySource="calculated"`: Rejected; `canMedley=false` forced.

### 7.2 Filtering [U]
- 7.2.1 Search: Returns matching songs preserving sort.
- 7.2.2 `canMedley=true` filter: Only eligible songs included.

---
## Module 8 — Key UI Invariants (TV)
### 8.1 TV — Select Players [U widget]
- 8.1.1 No phones connected: Blocking error state.
- 8.1.2 Medley mode: Player 2 section hidden entirely.

### 8.2 TV — Singing Screen [U widget]
- 8.2.1 Countdown: Shows N → 1 at 1 Hz.
- 8.2.2 Singer disconnects: Shows `PAUSED — PLAYER DISCONNECTED` overlay.

### 8.3 TV — Song List [U widget]
- 8.3.1 No phones: "No phones connected." message (§3.4).
- 8.3.2 Medley-false long-press: Blocking modal with exact text.

---
## Module 9 — Medley Sequencer 
### 9.1 medleyStartSec and medleyEndSec computation [U]
- 9.1.1 `timeFromBeat(startBeat) ≤ 8` → `medleyStartSec=0.0`.

### 9.2 Scoring window filter [U]
- 9.2.1 In-window: ScoreFactor applied normally.
- 9.2.2 Out-window: ScoreFactor=0.

### 9.3 Segment sequencing [U]
- 9.3.1 `medleyStartBeat >= medleyEndBeat`: Sequencer throws IllegalStateException.
- 9.3.2 `audioUrl` null: Segment skipped; brief error toast.

### 9.4 ExoPlayer seek accuracy [I]
- Assert `player.getCurrentPosition()` after seek is within ±100ms.