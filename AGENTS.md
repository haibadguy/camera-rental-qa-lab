# AGENTS.md — Camera Rental Product Development

## Mission
Develop Camera Rental Management System as a medium-sized business application for one professional camera rental store. Cover booking, rental operations, maintenance, counter settlement and management reporting. Base v1.0 is the frozen technical foundation and V2-M1 is integrated into main. Work on product development and developer verification only.

Follow [ROADMAP.md](ROADMAP.md) for V2-M2 through V2-M5 and release gates. Use [PROJECT_PLAN.md](PROJECT_PLAN.md) for the current work, [the product design](docs/v2-product-design.md) for scope and pending policy decisions, and [docs/verification.md](docs/verification.md) for recorded evidence. Obtain Hải's approval for the relevant policies before starting a milestone, then execute the approved work through verification.

## Read first
1. Inspect `git status`, active branch, staged and untracked files.
2. Read `README.md`, `PROJECT_PLAN.md`, `ROADMAP.md`, `CONTRIBUTING.md`, `docs/requirements.md`, `docs/architecture.md`, `docs/setup.md` and the relevant code.
3. Prefer current verified code/approved requirements over assumptions or stale conversation summaries. Identify mismatches, do not silently overwrite decisions.

## Architecture constraints
- Retain Django, Django Templates and JavaScript, DRF, PostgreSQL, Docker Compose and GitHub Actions.
- Keep a modular monolith. Keep the `catalog` Django app label and migrations stable unless change is demonstrably safe and explicitly approved.
- Give each domain rule one owner. Web and DRF call `catalog/services.py`. Keep domain dependencies acyclic and registration on Django auth. [Module ownership](docs/architecture.md#kiến-trúc-mục-tiêu)
- Keep ORM models and migrations in `catalog`. Split an adapter, module or set of templates when its responsibilities justify the move. Preserve caller contracts and verify the affected paths.

## Business invariants
- Dates: start-inclusive, end-exclusive; 1–30 days; no past start; Asia/Ho_Chi_Minh.
- Price calculation performed server-side; booking stores price snapshot.
- Lifecycle: CONFIRMED -> PICKED_UP -> RETURNED; CONFIRMED -> CANCELLED with documented no-show reason where applicable. V2-M2 records receipt and inspection separately for each asset. Confirmed loss can close a rental with its own timestamp. Early return preserves the promised schedule.
- Prevent booking and pickup over-allocation with PostgreSQL transactions and real database concurrency tests. Lock `Equipment` before `Rental` in operations that affect stock.
- Enforce ownership/roles on backend and DRF, not through UI visibility alone. Preserve booking history.
- Identify the requirement ID, scope and acceptance criteria before edits. Resolve scope questions against `docs/requirements.md` for Base and owner-approved v2 requirements for new work. Report conflicts and obtain Hải's approval before adding a business rule or changing the stack.

## Code and UI quality
- Prefer small, clear changes and idiomatic Django. No duplicate rules, needless dependencies, empty scaffolding, fake features or generated filler.
- Use consistent templates, accessible forms and responsive customer, staff and manager interfaces. Reports must derive from recorded business data and define their metrics.
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
A change is done when behavior meets the approved scope; relevant tests have run; diff is reviewed; no related regression is known; updated docs match code; and outstanding limitations are reported. Release readiness requires working end-to-end customer, staff and manager journeys, verified migrations and concurrency, reproducible Docker, green CI on the candidate, maintainable code and owner approval.

## Handoff format
Always summarize: (1) what changed/why, (2) files, (3) tests actually run and outputs, (4) blockers/risks, (5) Git status and next action. For large tasks save durable state in a concise document only if needed; avoid oversized progress files.

## Skills
Use the relevant project skill in `.agents/skills/` only for work it covers. Skills guide repeatable workflows; this AGENTS file and the approved requirements take precedence over generic advice.
