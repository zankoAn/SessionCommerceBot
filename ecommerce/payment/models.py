from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext as __

User = get_user_model()


class Transaction(models.Model):
    class StatusChoices(models.TextChoices):
        PAID = __("Success Transaction ✅")
        PAID_OVER = __("Success Transaction And Pay more ✅")
        FAIL = __("Failed Transaction ❌")
        IN_PROGRESS = __("⏳ In Progress")
        WRONG_AMOUNT = ("Wrong Amount Waiting ❌")

    class PaymentMethodChoices(models.TextChoices):
        ZARINPAL = __("ZarinPal")
        PERFECT_MONEY = __("PerfectMoney")
        CRYPTO = __("Cryptocurrency")

    payer = models.ForeignKey(
        to=User,
        on_delete=models.SET_NULL,
        related_name=_("payments"),
        null=True
    )
    status = models.CharField(
        max_length=50,
        verbose_name=_("session status"),
        choices=StatusChoices.choices,
        default=StatusChoices.IN_PROGRESS,
    )
    payment_method = models.CharField(
        max_length=50,
        verbose_name=_("payment method"),
        choices=PaymentMethodChoices.choices,
        default=PaymentMethodChoices.ZARINPAL,
    )
    amount_rial = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("amount rial"),
    )
    amount_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("amount dollar"),
    )
    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("creation time"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("update time")
    )

    @property
    def get_amount_rial(self):
        return int(self.amount_rial)

    def __str__(self) -> str:
        return _("Transaction: {}").format(self.id)

class ZarinPalPayment(models.Model):
    transaction = models.OneToOneField(
        to=Transaction,
        on_delete=models.CASCADE,
        verbose_name=_("related transaction"),
        related_name="zarinpal"
    )
    authority = models.CharField(
        max_length=70,
        null=True,
        blank=True,
        unique=True,
        verbose_name="authority id",
    )

    def __str__(self):
        return _("Authority: {}").format(self.authority)


class PerfectMoneyPayment(models.Model):
    transaction = models.OneToOneField(
        to=Transaction,
        on_delete=models.CASCADE,
        verbose_name=_("related transaction"),
        related_name="perfectmoney"
    )
    evoucher = models.CharField(
        max_length=10,
        verbose_name="E-voucher",
        null=True,
        blank=True
    )
    activation_code = models.CharField(
        max_length=16,
        verbose_name="activation code",
        null=True,
        blank=True
    )

    def __str__(self):
        return _("EVoucher: {}").format(self.evoucher)


class CryptoPayment(models.Model):
    transaction = models.OneToOneField(
        to=Transaction,
        on_delete=models.CASCADE,
        verbose_name=_("related transaction"),
        related_name="crypto"
    )
    from_addres = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("payer wallet address")
    )
    order_id = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("order id")
    )
    tx_hash = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("transaction hash")
    )
    network = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name=_("blockchain network")
    )
    currency = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name=_("invoice currency")
    )
    payer_currency = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name=_("actuall paid currency")
    )
    payment_amount_coin = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        verbose_name=_("actual pay amount crypto"),
    )

    def __str__(self):
        return _("Coin: {}:{}").format(self.network, self.currency)
