# ADR-004: UDP pitch-frame wire protocol

**Status:** Accepted (current layout since 2026-04-24)
**Date of this record:** 2026-04-24
**Deciders:** Product/spec author, Claude Code

This ADR is historical. It records three dated decisions that together shaped the current 20-byte UDP pitch-frame layout. Each section documents the concern of its moment — not what seems right in retrospect.

---

## Timeline

| Date | Event | Outcome |
|------|-------|---------|
| pre-2026-02-27 | Original spec: 30-byte frame, HMAC-SHA256 authTag, `pitchHmacKey` in `sessionState` | Live in spec v4.5 |
| 2026-02-27 | Initial full-spec audit | Found transport contradiction (WebSocket vs UDP for pitch) and other cross-section issues |
| 2026-02-28 | "Prompt confirmation" — role locked, v4.5 read end-to-end | 20 open gaps catalogued |
| **2026-03-01** | **"Acknowledgment" thread — Mike challenges HMAC and ZIP delivery as overengineering** | **HMAC removed; frame 30 B → 16 B; `connectionId` introduced** |
| 2026-03-09 | Migration plan review checkpoint | `connectionId` at bytes 14–15 confirmed; layout stable |
| 2026-03-10 | Comprehensive v4.16 audit | No wire-format changes; previous-audit findings re-flagged |
| **2026-04-24** | **"Implementation gap analysis" — `int32 tvTimeMs` overflow found** | **`tvTimeMs` widened to `int64`; frame 16 B → 20 B** |

---

## Act 1 — The original sin (pre-February 2026)

### Concerns of the moment

Early drafts of the spec were produced in a climate of accumulating "enterprise" patterns. Cryptographic authentication of pitch datagrams felt right on paper: the frames are sensitive to session, they traverse an uncontrolled LAN, and signing them at the sender looks responsible.

No specific threat model was written down to justify HMAC. It was inherited from the shape of systems that normally carry authenticated payloads, without asking whether that shape fit a karaoke game on a home Wi-Fi network.

### State at the beginning of the audit cycle

- 30-byte frame: `seq (uint32) | tvTimeMs (int32) | songSeq (uint32) | playerId (uint8) | midiNote (uint8) | authTag (16 bytes)`.
- `authTag = HMAC-SHA256(pitchHmacKey, frame[0..13])[0..15]`.
- `pitchHmacKey` distributed via `sessionState` on each WebSocket handshake.
- TV-side validation required per-datagram HMAC recomputation at 50 fps per singer.

### Parallel concerns

The same audit period (2026-02-27) surfaced a separate, louder contradiction: whether pitch frames travel over WebSocket or UDP at all. The spec said both in different sections. UDP won, but the discussion cemented a pattern that became load-bearing for Act 2: **the spec was at that moment dense with contradictions that only full re-reads would surface.**

The companion app was Flutter (iOS + Android) at this point — a fact that matters for Act 2 because GC pressure on Dart's hot path was a real concern, not a hypothetical one.

---

## Act 2 — The simplification (2026-03-01, "Acknowledgment" thread)

### Concerns of the moment

By early March, the preoccupation had shifted from "find the contradictions" to "does this actually need to be this complex?". Mike opened the 2026-03-01 conversation with two pre-formed observations, presented for critical evaluation rather than as conclusions to be accepted:

1. That ZIP-over-WebSocket for song delivery was a severe startup bottleneck caused by mid-tier Android TV disk I/O.
2. That HMAC-SHA256 on every 30-byte UDP datagram at 50 Hz was "textbook overengineering" causing battery drain and thermal throttling on older phones, plus CPU/GC pressure on both ends.

The analysis that followed rejected the reasoning behind both claims but kept both conclusions — and the reasons it kept the HMAC conclusion are the reasons that survive today:

