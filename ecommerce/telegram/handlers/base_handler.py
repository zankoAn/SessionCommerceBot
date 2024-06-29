import json

from django.contrib.auth import get_user_model
from django.core.cache import cache

from ecommerce.bot.models import BotUpdateStatus, Message
from ecommerce.telegram.deserializers import (
    CallbackUpdateDeSerializer,
    TextUpdateDeserializer,
)
from ecommerce.telegram.handlers.admin_handlers import (
    AdminCallbackHandler,
    AdminStepHandler,
    AdminTextHandler,
)
from ecommerce.telegram.handlers.user_handlers import (
    UserCallbackHandler,
    UserInputHandler,
    UserTextHandler,
)
from ecommerce.telegram.telegram import Telegram

User = get_user_model()
my_loop = None


class BaseHandler:
    def __init__(self, bot: Telegram, update: TextUpdateDeserializer):
        self.bot = bot
        self.update = update
        self.step = None  # override in add_new_user method

    def __getattr__(self, name):
        attribute = getattr(self.update, name, None)
        if attribute is not None:
            return attribute

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def add_new_user(self):
        """
        This method checks if the user object exists in the DB or not.
        If the user not exist, then add them to the DB.
        Sets the `user_qs` and `user_obj` as global variables.
        If the user is new, then call the `check_referral_user` method.
        """
        self.user_qs = User.objects.filter(user_id=self.chat_id)
        if not self.user_qs:
            username = self.username
            dup_username = User.objects.filter(username=username)
            if dup_username:
                username = self.chat_id

            user = User.objects.create_user(
                username=username,
                password=str(self.chat_id),
                first_name=self.first_name,
                last_name=self.last_name,
                user_id=self.chat_id,
                step="home_page",
            )
            self.user_qs = User.objects.filter(user_id=self.chat_id)
            self.user_obj = user
            # self.check_referral_user() #TODO: check refreall
        else:
            self.user_obj = self.user_qs.first()
        self.step = self.user_obj.step

    def is_deactive_user(self):
        """If the user is blocked, the user's message will be sent to himself."""
        if not self.user_obj.is_active:
            self.bot.forward_message(
                chat_id=self.chat_id,
                from_chat_id=self.chat_id,
                message_id=self.message_id,
            )
            return True

    def is_update_mode(self):
        """Check if the application is currently in update mode."""
        if self.user_obj.is_staff:
            return False

        update_obj = BotUpdateStatus.objects.first()
        if update_obj and update_obj.is_update:
            self.bot.send_message(self.chat_id, update_obj.update_msg)
            return True

        return False

    def generate_keyboards(self, msg):
        keys = msg.fetch_keys
        if msg.is_inline_keyboard:
            inline_keyboard = []
            for i in range(0, len(keys), msg.keys_per_row):
                inner_keys = []
                for key in keys[i : i + msg.keys_per_row]:
                    text, callback, url = key.replace("https://", "").split(
                        ":"
                    )  # TODO: check to see is there problem?
                    if callback:
                        inner_keys += [{"text": text, "callback_data": callback}]
                    else:
                        inner_keys += [{"text": text, "url": "https://" + url}]
                inline_keyboard.append(inner_keys)
            return json.dumps({"inline_keyboard": inline_keyboard})
        else:
            keyboard = [
                keys[i : i + msg.keys_per_row]
                for i in range(0, len(keys), msg.keys_per_row)
            ]
            return json.dumps(
                {
                    "keyboard": keyboard,
                    "resize_keyboard": True,
                    "one_time_keyboard": True,
                }
            )

    def text_handlers(self):
        msg_step = (
            Message.objects.filter(key=self.text)
            .values_list("current_step", flat=True)
            .first()
        )
        if msg_step and msg_step.startswith("admin") and not self.user_obj.is_staff:
            return

        if msg_step or "/start" in self.text:
            if self.user_obj.is_staff:
                AdminTextHandler(self).run()
            return UserTextHandler(self).run()

        if self.user_obj.is_staff:
            if self.reply_to_msg:
                return AdminStepHandler(self).respond_to_ticket()

            elif self.user_obj.step.startswith("admin"):
                AdminStepHandler(self).run()

        return UserInputHandler(self).run()

    def run(self):
        self.add_new_user()
        if self.is_update_mode():
            return
        if self.is_deactive_user():
            return
        self.text_handlers()


class BaseCallbackHandler(BaseHandler):
    def __init__(self, bot: Telegram, update: CallbackUpdateDeSerializer):
        self.bot = bot
        self.update = update

    def __getattr__(self, name):
        if attribute := getattr(self.update, name, None):
            return attribute

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def retrive_user(self):
        self.user_qs = User.objects.filter(user_id=self.from_chat_id)
        self.user_obj = self.user_qs.first()

    def validate_cached_data(self):
        cached_data = cache.get(self.chat_id)
        if not cached_data:
            self.user_qs.update(step="home")
            msg = Message.objects.filter(current_step="expired_order").first()
            reply_markup = self.generate_keyboards(msg)
            self.bot.send_message(self.chat_id, msg.text, reply_markup=reply_markup)
        return cached_data

    def callback_handlers(self):
        UserCallbackHandler(self).run()
        if self.user_obj.is_staff:
            AdminCallbackHandler(self).run()

    def run(self):
        self.retrive_user()
        if self.is_update_mode():
            return
        if self.is_deactive_user():
            return
        self.callback_handlers()
