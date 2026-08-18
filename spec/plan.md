# Couchraoke TV — Delivery Plan (v4)

Replaces `old/tv_app.md` §7. Same specification, different slicing and different gates.

## Why this exists

The previous plan had six iterations. Three of them bundled 9–12 deliverables and pulled
900–1,500 lines of specification into a single slice. Iteration 2 expanded into 100 tasks
and 15,806 lines across 128 files, was marked complete, and did not work.

Two defects caused that, and both are fixed here.

**Gates could not fail.** Every DOD line was a human observation with no automated
equivalent. "Preview plays on focus" and "shows sentence-paged lyrics" are both satisfied
by code that renders a first frame and then freezes. Section 4 below replaces every
observation with an assertion.

**Fakes were mandated at the peer boundary.** `old/tv_app.md` §2.7 says a mock phone MUST
be maintained. Appendix A says do NOT build one and prefer fakes. Appendix A won, and the
result was a test suite that exercised `FakeVlcPlayer` and `FakeVlcMediaFactory` while the
real transports were never invoked. Section 3 reverses this.

## 1. Slice rules

A slice is done when someone can watch it work. If you cannot demonstrate it end to end in
one sitting, it is too big and must be split.

- One risky new thing per slice. A new native dependency, a new transport, or a new seam —
  not two at once.
- 3–5 deliverables. More than 5 means split.
- Every slice ends in a runnable app. No slice leaves the tree in a state where the
  previous slice's demo has regressed.
- A slice references bounded spec subsections, never a whole behaviour section. See §5.

## 2. Gate vocabulary

Every DOD item below is tagged with the gate that proves it.

| Tag | Gate | Runs where | Cost |
|-----|------|------------|------|
| **U** | JVM unit test, no Android runtime | `testDebugUnitTest` | seconds |
| **S** | Screenshot, Robolectric at `w960dp-h540dp-land-television-xhdpi-notouch`, record-then-**verify** against a committed baseline | `verifyRoborazziDebug` | ~1 min |
| **L** | Loopback integration — the real `mockphone` process talking to the app over `127.0.0.1` | `mockphone` + JVM harness | ~1 min |
| **D** | Device — install on the S905X4, drive it, assert on screencaps | `adb` | ~2 min |

**Rule: every slice must carry at least one L or D gate.** A slice proved only by U and S is
not proved. U and S cannot observe a native decoder, a real socket, or a real clock.

**Rule: S is verify, not record.** Baselines are committed. `roborazzi.test.record` alone
never fails, which is why the oversized layouts shipped.

**Rule: no `assumeTrue` in a gate.** `VlcLibVlcPlayerHandleDeviceTest` skipped silently for
the entire project and stayed green. A missing precondition is a failure, not a skip.

## 3. Peer boundary policy (supersedes Appendix A)

`old/tv_app.md` Appendix A is withdrawn. It instructed the implementer to prefer in-process
fakes at exactly the boundary where a fake can lie about everything.

- The `mockphone` repository is the peer-boundary gate. It is a real out-of-process peer:
  real HTTP with Range support, real WebSocket, real UDP at 50fps, real mDNS, real
  reconnect with a persistent `clientId`. An implementation cannot fake a conversation with
  a separate OS process over a real socket.
- Fakes remain legal only where there is no peer: parser, scoring math, beat/time
  conversion, jitter buffer, GamePhase FSM, clock-sync arithmetic.
- Fakes are banned in any test that claims a transport, a decoder, or a clock works.

Loopback is unaffected by corporate egress filtering, so **L** gates run anywhere. Only **D**
needs the device.

## 4. Slices

Slice 0 is carried forward unchanged. It is the only part of the previous attempt with a
gate that could fail, and it is the only part that still works.

| # | Slice | What you watch | Gates |
|---|-------|----------------|-------|
| 0 | Foundation | fixtures pass | U |
| 1 | Phone joins | phone appears as connected | U L |
| 2 | Songs appear | phone's songs listed on screen | U L |
| 3 | Song grid at TV size | browsable, searchable grid | U S D |
| 4 | Preview playback | audio previews on focus | U L D |
| 5 | Select players | modal opens, Start dismisses | U S |
| 6 | Audio + lyrics scroll | song plays, lyrics advance | U L D |
| 7 | Playback control | pause, resume, stop, error paths | U S D |
| 8 | Clock sync + UDP ingress | pitch frames arrive and validate | U L |
| 9 | Live scoring, 1P | score climbs while singing | U L D |
| 10 | Results, single song | final score screen | U S |
| 11 | Two phones + duet | two singers, split tracks | U L D |
| 12 | Disconnect / reconnect | pull a phone, session recovers | U L |
| 13 | Medley playlist | build a playlist | U S |
| 14 | Medley sequencer | songs chain together | U L D |
| 15 | Medley results | per-segment scores | U S |
| 16 | Video backgrounds | video plays behind lyrics | U D |
| 17 | Settings — phones + library | two settings screens | U S |
| 18 | Settings — audio + timing | two settings screens | U S |
| 19 | Settings — gameplay + video | two settings screens | U S |
| 20 | Device tuning | ships on the S905X4 | D |

