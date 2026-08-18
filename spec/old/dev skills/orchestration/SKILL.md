---
name: orchestration
description: coordinate implementation slices from tasks.md. use for phase/slice implementation, test+impl task pairing, direct vs subagent execution, validation, audit, Claude Code task tracking, and marking tasks done.
---

# Orchestration

Use for implementation work defined in `tasks.md`.

## Read first

Read if not already loaded:

- `CLAUDE.md`
- `.specify/memory/constitution.md`
- `tasks.md`

`tasks.md` is the source of truth.

## Core rules

- Mirror the requested slice from `tasks.md` into the Claude Code task tracker before coding.
- Keep the Claude Code task tracker synchronized with `tasks.md`.
- Work in `tasks.md` order.
- Pair each test task with its matching implementation task.
- One test + implementation pair is one unit of work.
- Without subagents: work on one pair at a time.
- Parallel work is allowed only through subagents.
- A `parallelizable` marker only means eligible for subagent parallelism.
- The mandatory workflow is the only allowed execution path.
- Do not mark tasks done until validation and audit both pass.

## Mandatory workflow

Follow this exact sequence for the requested slice. Do not skip, reorder, or parallelize steps except where this skill explicitly allows subagents.

1. Find the slice in `tasks.md`.
2. Mirror its tasks into the Claude Code task tracker.
3. Pair matching test and implementation tasks.
4. For each pair, in `tasks.md` order:
   - mark the pair `in_progress`
   - implement it using the `implementation` skill
   - load `gradle-validation`
   - independently rerun `testBranch` using the FQCNs returned by implementation
   - run 2-5 spot-checks against the spec
   - if implementation returned green, orchestration `testBranch` passes, and spot-checks pass, mark the pair done in TaskUpdate and `tasks.md`
   - if either fails, fix using the `implementation` failure protocol and repeat validation

**IMPORTANT:** Do not start the next pair until the current pair is done or blocked.

## Subagents

Use subagents only when the user explicitly allows delegated or parallel work.

When using subagents:

- Assign exactly one test + implementation pair per subagent.
- Use one branch and one worktree per pair.
- Put worktrees under `.claude/worktrees`.
- Do not reuse worktrees.
- Do not check out the same branch in multiple worktrees.

Each subagent prompt must say:

- read `CLAUDE.md`
- load `navigation`, `implementation`, and `gradle-validation`
- implement only the assigned pair
- follow the `implementation` workflow
- return changed files, validation results, and spec notes

## Failures

If anything fails or is unclear:

- do not delegate the fix
- keep the pair incomplete
- follow the `implementation` failure protocol
- rerun `testBranch`
- repeat the spec spot-check

## Audit

- implementation returned `green`
- navigation checkpoint exists
- changed files match scope
- no unexpected files changed
- `testBranch` passes independently
- UI/spec verification passes when applicable
- behavior matches spec
- `@NoCoverageGenerated` usage is valid
- TaskUpdate matches `tasks.md`