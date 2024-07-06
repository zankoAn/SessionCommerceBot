from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser
from django.db.models import Sum


class User(AbstractUser):
    user_id = models.BigIntegerField(
        unique=True,
        verbose_name=_("user id")
    )
    step = models.CharField(
        max_length=30,
        default="home",
        verbose_name=_("current step")
    )
    is_send_ads = models.BooleanField(
        default=False,
        verbose_name=_("Advertising status")
    )
    balance = models.PositiveBigIntegerField(
        default=10000,
        verbose_name=_("balance")
    )
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["user_id"]

    @property
    def calculate_total_paid(self):
        from ecommerce.payment.models import Transaction
        from django.db.models import Q

        total_paid = (
            self.payments.filter(
                Q(status=Transaction.StatusChoices.PAID)
                & Q(status=Transaction.StatusChoices.PAID_OVER)
            ).aggregate(total=Sum("amount_rial"))["total"]
            or 0
        )
        if total_paid:
            total_paid = int(total_paid) / 10

        return int(0)

    def __str__(self):
        return str(self.user_id)
