# Repository agent instructions

This file is the operational entry point for AI coding agents working in this
repository. These instructions apply to all repository work.

## Mandatory standards

- Read and comply with `ENGINEERING.md` and `ARCHITECTURE.md` before making
  architectural or implementation changes.
- `ENGINEERING.md` is the canonical, mandatory source for engineering principles,
  code-quality rules, architecture discipline, testing expectations, security
  practices, and implementation standards for all work in this repository.
- `ARCHITECTURE.md` is the canonical source for system architecture and structural
  decisions.
- If instructions conflict, explicitly report the conflict rather than silently
  choosing one. Resolve the conflict before making affected changes.

## Current scope

Implement only capabilities authorized by the current task and keep changes
within the requested stage.

Stage 0 scaffolding is authorized and implemented. Do not implement product
features, authentication, provider integrations, or speculative domain models
until a later task explicitly authorizes them.

## Completion reporting

Follow the definition of done in `ENGINEERING.md`. For implementation tasks,
also run Django system checks where applicable and review migrations before
execution. Report checks actually run and their outcomes; explain checks that
are unavailable or not applicable. List changed files and unresolved issues
honestly, and never describe an unrun check as passing.
