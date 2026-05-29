---
rule_id: ITA-ADMIN-001
category: Local Admin
subcategory: laptop-admin
decision: approve
price_delta: 0
post_actions:
  - "Grant local admin role for the requested duration only"
  - "Add calendar reminder to review at duration end"
applies_when:
  access_type: local_admin
  requester_role: [engineer, contractor]
---

# Local admin on company laptop — time-bounded

Local admin on the requester's own company laptop is auto-approved for engineers
and contractors, subject to a duration limit.

## Conditions

- Requester must be engineer or contractor.
- Duration must be ≤ 90 days. Longer requests require security review.
- Auto-revoke at duration end is required (post_actions enforces this).

## Decision

**Approve.** Cite this rule (ITA-ADMIN-001). Grant for the requested duration
(maximum 90 days). Set a calendar reminder to review and revoke at expiry.

## When to escalate

- Duration > 90 days → escalate to security.
- Non-engineer/contractor role → escalate.
- Repeat admin requests in the last 6 months → escalate (pattern review).
