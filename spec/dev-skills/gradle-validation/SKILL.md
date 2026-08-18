---
name: gradle-validation
description: Runs the four validation gates (unit, screenshot, loopback, device) that prove a slice works. Use before returning from implementation and before marking a slice done.
---
# Gradle Validation

A slice is proved by the gates it declares in `plan.md`, not by `testBranch` alone. `testBranch`
runs entirely in the JVM. It cannot observe a native decoder, a real socket, or a real clock, so it
cannot see whether video plays, whether lyrics advance, or whether the layout fits a TV.

**Every slice MUST pass at least one L or D gate.** A slice proved only by U and S is not proved.

## Context

Read in order:
- `.specify/memory/constitution.md` — Principle IV defines the gates
- `plan.md` §2 — the gate vocabulary and which gates each slice declares
- `CLAUDE.md`
- Load `navigation` skill

## The four gates

| Tag | What it proves | Command |
|-----|----------------|---------|
| **U** | Pure logic. Parsers, scoring maths, state machines. | `./gradlew :app:testBranch --src=<FQCNs> --test=<FQCNs>` |
| **S** | Layout at real TV size, against a committed baseline. | `./gradlew :app:verifyRoborazziDebug` |
| **L** | The real peer protocol over loopback. | `mockphone` + `./gradlew :app:loopbackTest` |
| **D** | The real device: native decoder, real GPU, real clock. | `./gradlew :app:connectedDebugAndroidTest` |

Always wrap in a timeout: `timeout 10m ./gradlew <task>`. Never run bare `./gradlew`.

## U — unit

`timeout 10m ./gradlew :app:clean :app:testBranch --src=<changed prod FQCNs> --test=<changed test FQCNs>`

Include changed prod FQCNs in `--src` and changed test FQCNs in `--test`, comma-separated. When
either side of a source/test pair changes, include both.

`testBranch` also runs detekt and JaCoCo. Treat those as hygiene, not proof.

## S — screenshot

`timeout 10m ./gradlew :app:verifyRoborazziDebug`

Verify against a committed baseline. Do **not** use `testBranchRoborazzi` as evidence: it sets
`roborazzi.test.record=true`, which rewrites the baseline and therefore can never fail. That is why
the oversized layouts shipped three times.

The Robolectric qualifier MUST be `w960dp-h540dp-land-television-xhdpi-notouch`. This is a 1080p TV
at density 2.0, matching `TvPreviewWidth` and `TvPreviewHeight` in `tv_app.md` §2.6. A qualifier of
`w1920dp-h1080dp` renders at four times the target area, and every screenshot will look correct
while being wrong on the TV.

When a baseline changes, inspect the diff and state in the checkpoint why the new rendering is
right. A changed baseline nobody looked at is not evidence.

Required when the slice touches any Screen, Modal, Preview, or Roborazzi state. Steps:

1. Run `git branch --show-current`.
2. Read `specs/<branch-name>/spec.md` and the wireframe it references.
3. Compare each rendered screenshot to the spec: labels, layout, sizes, colours, fonts.
4. Record a UI checkpoint: screenshot filename, spec section compared against, result.

## L — loopback

Start the real `mockphone` process and drive the app against it over `127.0.0.1`. `mockphone` is a
separate Python repo. It is not a fake and cannot be stubbed, which is the point.

```
python mock_phone_reconnect.py --tv-host 127.0.0.1 --song-dir <fixture songs> --mode perfect
```

Modes: `perfect`, `silence`, `partial`, `octave_off`, `fixed_gaps`, `replay`. Use `--hit-rate` with
`partial`, `--gap-frames` with `fixed_gaps`, `--replay-file` with `replay`. Add `--disconnect-after`
and `--reconnect-delay` to exercise session lifecycle.

L is the default gate for anything crossing the peer boundary: handshake, clock sync, pitch stream,
manifest fetch, file transfer, reconnect.

## D — device

`timeout 10m ./gradlew :app:connectedDebugAndroidTest`

Required for anything touching LibVLC, the GPU, or wall-clock timing. Assert on screencaps pulled
from the device, not on log lines.

If no device is reachable, the slice is **blocked**, not passed. Say so and stop.

## Validation fails if

- any declared gate fails
- the slice declares no L or D gate
- a test inside a gate was skipped; `assumeTrue` and equivalent runtime skips are failures, not
  passes
- a screenshot baseline changed and nobody inspected the diff
- a required Screen, Modal, or `@Preview` is missing or wrong
- a rendered screenshot differs from the spec's behaviour, copy, state, or layout

## Completion

Report green only when every gate the slice declares passed fresh, at least one of them was L or D,
and all failures are resolved. Report `blocked` when a gate cannot run.

Never report a slice complete on U and S alone. An implementation green result is not completion:
completion requires `orchestration` to run the gates independently and audit the evidence.