**Why the performance reasoning was rejected.** ARMv8-A (every post-2020 Android SoC) has hardware SHA-2 extensions. HMAC-SHA256 at 300–600 MB/s in hardware is ~0.5–2 μs per 30-byte op, 25–100 μs per second at 50 Hz, <0.01 % CPU. Thermal throttling and battery claims did not survive contact with the arithmetic. The GC-pressure argument was weak too: a naive Dart implementation would allocate ~1,500 bytes/sec of garbage, well within generational GC tolerance.

**Why the conclusion survived anyway — the real argument.** HMAC on a LAN with no transport encryption is **false security**. The control channel (WebSocket) was already cleartext. An adversary able to sniff or inject on the LAN could already disrupt the session through the control path; HMAC on the pitch path protected nothing that wasn't already exposed. The threat model that actually matters for a home karaoke game is **accidental cross-session traffic** — two TVs advertising similar codes on the same network, a phone whose old UDP frames linger after reconnect, a stale session ID. That's a **routing problem**, not a cryptographic one.

`connectionId` solved the routing problem directly: uint16 assigned by the TV at `hello`, delivered once via `sessionState`, embedded in every subsequent datagram. Reconnect triggers a new ID, which implicitly invalidates every stale frame from the prior connection. No crypto, no key distribution, no hot-path cost.

### Decision (taken 2026-03-01)

- Remove HMAC-SHA256 authentication entirely. Remove `pitchHmacKey` from `sessionState`.
- Shrink frame to 16 bytes: `seq (uint32) | tvTimeMs (int32) | songSeq (uint32) | playerId (uint8) | midiNote (uint8) | connectionId (uint16)`.
- TV validation reduces to: length check, `connectionId → playerId` table lookup, `songInstanceSeq` match.
- Explicit in the spec: "best-effort routing, not a security control."

### Causal links to other ADRs

The same conversation produced the decision recorded as [ADR-003](ADR-003-song-delivery-phone-http-server.md). It is not a coincidence that both landed on the same day: both came from the same critical re-read, and the pattern — "accept the conclusion, reject the sloppy reasoning, write down the actual reason" — carried across both.

The connection to [ADR-002](ADR-002-framework-native-kotlin-swift-over-flutter.md) is indirect but real. On 2026-03-01, Flutter was still the framework; the GC-pressure argument for removing HMAC was therefore evaluated in a Flutter context. Five days later Flutter was out, and with it the original motivation for worrying about Dart GC on the hot path. The decision to remove HMAC survived the framework change unchanged, because its real justification ("false security on LAN") was platform-independent.

### What stayed unsaid in Act 2

The wire format kept `int32 tvTimeMs` unchanged from the 30-byte layout. No one challenged it. The concern of the moment was overengineering; arithmetic correctness of the monotonic clock field was not on the table.

---

## Act 3 — The arithmetic bug (2026-04-24, "Implementation gap analysis" thread)

### Concerns of the moment

By late April, implementation was imminent. ADR-001 had just landed (2026-04-24), consolidating 16 spec clarifications to unblock build-out. The mood had shifted from "is this too complex?" to "does this actually work in production?"

The gap analysis performed that day walked the spec looking for correctness failures, not stylistic ones.

### Finding

`pitchFrame.tvTimeMs` was declared `int32` on the wire. The TV's monotonic clock uses `System.nanoTime() / 1_000_000`, which is an arbitrary value anchored at device boot. `Int.MAX_VALUE = 2,147,483,647 ms ≈ 24.86 days`.

Android TV sticks routinely run for weeks between reboots. The first time the TV's uptime crosses ~25 days mid-session, the phone's `tvTimeEstMs` estimate pushes `tvTimeMs` into the wire as a *negative* signed int32. On the TV side:

- `latenessMs = arrivalTvMs - tvTimeMs` goes wildly wrong.
- `latenessMs > MAX_PLAYOUT_DELAY_MS (450)` becomes true for essentially every frame.
- The jitter buffer silently drops every subsequent pitch frame.
- Scoring sees silence.

