from ecommerce.bot.models import Message
from ecommerce.payment.models import Payment
from ecommerce.bot.telegram.telegram import Telegram
from ecommerce.product.models import Order, Product, AccountSession

from datetime import timedelta
from pyrogram import Client, errors

from django.utils import timezone
from django.db.models import Q, F, Sum
from django.db.models import Count, Case, When, Value, IntegerField
from django.contrib.auth import get_user_model
from django.core.cache import cache

import json
import asyncio
import io


from utils.load_env import config as CONFIG


User = get_user_model()
my_loop = None
cache_account_sessions = {}



class TMAccountHandler:

    def __init__(self, session_id = 0) -> None:
        self.session_id = session_id

    async def intialize_client(self):
        session_obj = await AccountSession.objects.aget(id=self.session_id)
        _proxy = session_obj.proxy.split(":")
        proxy = {
            "scheme": "socks5",
            "hostname": _proxy[0],
            "port": int(_proxy[1])
        }
        account = Client(
            name="",
            api_id=session_obj.api_id,
            api_hash=session_obj.api_hash,
            proxy=proxy,
            session_string=session_obj.session_string,
            in_memory=True,
            no_updates=True
        )
        return session_obj, account

    async def check_session_string_status(self, session_obj:AccountSession, account: Client):
        try:
            if await account.connect():
                x = await account.get_me()
                print(x)
                session_obj.status = AccountSession.StatusChoices.active
                await session_obj.asave()
                await account.disconnect()
                return session_obj.status.value
        except Exception as err:
            print(err)
            session_obj.status = AccountSession.StatusChoices.disable
            await session_obj.asave()
            return session_obj.status.value
        finally:
            return session_obj.status.value

    async def extract_session_string(self):
        proxy = None
        if CONFIG.PROXY_SOCKS:
            proxy = {"scheme": "socks5", "hostname": "127.0.0.1", "port": 1359}

        account = Client(
            name="/tmp/session_file",
            api_id=901903,
            api_hash="ef8acfacf0d45e16bba0b0568251ef2b",
            proxy=proxy
        )
        try:
            await account.connect()
            session_string = await account.export_session_string()
            await account.disconnect()
            return session_string
        except Exception as error:
            print("[Error] Export session string: ",error)
            return False, False

    async def send_login_code(self):
        session_obj = await AccountSession.objects.aget(id=self.session_id)
        _proxy = session_obj.proxy.split(":")
        proxy = {
            "scheme": "socks5",
            "hostname": _proxy[0],
            "port": int(_proxy[1])
        }
        account = Client(
            name="",
            phone_number=session_obj.phone,
            api_id=session_obj.api_id,
            api_hash=session_obj.api_hash,
            proxy=proxy,
            in_memory=True,
        )
        try:
            await account.connect()
            result = await account.send_code(session_obj.phone)
            print(result)
            return account, result
        except Exception as error:
            print("[Error] Send login code: ",error)
            return False

    async def sign_in_account(self, account: Client, phone_code_hash, login_code):
        session_obj = await AccountSession.objects.aget(id=self.session_id)
        try:
            user = await account.sign_in(
                phone_number=session_obj.phone,
                phone_code_hash=phone_code_hash,
                phone_code=login_code
            )
            print(user)
            if user.id:
                session_string = await account.export_session_string()
                session_obj.session_string = session_string
                await session_obj.asave()
                return True, None, None
        except errors.SessionPasswordNeeded:
            hint = await account.get_password_hint()
            return False, hint, errors.SessionPasswordNeeded

        except errors.PhoneCodeInvalid:
            return False, "Login code invalid", errors.PhoneCodeInvalid

        except errors.PhoneCodeExpired:
            return False, "Login code expired", errors.PhoneCodeExpired

        except errors.PhonePasswordFlood:
            return False, "Password foold", errors.PhonePasswordFlood

        except errors.FloodWait:
            return False, "FoolWait tray later", errors.FloodWait

        except Exception as err:
            print(err)
            return False, "Unexpected error, check server log", False

        return False, "Unexpected error, check server log", False

    async def confirm_password(self, account: Client, password):
        try:
            await account.check_password(password)
            session_obj = await AccountSession.objects.aget(id=self.session_id)
            session_string = await account.export_session_string()
            session_obj.session_string = session_string
            session_obj.password = password
            await session_obj.asave()
            return True, None
        except errors.PasswordHashInvalid:
            error = "❌ Invalid Password"
            hint = await account.get_password_hint()
            return False, hint + error, errors.PasswordHashInvalid

        except Exception as err:
            print(err)
            return False, "Unexpected error, check server log", False

    async def runner(self, method_name):
        method = getattr(self, method_name)
        session_obj, account = await self.intialize_client()
        result = await method(session_obj, account)
        return result


