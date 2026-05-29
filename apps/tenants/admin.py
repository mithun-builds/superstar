from django.contrib import admin

from .models import Org, OrgMembership


@admin.register(Org)
class OrgAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "is_active", "created_at")
    search_fields = ("slug", "name")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(OrgMembership)
class OrgMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "org", "role", "created_at")
    list_filter = ("role", "org")
    search_fields = ("user__email", "org__slug")
    raw_id_fields = ("user", "org")
