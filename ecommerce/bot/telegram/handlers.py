from ecommerce.bot.models import Message
from ecommerce.payment.models import Payment
from ecommerce.bot.telegram.telegram import Telegram
from ecommerce.product.models import Order, Product, AccountSession
# from django.db import transaction

from datetime import timedelta
from pyrogram import Client, errors
#from pyrogram.types import Message

 

from django.utils import timezone
from django.db.models import Q, F, Sum
from django.db.models import Count, Case, When, Value, IntegerField
from django.contrib.auth import get_user_model
from django.core.cache import cache
import json
import asyncio
import re
import random

from utils.load_env import config as CONFIG
from fixtures.app_info import fake_info_list
from fixtures.names import fake_names



User = get_user_model()
my_loop = None
cache_account_sessions = {}


class TMAccountHandler:

    def __init__(self, session_id = 0) -> None:
        self.session_id = session_id

    async def get_proxy(self, data):
        proxy = {"scheme": "socks5"}
        if len(data) > 3:
            host, port, username, passwd = data
            proxy.update({
                "hostname": host,
                "port": int(port),
                "username": username,
                "password": passwd
            })
        else:
            host, port = data
            proxy.update({
                "hostname": host,
                "port": int(port),
            })
        return proxy

    async def check_session_status(self):
        session_obj = await AccountSession.objects.aget(id=self.session_id)
        _proxy = session_obj.proxy.split(":")
        proxy = await self.get_proxy(_proxy)
        account = Client(
            name="",
            api_id=session_obj.api_id,
            api_hash=session_obj.api_hash,
            proxy=proxy,
            session_string=session_obj.session_string,
            in_memory=True,
            no_updates=True
        )
        try:
            if await account.connect():
                await account.get_me()
                session_obj.status = AccountSession.StatusChoices.active
                await session_obj.asave()
                await account.disconnect()
                return True, session_obj.status.value, True
        except Exception as err:
            print(err)

        session_obj.status = AccountSession.StatusChoices.disable
        await session_obj.asave()
        return False, session_obj.status.value, None

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
        proxy = await self.get_proxy(_proxy)
        account = Client(
            name="",
            phone_number=session_obj.phone,
            api_id=session_obj.api_id,
            api_hash=session_obj.api_hash,
            app_version=session_obj.app_version,
            device_model=session_obj.device_model,
            system_version=session_obj.system_version,
            proxy=proxy,
            in_memory=True,
            no_updates=True,
        )
        try:
            await account.connect()
            result = await account.send_code(session_obj.phone)
            return True, account, result

        except errors.PhoneNumberInvalid:
            return False, "Phone number invalid", errors.PhoneNumberInvalid

        except Exception as error:
            return False, "Unexpected error, check server log", False

    async def sign_in_account(self, account: Client, phone_code_hash, login_code):
        session_obj = await AccountSession.objects.aget(id=self.session_id)
        try:
            user = await account.sign_in(
                phone_number=session_obj.phone,
                phone_code_hash=phone_code_hash,
                phone_code=login_code
            )
            if user.id:
                session_string = await account.export_session_string()
                session_obj.session_string = session_string
                session_obj.status = AccountSession.StatusChoices.active
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
            session_obj.status = AccountSession.StatusChoices.active
            await session_obj.asave()
            return True, None, None
        except errors.PasswordHashInvalid:
            error = "❌ Invalid Password"
            hint = await account.get_password_hint()
            return False, hint + error, errors.PasswordHashInvalid

        except Exception as err:
            print(err)
            return False, "Unexpected error, check server log", False

    async def retrive_login_code(self, phone):
        session_obj = await AccountSession.objects.aget(phone=phone)
        _proxy = session_obj.proxy.split(":")
        proxy = await self.get_proxy(_proxy)
        account = Client(
            name="",
            api_id=session_obj.api_id,
            api_hash=session_obj.api_hash,
            proxy=proxy,
            session_string=session_obj.session_string
        )
        try:
            await account.connect()
            async for msg in account.get_chat_history(777000, limit=1):
                await account.disconnect()
                pattern = "(\d{1,5})"
                code = re.findall(pattern, msg.text.lower())
                if code:
                    return True, code[0], None
                return False, None, None
        except Exception as error:
            print("[Error] Retrive login code: ",error)

        return False, False, False



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

    def user_profile(self, msg):
        return msg.text.format(
            user_id=self.chat_id,
            total_order=self.user_obj.orders.count(),
            total_pay=self.user_obj.calculate_total_paid,
            balance=self.user_obj.balance
        ), None

    def admin_get_bot_info(self, msg):
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
        return msg.text.format(
            total_users_per_week=result_user["current_week"],
            total_users_per_month=result_user["current_month"],
            total_users=result_user["total"],
            total_payments_per_week=result_pay["current_week"],
            total_payments_per_month=result_pay["current_month"],
            total_payments=result_pay["total"],
        ), None

    def admin_statistics(self, msg):
        return msg.text.format(
            users=User.objects.count(),
            buy_count=Payment.objects.filter(is_paid=True).count(),
            sell_count=Order.objects.filter(status=Order.StatusChoices.down).count(),
            disable_account=AccountSession.objects.filter(
                Q(status=AccountSession.StatusChoices.disable) & 
                Q(status=AccountSession.StatusChoices.purchased)
            ).count(),
            enable_account=AccountSession.objects.filter(
                status=AccountSession.StatusChoices.active
            ).count()
        ), None

    def buy_phone_number(self, msg):
        product = Product.objects.order_by("price").first()
        if not self.user_obj.is_staff and self.user_obj.balance < product.price and cache.get(f"limit-buy:{self.chat_id}"):
            msg = Message.objects.get(current_step="limit-buy-session-error").text
            return msg, None

        products = Product.objects.filter(accounts__status=AccountSession.StatusChoices.active)
        if not products:
            msg = Message.objects.get(current_step="no-phone-error").text
            return msg, None

        keys = ""
        for product in products:
            keys += f"\n{product.price:,} | {product.name}:country_{product.country_code}:"
        msg.keys = keys.strip()
        key = self.generate_keyboards(msg)
        return msg.text, key

    def _show_country(self, msg):
        products = Product.objects.all()
        keys = ""
        for product in products:
            keys += f"\n{product.name}:add_session_phone_code_{product.phone_code}:"
        msg.keys = keys.strip()
        key = self.generate_keyboards(msg)
        return msg.text, key

    def get_amount(self, msg):
        msg = Message.objects.get(current_step="no-payment")
        return msg.text, None

    def admin_add_session_file_get_country(self, msg):
        cache.set(f"{self.chat_id}:add-session-country", "admin-get-session-file")
        return self._show_country(msg)

    def admin_add_session_string_get_country(self, msg):
        cache.set(f"{self.chat_id}:add-session-country", "admin-get-session-string")
        return self._show_country(msg)

    def admin_add_session_phone_get_country(self, msg):
        cache.set(f"{self.chat_id}:add-session-country", "admin-get-session-phone")
        return self._show_country(msg)

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
            "admin-get-session-string": self.add_session_string,
            "admin-get-session-file": self.add_session_file,
            "admin-get-session-phone": self.add_session_phone,
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

        phone_code = cache.get(f"{self.chat_id}:add-session-phone-code")
        product = Product.objects.get(phone_code=phone_code)
        session,_ = AccountSession.objects.get_or_create(session_string=self.text, product=product)
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

        session_string = asyncio.run(TMAccountHandler().extract_session_string())
        if not session_string:
            return self.bot.send_message(self.chat_id, error_msg)

        phone_code = cache.get(f"{self.chat_id}:add-session-phone-code")
        product = Product.objects.get(phone_code=phone_code)
        random_info = random.choice(fake_info_list)
        session, _ = AccountSession.objects.get_or_create(
            session_string=session_string,
            product=product,
            app_version=random_info["app_version"],
            device_model=random_info["device_model"],
            system_version=random_info["system_version"],
        )
        msg, keys = self.retrive_msg_and_keys("admin-get-api-id-hash")
        self.update_cached_data(session_id=session.id)
        self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
        self.user_qs.update(step="admin-get-api-id-hash-session")

    def add_session_phone(self):
        error_msg = "❌ فرمت دیتای ارسال شده درست نیست ❌"
        user_phone = self.text.replace(" ", "")
        if not 10 < len(user_phone) < 15:
            return self.bot.send_message(self.chat_id, error_msg)

        phone_code = cache.get(f"{self.chat_id}:add-session-phone-code")
        product = Product.objects.get(phone_code=phone_code)
        if user_phone[:1] != phone_code[:1]:
            return self.bot.send_message(self.chat_id, error_msg)

        random_info = random.choice(fake_info_list)
        session, _ = AccountSession.objects.get_or_create(
            phone=user_phone,
            product=product,
            app_version=random_info["app_version"],
            device_model=random_info["device_model"],
            system_version=random_info["system_version"],
        )
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
        status, data, err = asyncio.run(TMAccountHandler(session_id).check_session_status())
        text = msg.text.format(status=data)
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
        login_code = self.text.strip()
        status, msg, action = my_loop.run_until_complete(
            TMAccountHandler(session_id).sign_in_account(account, phone_code_hash, login_code)
        )
        print(status, msg, action)
        if status:
            msg, keys = self.retrive_msg_and_keys("admin-add-session-success")
            self.user_qs.update(step="admin-add-session")
            self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
            return

        if action == errors.SessionPasswordNeeded:
            msg_obj, keys = self.retrive_msg_and_keys("admin-get-login-password")
            self.user_qs.update(step=msg_obj.current_step)
            self.bot.send_message(self.chat_id, msg_obj.text.format(hint=msg))
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
            return

        if action == errors.PasswordHashInvalid:
            msg_obj, keys = self.retrive_msg_and_keys("admin-get-login-password")
            self.bot.send_message(self.chat_id, msg_obj.text.format(hint=msg))
            return

        self.bot.send_message(self.chat_id, msg)

    def respond_to_ticket(self):
        user_id = self.reply_to_msg["text"].split("\n")[0].split(":")[1].strip()
        self.bot.copy_message(user_id, self.chat_id, self.message_id)
        msg = Message.objects.get(current_step="success-ticket")
        self.bot.send_message(self.chat_id, msg.text)

    def handler(self):
        if callback := self.steps.get(self.user_obj.step):
            callback()

    def run(self):
        self.handler()


