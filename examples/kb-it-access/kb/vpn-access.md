---
rule_id: ITA-VPN-001
category: VPN
subcategory: standard-access
decision: approve
price_delta: 0
post_actions:
  - "Provision VPN profile via Tailscale within 4 business hours"
applies_when:
  access_type: vpn
  requester_role: [engineer, contractor, ops]
---

# VPN access — standard

VPN access is auto-approved for engineers, contractors, and ops staff.

## Conditions

- Requester role must be one of: engineer, contractor, ops.
- Duration must be ≤ 365 days. Requests above 365 days require security review.
- Contractors get auto-approval but their access expires when their contractor
  agreement ends (tracked separately in HR).

## Decision

**Approve.** Cite this rule (ITA-VPN-001). No price impact. Provision via
Tailscale within 4 business hours.

## When to escalate

If the requester is in a role not listed above (e.g. designer, finance, sales)
they need a security review — escalate to the Security Review stage.
