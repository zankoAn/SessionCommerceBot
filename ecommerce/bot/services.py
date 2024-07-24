from django.utils.translation import gettext, override

from ecommerce.bot.models import Message


class MessageService:
    def __init__(self, user) -> None:
        self.user = user

    def transalte(self, msg):
        if self.user.language != "fa":
            with override(self.user.language):
                if keys := msg.keys:
                    msg.keys = gettext(keys)
                if text := msg.text:
                    msg.text = gettext(text)

        return msg

    def get(self, step) -> Message:
        msg = Message.objects.get(current_step=step)
        msg = self.transalte(msg)
        return msg

    def filter_user_msgs(self, **kwargs) -> list:
        msgs = Message.objects.filter(**kwargs).exclude(
            current_step__startswith="admin"
        )
        translated_msgs = []
        for msg in msgs:
            translated_msgs.append(self.transalte(msg))

        return translated_msgs

    def filter_admin_msgs(self, **kwargs) -> list:
        msgs = Message.objects.filter(current_step__startswith="admin", **kwargs)
        translated_msgs = []
        for msg in msgs:
            translated_msgs.append(self.transalte(msg))

        return translated_msgs

    @staticmethod
    def get_step(key) -> str:
        step = (
            Message.objects.filter(key=key)
            .values_list("current_step", flat=True)
            .first()
        )
        return step
