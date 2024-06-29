from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model


User = get_user_model()


class BotUpdateStatus(models.Model):
    is_update = models.BooleanField(
        default=False,
        verbose_name=_("update status")
    )
    update_msg = models.TextField(default="")

    def save(self, *args, **kwargs):
        self.id = 1
        return super().save(*args, **kwargs)

    def __str__(self):
        return str(_(f"Bot status is: {self.is_update}"))


class Message(models.Model):
    text = models.TextField(default="")
    current_step = models.CharField(
        max_length=80,
        default="home",
        verbose_name=_("current step"),
    )
    key = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name=_("base keyboard"),
    )
    keys = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("all other keys"),
    )
    keys_per_row = models.PositiveIntegerField(
        default=2,
        null=True,
        blank=True,
        verbose_name=_("keys per row"),
    )
    is_inline_keyboard = models.BooleanField(
        default=False,
        verbose_name=_("Is inline keyboard?")
    )

    @property
    def fetch_keys(self):
        return self.keys.split("\n")

    def save(self, *args, **kwargs):
        self.text = self.text.strip()
        self.current_step = self.current_step.strip()
        self.keys = self.keys.strip() if self.keys else None
        self.key = self.key.strip() if self.key else None
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.key or self.current_step

