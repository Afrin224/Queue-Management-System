from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Manager, Queue, Token


@admin.register(Manager)
class ManagerAdmin(UserAdmin):
    ordering = ["email"]
    list_display = ["email", "name", "is_demo", "is_staff", "is_active"]
    search_fields = ["email", "name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("name", "is_demo")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "name", "password1", "password2")}),)


class QueueRecordsAdmin(admin.ModelAdmin):
    """Queue mutations stay in the API, where lifecycle rules are enforced."""
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Queue)
class QueueAdmin(QueueRecordsAdmin):
    list_display = ["name", "manager", "paused", "next_number", "revision"]
    list_filter = ["paused"]
    search_fields = ["name", "manager__email"]


@admin.register(Token)
class TokenAdmin(QueueRecordsAdmin):
    list_display = ["name", "queue", "number", "status", "position"]
    list_filter = ["status", "queue"]
    search_fields = ["name", "note"]
