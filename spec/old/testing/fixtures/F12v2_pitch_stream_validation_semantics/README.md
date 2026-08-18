# F12v2: Binary Pitch Codec

## Purpose

This fixture tests the parsing and validation of the highly optimized 20-byte binary UDP datagram codec used for streaming real-time pitch data from the mobile companion app to the TV host.

It replaces the legacy text-based `F12` fixture to comply with the v4.19 specification requirements for minimal audio latency and zero GC spikes.

## Files

* `frames.bin`: A raw 60-byte binary file containing exactly three 20-byte little-endian UDP datagrams.

* `expected.json`: An array of JSON objects representing the expected decoded output of those frames, including their derived `toneValid` status.

## Payload Structure

Each frame must be parsed strictly as a 20-byte little-endian struct (`<IqIBBH`):

| Offset | Field | Type | Size | Description | 
 | ----- | ----- | ----- | ----- | ----- | 
| `0x00` | `seq` | `uint32` | 4 bytes | Monotonically increasing sequence number. | 
| `0x04` | `tvTimeMs` | `int64` | 8 bytes | The synchronized TV clock time of the vocal capture. | 
| `0x0C` | `songInstanceSeq` | `uint32` | 4 bytes | Identifier for the current song instance (prevents stale frame bleeds). | 
| `0x10` | `playerId` | `uint8` | 1 byte | `0` for Player 1, `1` for Player 2. | 
| `0x11` | `midiNote` | `uint8` | 1 byte | The detected pitch. `255` is a reserved sentry value indicating silence. | 
| `0x12` | `connectionId` | `uint16` | 2 bytes | The active socket connection ID of the client. | 

## Test Scenarios Covered

The `frames.bin` payload (60 bytes total: 3 frames × 20 bytes) contains three specific scenarios targeting Modules 5.1 and 5.2 of the test strategy:

1. **Valid Frame (Offset 0):** A standard hit (`midiNote=60`). Must parse successfully and yield `toneValid=true`.

2. **Silence Marker (Offset 20):** A frame where no pitch is detected (`midiNote=255`). Must parse successfully but yield `toneValid=false`.

3. **Stale/Mismatched Instance (Offset 40):** A frame with an invalid `songInstanceSeq` (e.g., `99` instead of `3`). The decoder parses it successfully (`toneValid=true`), but the host application's validation layer must silently drop it.

## Wire Format Change History

Per ADR-004:
- **2026-04-24**: `tvTimeMs` widened from `int32` (4 bytes) to `int64` (8 bytes) to handle TV uptime >25 days. Frame size: 16 → 20 bytes. Struct: `<IiIBBH` → `<IqIBBH`.
- **2026-03-01**: HMAC-SHA256 removed, `connectionId` routing introduced. Frame size: 30 → 16 bytes.