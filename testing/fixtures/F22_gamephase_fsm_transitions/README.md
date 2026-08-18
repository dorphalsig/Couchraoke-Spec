# F22 — GamePhase FSM transitions

**Platform scope**: TV-side (Android TV only).

Purpose: verify the TV GamePhase finite-state machine accepts all normative transitions and rejects representative invalid transitions from tv_app.md §4.1.

## Files

- `valid_transitions.json` — every allowed `from -> to` pair.
- `invalid_transitions.json` — representative forbidden transitions.
- `expected.transitions.json` — normalized expected validity results.

## States

`Open`, `Preparing`, `Countdown`, `Live`, `Paused`, `Error`, `DisconnectPaused`, `Stopped`, `Results`

Spec covers: tv_app.md §4.1.
