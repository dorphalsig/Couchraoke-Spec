---
name: navigation
description: repository navigation rules. use before locating symbols, reading files, tracing references, or deciding code context.
---

# Navigation
**CRITICAL INSTRUCTION** You may only navigate the repository by following the rules below. This is mandatory and non-negotiable

## Rules

- Prefer symbol-aware tools before text search.
- Do not read full files by default.
- Read only the needed symbol, slice, or line range.
- Expand only when needed to understand contract, control flow, data flow, or tests.
- Stop at one hop from scoped files unless a governing document explicitly expands scope.
- Do not use bash as a navigation strategy.

## Boundary
Allowed context:
- scoped files
- direct tests for scoped files
- one-hop first-party callers, callees, definitions, implementations, references, contracts, or data types

Do not cross this boundary without reporting scope expansion.

## Tools
Prefer symbol-aware navigation. Use LSP tools in this order when available:

| Goal | Tools |
|---|---|
| Locate a definition | `goToDefinition` |
| Find usages | `findReferences` |
| Inspect a type or signature | `hover` |
| List symbols in a file | `documentSymbol` |
| Search across the repo | `workspaceSymbol` |
| Trace call graph | `incomingCalls`, `outgoingCalls`, `prepareCallHierarchy` |
| Locate an implementation | `goToImplementation` |
| Discover an unknown file | `Glob` |

Use non-symbol search (text grep, broad bash) only after symbol-aware navigation has failed to resolve the target.
Do not use bash as a navigation strategy. Do not wander directories or open files speculatively from the shell. Shell is acceptable only for narrow file discovery or line-targeted reads when the target is already known.

## Required checkpoint
Before editing, create a concise navigation checkpoint:

- scoped files
- symbols or slices read
- one-hop context read, if any
- why the context is sufficient