import json

from django.core.cache import cache
from django.http import HttpResponse

from ecommerce.bot.models import Message
from ecommerce.telegram.telegram import Telegram


class AntiSpamerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.bot = Telegram()
        self.anti_spm_err_msg = Message.objects.get(current_step="anti-spam-msg")

    def __call__(self, request):
        update = request.body.decode()
        if not update:
            return self.get_response(request)

        try:
            update = json.loads(request.body.decode())
            user_id = update.get("message", {}).get("from", {}).get("id")
            if not user_id:
                return self.get_response(request)
        except Exception:
            return self.get_response(request)

        key = f"spam_count_{user_id}"
        spam_count = cache.get_or_set(key, 1, timeout=20)
        if spam_count >= 10:
            self.bot.send_message(chat_id=user_id, text=self.anti_spm_err_msg.text)
            # Limit user for 15 second if send 10 msg in 20 second.
            cache.set(key, 11, timeout=15)
            return HttpResponse("Bad", status=429)
        else:
            cache.incr(key)

        return self.get_response(request)
