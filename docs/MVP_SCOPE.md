# Camera Rental QA Lab — MVP Scope (v0.1)

Status: **Draft for review**. This document defines a learning-focused, testable MVP, not a production rental service.

## Goal
Build a small, functioning rental application that a Manual QA intern can explain, test, and demonstrate. Prioritize observable business rules and traceable test evidence over feature count.

## Personas
- Visitor: browse catalog and view item details.
- Customer: sign in, check availability, create and view own rentals, request eligible cancellation.
- Staff/Admin: manage equipment inventory and change rental status.

## In scope
1. Catalog: list/detail, search/filter and a clear daily rental price.
2. Authentication and basic customer/staff authorization.
3. Rental booking: select equipment, pickup and return dates, availability check, price calculation and order confirmation.
4. Rental lifecycle: pending -> confirmed -> checked-out -> returned; cancellation according to explicit rules.
5. Seed fixtures and repeatable reset instructions for testing.
6. QA artifacts: requirements, manual test cases, defect reports, execution evidence, and a test summary.

## Out of scope in MVP
Real payment gateway, delivery/shipping, identity-document collection, AI recommendations, multi-store inventory, promotions, complex pricing/insurance, microservices and mobile apps.

## Initial business-rule proposals (confirm before implementation)
- BR-01: Dates are calendar dates in one configured local timezone; pickup date must be on/before return date.
- BR-02: Both pickup and return dates count as rental days; number of rental days = calendar difference + 1. (Proposal: easy to test; may revise.)
- BR-03: A physical equipment unit cannot have overlapping bookings with status **confirmed** or **checked-out**.
- BR-04: A pending booking does not reserve stock. Staff confirmation must recheck availability atomically; first valid confirmation wins.
- BR-05: Returned/cancelled bookings do not block future dates.
- BR-06: Customers see only their own bookings; staff may manage all.
- BR-07: Total = daily rate * rental days, stored and displayed in VND; no live payment.

## Definition of Done for each feature
- Requirement and acceptance criteria documented with IDs.
- Input validation and relevant authorization handled server-side.
- Deterministic fixtures permit repeatable test runs.
- At least happy path, boundary and negative manual tests recorded.
- Defects documented with steps, expected/actual behavior, environment and evidence; resolved defects retested.
- Application starts from written setup instructions; tests run without hidden manual setup.

## Suggested 4-week sequence
- Week 1: requirements, QA vocabulary and test design; build one minimal runnable catalog flow.
- Week 2: rental date/availability rules and manual functional testing.
- Week 3: booking lifecycle, roles, API and SQL checks.
- Week 4: regression, small automation smoke tests if ready, CI basics, evidence, README, interview walkthrough.

## Guardrails
- One small vertical slice per pull request; avoid generating the entire app at once.
- Never claim a test passed unless executed with evidence.
- Keep seeded intentional defects separate from the normal working version.
- Document AI-assisted contributions, decisions and independently verified work.
- No merges to `main` without review.
