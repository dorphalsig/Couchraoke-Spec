# ADR-006: Three self-contained per-platform specs with duplicated shared sections

**Status:** Accepted
**Date:** 2026-03-08 (recorded retroactively 2026-04-24)
**Deciders:** Product/spec author, Claude Code

## Context

The project was specified as a single monolithic document (`couchraoke_spec.md` v4.20) covering TV host, Android companion, and iOS companion in one file. The monolith was the right design *tool* — holding the whole picture in one place while decisions were still being made — but it became the wrong delivery mechanism once implementation started across three independent repositories:

- **Android TV host** (Kotlin, Jetpack Compose for TV).
- **Android companion** (Kotlin).
- **iOS companion** (Swift).

Each repository is driven by SpecKit, whose agent sessions load whatever markdown is visible as context. Three concrete problems surfaced:

1. **Context pollution.** An agent building the iOS companion does not need the TV-side medley sequencer, scoring engine, or song-list grid. Feeding it the full monolith wastes context window and invites hallucinated cross-platform decisions.
2. **Drift risk.** Cross-document references (e.g., "see `§8.3` of the main spec") are stable on paper but unreliable in practice: agents follow the referenced content only sometimes, and the reference itself rots when the pointed-to document moves.
3. **Constitution coupling.** Per-repo SpecKit constitutions (`.specify/memory/constitution.md`) should name the platform's libraries and test frameworks. A monolithic spec forces every constitution to either duplicate or vaguely reference the shared text.

A further constraint: shared protocol sections — wire formats, session handshake, clock sync, message schemas — MUST NOT diverge across platforms. Any mechanism for sharing must make divergence visibly wrong, not merely discouraged.

## Decision

Split the monolithic spec into three **fully self-contained** platform-specific documents. Shared protocol sections are **duplicated verbatim** across every doc where they apply, each copy marked with an explicit immutability warning.

**Documents:**

- `tv_app.md` — Android TV host, full spec including UI, rendering, scoring, playback, session, medley.
- `phone_app.md` — Android + iOS companion combined in one document (both targets share the same spec surface for mic capture, HTTP server, pairing, pitch detection; platform-specific sections are called out explicitly inside).
- Per-platform SpecKit constitutions live in each repo's `.specify/memory/constitution.md` and name only library/version pins plus a pointer to the test policy.

**Duplication rules:**

- Shared protocol sections (`§8.x` wire formats, message schemas, clock sync, mDNS advertisement, session token/join code) are **duplicated verbatim** between `tv_app.md` and `phone_app.md`.
- Every duplicated block is wrapped or prefixed with a `⛔ DO NOT MODIFY WITHOUT CROSS-PLATFORM COORDINATION` marker.
- Placeholder references like `[See spec_android_tv.md for full content]` are explicitly **wrong** — fully self-contained specs is a hard requirement.

**Fixture sharing:**

- `fixtures/manifest.json` with a `covers` property mapping fixtures to spec sections — fixtures are the one exception to duplication because they are machine-consumed test artefacts, not human-read spec content.

## Options Considered

### Option A: Keep the monolith in every repo

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low (no split) |
| Cost | High per-agent context waste |
| Scalability | Poor |
| Team familiarity | High |

**Pros:** One source of truth.
**Cons:** Every agent session for every platform loads the full document. SpecKit does not filter content by platform. Context waste compounds over time.

### Option B: Shared file plus pointer references from per-platform specs

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium (submodules or sync scripts) |
| Cost | Medium |
| Scalability | Medium |
| Team familiarity | Medium |

**Pros:** Single source of truth for shared sections. DRY.
**Cons:** Pointers are followed unreliably by LLM agents. Submodules add Git friction. Sync scripts add build-system dependencies. When a cross-platform change is needed, the process is "update shared/, then each repo pulls" — a multi-step dance that drifts in practice.

### Option C: Fully self-contained per-platform specs with verbatim duplication (adopted)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium at edit time (must touch multiple files for shared changes) |
| Cost | Zero at read time |
| Scalability | Excellent |
| Team familiarity | High |

**Pros:** Agent sessions see only relevant content. No pointers to follow. No submodule friction. Shared-section drift is catchable by a textual diff script. The `⛔` marker makes the intent of each duplicated block obvious to humans and agents alike.
**Cons:** Protocol changes touch multiple files in one pass. Discipline required to keep duplicates aligned.

## Trade-off Analysis

**Read cost vs. edit cost.** Option A minimises edit cost at the price of reading the full monolith every agent session, for every platform, forever. Option B claims to minimise both but fails in practice because LLM agents don't reliably cross document boundaries. Option C accepts a larger edit cost — which is episodic, happens only when shared protocol changes — in exchange for zero read-time waste, which is continuous.

**DRY vs. visibility.** DRY is an optimisation for human maintenance cost. Verbatim duplication with an `⛔` marker is an optimisation for *agent* correctness: an agent that sees the full protocol inline cannot accidentally ignore it, and the marker makes the cross-cutting constraint visible at the point of use rather than hidden behind a link.

**Drift mitigation.** A simple textual-diff script can flag cross-platform divergence in shared blocks at CI time. This gives the safety net that Option B's pointer model claimed to provide but did not deliver.

## Consequences

- Every protocol change is an explicit multi-file edit. This is a feature, not a bug — it forces cross-platform coordination to be visible.
- Shared-block drift is possible if duplicates diverge unnoticed. Mitigation: a CI check that diffs `⛔`-marked regions across documents.
- Per-repo SpecKit constitutions stay small (library pins + pointer to test policy); platform-specific normative content lives in the relevant spec doc, not in the constitution.
- TV-only UI content (design tokens, wireframes, focus rules, motion budgets) lives only in `tv_app.md` and is absent from `phone_app.md`.
- iOS-only concerns (iCloud ubiquity, `NSFileCoordinator`, backgrounding suspension, idle-timer rules) are marked inline within `phone_app.md` as iOS-specific sections; they are not duplicated to the Android companion.
- The original monolith (`couchraoke_spec.md`) is archived, not deleted; it remains the reference for the pre-split period and for verifying that nothing was lost in translation.
- Future design documents (e.g., the 2026-04-21 TV UI design spec) are merged into the relevant platform spec rather than added as separate cross-referenced documents; keeping a floating design doc alive reintroduces the drift problem Option C was chosen to avoid.

## Action Items

1. [x] Split monolithic `couchraoke_spec.md` v4.20 into `tv_app.md` and `phone_app.md`.
2. [x] Duplicate shared protocol sections verbatim with `⛔ DO NOT MODIFY WITHOUT CROSS-PLATFORM COORDINATION` markers.
3. [x] Merge `2026-04-21-tv-app-design.md` into `tv_app.md` §2.6 (Design Tokens and Visual System) rather than keeping it as a floating cross-referenced doc.
4. [x] Update test strategy and fixture manifest to reference the split structure.
5. [ ] Add a CI check that diffs `⛔`-marked regions across `tv_app.md` and `phone_app.md` and fails the build on divergence.
6. [ ] Archive (don't delete) the pre-split `couchraoke_spec.md` in an `/archive` folder of the spec repo.