class BaseHandler:
    def __init__(self, bot: Telegram, update):
        self.bot = bot
        self.update = update
        self.step = None # override in add_new_user method

    def serializer(self):
        self.chat_id = self.update.get("chat", {}).get("id")
        self.message_id = self.update.get("message_id")        
        self.first_name = self.update.get("chat", {}).get("first_name", "id")
        self.last_name = self.update.get("chat", {}).get("last_name", "id")
        self.username = self.update.get("chat", {}).get("username", self.chat_id)
        self.text = self.update.get("text", "")
        self.reply_to_msg = self.update.get("reply_to_message", "")
        self.file_id = self.update.get("document", {}).get("file_id")

    def add_new_user(self):
        """This method checks if the user object exists in the DB or not.
        If the user not exist, then add them to the DB.
        Sets the `user_qs` and `user_obj` as global variables.
        """
        self.user_qs = User.objects.filter(user_id=self.chat_id)
        if not self.user_qs:
            user = User.objects.create_user(
                username=self.username,
                password=str(self.chat_id),
                first_name=self.first_name,
                last_name=self.last_name,
                user_id=self.chat_id,
                step="home",
            )
            self.user_qs = User.objects.filter(user_id=self.chat_id)
            self.user_obj = user
            self.check_referral_user()
        else:
            self.user_obj = self.user_qs.first()
        self.step = self.user_obj.step

    def generate_keyboards(self, msg):
        keys = msg.fetch_keys
        if msg.is_inline_keyboard:
            inline_keyboard = []
            for i in range(0, len(keys), msg.keys_per_row):
                inner_keys = []
                for key in keys[i:i + msg.keys_per_row]:
                    text, callback, url = key.split(":")
                    if callback:                        
                        inner_keys += [{"text": text, "callback_data": callback}]
                    else:
                        inner_keys += [{"text": text, "url": "https://" + url}]
                inline_keyboard.append(inner_keys)
            return json.dumps({
                "inline_keyboard": inline_keyboard
            })
        else:
            keyboard = [
                keys[i: i + msg.keys_per_row]
                for i in range(0, len(keys), msg.keys_per_row)
            ]
            return json.dumps({
                "keyboard": keyboard,
                "resize_keyboard": True,
                "one_time_keyboard": True
            })

    def handlers(self):
        msg_step = Message.objects.filter(key=self.text).values_list("current_step", flat=True).first()
        is_admin_message = msg_step and msg_step.startswith("admin")

        if is_admin_message and not self.user_obj.is_staff:
            return

        if msg_step:
           return TextHandler(self).run()

        if self.reply_to_msg and self.user_obj.is_staff:
            return AdminStepHandler(self).respond_to_ticket()

        if self.user_obj.is_staff and self.user_obj.step.startswith("admin"):
            return AdminStepHandler(self).run()
        else:
            return UserStepHandler(self).run()

    def run(self):
        self.serializer()
        self.add_new_user()
        self.handlers()


