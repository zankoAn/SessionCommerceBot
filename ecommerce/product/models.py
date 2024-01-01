
from django.db import models
from ecommerce.bot.models import Message
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from uuid import uuid4

User = get_user_model()


def generate_short_uuid():
    return str(uuid4()).split('-')[-1]


class Product(models.Model):
    name = models.CharField(
        max_length=50,
        verbose_name=_("product name")
    )
    price = models.PositiveIntegerField(
        default=0,
        verbose_name=_("product price")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("is active product?")
    )

    def __str__(self) -> str:
        return str(self.name)

    def calculate_order_price(self, order_count):
        price = int(self.price * (int(order_count) / 100))
        return f"{price:,}"


class AccountSession(models.Model):
    class StatusChoices(models.Choices):
        active = "active"
        disable = "disable"
        limit = "limit"

    proxy = models.CharField(
        max_length=20,
        verbose_name=_("proxy(ip:port)")
    )
    api_id = models.CharField(
        max_length=20,
        verbose_name=_("api hash")
    )
    api_hash = models.CharField(
        max_length=20,
        verbose_name=_("api id")
    )
    phone = models.CharField(
        max_length=20,
        verbose_name=_("phone number")
    )
    session_string = models.CharField(
        max_length=20,
        verbose_name=_("session string")
    )
    status = models.CharField(
        max_length=50,
        verbose_name=_("session status"),
        choices=StatusChoices,
    )
    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("created time")
    )

    def __str__(self) -> str:
        return str(self.phone)


class Order(models.Model):

    class StatusChoices(models.Choices):
        down = "انجام شد ✅"
        reject = "رد شد ❌"
        waiting = "در صف "

    user = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    session = models.OneToOneField(
        to=AccountSession,
        related_name="session",
        on_delete=models.CASCADE,
    )
    login_code = models.CharField(
        max_length=20,
        verbose_name=_("login code")
    )
    price = models.IntegerField(
        default=0,
        verbose_name=_("price")
    )
    track_id = models.CharField(
        max_length=80,
        default=generate_short_uuid,
        verbose_name=_("tracking id")
    )
    status = models.CharField(
        max_length=30,
        choices=StatusChoices,
        default="waiting"
    )
    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("created time")
    )

    def __str__(self) -> str:
        return str(self.user)