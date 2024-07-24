from ecommerce.bot.models import Message


class MessageService:
    def __init__(self, user) -> None:
        self.user = user

    def get(self, step) -> Message:
        msg = Message.objects.get(current_step=step)
        return msg

    def filter_user_msgs(self, **kwargs) -> list:
        msgs = Message.objects.filter(**kwargs).exclude(
            current_step__startswith="admin"
        )
        return list(msgs)

    def filter_admin_msgs(self, **kwargs) -> list:
        msgs = Message.objects.filter(current_step__startswith="admin", **kwargs)

        return list(msgs)

    @staticmethod
    def get_step(key) -> str:
        step = (
            Message.objects.filter(key=key)
            .values_list("current_step", flat=True)
            .first()
        )
        return step
