"""Ticket viewsets.

Tenant scoping is enforced two ways for defense-in-depth:
1. TenantMiddleware sets `app.org_id` → RLS predicates on the DB rows.
2. Viewset `get_queryset` explicitly filters by `request.org`.

If both pass, queries return rows. If either fails, no rows.

`request.org` is set by TenantMiddleware when the URL is org-scoped
(`/o/<slug>/...`). API consumers should hit the org-scoped variant; the
flat `/api/tickets/` endpoint requires an `X-Org-Slug` header.
"""
from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .approval import ApprovalError, current_stage, decide_stage
from .models import ApprovalStage, Ticket, TicketType
from .serializers import (
    ApprovalStageSerializer,
    StageDecisionSerializer,
    TicketSerializer,
    TicketTypeDiscoverySerializer,
)
from .services import TicketTypeNotFound, get_ticket_type


class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):  # type: ignore[override]
        org = getattr(self.request, "org", None)
        if org is None:
            return Ticket.objects.none()
        return Ticket.objects.filter(org=org).order_by("-created_at")

    def perform_create(self, serializer) -> None:
        org = getattr(self.request, "org", None)
        if org is None:
            raise PermissionError("No org context — set X-Org-Slug header or use /o/<slug>/ route.")
        ticket = serializer.save(org=org, requester=self.request.user)

        from apps.audit.services import log_event

        log_event(
            event_type="ticket.created",
            org=org,
            actor=self.request.user,
            subject=ticket,
            data={"ticket_type": ticket.ticket_type, "title": ticket.title},
        )

    @action(detail=False, methods=["get"], url_path="plugins")
    def list_plugins(self, request: Request) -> Response:
        """Discover the ticket types this org has configured.

        Renamed from "plugins" in the codebase (the old YAML model called
        them plugins) but the URL stays for client compatibility.
        """
        org = getattr(request, "org", None)
        if org is None:
            return Response([], status=status.HTTP_200_OK)
        qs = TicketType.objects.filter(org=org, is_active=True).prefetch_related("fields")
        return Response(TicketTypeDiscoverySerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="decide")
    def decide(self, request: Request, pk: str | None = None) -> Response:
        """Force a (re-)decisioning run for this ticket. Synchronous in v0."""
        ticket = self.get_object()
        org = ticket.org

        try:
            tt = get_ticket_type(org=org, identifier=ticket.ticket_type)
        except TicketTypeNotFound as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not tt.ai_enabled:
            return Response(
                {"detail": f"AI decisioning disabled for ticket type {tt.identifier!r}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not tt.system_prompt.strip():
            return Response(
                {"detail": "System prompt is empty. Edit the ticket type in admin UI."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.decisioning.services import decide as run_decide

        decision = run_decide(ticket=ticket, system_prompt=tt.system_prompt)
        return Response({
            "decision_id": str(decision.id),
            "outcome": decision.outcome,
            "cited_rule_ids": decision.cited_rule_ids,
            "confidence": decision.confidence,
            "reason_text": decision.reason_text,
            "price_delta": str(decision.price_delta),
            "post_actions": decision.post_actions,
            "shadow_mode": decision.shadow_mode,
        })

    @action(detail=True, methods=["get"], url_path="stages")
    def list_stages(self, request: Request, pk: str | None = None) -> Response:
        ticket = self.get_object()
        stages = ticket.stages.order_by("order")
        cur = current_stage(ticket)
        return Response({
            "active_stage_id": str(cur.id) if cur else None,
            "stages": ApprovalStageSerializer(stages, many=True).data,
        })

    @action(
        detail=True,
        methods=["post"],
        url_path=r"stages/(?P<stage_id>[0-9a-f-]+)/decide",
    )
    def decide_stage(self, request: Request, pk: str | None = None, stage_id: str | None = None) -> Response:
        ticket = self.get_object()
        try:
            stage = ticket.stages.get(id=stage_id)
        except ApprovalStage.DoesNotExist:
            return Response({"detail": "Stage not found on this ticket"}, status=status.HTTP_404_NOT_FOUND)

        input_ser = StageDecisionSerializer(data=request.data)
        input_ser.is_valid(raise_exception=True)

        try:
            updated_ticket = decide_stage(
                stage=stage,
                user=request.user,
                decision=input_ser.validated_data["decision"],
                note=input_ser.validated_data.get("note", ""),
            )
        except ApprovalError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        stage.refresh_from_db()
        next_active = current_stage(updated_ticket)
        return Response({
            "stage": ApprovalStageSerializer(stage).data,
            "ticket_status": updated_ticket.status,
            "next_stage": ApprovalStageSerializer(next_active).data if next_active else None,
        })
