---
name: security-review
description: Review security and operational safety of the Django Camera Rental base before release, focusing on actual project risks rather than generic checklists.
---
# Security and Safety Review

1. Inspect auth and role enforcement on both Django web endpoints and DRF, including object ownership and staff-only writes.
2. Check CSRF for session-backed writes; password validation, session/logout behavior, and safe error responses.
3. Check secret exposure in tracked/staged/untracked content and Docker env, plus DEBUG/ALLOWED_HOSTS and local-only demo credentials.
4. Validate unsafe input and database integrity: date bounds, quantity, price snapshot, status transitions, transaction atomicity, concurrency.
5. Review dependency pinning and Docker/CI privileges; avoid broad full-system access if workspace-scoped workflow works.
6. Produce findings with severity, evidence, impact and narrow fixes. Do not fabricate vulnerabilities or silently change scope.
7. Do not dump tokens, credentials or actual secrets into output or Git.