This is not a theoretical edge case. The internal scoring code (`PitchFrame.tvTimeMs`, `songStartTvMs`) was already `Long` in Kotlin; the wire codec was the narrow point compressing it. The bug was entirely in the wire format.

### Options considered (on the day)

- **Widen to `int64`.** Frame grows 16 → 20 bytes. Struct `<IqIBBH`. +4 B × 50 fps × 2 singers = ~800 B/s per session. **Adopted.**
- **Redefine `tvTimeMs` as song-relative.** Requires a zero-point field in `assignSinger` and breaks the symmetry where phone and TV read the same monotonic value. Complicates worked examples in Appendix C. **Rejected.**
- **Reinterpret `int32` as `uint32` with epoch heuristic.** Extends range to 49.7 days and requires sliding-epoch logic that will break silently at an unpredictable boundary. **Rejected as brittle.**

The widening was mechanical: fixture F12v2 golden bytes, Appendix A.3 UDP test data policy references to "16-byte", and mock phone packing (`<IiIBBH` → `<IqIBBH`) all changed in one pass.

### Consequence visible in later state

The `userMemories` entry records the pitch frame as 30 bytes with format `<IiIBBH` — a description that blends the 30-byte layout's total with the 16-byte layout's struct. It is stale by ~1 day relative to the current spec and never matched any shipped version exactly. The authoritative record is now this ADR plus the spec text: **20 bytes, `<IqIBBH`**.

---

## Current wire format

20-byte fixed-size little-endian UDP datagram, struct `<IqIBBH`:

```
Offset  Size  Type     Field
  0      4   uint32   seq              — frame counter
  4      8   int64    tvTimeMs         — phone's estimate of TV monotonic ms
 12      4   uint32   songInstanceSeq  — from assignSinger
 16      1   uint8    playerId         — 0=P1, 1=P2
 17      1   uint8    midiNote         — 0..127 voiced, 255=unvoiced
 18      2   uint16   connectionId     — assigned by TV at hello, delivered via sessionState
```

TV validation per datagram: length check, `connectionId` is registered, `connectionId` matches expected connection for `playerId`, `songInstanceSeq` matches the active song or (during medley transition) the segment that has reached `loadChart()` but not yet `setSongStart()`. Drop on any failure.

Authenticity: best-effort routing, not a security control. `toneValid = (midiNote != 255)`.

## Consequences

- The spec will never again carry HMAC or a `pitchHmacKey`. Re-adding either requires revisiting this ADR and articulating a threat model that Act 2 didn't see.
- `connectionId` invalidation on reconnect is the sole mechanism preventing stale-frame admission. No session-resume path carries the old ID forward.
- The 2026-04-24 widening is the last change this format is expected to see for the MVP. Any further wire change (e.g., adding a secondary pitch candidate for pYIN HMM support) is a new ADR, not an amendment to this one.
- Fixture F12v2 must reflect 20 bytes / `<IqIBBH` everywhere. Any fixture that still carries "16 bytes" or `<IiIBBH` is a stale artefact to be updated.

## Action Items

1. [x] 2026-03-01: HMAC removed, `connectionId` introduced, frame 30 B → 16 B.
2. [x] 2026-03-01: `pitchHmacKey` removed from `sessionState` schema.
3. [x] 2026-04-24: `tvTimeMs` widened to `int64`, frame 16 B → 20 B, struct `<IqIBBH`.
4. [x] 2026-04-24: `mock_phone.py` and `mock_phone_reconnect.py` updated to new packing.
5. [x] Verify Appendix A.3 UDP test data policy references "20-byte" consistently — any lingering "16-byte" is a stale artefact from Act 2.
6. [ ] Update stored memory note that records a 30-byte / `<IiIBBH>` layout (never matched any shipped version).
7. [ ] Revisit this ADR if a public-venue deployment model is ever proposed — the "trusted LAN" threat model is the only thing holding the no-crypto decision in place.
