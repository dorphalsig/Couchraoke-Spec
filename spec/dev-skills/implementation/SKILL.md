---
name: implementation
description: implementation workflow for code, tests, bug fixes, refactors, and feature work.
---

# Implementation
**CRITICAL INSTRUCTION 1** This workflow is mandatory for all implementation tasks. Follow every step in order. Do not deviate
**CRITICAL INSTRUCTION 2** Debugging MUST follow the Failure Protocol below
## Workflow

1. Read:
   - `.specify/memory/constitution.md`
   - `CLAUDE.md`

2. Load `navigation`.

3. Create the navigation checkpoint before editing:
   - scoped files
   - symbols or slices read
   - one-hop context read, if any
   - why the context is sufficient

4. Plan the smallest in-scope change.
5. Write or update tests first.
6. Implement the change.
7. Load `gradle-validation`.
8. Run the gates the slice declares for this change. U for logic, S for UI. Do not claim the slice's
   L or D gate — `orchestration` runs that on the integrated slice.
9. If validation fails, follow Failure Protocol.
10. Return either:
    - `green`: changed files, source/test FQCNs, gates run, gate results
    - `blocked`: failure output, context, attempted fixes, next steps

Do not mark tasks complete. Only `orchestration` may do that. A `green` return means your pair's
gates passed, not that the slice works.

## Failure Protocol

For any failure:

1. Read the full failure output.
2. Identify the error type.
3. Use the right research tool if needed.
4. Navigate to the failing symbol or file.
5. Trace backward to root cause.
6. Make the smallest valid fix.
7. Rerun validation.
8. Stop after three failed fix+validate attempts and return `blocked`.

## Coverage rules

| Class type | Requirement |
|---|---|
| Pure UI helpers | `@NoCoverageGenerated`; no JVM unit tests |
| Screens / Modals | `@NoCoverageGenerated`; required `@Preview`; no JVM unit tests |
| UI with meaningful visual states/spec states| `@NoCoverageGenerated`; Roborazzi state tests |
| Non-UI logic / ViewModels | JVM unit tests; no `@NoCoverageGenerated` |
| Wiring and composition roots | JVM unit tests on the factory, plus an L or D gate |

@NoCoverageGenerated comes from com.couchraoke.quality.NoCoverageGenerated

Wiring is the seam unit tests miss. A ViewModel can pass every unit test while the value it reads is
hardcoded at its one production call site. When a class constructs collaborators or passes values
between them, extract a factory the tests can call, and prove the wired result with a gate that runs
the real thing.


## Preview rules

For every Screen/Modal composable:

- public
- `@Preview(name="...", widthDp=960, heightDp=540)` for a fullscreen surface
- preview name matches spec/wireframe
- dimensions in dp, sized against the 960×540dp TV viewport — never the 1920×1080 pixel figure
- one preview per meaningful spec state

960×540dp is a 1080p TV at density 2.0. It is `TvPreviewWidth` and `TvPreviewHeight` in `tv_app.md`
§2.6. A preview authored at 1920×1080dp renders at four times the target area and hides every
oversized element.