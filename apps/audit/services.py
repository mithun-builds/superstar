"""Audit log helper.

One function, `log_event`, called from anywhere a meaningful state change
happens. Designed to never raise — audit writes must never block the user
operation that caused them. Errors are logged, not propagated.

Why explicit calls instead of `post_save` signals:
- Signals fire on every save, including incidental updates (status touches,
  `updated_at` bumps from unrelated edits). Audit should reflect *intent*,
  not low-level row mutations.
- Easier to test and grep for: every audit event has a call site you can find.
- The `actor` (who did it) is usually request-scoped and easier to pass
  explicitly than to thread through signals.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db import models, transaction

from .models import AuditEvent

if TYPE_CHECKING:
    from apps.tenants.models import Org

logger = logging.getLogger(__name__)


def log_event(
    *,
    event_type: str,
    org: "Org | None" = None,
    actor: Any | None = None,
    subject: models.Model | None = None,
    data: dict | None = None,
) -> AuditEvent | None:
    """Append an audit event. Returns the row, or None on internal failure.

    `subject` (any Django model) is reflected into `subject_type` and
    `subject_id`. Pass `data` as a JSON-serializable dict — request context,
    field-level deltas, the citations on a decision, etc.
    """
    try:
        subject_type = subject._meta.label if subject is not None else ""
        subject_id = str(subject.pk) if subject is not None else ""

        # Wrap in a savepoint so an audit failure can't roll back the caller's
        # transaction. If we're not in a transaction, this is effectively a no-op.
        with transaction.atomic(savepoint=True):
            return AuditEvent.objects.create(
                event_type=event_type,
                org=org,
                actor=actor if (actor and getattr(actor, "is_authenticated", False)) else None,
                subject_type=subject_type,
                subject_id=subject_id,
                data=data or {},
            )
    except Exception:  # noqa: BLE001 — audit must never block the caller
        logger.exception("log_event failed for event_type=%s subject=%s", event_type, subject)
        return None


def for_subject(subject: models.Model) -> "models.QuerySet[AuditEvent]":
    """Convenience: all events about a given model instance, newest first."""
    return AuditEvent.objects.filter(
        subject_type=subject._meta.label,
        subject_id=str(subject.pk),
    ).order_by("-created_at")
