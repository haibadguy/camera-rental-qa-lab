---
name: safe-refactor
description: Refactor existing Django modules safely without changing observable behavior, app labels, migrations or API contracts. Use for architectural cleanup and duplication reduction.
---
# Safe Refactor

1. Read current status, requirements, architecture and impacted modules. Require a recoverable checkpoint before wide changes.
2. Document the specific maintenance defect (duplication, coupling, circular import, unclear responsibility); do not refactor merely for style.
3. Record current public interfaces: URLs, view names, DRF routes, service signatures, model labels, migration graph, template names and test behavior.
4. Choose the smallest behavior-preserving step within the module boundaries in [the architecture](../../../docs/architecture.md). Keep models and applied migrations in `catalog`.
5. Refactor one cohesive responsibility at a time. Preserve `catalog.services` as the shared entry point for web and API.
6. Run targeted checks, full tests when possible, migration drift checks and diff inspection. Report the precise differences and remaining risk.
7. If tests cannot run, mark Blocked and do not claim behavior preservation has been verified.

**Never:** rewrite the whole app, delete migrations, change schema without migration, introduce interfaces/repositories purely for architecture cosmetics, force-push, or erase worktree changes.
