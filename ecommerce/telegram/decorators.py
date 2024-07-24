from django.core.cache import cache

from ecommerce.bot.services import MessageService


def restrict_user_payment_rate(func):
    """
    Limits a user to 3 payment attempts per 30 minutes. Exceeding this limit triggers a 30-minute block.
    """
    def wrapper(self):
        key_per_user = f"payment_spam_count_{self.chat_id}"
        spam_count = cache.get_or_set(key_per_user, 1, timeout=1800)
        if spam_count > 3:
            msg = MessageService(self.user_obj).get(step="anti-pay-spam-msg").text
            self.bot.send_message(self.chat_id, text=msg)
            cache.set(key_per_user, 4, timeout=1800)
            return False
        else:
            cache.incr(key_per_user)
            return func(self)

    return wrapper


def restrict_global_payment_rate(func):
    """
    Limits all users to a total of 30 payment attempts per hour. Exceeding this limit results in a global 30-minute block.
    """

    def wrapper(self):
        key = "global_payment_spam_count"
        spam_count = cache.get_or_set(key, 1, timeout=3600)
        if spam_count > 30:
            msg = MessageService(self.user_obj).get(step="anti-pay-spam-msg").text
            self.bot.send_message(self.chat_id, text=msg)
            cache.set(key, 31, timeout=1800)
            return False
        else:
            cache.incr(key)
            return func(self)

    return wrapper
