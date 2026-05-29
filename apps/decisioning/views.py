"""Polling endpoint for async decisions.

GET /api/decisions/by-task/<task_id>/ — returns:
  202 + {status: "pending"} while the worker is running
  200 + DecisionSerializer payload once the row is written
  404 if the task id doesn't match anything within this org
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Decision
from .serializers import DecisionSerializer


class DecisionByTaskView(APIView):
    """Read a Decision by the Celery task id that produced it.

    Org-scoped via the same TenantMiddleware contract as everything else.
    No write methods — decisions are immutable once written.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: str) -> Response:
        org = getattr(request, "org", None)
        if org is None:
            return Response(
                {"detail": "Org context required (X-Org-Slug or /o/<slug>/ route)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            decision = Decision.objects.get(org=org, task_id=task_id)
        except Decision.DoesNotExist:
            # Worker hasn't written the row yet — 202 lets the frontend know
            # "keep polling" without needing a special status code in JSON.
            return Response(
                {"status": "pending", "task_id": task_id},
                status=status.HTTP_202_ACCEPTED,
            )

        return Response(DecisionSerializer(decision).data)
