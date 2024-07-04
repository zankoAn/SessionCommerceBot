from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

User = get_user_model()


def generate_short_uuid():
    return str(uuid4()).split("-")[-1]


class Product(models.Model):
    name = models.CharField(
        max_length=50,
        verbose_name=_("product name")
    )
    country_code = models.CharField(
        max_length=50,
        verbose_name=_("country code"),
        help_text=_("us, ir, uk and etc.."),
        default="",
    )
    phone_code = models.CharField(
        max_length=50,
        verbose_name=_("phone code"),
        help_text=_("+98, +1, +964, +234 and etc.."),
        default="",
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
    class StatusChoices(models.TextChoices):
        active = "فعال ✅"
        disable = "غیر فعال ❌"
        limit = "محدود ⚠️"
        purchased = "فروخته شد 💸"
        wait = "در انتظار ⏳"
        unknown = "نامشخص 🔘"

    product = models.ForeignKey(
        to=Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounts",
    )
    proxy = models.CharField(
        max_length=50,
        verbose_name=_("proxy(ip:port)"),
        blank=True,
    )
    api_id = models.CharField(
        max_length=20,
        verbose_name=_("api id"),
        blank=True,
    )
    api_hash = models.CharField(
        max_length=50,
        verbose_name=_("api hash"),
        blank=True,
    )
    phone = models.CharField(
        max_length=20,
        verbose_name=_("phone number"),
        blank=True,
    )
    app_version = models.CharField(
        max_length=30,
        verbose_name=_("App Version"),
        blank=True,
        null=True,
    )
    device_model = models.CharField(
        max_length=30,
        verbose_name=_("Device Model"),
        blank=True,
        null=True,
    )
    system_version = models.CharField(
        max_length=30,
        verbose_name=_("System Version"),
        blank=True,
        null=True,
    )
    password = models.CharField(
        max_length=64,
        verbose_name=_("account password"),
        default="",
        blank=True,
    )
    status = models.CharField(
        max_length=50,
        verbose_name=_("session status"),
        choices=StatusChoices.choices,
        default=StatusChoices.unknown,
    )
    session_string = models.CharField(
        max_length=400,
        verbose_name=_("session string")
    )
    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("created time")
    )

    def __str__(self) -> str:
        return str(self.phone)


class Order(models.Model):
    class StatusChoices(models.TextChoices):
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
        related_name="order",
        on_delete=models.CASCADE,
    )
    login_code = models.CharField(
        max_length=20,
        verbose_name=_("login code"),
        null=True,
        blank=True,
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
        choices=StatusChoices.choices,
        default=StatusChoices.waiting
    )
    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("created time")
    )

    def __str__(self) -> str:
        return str(self.user)
