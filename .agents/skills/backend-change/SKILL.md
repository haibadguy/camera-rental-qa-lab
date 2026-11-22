---
name: backend-change
description: Implement or repair Camera Rental Django/DRF business logic while preserving date, price, authorization, booking lifecycle and inventory invariants.
---
# Backend Business Change

1. Identify requirement ID and acceptance criteria; read current tests, models, services, views, API routes and migrations.
2. Map affected customer/staff paths and transaction boundaries before coding.
3. Implement the rule in the module assigned by [the architecture](../../../docs/architecture.md). Route web and DRF through `catalog.services`.
4. Validate authorization and ownership on backend. Apply form/serializer validation without treating it as the only guard.
5. For changes affecting stock, lock `Equipment` before `Rental` in the same transaction. Account for scheduled holds and physically checked-out stock. Verify concurrent sessions on PostgreSQL.
6. Add relevant automated cases for success, boundaries, invalid transitions, repeated requests, rollback and permissions.
7. Run targeted suite then integration checks; identify blocked steps rather than making unverifiable claims.
8. Update only the requirement/API/docs materially affected; do not expand scope.
