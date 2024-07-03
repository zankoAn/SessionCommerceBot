from django.contrib import admin
from .models import Transaction, CryptoPayment, ZarinPalPayment, PerfectMoneyPayment


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "payer",
        "status",
        "payment_method",
        "amount_usd",
        "amount_rial",
    )
    list_editable = ("status",)
    list_display_links = ("payer", )


@admin.register(CryptoPayment)
class CryptoAdmin(admin.ModelAdmin):
    list_display = ("id", "network", "currency", "payment_amount_coin")
    list_display_links = ("id", "network", "currency")


@admin.register(ZarinPalPayment)
class ZarinPalAdmin(admin.ModelAdmin):
    list_display = ("id", "transaction", "authority")
    list_display_links = ("id", "transaction")


@admin.register(PerfectMoneyPayment)
class PerfectMoneyAdmin(admin.ModelAdmin):
    list_display = ("id", "evoucher", "activation_code")
    list_display_links = ("id", "evoucher", "activation_code")
