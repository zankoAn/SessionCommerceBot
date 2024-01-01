from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Payment(models.Model):
    payer = models.ForeignKey(
        to=User,
        on_delete=models.SET_NULL,
        related_name='payments',
        null=True
    )
    amount  = models.BigIntegerField(
        default=0,
        verbose_name='amount',
    )
    transaction_id = models.CharField(
        max_length=70,
        verbose_name="Transaction Id",
    )
    is_paid = models.BooleanField(
        default=False,
        verbose_name='Is Paid ?',
    )
    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name='payment creation time',
    )

    def __str__(self):
        return str(self.payer)