from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from ecommerce.bot.models import Message, BotUpdateStatus


class MsgStepFilter(admin.SimpleListFilter):
    title = _("User or Admin msg")
    parameter_name = "step"

    def lookups(self, request, model_admin):
        return (("user", _("Related User Msg")), ("admin", _("Related Admin Msg")))

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
            ("error", _("Error Msg")),
        )

    def queryset(self, request, queryset):
        filterd_value = self.value()
        if filterd_value == "key":
            return queryset.filter(key__isnull=False)
        if filterd_value == "inline":
            return queryset.filter(is_inline_keyboard=True)
        if filterd_value == "msg":
            return queryset.filter(key__isnull=True).filter(is_inline_keyboard=False)
        if filterd_value == "error":
            return queryset.filter(key__isnull=True).filter(current_step__endswith="error")
        else:
            return queryset.all()



@admin.register(BotUpdateStatus)
class BotUpdateAdmin(admin.ModelAdmin):
    list_display = ("id", "is_update")
    list_display_links = ("id",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "display_key", "current_step")
    list_display_links = ("id", "display_key")
    search_fields = ("id", "display_key")
    list_editable = ("current_step",)
    list_filter = (MsgStepFilter, MsgKeyFilter)

    def display_key(self, obj):
        return obj.key or obj.current_step
