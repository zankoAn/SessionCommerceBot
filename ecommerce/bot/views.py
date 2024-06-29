from rest_framework.decorators import api_view
from rest_framework.response import Response

from ecommerce.telegram.handlers.base_handler import BaseCallbackHandler, BaseHandler
from ecommerce.telegram.deserializers import (
    TextUpdateDeserializer,
    CallbackUpdateDeSerializer,
)
from ecommerce.telegram.telegram import Telegram
import traceback


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
    except Exception:
        msg = traceback.format_exc().strip()
        formated_msg = (
            f"\n{'-'*30}\n{' '*7}Your Exception:{' '*7}| \n{'-'*100}\n{msg}\n{'-'*100}"
        )
        print(formated_msg)
        return Response("error")


def callback_handler(update):
    bot = Telegram()
    deserializer = CallbackUpdateDeSerializer(update)
    deserializer.deserialize()
    callback_handler = BaseCallbackHandler(bot, deserializer)
    callback_handler.run()


def text_handler(update):
    bot = Telegram()
    deserializer = TextUpdateDeserializer(update)
    deserializer.deserialize()
    base_handler = BaseHandler(bot, deserializer)
    base_handler.run()
