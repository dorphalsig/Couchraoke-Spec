# Couchraoke — Testing Policy
**Applies to**: Android TV host (Kotlin), Android companion (Kotlin), iOS companion (Swift)  
**Spec ref**: §Appendix D.1 (normative coverage targets)  
**Version**: 1.3 — 2026-03-08
This document is the single source of rules governing how tests are written, run, and enforced across all platforms. 
> **Focus Directive:** When reading this policy, strictly apply only the rules, linters, and libraries relevant to your current target platform (Android/Kotlin vs. iOS/Swift). Ignore sections dedicated to other platforms.
> **Platform Maps:** For the exact test cases, module breakdowns, and fixture mappings required for Android features, **you MUST retrieve and follow `test_guide_android.md`** before writing tests for a specific module. iOS inventories live in `test_strategy_ios.md`.
---
## 1. Approach
**Test-Driven Development (TDD).** Tests MUST be written before or alongside the production code they cover. No production code is merged without corresponding tests. This is a CI gate, not a suggestion.
---
## 2. Test Libraries 
*(Note: Android testing libraries and version constraints are strictly defined in `android_constitution.md` under Technology Constraints.)*
### 2.1 iOS (Swift)
| Purpose | Library | Notes |
|---|---|---|
| Unit + integration | `XCTest` | Xcode built-in; no external dependency |
| Mocking | Protocol-based test doubles | No third-party mock library; define lightweight `protocol` facades |
| JSON assertions | `JSONDecoder` + `Codable` | Decode and compare field-by-field; never string-compare JSON |
---
## 3. Coverage Requirements
From **Appendix D.1** (normative, reproduced here for visibility):
| Threshold | Value |
|---|---|
| Overall project line coverage | ≥ 80% |
| Per-file minimum | ≥ 60% |
| Tiny file exemption | Files with ≤ 30 non-comment, non-blank lines |
| Generated code exemption | Protobuf stubs, schema-generated types |
- Coverage is measured across the **full** test suite (unit + integration + acceptance). Running only unit tests does not satisfy the target.
- **CI MUST fail the build** if either threshold is not met on any qualifying file.
- Coverage tooling: **JaCoCo** for Android (configured in Gradle); **Xcode code coverage** enabled on the test scheme (`LLVM_COV`).
---
## 4. Test Categories
| Category | Definition | Annotation |
|---|---|---|
| **Unit [U]** | Single class/function in isolation; all I/O mocked | (default) |
| **Instrumented [I]** | Requires real OS resource: socket, filesystem, hardware | Android: `@MediumTest` or `@LargeTest`; iOS: on-simulator/device |
| **Acceptance** | Fixture-driven; consumes `fixtures/` and asserts against `expected.*` files | Tag with `@Tag("acceptance")` (Android) / `XCTestCase` subclass suffixed `AcceptanceTests` (iOS) |
Instrumented tests MUST NOT run in the unit test CI job. They run in a separate job that provisions an emulator or simulator.
---
## 5. Test Naming Convention
### Android (Kotlin)
```kotlin
fun `given <context>, when <action>, then <expected outcome>`()
```
Example:
```kotlin
@Test
fun `given toneValid false, when encoding pitchFrame, then midiNote byte is 255`()
```
### iOS (Swift)
```swift
func test_<subject>_<action>_<expectedOutcome>()
```
Example:
```swift
func test_pitchFrameEncoder_toneValidFalse_setsMidiNoteTo255()
```
One assertion focus per test. A test that validates 5 unrelated behaviours is 5 tests.
---
## 6. Test Isolation
- Tests MUST NOT share mutable state. No `static` / `companion object` fields that accumulate state across tests.
- Tests MUST NOT depend on execution order. Each test sets up and tears down its own state.
- Tests MUST NOT touch the real filesystem, real network, or real clock unless explicitly tagged `[I]`.
- **Clock**: inject a `FakeClock` / `TestCoroutineScheduler` — never call `System.currentTimeMillis()` or `Date()` directly in testable code.
---
## 7. Coroutine Testing (Android)
- Use `StandardTestDispatcher` (not `UnconfinedTestDispatcher`) as the default in all unit tests. `UnconfinedTestDispatcher` masks ordering bugs by running coroutines eagerly.
- Wrap test bodies with `runTest { }` from `kotlinx-coroutines-test`.
- Inject dispatchers via constructor — never hardcode `Dispatchers.IO` or `Dispatchers.Main` in production classes that need to be tested.
```kotlin
// Production
class SongScanner(private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO)
// Test
val scanner = SongScanner(ioDispatcher = StandardTestDispatcher(testScheduler))
```
---
## 8. Skip / Disable Policy
A test MAY be skipped only under one of these three conditions:
| Condition | Required action |
|---|---|
| Blocked by a known spec ambiguity | Annotate with `@Disabled("SPEC-<issue>: <one-line reason>")` (Android) or `try XCTSkip("SPEC-<issue>: ...")` (iOS). Must link to a tracked issue. |
| Hardware-only test running in unit CI job | Move to the instrumented job instead. Do not skip — fix the job configuration. |
| Test is demonstrably flaky (intermittent failure ≥ 2 times in 10 runs) | Move to quarantine (see §9). Do not leave a flaky test enabled in main CI. |
**Skipped tests count against coverage.** A file full of skipped tests will fail the per-file coverage gate. There is no silent exemption.
Blanket `@Disabled` on a test class is not permitted. Disable individual test methods only.
---
## 9. Flaky Test Quarantine
A test is **flaky** if it fails intermittently without code changes (e.g., timing sensitivity, uncontrolled I/O).
Process:
1. Move the test to a `quarantine` source set / test target (separate from the main suite).
2. Open a tracking issue with: test name, failure mode, reproduction rate.
3. The quarantine suite runs on a nightly schedule, not on every PR.
4. A quarantined test MUST be fixed or deleted within **2 sprints**. It may not live in quarantine indefinitely.
5. Quarantined tests are **excluded** from the coverage measurement until restored.
---
## 10. Static Analysis and Linting
Static analysis is a **CI gate** — the build fails if any rule configured as `error` is violated.
### 10.1 Android
| Tool | Role | Config file | CI gate |
|---|---|---|---|
| **Detekt** `1.23.x` | Kotlin code smells, complexity, style | `detekt.yml` in repo root | Yes — error-level findings fail build |
| **ktlint** `1.2.x` | Formatting (via Detekt `detekt-formatting` plugin) | `.editorconfig` | Yes |
| **Android Lint** | Android-specific issues (missing permissions, deprecated APIs) | `lint.xml` | Yes — `abortOnError true` in Gradle |
Detekt rules in scope (others left at default):
```yaml
complexity:
  LongMethod:
    threshold: 40        # test methods exempt via @Suppress if genuinely data-driven
  CyclomaticComplexMethod:
    threshold: 10
style:
  MagicNumber:
    active: true
    ignoreTests: true    # fixture numeric literals in tests are fine
naming:
  FunctionNaming:
    active: true
    functionPattern: '^[a-z`][a-zA-Z0-9 ,_`<>()?.]*$'   # allows backtick test names
```
### 10.2 iOS
| Tool | Role | Config file | CI gate |
|---|---|---|---|
| **SwiftLint** `0.57.x` | Swift style and code smells | `.swiftlint.yml` in repo root | Yes — errors fail build, warnings do not |
SwiftLint rules enabled beyond defaults:
```yaml
opt_in_rules:
  - force_unwrapping        # error: no force-unwrap in production code
  - explicit_init
  - closure_spacing
disabled_rules:
  - todo                    # TODOs allowed with ticket reference; enforced by PR review not lint
```
Force-unwrap (`!`) in **test** files is permitted where the test will immediately crash and clearly indicate the failure. It is **not** permitted in production code.
---
## 11. Known Spec Inconsistency Handling
When a test is blocked or ambiguous due to a documented spec inconsistency, follow this process:
1. Use the **authoritative value** declared in the relevant test strategy file (e.g., `§8.3` threshold table values, not `§5.2.5`).
2. Annotate the test with the inconsistency reference:
   - Android: `@Tag("spec-inconsistency")` + `// SPEC-BUG: §5.2.5 vs §8.3`
   - iOS: a comment `// SPEC-BUG: §5.2.5 vs §8.3` immediately above the test method
3. Do **not** write two conflicting tests — write one test against the authoritative value and note the open issue.
4. When the spec is corrected, remove the annotation and verify the test still passes.
Currently tracked inconsistencies:
- `§5.2.5` `thresholdTable` vs `§8.3` — **§8.3 is authoritative**: `[0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.60]`
---
## 12. What Is Not Tested Here
The following are explicitly outside the scope of both platform test strategies:
- `AudioRecord` / `AVAudioEngine` hardware latency characterisation
- ExoPlayer streaming latency (only seek accuracy is tested — Module 12.4)
- mDNS advertisement timing and multi-device discovery (manual integration test only)
- Advanced Search — `§3.5` is POST-MVP
- Screenshot / snapshot regression tests
- ISO-8859-1 legacy encoding (`F02 encoding_legacy_honors`) — explicitly skipped
---
## 13. CI Job Structure (recommended)
```text
PR gate (runs on every commit):
  ├── unit-tests-android      [U] only — JUnit5, no emulator
  ├── unit-tests-ios          [U] only — XCTest, no simulator hardware
  ├── lint-android            Detekt + ktlint + Android Lint
  ├── lint-ios                SwiftLint
  └── coverage-check          Fails build if thresholds not met
Nightly:
  ├── instrumented-android    [I] — emulator required
  ├── instrumented-ios        [I] — simulator required
  └── quarantine-suite        Flaky tests; results reported but do not block
```