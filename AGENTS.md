# AGENTS.md — Camera Rental Product Development

## Mission and phase
Complete a polished, maintainable Camera Rental Base v1.0. This is PRODUCT DEVELOPMENT ONLY. Do not create manual test cases, fabricated bug reports, QA portfolio materials or CV content until the owner explicitly begins Phase 2 after a frozen baseline.

Follow [ROADMAP.md](ROADMAP.md) for milestones and G0–G4. Use [PROJECT_PLAN.md](PROJECT_PLAN.md) to locate the current work and [docs/verification.md](docs/verification.md) for recorded evidence.

## Read first
1. Inspect `git status`, active branch, staged and untracked files.
2. Read `README.md`, `PROJECT_PLAN.md`, `ROADMAP.md`, `CONTRIBUTING.md`, `docs/requirements.md`, `docs/architecture.md`, `docs/setup.md` and the relevant code.
3. Prefer current verified code/approved requirements over assumptions or stale conversation summaries. Identify mismatches, do not silently overwrite decisions.

## Architecture constraints
- Retain Django + Django Templates + DRF + PostgreSQL + Docker Compose.
- Keep a modular monolith. Keep the `catalog` Django app label and migrations stable unless change is demonstrably safe and explicitly approved.
- Give each domain rule one authoritative implementation. Views/API are adapters; use shared domain services. Avoid circular dependencies and speculative abstractions.
- Use `catalog/services.py` as the shared entry point for web and API. Implement equipment and list prices in `catalog/equipment.py`, stock rules in `catalog/inventory.py`, and booking and rental transitions in `catalog/rentals.py`. Keep registration in `catalog/views.py` using Django auth.
- Do not move ORM models between Django apps casually. Do not rewrite a working module for style alone.

## Business invariants
- Dates: start-inclusive, end-exclusive; 1–30 days; no past start; Asia/Ho_Chi_Minh.
- Price calculation performed server-side; booking stores price snapshot.
- Lifecycle: CONFIRMED -> PICKED_UP -> RETURNED; CONFIRMED -> CANCELLED; no-show uses documented reason. Early/late returns record actual timestamps; scheduled and physical availability differ.
- Prevent booking and pickup over-allocation with PostgreSQL transactions and real database concurrency tests. Lock `Equipment` before `Rental` in operations that affect stock.
- Enforce ownership/roles on backend and DRF, not through UI visibility alone. Preserve booking history.
- Identify the requirement ID, scope and acceptance criteria before edits. Resolve scope questions against `docs/requirements.md` and report conflicts. Obtain Hải's approval before adding a business rule or changing the stack.

## Code and UI quality
- Prefer small, clear changes and idiomatic Django. No duplicate rules, needless dependencies, empty scaffolding, fake features or generated filler.
- Consistent templates, accessible forms, responsive layouts, useful empty/loading/error/success states.
- All interactive controls must work. Do not fake external integrations or use unlicensed images.
- Keep docs true to current implementation; do not create documentation for its own sake.

## Safety and Git
- One modifying agent per Git worktree.
- Before risky changes, secure an owner-approved safe checkpoint; inspect `.gitignore` and secrets. Do not run destructive Git commands or delete existing database volumes.
- Do not commit credentials, `.env`, dumps, caches, runtime state or personal data.
- Local commits are permissible only in the authorized workflow. Push, merge, release and tag each require Hải's separate approval. Do not force-push or delete significant data without owner approval.
- Never disable security, validation or tests just to achieve a green run.

## Verification
- Run targeted tests after changes and full PostgreSQL suite/smoke/Compose verification before release review.
- Distinguish Implemented, Verified, Not Run, Failed and Blocked. Never claim a test passed without execution evidence.
- For Docker, use isolated Compose project/volumes for clean verification. Record exact commands, environment, exit code and key results.
- Record the data used and preserve existing volumes. Use the clean verification procedure in [docs/setup.md](docs/setup.md).
- CI must actually run on an approved pushed branch before release readiness.

## Definition of Done
A change is done when behavior meets the approved scope; relevant tests have run; diff is reviewed; no related regression is known; updated docs match code; and outstanding limitations are reported. Base v1.0 is ready only with working end-to-end customer/staff journeys, verified migrations and concurrency, reproducible Docker, green CI, maintainable code and owner approval.

## Handoff format
Always summarize: (1) what changed/why, (2) files, (3) tests actually run and outputs, (4) blockers/risks, (5) Git status and next action. For large tasks save durable state in a concise document only if needed; avoid oversized progress files.

## Skills
Use the relevant project skill in `.agents/skills/` only for work it covers. Skills guide repeatable workflows; this AGENTS file and the approved requirements take precedence over generic advice.
