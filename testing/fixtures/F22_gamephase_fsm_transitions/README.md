# F22 — GamePhase FSM transitions

**Platform scope**: TV-side (Android TV only).

Purpose: verify the TV GamePhase finite-state machine accepts all normative transitions and rejects invalid transitions.

## Files

- `valid_transitions.json` — every allowed `from -> to` pair
- `invalid_transitions.json` — representative forbidden transitions
- `expected.transitions.json` — normalized expected validity results

## States

`Idle`, `Loading`, `Countdown`, `Playing`, `Paused`, `DisconnectPaused`, `Stopped`, `Results`

Spec covers: §2.4 (functional behavior), architecture/tv_app_architecture.md §4.1
