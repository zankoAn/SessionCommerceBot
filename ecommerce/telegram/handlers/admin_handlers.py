import asyncio
import random
import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Case, Count, F, IntegerField, Q, Sum, Value, When
from django.utils import timezone
from pyrogram import errors
from pyrogram.enums import SentCodeType

from ecommerce.bot.models import BotUpdateStatus, Message
from ecommerce.payment.models import Transaction
from ecommerce.product.models import AccountSession, Order, Product
from ecommerce.telegram.account_manager import TMAccountManager
from fixtures.app_info import fake_info_list
from utils.load_env import config as CONFIG

User = get_user_model()

cache_account_sessions = {}


class AdminTextHandler:
    def __init__(self, base_handler):
        self.base_handler = base_handler

    def __getattr__(self, name):
        attribute = getattr(self.base_handler, name, None)
        if attribute is not None:
            return attribute

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def _show_country(self, msg):
        products = Product.objects.all()
        keys = ""
        for product in products:
            keys += f"\n{product.name}:add_session_phone_code_{product.phone_code}:"
        msg.keys = keys.strip()
        return msg

    def admin_statistics(self, msg_obj):
        now = timezone.now()
        current_month_start = now.date() - timedelta(days=31)
        current_week_start = now.date() - timedelta(days=7)
        current_day_start = now.date() - timedelta(days=1)
        admins = User.objects.filter(is_staff=True)

        result_user = User.objects.aggregate(
            current_month=Count(
                Case(
                    When(date_joined__gte=current_month_start, then=Value(1)),
                    default=Value(None),
                    output_field=IntegerField(),
                ),
            ),
            current_week=Count(
                Case(
                    When(date_joined__gte=current_week_start, then=Value(1)),
                    default=Value(None),
                    output_field=IntegerField(),
                )
            ),
            current_day=Count(
                Case(
                    When(date_joined__gte=current_day_start, then=Value(1)),
                    default=Value(None),
                    output_field=IntegerField(),
                ),
            ),
            total=Count("id"),
        )
        result_pay = (
            Transaction.objects.filter(
                Q(status=Transaction.StatusChoices.PAID)
                | Q(status=Transaction.StatusChoices.PAID_OVER)
            )
            .exclude(payer__in=admins)
            .aggregate(
                current_month=Sum(
                    Case(
                        When(created__gte=current_month_start, then=F("amount_rial")),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                current_week=Sum(
                    Case(
                        When(created__gte=current_week_start, then=F("amount_rial")),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                current_day=Sum(
                    Case(
                        When(created__gte=current_day_start, then=F("amount_rial")),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                total=Sum("amount_rial"),
            )
        )
        return msg_obj.text.format(
            users=User.objects.count(),
            buy_count=Transaction.objects.filter(
                Q(status=Transaction.StatusChoices.PAID)
                | Q(status=Transaction.StatusChoices.PAID_OVER)
            ).count(),
            sell_count=Order.objects.filter(status=Order.StatusChoices.down).count(),
            disable_account=AccountSession.objects.filter(
                Q(status=AccountSession.StatusChoices.disable)
                & Q(status=AccountSession.StatusChoices.purchased)
            ).count(),
            enable_account=AccountSession.objects.filter(
                status=AccountSession.StatusChoices.active
            ).count(),
            total_users_per_day=result_user["current_day"],
            total_users_per_week=result_user["current_week"],
            total_users_per_month=result_user["current_month"],
            total_users=result_user["total"],
            total_payments_per_day=result_pay["current_day"] or 0,
            total_payments_per_week=result_pay["current_week"] or 0,
            total_payments_per_month=result_pay["current_month"] or 0,
            total_payments=result_pay["total"] or 0,
        )

    def admin_bot_status(self, msg_obj):
        status = BotUpdateStatus.objects.first().is_update
        return msg_obj.text.format(status="غیر فعال 🚫" if status else "فعال است ✅")

    def admin_add_session_file_get_country(self, msg_obj):
        cache_key = f"{self.chat_id}:add-session-country"
        cache.set(cache_key, "admin-get-session-file")
        return self._show_country(msg_obj)

    def admin_add_session_string_get_country(self, msg_obj):
        cache_key = f"{self.chat_id}:add-session-country"
        cache.set(cache_key, "admin-get-session-string")
        return self._show_country(msg_obj)

    def admin_add_session_phone_get_country(self, msg_obj):
        cache_key = f"{self.chat_id}:add-session-country"
        cache.set(cache_key, "admin-get-session-phone")
        return self._show_country(msg_obj)

    def back_to_add_session(self, msg_obj):
        # print(my_loop)  # TODO: must checked
        if my_loop:
            my_loop.close()

        return msg_obj

    def handler(self):
        messages = Message.objects.filter(
            key=self.text, current_step__startswith="admin"
        )
        if not messages:
            return

        self.user_qs.update(step=messages.last().current_step)
        # Itrate over all related step msg.
        for msg in messages:
            reply_markup = None
            text = msg.text
            if msg.keys:
                reply_markup = self.generate_keyboards(msg)

            if update_text_method := getattr(self, msg.current_step, None):
                text = update_text_method(msg)
                if isinstance(text, Message):
                    reply_markup = self.generate_keyboards(text)
                    text = text.text

            self.bot.send_message(self.chat_id, text, reply_markup=reply_markup)

    def run(self):
        self.handler()


class AdminStepHandler:
    def __init__(self, base_handler=None):
        self.base_handler = base_handler
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
            "admin-accept-signup-signin": self.accept_signup_or_signin,
        }

    def __getattr__(self, name):
        attribute = getattr(self.base_handler, name, None)
        if attribute is not None:
            return attribute

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def retrive_msg_and_keys(self, step):
        msg = Message.objects.filter(current_step=step).first()
        keys = self.generate_keyboards(msg)
        return msg, keys

    def update_cached_data(self, key, **kwargs):
        cached_data = cache.get(f"{self.chat_id}:{key}", {})
        for key_, value in kwargs.items():
            cached_data[key_] = value
        cache.set(f"{self.chat_id}:{key}", cached_data)

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
        random_info = random.choice(fake_info_list)
        session, _ = AccountSession.objects.get_or_create(
            session_string=self.text,
            product=product,
            app_version=random_info["app_version"],
            device_model=random_info["device_model"],
            system_version=random_info["system_version"],
        )
        msg, keys = self.retrive_msg_and_keys("admin-get-api-id-hash")
        self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
        self.update_cached_data(key="session", session_id=session.id)
        self.user_qs.update(step="admin-get-api-id-hash-session")

    def add_session_file(self):
        error_msg = "Bad format"
        if not self.file_id:
            return self.bot.send_message(self.chat_id, error_msg)

        content = self.bot.download_file(self.file_id)
        with open("/tmp/session_file.session", "wb") as session_file:
            session_file.write(content)

        session_string = asyncio.run(TMAccountManager().extract_session_string())
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
        self.update_cached_data(key="session", session_id=session.id)
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
        self.update_cached_data(key="session", session_id=session.id)
        self.user_qs.update(step="admin-get-api-id-hash-login")

    def _get_api_id_and_hash_base(self):
        error_msg = "❌ فرمت دیتای ارسال شده درست نیست ❌"
        msg, keys = self.retrive_msg_and_keys("admin-get-session-proxy")
        session_id = cache.get(f"{self.chat_id}:session")["session_id"]
        if "دیفالت" in self.text:
            AccountSession.objects.filter(id=session_id).update(
                api_id=CONFIG.API_ID, api_hash=CONFIG.API_HASH
            )
            return self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)

        # Validate data
        if not 1 < len(self.text.split("\n")) < 3:
            return self.bot.send_message(self.chat_id, error_msg)

        api_id, api_hash = self.text.split("\n")
        # Validate api_id
        try:
            int(api_id)
        except Exception:
            return self.bot.send_message(self.chat_id, error_msg)

        AccountSession.objects.filter(id=session_id).update(
            api_id=api_id, api_hash=api_hash
        )
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
            AccountSession.objects.filter(id=session_id).update(
                proxy=CONFIG.PROXY_SOCKS
            )
            return session_id

        if len(self.text.split(":")) not in (2, 3):
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
        status, data, err = asyncio.run(
            TMAccountManager(session_id).check_session_status()
        )
        text = msg.text.format(status=data)
        self.bot.send_message(self.chat_id, text, reply_markup=keys)
        self.user_qs.update(step=msg.current_step)

    def get_proxy_login(self):
        global my_loop
        session_id = self._get_proxy_base()
        wait_msg = self.bot.send_message(self.chat_id, "⏳")
        # Create new event loop
        my_loop = asyncio.new_event_loop()
        status, account, result = my_loop.run_until_complete(
            TMAccountManager(session_id).send_login_code()
        )
        if not status:
            self.bot.delete_message(self.chat_id, wait_msg["result"]["message_id"])
            msg = Message.objects.filter(current_step="invalid-phone-error").first()
            return self.bot.send_message(self.chat_id, msg.text)

        # Cache the client object
        cache_account_sessions[self.chat_id] = account
        self.update_cached_data(
            key="session",
            phone_code_hash=result.phone_code_hash,
            login_code_type=result.type,
        )
        msg, keys = self.retrive_msg_and_keys("admin-get-login-code")
        self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
        self.user_qs.update(step=msg.current_step)

    def get_login_code(self):
        login_code = self.text.strip()
        msg_obj, keys = self.retrive_msg_and_keys("admin-accept-signup-signin")
        self.bot.send_message(self.chat_id, msg_obj.text, reply_markup=keys)
        self.update_cached_data(key="session", login_code=login_code)
        self.user_qs.update(step=msg_obj.current_step)

    def get_login_password(self):
        account = cache_account_sessions[self.chat_id]
        data = cache.get(f"{self.chat_id}:session")
        session_id = data["session_id"]
        password = self.text
        status, msg, action = my_loop.run_until_complete(
            TMAccountManager(session_id).confirm_password(account, password)
        )
        if status:
            my_loop.close()
            msg, keys = self.retrive_msg_and_keys("admin-add-session-success")
            self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
            cache_account_sessions.pop(self.chat_id)
            return

        if action == errors.PasswordHashInvalid:
            msg_obj, keys = self.retrive_msg_and_keys("admin-get-login-password")
            self.bot.send_message(self.chat_id, msg_obj.text.format(hint=msg))
            return

        self.bot.send_message(self.chat_id, msg)

    def accept_signup_or_signin(self):
        account = cache_account_sessions[self.chat_id]
        data = cache.get(f"{self.chat_id}:session")
        phone_code_hash = data["phone_code_hash"]
        login_code_type = data["login_code_type"]
        login_code = data["login_code"]
        session_id = data["session_id"]

        if login_code_type == SentCodeType.SMS:
            status, msg, action = my_loop.run_until_complete(
                TMAccountManager(session_id).sign_up_account(account, phone_code_hash)
            )
        else:
            status, msg, action = my_loop.run_until_complete(
                TMAccountManager(session_id).sign_in_account(
                    account, phone_code_hash, login_code
                )
            )
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

    def respond_to_ticket(self):
        user_id = self.reply_to_msg["text"].split("\n")[0].split(":")[1].strip()
        self.bot.copy_message(user_id, self.chat_id, self.message_id)
        msg = Message.objects.get(current_step="admin-respond-success-ticket")
        self.bot.send_message(self.chat_id, msg.text)


    def handler(self):
        if callback := self.steps.get(self.user_obj.step):
            callback()

    def run(self):
        self.handler()


class AdminCallbackHandler:
    def __init__(self, base_handler=None) -> None:
        self.base_handler = base_handler
        self.callback_handlers = {
            "block_user": self.block_user_ticket,
            "unblock_user": self.unblock_user_ticket,
            "enable_bot": self.change_bot_status,
            "update_bot": self.change_bot_status,
        }

    def __getattr__(self, name):
        attribute = getattr(self.base_handler, name, None)
        if attribute is not None:
            return attribute

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def _get_ticket_user_id(self):
        pattern = "user.+(\d+)\n"
        user_id = re.findall(pattern, self.text.lower())
        return user_id[0]

    def block_user_ticket(self):
        user = self._get_ticket_user_id()
        msg = f"کاربر {user} بلاک شد ❌"
        self.bot.send_answer_callback_query(self.callback_query_id, msg)
        self.user_qs.update(is_active=False)

    def unblock_user_ticket(self):
        user = self._get_ticket_user_id()
        msg = f"کاربر {user} آزاد شد ✅"
        self.bot.send_answer_callback_query(self.callback_query_id, msg)
        self.user_qs.update(is_active=True)

    def change_bot_status(self):
        if self.callback_data == "enable_bot":
            BotUpdateStatus.objects.filter(id=1).update(is_update=False)
            text = "فعال است ✅"
        else:
            BotUpdateStatus.objects.filter(id=1).update(is_update=True)
            text = "غیر فعال 🚫"

        self.bot.send_answer_callback_query(self.callback_query_id, text)

    def run(self):
        callback_data = self.callback_data
        if callback_data in self.callback_handlers:
            self.callback_handlers[callback_data]()
            return