---

### Slice 0 — Foundation *(carried forward, done)*

USDX parser, beat/time conversion, per-note scoring math, line bonus and rounding, fixture
harness.

- **U** F01–F06, F08–F11 pass
- **U** no Android imports in parser or scoring modules
- **U** coverage ≥80% on those modules

---

### Slice 1 — Phone joins

WebSocket server, mDNS advertisement, join overlay, GamePhase `Open` and `Error` only.

- **U** F20 WebSocket message validation
- **U** F22 GamePhase `Open` and `Error` transitions
- **L** `mockphone` discovers the app over mDNS on loopback and completes `hello`
- **L** protocol version mismatch is rejected with the specified close code
- **L** a second phone joining an occupied session gets the specified rejection
- **L** F15 session lifecycle, join half

Song list, HTTP and playback are out of scope. The join overlay may show a placeholder
count.

---

### Slice 2 — Songs appear

HTTP client, manifest aggregation, plain vertical song list. No grid styling, no search, no
preview.

- **U** manifest aggregation merges two phones' manifests per §2.5, deduplicating by hash
- **L** `mockphone` serves `/manifest.json`; the app lists exactly those titles
- **L** F18 HTTP Range coordination — a ranged `GET /songs/<path>` returns the right bytes
- **L** F23 library multiphone
- **L** a phone disconnecting removes its songs from the list

Layout is deliberately ugly here. Slice 3 makes it a TV grid.

---

### Slice 3 — Song grid at TV size

`SongListScreen` grid layout, focus handling, search and filter. First slice with a
screenshot gate.

- **S** every screen renders at `w960dp-h540dp-land-television-xhdpi-notouch` and matches a
  committed baseline
- **S** no text below the §2.6.5 minimum size at 1080p, checked at 3× viewing distance
- **U** search filters the grid per §2.6.12
- **D** install, navigate the grid with a D-pad, screencap shows focus moving

The old `robolectric.properties` used `w1920dp-h1080dp`, which is twice the real dp in each
dimension. Every preview was rendered at four times the correct area and that was recorded
as the baseline. Fix the qualifier before generating any baseline.

---

### Slice 4 — Preview playback

First appearance of LibVLC. Preview on focus, seek-position fallback.

- **U** seek fallback: when `previewStartSec` is absent or ≤0 and `audioLengthSec` > 120s,
  seek to `min(audioLengthSec / 4, 60s)`
- **L** preview streams from `mockphone`'s HTTP server, not from a local file
- **D** focus a tile, wait 2s, assert the LibVLC handle reports position > 0
- **D** two screencaps 2s apart differ, and neither is uniformly black
- **D** moving focus stops the previous preview before starting the next

This is the slice that silently failed last time. It is isolated here precisely because it
is the first native dependency, and because a fake player reports success while nothing
decodes.

---

### Slice 5 — Select players

`SelectPlayersModal` for real. Start remains a no-op. GamePhase `Preparing`.

- **S** modal renders at TV size and matches baseline
- **U** F22 `Preparing` transitions
- **U** Start with no assigned singer is rejected

Closes the original Iter 1 scope. Slices 1–5 together deliver: launch, pair, browse,
preview, open the modal, return to the list.

---

### Slice 6 — Audio + lyrics scroll

`LibVlcPlayerHandle` wiring, `SingingScreen` lyrics and countdown, playback timing,
remaining GamePhase states, minimal clock-sync gate.

- **U** the lyrics clock advances: feed the ViewModel a rising player time and assert the
  active lyric index and elapsed display both change
- **U** `PlaybackEvent.Prepared(effectivePlaybackDurationMs)` precedes countdown
- **U** `PlaybackEvent.Ready(songStartTvMs)` derives from the first audio `Playing` event,
  and `setSongStart` is called only after it
- **U** F22 all GamePhase states
- **L** clock-sync gate: playback does not begin until every assigned singer has one valid
  sample from `mockphone`