class UserStepHandler(BaseHandler):

    def __init__(self, base):
        self.steps = {
            "get-amount": self.make_payment,
            "support-ticket-msg": self.ticket_msg
            
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

    def ticket_msg(self):
        admin = User.objects.filter(is_staff=True).last()
        msg = Message.objects.get(current_step="success-ticket")
        self.bot.forward_message(admin, self.chat_id, self.message_id)
        self.bot.send_message(self.chat_id, msg.text)
        # Send ticket info to admin(block/unblock)
        msg = Message.objects.get(current_step="admin-ticket-info")
        self.bot.send_message(
            admin,
            msg.text.format(
                user_id=self.chat_id,
                name=self.user_obj.first_name,
                username=self.user_obj.username
            )
        )

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
            "show_countrys": self.back_to_show_countrys,
            "login_code": self.get_login_code,
            "add_session_phone_code_": self.admin_choice_country,
        }
        for key, value in vars(base).items():
            setattr(self, key, value)

    def update_cached_data(self, **kwargs):
        cached_data = cache.get(f"{self.chat_id}:order", {})
        for key, value in kwargs.items():
            cached_data[key] = value

        cache.set(f"{self.chat_id}:order", cached_data, timeout=None)

    def get_cached_data(self, sub_key):
        cached_data = cache.get(f"{self.chat_id}:order", {}).get(sub_key, 0)
        return cached_data

    def admin_choice_country(self):
        step = cache.get(f"{self.chat_id}:add-session-country")
        msg = Message.objects.get(current_step=step)
        self.bot.delete_message(self.chat_id, self.message_id)
        keys = self.generate_keyboards(msg)
        self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
        phone_code = self.callback_data.replace("add_session_phone_code_", "")
        cache.set(f"{self.chat_id}:add-session-phone-code", phone_code)
        self.user_qs.update(step=msg.current_step)

    def back_to_show_countrys(self):
        msg = Message.objects.get(current_step="buy_phone_number")
        text, keys = TextHandler(self).buy_phone_number(msg)
        self.bot.edit_message_text(self.chat_id, self.message_id, text, reply_markup=keys)

    def get_phone_number(self):
        _, cr_code = self.callback_data.split("_")
        product = Product.objects.get(country_code=cr_code)

        session = self.get_active_account_session(product)
        if not session:
            return self.send_no_phone_error()

        # Check session to see is connect
        status, _, _ = asyncio.run(TMAccountHandler(session_id=session.id).check_session_status())
        if not status:
            return self.back_to_show_countrys()

        self.update_cached_data_and_set_rate_limit(session)

        session.status = AccountSession.StatusChoices.purchased
        session.save()

        self.create_order_and_decrease_inventory(session, product)

        msg = Message.objects.filter(current_step="show-phone-number").first()
        keys = self.generate_keyboards(msg)
        self.bot.edit_message_text(
            self.chat_id,
            self.message_id,
            msg.text.format(phone=session.phone),
            reply_markup=keys
        )

    def get_active_account_session(self, product):
        return AccountSession.objects.filter(
            product=product,
            status=AccountSession.StatusChoices.active
        ).order_by("?").first()

    def send_no_phone_error(self):
        msg = Message.objects.get(current_step="no-phone-error").text
        return self.bot.send_message(self.chat_id, msg)

    def update_cached_data_and_set_rate_limit(self, session):
        self.update_cached_data(phone=session.phone)
        cache.set(f"limit-buy:{self.chat_id}", "true", timeout=345600)

    def create_order_and_decrease_inventory(self, session, product):
        Order.objects.create(user=self.user_obj, session=session, price=product.price)
        if self.user_obj.balance > product.price:
            self.user_obj.balance -= product.price
            self.user_obj.save()

    def get_login_code(self):
        phone = self.get_cached_data("phone")
        msg = Message.objects.get(current_step="show-login-code")
        login_code_counter_key = f"{self.chat_id}:order:get:login:code:{phone}"

        if not cache.get(login_code_counter_key):
            cache.set(login_code_counter_key, 1)

        if int(cache.get(login_code_counter_key)) > 3:
            password = data = "Reach limit"
            msg = Message.objects.get(current_step="limit-login-code-error").text
            return self.bot.send_message(self.chat_id, msg)
        else:
            session = AccountSession.objects.get(phone=phone)
            password = session.password
            status, data, err = asyncio.run(TMAccountHandler().retrive_login_code(phone))
            if status:
                Order.objects.filter(session=session.id).update(login_code=data)
            else:
                return self.bot.send_answer_callback_query(self.callback_query_id, "❌ کد یافت نشد ❌")

        keys = self.generate_keyboards(msg)
        self.bot.send_message(
            self.chat_id,
            msg.text.format(code=str(data), password=password),
            reply_markup=keys
        )
        self.bot.send_answer_callback_query(self.callback_query_id,"✅")
        cache.incr(login_code_counter_key)

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
