# F20 — WebSocket message validation

**Platform scope**: TV-side (Android TV only).

Purpose: verify WebSocket handshake validation and error responses for malformed or incompatible `hello` messages.

## Files

- `case_valid_hello/input.hello.json` / `expected.sessionState.json`
- `case_missing_clientId/input.hello.json` / `expected.error.json`
- `case_bad_protocolVersion/input.hello.json` / `expected.error.json`
- `case_missing_httpPort/input.hello.json` / `expected.error.json`

## Validation rules covered

- Missing `clientId` → reject with `invalid_message`
- `protocolVersion != 1` → reject with `protocol_mismatch`
- Missing `httpPort` → reject with `invalid_message`
- Valid `hello` → accept and return `sessionState` with `connectionId`

Spec covers: §8.3.2.1, §8.3.3, Appendix B