- **D** start a song, screencap at 2s and 5s, assert the highlighted lyric line differs

The first **U** item is the one that matters. Last time `SingingViewModel` passed
`lyricsTimeMs = 0L` at the only production call site of `buildAtLyricsTime`, so the lyric
highlight and the elapsed timer never moved. Every builder unit test passed because each
supplied `lyricsTimeMs` explicitly. The wiring was the untested seam.

---

### Slice 7 — Playback control

Pause, resume, restart, quit, interruption overlay shell, audio focus, error handling.

- **U** each control drives the specified GamePhase transition
- **S** loading and error overlay variants match baselines
- **D** pause mid-song, screencap twice 2s apart, assert frames are identical
- **D** resume, assert frames differ again
- **D** a playback error returns to the song list with the blocking modal, session stays
  `Open`
- **U** audio focus is requested before playback and abandoned on end, error, or restart

---

### Slice 8 — Clock sync + UDP ingress

Full clock-sync protocol, UDP listener, pitch frame validation, jitter buffer.

- **U** F13 jitter buffer selection and staleness
- **U** F14v2 and F21 clock-sync arithmetic, both sides
- **L** F12v2 — `mockphone` sends real 20-byte `<IqIBBH` datagrams at 50fps; the app decodes
  them and emits matching `PitchFrame` values
- **L** frames carrying a stale `connectionId` are dropped
- **L** malformed and short datagrams are rejected without killing the listener

The frame layout is 20 bytes, `<IqIBBH`. This is confirmed by `tv_app.md:766`,
`phone_app.md:905`, the F12v2 fixtures (60 bytes = 3 × 20 at offsets 0/20/40) and
`mockphone` itself. The constitution's 16-byte claim and `mockphone`'s readme table are both
stale and must be corrected.

---

### Slice 9 — Live scoring, 1P

Scoring coroutine, live score display, pitch lane UI.

- **U** F08, F24 scoring integration
- **L** a perfect performance replayed from `mockphone` yields `scoreTotalInt == 10000`
- **L** a silent performance yields 0 without stalling the coroutine
- **D** sing through `mockphone` against the device, screencap at 2s and 6s, assert the
  displayed score increased
- **S** pitch lane renders at TV size and matches baseline

---

### Slice 10 — Results, single song

`ResultsScreen` per §2.6.18.1.

- **S** matches baseline at TV size
- **U** rating bands map to the specified thresholds
- **U** Back returns to the song list with the session still `Open`

---

### Slice 11 — Two phones + duet

Two-phone handling, P1/P2 assignment, duet chart routing, Swap Parts.

- **U** F04 duet parsing and track routing
- **L** two `mockphone` instances connect; both appear in `SelectPlayers`
- **L** F23 with two phones
- **L** P1 frames score against track 1 and P2 against track 2
- **L** Swap Parts reverses that routing
- **D** two phones, one duet, both scores advance independently

---

### Slice 12 — Disconnect / reconnect

Auto-pause overlay, reconnect handling, state resend.

- **L** required singer disconnects during singing → `DisconnectPaused`
- **L** reconnect with the same `clientId` gets a new `connectionId`
- **L** `assignSinger` is resent after reconnect
- **L** current `playbackState` is resent after reconnect
- **L** UDP frames carrying the old `connectionId` are rejected
- **L** Continue Without Them resumes with the remaining singers
- **U** F15 full session lifecycle

---

### Slice 13 — Medley playlist

Left-rail playlist: add, remove, reorder, `Play Medley` enabled.

- **S** populated and empty rail match baselines
- **U** reorder and remove preserve playlist invariants
- **U** `Play Medley` is non-focusable while the playlist is empty

---

### Slice 14 — Medley sequencer

Segment transitions, audio prebuffer and crossfade, medley scoring windows, segment
indicator.

- **U** F16 medley sequencer
- **L** segment boundaries fire at the specified lyric times
- **D** run a two-song medley, assert the audible gap at the transition is under 100ms when
  the prebuffer is ready
- **D** screencap across a transition, assert the segment indicator advanced

---

### Slice 15 — Medley results

`ResultsScreen` per §2.6.18.2.

- **S** matches baseline at TV size
- **U** per-segment scores and the average match the scoring engine's output

---

### Slice 16 — Video backgrounds

Real two-MediaPlayer LibVLC wiring, `#VIDEOGAP`, `SurfaceView` z-order, fallback.

