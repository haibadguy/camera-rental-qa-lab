---
name: agent-handoff
description: Validate that a new developer or Codex agent can understand, run and safely extend the Camera Rental base using only repository files.
---
# Independent Handoff

1. Start a clean agent context without relying on prior chat or invisible memory. Read README, AGENTS, requirements, architecture and setup.
2. State the stack, domain modules, business invariants, start/test/verification commands and known limitations; corroborate against code.
3. Attempt a fresh non-destructive setup in an isolated environment and record blockers.
4. Given a small hypothetical change request, identify the correct files, dependencies, tests and migration implications. Do not implement until explicitly authorized.
5. Flag stale/contradictory docs and missing runbook steps, then recommend minimal corrections.
6. Handoff passes only if the new agent can locate responsibilities, reproduce environment and explain the change impact without prior chat history.
