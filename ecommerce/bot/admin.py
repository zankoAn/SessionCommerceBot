from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import *


class MsgStepFilter(admin.SimpleListFilter):
    title = _("User or Admin msg")
    parameter_name = "step"

    def lookups(self, request, model_admin):
        return (
            ("user", _("Related User Msg")),
            ("admin", _("Related Admin Msg"))
        )

    def queryset(self, request, queryset):
        if self.value() == "user":
            return queryset.exclude(current_step__startswith="admin")
        if self.value() == "admin":
            return queryset.filter(current_step__startswith="admin")
        else:
            return queryset.all()


class MsgKeyFilter(admin.SimpleListFilter):
    title = _("Keyboard")
    parameter_name = "key"

    def lookups(self, request, model_admin):
        return (
            ("key", _("Normal keyboard")),
            ("inline", _("Inline keyboard")),
            ("msg", _("Normal Msg")),
        )

    def queryset(self, request, queryset):
        filterd_value = self.value()
        if filterd_value == "key":
            return queryset.filter(key__isnull=False)
        if filterd_value == "inline":
            return queryset.filter(is_inline_keyboard=True)
        if filterd_value == "msg":
            return queryset.filter(key__isnull=True).filter(is_inline_keyboard=False)
        else:
            return queryset.all()


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "display_key", "current_step")
    list_display_links = ("id", "display_key")
    search_fields = ("id", "display_key")
    list_editable = ("current_step", )
    list_filter = (MsgStepFilter, MsgKeyFilter)

    def display_key(self, obj):
        return obj.key or obj.current_step