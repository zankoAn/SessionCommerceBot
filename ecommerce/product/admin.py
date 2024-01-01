from django.contrib import admin
from .models import *


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price", "is_active")
    list_display_links = ("id", "name")
    list_editable = ("is_active",)
    search_fields = ("key", "id")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session", "track_id", "status")
    list_display_links = ("id", "user", "session")
    search_fields = ("track_id", "status", "user")