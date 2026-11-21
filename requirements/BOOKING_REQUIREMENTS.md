# Booking Requirements — Draft v0.1

These are **proposed rules** for a QA learning project. They require review before implementation. IDs are stable for traceability.

## Terminology
- **Unit**: a single physical camera or lens identified by unit ID.
- **Booking**: a request to rent one unit for a calendar-date range.
- **Blocking booking**: a confirmed or checked-out booking of that unit.
- **Overlap**: date intervals [start, end] share at least one calendar day.

## Functional requirements
| ID | Requirement | Acceptance example |
|---|---|---|
| FR-001 | Customer can browse equipment details and daily rental price. | Item page shows unit, description and VND/day. |
| FR-002 | Booking requires an authenticated customer. | Visitor is prompted to sign in; no booking created. |
| FR-003 | Dates are validated on the server. | End before start returns validation error, no booking created. |
| FR-004 | Total rental price follows BR-02 and BR-07. | 3 days at 200,000 VND/day totals 600,000 VND. |
| FR-005 | Confirmation rechecks availability for the same unit. | Overlapping confirmed reservation prevents confirmation. |
| FR-006 | Customer may view own booking details only. | Customer B cannot read Customer A's booking by ID. |
| FR-007 | Staff controls state changes. | Customer cannot directly mark a booking returned. |

## Availability decision table
| Same unit? | Dates overlap? | Existing status | May confirm new booking? |
|---|---|---|---|
| Yes | Yes | confirmed | No |
| Yes | Yes | checked-out | No |
| Yes | Yes | cancelled | Yes |
| Yes | Yes | returned | Yes |
| Yes | No | confirmed | Yes |
| No | Yes | confirmed | Yes |

## Boundary examples (rule proposal)
- A: Dec 10–12, B: Dec 12–13, same unit => overlap, reject confirmation.
- A: Dec 10–12, B: Dec 13–15, same unit => no overlap, may confirm.
- Start = end => 1 rental day.
- End before start => invalid.
- Two simultaneous confirmations for overlapping requests => at most one succeeds.

## Manual QA starter scenarios
| Scenario ID | Requirement | Scenario |
|---|---|---|
| TS-001 | FR-003 | Validate date range input. |
| TS-002 | FR-004 | Verify daily price calculation for one and multiple days. |
| TS-003 | FR-005 | Confirm booking when dates overlap. |
| TS-004 | FR-005 | Confirm booking when ranges are adjacent. |
| TS-005 | FR-006 | Verify one customer cannot access another customer's booking. |

## Open decisions
1. Should the last calendar day be inclusive, or should pickup/return be modeled as time slots?
2. When can a customer cancel: only pending, or pending and confirmed before pickup?
3. Is the initial MVP one unit per booking or multiple units per order? **Proposed: one.**
4. Is stock modeled per physical unit? **Proposed: yes.**

Do not infer that these requirements are implemented or tested yet.
