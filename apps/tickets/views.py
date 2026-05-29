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

from superstar.plugins import all_plugins, get_plugin

from .approval import ApprovalError, current_stage, decide_stage
from .models import ApprovalStage, Ticket
from .serializers import ApprovalStageSerializer, StageDecisionSerializer, TicketSerializer


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
        """Discover ticket types this deployment supports."""
        out = []
        for ident, plugin in all_plugins().items():
            contract = plugin.contract if hasattr(plugin, "contract") else plugin
            out.append({
                "identifier": ident,
                "display_name": contract.display_name,
                "fields": [
                    {
                        "name": f.name, "type": f.type, "label": f.label,
                        "required": f.required, "choices": list(f.choices),
                        "help_text": f.help_text,
                    }
                    for f in contract.schema.fields
                ],
                "ai_enabled": contract.ai_policy.enabled,
                "shadow_mode": contract.ai_policy.shadow_mode,
            })
        return Response(out)

    @action(detail=True, methods=["post"], url_path="decide")
    def decide(self, request: Request, pk: str | None = None) -> Response:
        """Force a (re-)decisioning run for this ticket. Synchronous in v0.

        Phase 2 will move this to a Celery task and stream the result back via
        polling or SSE. For now, blocks until the LLM responds.
        """
        ticket = self.get_object()
        plugin = get_plugin(ticket.ticket_type)
        contract = plugin.contract if hasattr(plugin, "contract") else plugin

        # Read system prompt from disk (relative to SUPERSTAR_CONFIG_DIR).
        from pathlib import Path
        from django.conf import settings

        prompt_path = Path(settings.SUPERSTAR_CONFIG_DIR) / contract.ai_policy.system_prompt_path
        if not prompt_path.is_file():
            # Try resolving with the plugin folder prefix.
            for p in Path(settings.SUPERSTAR_CONFIG_DIR).rglob(contract.ai_policy.system_prompt_path):
                prompt_path = p
                break
        if not prompt_path.is_file():
            return Response(
                {"detail": f"System prompt not found at {contract.ai_policy.system_prompt_path}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.decisioning.services import decide as run_decide

        decision = run_decide(ticket=ticket, system_prompt=prompt_path.read_text())
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
        """List the approval chain for a ticket, in order."""
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
        """Approve or reject a stage. Advances the chain or closes the ticket."""
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

        # Re-read the stage from DB so we return the post-decision shape.
        stage.refresh_from_db()
        next_active = current_stage(updated_ticket)
        return Response({
            "stage": ApprovalStageSerializer(stage).data,
            "ticket_status": updated_ticket.status,
            "next_stage": ApprovalStageSerializer(next_active).data if next_active else None,
        })