class TextHandler(BaseHandler):
    def __init__(self, base):
        for key, value in vars(base).items():
            setattr(self, key, value)

    def user_profile(self, text):
        return text.format(
            user_id=self.chat_id,
            total_order=self.user_obj.orders.count(),
            total_pay=self.user_obj.calculate_total_paid,
            balance=self.user_obj.balance
        )

    def admin_get_bot_info(self, text):
        now = timezone.now()
        current_month_start = now.date() - timedelta(days=31)
        current_week_start = now.date() - timedelta(days=7)

        result_user = User.objects.aggregate(
            current_month=Count(
                Case(
                    When(date_joined__gte=current_month_start, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                ),
            ),
            current_week=Count(
                Case(
                    When(date_joined__gte=current_week_start, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            total=Count("id")
        )
        result_pay = Payment.objects.filter(is_paid=True).aggregate(
            current_month=Sum(
                Case(
                    When(created__gte=current_month_start, then=F("amount")),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            current_week=Sum(
                Case(
                    When(created__gte=current_week_start , then=F("amount")),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            total=Sum("amount")
        )
        return text.format(
            total_users_per_week=result_user["current_week"],
            total_users_per_month=result_user["current_month"],
            total_users=result_user["total"],
            total_payments_per_week=result_pay["current_week"],
            total_payments_per_month=result_pay["current_month"],
            total_payments=result_pay["total"],
        )

    def buy_phone_number(self, msg):
        products = Product.objects.all()
        keys = ""
        for product in products:
            keys += f"\n{product.price:,} | {product.name}:country_{product.country_code}:"
        msg.keys = keys.strip()
        key = self.generate_keyboards(msg)
        return msg.text, key

    def back_to_add_session(self, msg):
        if my_loop:
            my_loop.close()
        keys = self.generate_keyboards(msg)
        return msg.text, keys

    def handler(self):
        messages = Message.objects.filter(key=self.text)
        self.user_qs.update(step=messages.last().current_step)

        # Itrate over all msg in related section.
        for msg in messages:
            reply_markup = None
            text = msg.text
            if msg.keys:
                reply_markup = self.generate_keyboards(msg)

            if update_text_method := getattr(self, msg.current_step, None):
                text, keys = update_text_method(msg)
                if keys:
                    reply_markup = keys

            self.bot.send_message(self.chat_id, text, reply_markup=reply_markup)

    def run(self):
        self.handler()


class AdminStepHandler(BaseHandler):

    def __init__(self, base):
        self.steps = {
            "admin-get-user-info": self.user_info,
            "admin-add-session-string": self.add_session_string,
            "admin-add-session-file": self.add_session_file,
            "admin-add-session-phone": self.add_session_phone,
            "admin-get-api-id-hash-session": self.get_api_id_and_hash_session,
            "admin-get-api-id-hash-login": self.get_api_id_and_hash_login,
            "admin-get-session-proxy-session": self.get_proxy_session,
            "admin-get-session-proxy-login": self.get_proxy_login,
            "admin-get-login-code": self.get_login_code,
            "admin-get-login-password": self.get_login_password,
        }
        for key, value in vars(base).items():
            setattr(self, key, value)

    def retrive_msg_and_keys(self, step):
        msg = Message.objects.filter(current_step=step).first()
        keys = self.generate_keyboards(msg)
        return msg, keys

    def update_cached_data(self, **kwargs):
        cached_data = cache.get(f"{self.chat_id}:session", {})
        for key, value in kwargs.items():
            cached_data[key] = value
        cache.set(f"{self.chat_id}:session", cached_data, timeout=None)

    def user_info(self):
        # TODO: show the total orders
        user = self.text
        user = User.objects.filter(Q(username=user) | Q(user_id=user)).first()
        if user:
            msg = Message.objects.filter(current_step="admin-user-info").first()
            text_msg = msg.text.format(
                user_id=user.user_id,
                name=user.first_name,
                last_name=user.last_name,
                username=user.username,
                balance=user.balance,
                total_session=0,
                total_pay=user.calculate_total_paid,
                created=user.date_joined.strftime("%Y-%m-%d %H:%M:%S"),
            )
        else:
            text_msg = "❌ User not found"
        self.bot.send_message(self.chat_id, text_msg)

    def add_session_string(self):
        error_msg = "Bad format"
        if len(self.text) < 60:
            return self.bot.send_message(self.chat_id, error_msg)

        session,_ = AccountSession.objects.get_or_create(session_string=self.text)
        msg, keys = self.retrive_msg_and_keys("admin-get-api-id-hash")
        self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
        self.update_cached_data(session_id=session.id)
        self.user_qs.update(step="admin-get-api-id-hash-session")

    def add_session_file(self):
        error_msg = "Bad format"
        if not self.file_id:
            return self.bot.send_message(self.chat_id, error_msg)

        content = self.bot.download_file(self.file_id)
        with open("/tmp/session_file.session", "wb") as session_file:
            session_file.write(content)

        session_string = async_to_sync(TMAccountHandler().extract_session_string)()
        if not session_string:
            return self.bot.send_message(self.chat_id, error_msg)

        session, _ = AccountSession.objects.get_or_create(session_string=session_string)
        msg, keys = self.retrive_msg_and_keys("admin-get-api-id-hash")
        self.update_cached_data(session_id=session.id)
        self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
        self.user_qs.update(step="admin-get-api-id-hash-session")

    def add_session_phone(self):
        error_msg = "❌ فرمت دیتای ارسال شده درست نیست ❌"
        if not 10 < len(self.text) < 15:
            return self.bot.send_message(self.chat_id, error_msg)

        session, _ = AccountSession.objects.get_or_create(phone=self.text)
        msg, keys = self.retrive_msg_and_keys("admin-get-api-id-hash")
        self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
        self.update_cached_data(session_id=session.id)
        self.user_qs.update(step="admin-get-api-id-hash-login")

    def _get_api_id_and_hash_base(self):
        error_msg = "❌ فرمت دیتای ارسال شده درست نیست ❌"
        msg, keys = self.retrive_msg_and_keys("admin-get-session-proxy")
        session_id = cache.get(f"{self.chat_id}:session")["session_id"]
        if "دیفالت" in self.text:
            AccountSession.objects.filter(id=session_id).update(api_id=CONFIG.API_ID, api_hash=CONFIG.API_HASH)
            return self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)

        # Validate data
        if not 1 < len(self.text.split("\n")) < 3:
            return self.bot.send_message(self.chat_id, error_msg)

        api_id, api_hash = self.text.split("\n")
        # Validate api_id
        try:
            int(api_id)
        except:
            return self.bot.send_message(self.chat_id, error_msg)

        AccountSession.objects.filter(id=session_id).update(api_id=api_id, api_hash=api_hash)
        self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)

    def get_api_id_and_hash_session(self):
        self._get_api_id_and_hash_base()
        self.user_qs.update(step="admin-get-session-proxy-session")

    def get_api_id_and_hash_login(self):
        self._get_api_id_and_hash_base()
        self.user_qs.update(step="admin-get-session-proxy-login")

    def _get_proxy_base(self):
        error_msg = "❌ فرمت دیتای ارسال شده درست نیست ❌"
        session_id = cache.get(f"{self.chat_id}:session")["session_id"]
        if "دیفالت" in self.text:
            AccountSession.objects.filter(id=session_id).update(proxy=CONFIG.PROXY_SOCKS)
            return session_id

        if len(self.text.split(":")) not in (2,3):
            return self.bot.send_message(self.chat_id, error_msg)

        if "//" in self.text:
            proxy = self.text.split("//")[1]
        else:
            proxy = self.text

        AccountSession.objects.filter(id=session_id).update(proxy=proxy)
        return session_id

    def get_proxy_session(self):
        session_id = self._get_proxy_base()
        msg, keys = self.retrive_msg_and_keys("admin-add-session-success")
        status = asyncio.run(TMAccountHandler(session_id).runner("check_session_string_status"))
        text = msg.text.format(status=status)
        self.bot.send_message(self.chat_id, text, reply_markup=keys)
        self.user_qs.update(step=msg.current_step)

    def get_proxy_login(self):
        global my_loop
        session_id = self._get_proxy_base()
        self.bot.send_message(self.chat_id, "⏳")
        # Create new event loop
        my_loop = asyncio.new_event_loop()
        account, result = my_loop.run_until_complete(TMAccountHandler(session_id).send_login_code())
        # Cache the client object
        cache_account_sessions[self.chat_id] = account
        self.update_cached_data(phone_code_hash=result.phone_code_hash)        
        msg, keys = self.retrive_msg_and_keys("admin-get-login-code")
        self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
        self.user_qs.update(step=msg.current_step)

    def get_login_code(self):
        account = cache_account_sessions[self.chat_id]
        data = cache.get(f"{self.chat_id}:session")
        session_id = data["session_id"]
        phone_code_hash = data["phone_code_hash"]
        login_code = self.text
        status, msg, action = my_loop.run_until_complete(
            TMAccountHandler(session_id).sign_in_account(account, phone_code_hash, login_code)
        )
        if status:
            msg, keys = self.retrive_msg_and_keys("admin-add-session-success")
            self.user_qs.update(step="admin-add-session")
            self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
            return

        if action == errors.SessionPasswordNeeded:
            msg, keys = self.retrive_msg_and_keys("admin-get-login-password")
            self.user_qs.update(step=msg.current_step)
            self.bot.send_message(self.chat_id, msg.text)
            return

        self.bot.send_message(self.chat_id, msg)

    def get_login_password(self):
        account = cache_account_sessions[self.chat_id]
        data = cache.get(f"{self.chat_id}:session")
        session_id = data["session_id"]
        password = self.text
        status, msg, action = my_loop.run_until_complete(
            TMAccountHandler(session_id).confirm_password(account, password)
        )
        if status:
            my_loop.close()
            msg, keys = self.retrive_msg_and_keys("admin-add-session-success")
            self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)

        self.bot.send_message(self.chat_id, msg)

    def handler(self):
        if callback := self.steps.get(self.user_obj.step):
            callback()

    def run(self):
        self.handler()


class UserStepHandler(BaseHandler):

    def __init__(self, base):
        self.steps = {
            "get-amount": self.make_payment,
            
        }
        for key, value in vars(base).items():
            setattr(self, key, value)


    def make_payment(self):
        msg = Message.objects.filter(current_step="payment").first()
        url = f"google.com?pay={self.text}&user_id={self.chat_id}"
        msg.keys = msg.keys.format(url=url, callback="")
        reply_markup = self.generate_keyboards(msg)
        text = msg.text.format(user_id=self.chat_id, amount=int(self.text))
        self.bot.send_message(self.chat_id, text, reply_markup=reply_markup)

    def handlers(self):
        if callback := self.steps.get(self.user_obj.step):
            callback()

    def run(self):
        self.handlers()


class BaseCallbackHandler(BaseHandler):

    def __init__(self, bot: Telegram, update: dict):
        self.bot = bot
        self.update = update

    def serializer(self):
        self.callback_data = self.update["data"]
        self.from_chat_id = self.update.get("from", {}).get("id")
        self.chat_id = self.update.get("message", {}).get("chat", {}).get("id")
        self.text = self.update.get("message", {}).get("text", {})
        self.message_id = self.update.get("message", {}).get("message_id")
        self.callback_query_id = self.update.get("id")
        self.entities = self.update.get("message", {}).get("entities")

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

    def callback_handler(self):
        UserCallbackHandler(self).run()

    def run(self):
        self.serializer()
        self.retrive_user()
        self.callback_handler()


class UserCallbackHandler(BaseCallbackHandler):

    def __init__(self, base) -> None:
        self.callback_handlers = {
            "country_": self.get_phone_number,
            "login_code": self.get_login_code
        }
        for key, value in vars(base).items():
            setattr(self, key, value)

    def get_phone_number(self):
        # TODO: retrive random session.
        # TODO: Cache the number and validated        
        msg = Message.objects.filter(current_step="send_phone_number").first()
        keys = self.generate_keyboards(msg)
        phone = "+98154878787"
        self.bot.edit_message_text(
            self.chat_id,
            self.message_id,
            msg.text.format(phone=phone),
            reply_markup=keys
        )

    def get_login_code(self):
        # TODO:  Get number from cache if exists 
        # TODO: get login code
        msg = Message.objects.filter(current_step="send_login_code").first()
        code = 787878
        keys = self.generate_keyboards(msg)
        self.bot.edit_message_text(
            self.chat_id,
            self.message_id,
            msg.text.format(code=code),
            reply_markup=keys
        )
        self.bot.send_answer_callback_query(self.callback_query_id,"xx")

 
    def handler(self):
        callback_data = self.callback_data
        if self.callback_handlers.get(callback_data):
            self.callback_handlers[callback_data]()
            return
        
        for key in self.callback_handlers.keys():
            if callback_data.startswith(key):
                self.callback_handlers.get(key)()

    def run(self):
        self.handler()