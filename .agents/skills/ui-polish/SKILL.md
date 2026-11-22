---
name: ui-polish
description: Improve coherent, functional, responsive Django Templates UI without adding fake screens or changing business rules. Use for customer/staff user journeys and design consistency.
---
# UI Polish

1. Inventory the existing screens and shared CSS/templates; do not invent a new design system unnecessarily.
2. Inspect the full user journey: catalog -> details -> dates/quantity -> booking -> history; staff equipment -> orders -> pickup/return/no-show.
3. Use one typography scale, spacing system, controls and feedback language. Keep important actions obvious.
4. Verify at desktop and mobile widths, plus keyboard focus, form labels, error and empty states. Do not fake completed bookings or API responses.
5. Preserve independent search/type filters even if rental date form has validation errors.
6. Ensure assets are locally reliable and licensed; use honest illustrations if real imagery is unavailable.
7. When browser access exists, inspect rendering and actual interactions. If not, state visual verification was not performed.
8. Run relevant Django tests and smoke; report screenshots or observations tied to build/commit where possible.
