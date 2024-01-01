from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ecommerce.bot.telegram.telegram import Telegram
from ecommerce.bot.telegram.handlers import BaseHandler, BaseCallbackHandler

User = get_user_model()


@api_view(("GET", "POST"))
def webhook(request):
    data = request.data
    print(data)
    print("=" * 100)
    try:
        if text_data := data.get("message"):
            text_handler(text_data)

        elif callback_data := data.get("callback_query"):
            callback_handler(callback_data)
        else:
            return Response("not found")

        # Return the simple HttpResponse to handel the non returned exception
        return Response("ok")
    except Exception as e:
       print(e)
       return Response("error")


def callback_handler(update):
    bot = Telegram()
    callback_handler = BaseCallbackHandler(bot, update)
    callback_handler.run()

def text_handler(update):
    bot = Telegram()
    base_handler = BaseHandler(bot, update)
    base_handler.run()