- **D** with `videoUrl` present, both audio and video players report `Playing`
- **D** both players advance, and A/V stay within the 750ms tolerance
- **D** screencaps 2s apart differ and are not uniformly black
- **U** `#VIDEOGAP` produces the specified delay or seek
- **U** the video player is configured `:no-audio`
- **D** video failure falls back to `#BACKGROUND` with no error modal, and audio, scoring
  and session state are unaffected
- **D** fullscreen video uses `SurfaceView.setZOrderMediaOverlay(true)`, not `TextureView`

The existing `VlcLibVlcPlayerHandleDeviceTest` already asserts most of this correctly. It
has never run: two `assumeTrue` calls on the `audioUri` and `videoUri` instrumentation
arguments make it skip silently, and `androidTest` was never part of the branch gate.
Convert both to hard failures and wire `androidTest` into the gate.

---

### Slices 17–19 — Settings

Six screens, two per slice, so no slice hides six deliverables in one table row.

- **17** Connect Phones, Song Library
- **18** Audio (including the Preview Volume gate), Scoring Timing
- **19** Gameplay, Video

Each: **S** matches baseline at TV size, **U** each setting persists and takes effect.

---

### Slice 20 — Device tuning

- **D** HD and FHD playback verified on the Amlogic S905X4 with
  `--codec=mediacodec_ndk,all`
- **D** if that fails, Video is forced off for the device profile and the `#BACKGROUND`
  still-image fallback is used
- **D** the §2.6.16 degradation monitor degrades video without affecting audio or scoring
- **D** full flow on the device: launch, pair, browse, preview, solo, scored, duet,
  disconnect, settings, medley, results

## 5. Required specification changes

**Status: done.** `tv_app.md` v2.0 carries all of these. Recorded here so the reasoning survives.

The slicing above only works if a slice can reference part of a behaviour section. Four sections
were pulled into three or more iterations whole, which is what made the generated iteration specs
unmanageable. Each is now addressable by subsection:

| Section | Was | Now | Referenced by |
|---------|-----|-----|---------------|
| §2.6.16 SingingScreen | 305 lines, one block | 364 lines, 7 numbered groups over 25 subsections | slices 6, 7, 9, 14, 16 |
| §2.3 NetworkController | 386 lines | 443 lines, 22 numbered subsections | slices 1, 2, 8, 12 |
| §2.2 ScoringEngine | 289 lines | 342 lines, 38 subsections | slices 0, 9, 14 |
| §2.1 PlaybackCoordinator | 143 lines | 169 lines, 16 subsections | slices 6, 7, 8, 16 |

Also done:

- §7 Project Plan and Appendix A removed from `tv_app.md`; this file replaces both.
- Iteration numbering stripped. The spec says what, this plan says when. Where an iteration
  reference encoded real behaviour, the final behaviour was kept and the framing dropped.
- New §2.6.5.4.1 Design viewport binds the screenshot harness to `w960dp-h540dp-land-television-xhdpi-notouch`.
  The spec already gave 960×540dp as the design target; nothing had bound the test harness to it,
  which is how `w1920dp-h1080dp` shipped three times.
- §2.7 rewritten to describe the real `mockphone` Python repo instead of a `:mock-phone` Gradle
  module.
- `mockphone`'s readme frame table → 20 bytes, matching its own implementation.
- Constitution → v2.0.0. Principle IV no longer makes `testBranch` the single source of truth and
  now requires an L or D gate per slice. Principle I pins the 20-byte `<IqIBBH` frame.

Two items listed here in v3 were wrong and are withdrawn: the on-disk constitution is v1.0.0 and
never specified a 16-byte frame, nor mandated Media3. `tv_app.md` does not mention Media3 anywhere.

A cross-check of both specs against the 24 fixture sets found no contradictions in the pitch frame
layout, clock sync formulas, jitter thresholds, scoring constants, GamePhase FSM, `connectionId`
semantics, mDNS naming, manifest schema, or error codes. The spec was never the defect.

`phone_app.md` is untouched and still carries its own §6 Project Plan. The phone app is not in this
plan — `mockphone` plays that role — so it is deferred, not forgotten.

## 6. Definition of done

A slice is done when all of the following hold. Not a subset.

1. Its **U**, **S**, **L** and **D** gates pass, run by name, with no skips.
2. Its demo runs end to end on the device without a human editing anything mid-run.
3. Every prior slice's demo still runs.
4. No production code path is backed by a fake, a demo seed, or a no-op contract method.

Point 4 is checked, not assumed. `grep` the main source set for fake and stub types before
declaring a slice complete. The previous attempt reached 100 of 100 tasks marked complete
while production behaviour was, in its own remediation notes, "backed by demo data, fake
transports, and no-op contract methods".
