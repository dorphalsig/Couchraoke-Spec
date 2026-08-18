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
8. Run the scoped validation it defines.
9. If validation fails, follow Failure Protocol.
10. Return either:
    - `green`: changed files, source/test FQCNs, validation command, validation result
    - `blocked`: failure output, context, attempted fixes, next steps

Do not mark tasks complete. Only `orchestration` may do that.

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

@NoCoverageGenerated comes from com.couchraoke.quality.NoCoverageGenerated


## Preview rules

For every Screen/Modal composable:

- public
- `@Preview(name="...", widthDp=X, heightDp=Y)`
- preview name matches spec/wireframe
- dimensions match target platform
- one preview per meaningful spec state