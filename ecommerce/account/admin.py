from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset

    list_display = ("id", "username", "user_id", "balance", "step", "is_send_ads")
    list_display_links = ("id", "username")

    fieldsets = (
        (None, {"fields": ("password", "user_id")}),
        (
            "Personal info",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "username",
                    "balance",
                    "step",
                    "is_send_ads",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
    )

    search_fields = ("first_name", "username", "user_id")
    ordering = ("id", "username")
    list_editable = ("balance", )
