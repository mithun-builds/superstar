---
rule_id: ITA-PROD-001
category: Production Data
subcategory: read-access
decision: escalate
price_delta: 0
post_actions: []
applies_when:
  access_type: [prod_db_read, prod_db_write]
---

# Production data access — always escalate

Any access to production databases — read or write — requires human security
review. There is no auto-approve path.

## Conditions

This rule fires whenever `access_type` is `prod_db_read` or `prod_db_write`,
regardless of role or duration. SuperStar must not approve these without a
human in the loop.

## Decision

**Escalate** to the Security Review stage. Cite this rule (ITA-PROD-001) in
the reason text so the security team knows which policy required escalation.

## Why no auto-approve

Prod data carries PII and revenue-impact risk. The cost of a wrong auto-approve
is high enough that even a high-confidence model match must defer to humans.
This is by policy, not by capability.
