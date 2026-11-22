---
name: release-verification
description: Reproduce and verify a Camera Rental release candidate end-to-end on isolated Docker/PostgreSQL, with credible evidence and explicit go/no-go decision.
---
# Release Verification

1. Record branch, HEAD SHA, working tree and candidate diff. Tie release evidence to the exact candidate commit. Label checks on a dirty working tree as local development evidence.
2. Run the clean verification procedure in [the setup guide](../../../docs/setup.md) with a free port and fresh Compose project and volume. Preserve existing data and containers.
3. Run Compose config/build/up/health, migrations, seed, Django checks, `makemigrations --check --dry-run`, automated tests including PostgreSQL transaction/concurrency, HTTP smoke.
4. Walk authenticated customer and staff paths using a supported browser when available, at desktop/mobile widths; verify web/API consistency and permission boundaries.
5. Check environment template, no secrets, setup accuracy, broken links and reproducibility. Inspect CI runs for the exact candidate commit once it is pushed with approval.
6. Capture each command's result: PASS, FAIL, BLOCKED or NOT RUN; include errors rather than paraphrased optimism.
7. Report READY FOR OWNER REVIEW when G0–G3 have evidence and independent handoff is verified. Report NOT READY with the outstanding evidence when those conditions are open.
8. Follow [G4 in the roadmap](../../../ROADMAP.md). Hải approves merge, release and tag separately.
