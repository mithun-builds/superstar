"""Django admin registration for ticket-type configuration.

Until the dedicated SuperStar admin UI lands, org admins can create and edit
TicketType, TicketTypeField, and WorkflowStage rows via Django's built-in
/admin/. This is a stop-gap — production use should go through the SuperStar
admin UI once it ships, because Django admin doesn't respect org-scoping by
default (a platform superuser sees all orgs' rows).
"""
from django.contrib import admin

from .models import ApprovalStage, Ticket, TicketType, TicketTypeField, WorkflowStage


class TicketTypeFieldInline(admin.TabularInline):
    model = TicketTypeField
    extra = 1
    fields = ("order", "name", "field_type", "label", "required", "choices", "help_text")
    ordering = ("order",)


class WorkflowStageInline(admin.TabularInline):
    model = WorkflowStage
    extra = 1
    fields = ("order", "name", "approvers", "mode", "sla_hours")
    ordering = ("order",)


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ("identifier", "org", "display_name", "ai_enabled", "shadow_mode", "is_active")
    list_filter = ("org", "ai_enabled", "shadow_mode", "is_active")
    search_fields = ("identifier", "display_name", "org__slug")
    inlines = [TicketTypeFieldInline, WorkflowStageInline]
    fieldsets = (
        (None, {"fields": ("org", "identifier", "display_name", "description", "is_active")}),
        ("Workflow", {"fields": ("sequential",)}),
        ("AI policy", {
            "fields": ("ai_enabled", "confidence_threshold", "require_citation", "shadow_mode", "system_prompt"),
        }),
        ("Notifications", {"fields": ("notifications",), "classes": ("collapse",)}),
    )


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "org", "ticket_type", "title", "status", "created_at")
    list_filter = ("org", "ticket_type", "status")
    search_fields = ("title", "id")
    readonly_fields = ("id", "created_at", "updated_at", "closed_at")


@admin.register(ApprovalStage)
class ApprovalStageAdmin(admin.ModelAdmin):
    list_display = ("ticket", "order", "name", "status", "decided_by", "decided_at")
    list_filter = ("status", "mode")
    readonly_fields = ("id", "ticket", "decided_at", "created_at")
