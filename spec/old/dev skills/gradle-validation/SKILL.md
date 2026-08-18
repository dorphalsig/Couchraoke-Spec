---
name: gradle-validation
description: Executes unit tests, detekt inspections, ensures test coverage and generates Roborazzi screenshots.
---
# Gradle Validation
**CRITICAL INSTRUCTION 1** Testing MUST always be done using testBranch.

## Context
Read in order:
- `.specify/memory/constitution.md`
- `CLAUDE.md`
- Load `navigation` skill

The custom gradle task `testBranch` executes unit tests, detekt inspections, ensures test coverage and generates Roborazzi screenshots
## Ownership
This skill defines how validation is run.
It may be used by:
- `implementation` for self-validation before returning
- `orchestration` for independent verification before marking tasks done
Do not treat an implementation green result as completion. Completion requires orchestration validation and audit.

## Command Pattern
Always use `timeout 10m ./gradlew <task>`
Never use bare `./gradlew`

## testBranch
Run:
`timeout 10m ./gradlew :app:clean :app:testBranch --src=<changed prod FQCNs> --test=<changed test FQCNs>`
Rules:
- include changed prod FQCNs in `--src`
- include changed test FQCNs in `--test`
- include both sides of a source/test pair when either side changed
- comma-separate FQCNs

# UI/spec verification
Required if the task touches any Screen, Modal, Preview, Roborazzi state, or class requiring `@Preview`.
testBranch will generate the Roborazzi screenshots automatically
Steps:
1. Run `git branch --show-current`.
2. Read `specs/<branch-name>/spec.md`.
3. Compare rendered Roborazzi screenshots to the spec/wireframe. Make sure to validate labels, layout, sizes, colors and fonts.
4. Create a UI checkpoint: what image (filename is enough) was compared vs what section of the spec + result

Validation fails if:
- required Screen/Modal is missing
- required `@Preview` is missing or wrong
- screenshot differs from required spec/wireframe behavior, copy, state, or layout


## Completion result
Validation is green only if:
- `testBranch` passes
- UI/spec verification passes when applicable
- all validation failures are resolved

