import asyncio
import io
import os
import re
import shutil
import zipfile
from datetime import timedelta

import rarfile
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.utils import timezone
from pyrogram import errors
from pyrogram.enums import SentCodeType

from ecommerce.bot.models import BotUpdateStatus, Message
from ecommerce.payment.services import TransactionService
from ecommerce.product.models import AccountSession, Product
from ecommerce.product.services import AccountSessionService, OrderService
from ecommerce.telegram.account_manager import (
    SignInSignUpSessionManager,
    TdataSessionManager,
    TMAccountManager,
)
from ecommerce.telegram.validators import Validators
from ecommerce.bot.services import MessageService

User = get_user_model()

cached_accounts = {}


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
            keys += f"\n{product.name}:add-session-country-{product.country_code}-{product.phone_code}:"
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
        result_pay = TransactionService().get_transactions_statistics(
            admins, current_day_start, current_week_start, current_month_start
        )
        return msg_obj.text.format(
            users=User.objects.count(),
            sell_count=OrderService().get_success_order_count(),
            disable_account=AccountSessionService().get_deactive_session_count(),
            enable_account=AccountSessionService().get_active_session_count(),
            total_users_per_day=result_user["current_day"],
            total_users_per_week=result_user["current_week"],
            total_users_per_month=result_user["current_month"],
            total_users=result_user["total"],
            total_pays=result_pay["total_pays"],
            total_payments_per_day=result_pay["current_day"] or 0,
            total_payments_per_week=result_pay["current_week"] or 0,
            total_payments_per_month=result_pay["current_month"] or 0,
            total_payments=result_pay["total"] or 0,
        )

    def admin_bot_status(self, msg_obj):
        status = BotUpdateStatus.objects.first().is_update
        return msg_obj.text.format(status="غیر فعال 🚫" if status else "فعال است ✅")

    def admin_add_session_file_get_country(self, msg_obj):
        cache_key = f"{self.chat_id}:add:session:type"
        cache.set(cache_key, "file")
        return self._show_country(msg_obj)

    def admin_add_session_string_get_country(self, msg_obj):
        cache_key = f"{self.chat_id}:add:session:type"
        cache.set(cache_key, "string")
        return self._show_country(msg_obj)

    def admin_add_session_phone_get_country(self, msg_obj):
        cache_key = f"{self.chat_id}:add:session:type"
        cache.set(cache_key, "phone")
        return self._show_country(msg_obj)

    def event_loop_cleanup(self, loop_name):
        if f"{loop_name}" not in globals():
            return

        for task in asyncio.all_tasks(session_loop):
            task.cancel()

        session_loop.close()

    def admin_back_to_add_session(self, msg_obj):
        self.event_loop_cleanup("session_loop")
        return msg_obj

    def handler(self):
        messages = MessageService(self.user_obj).filter_admin_msgs(key=self.text)
        if not messages:
            return

        self.user_qs.update(step=messages[-1].current_step)
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
    validators = Validators()

    def __init__(self, base_handler=None):
        self.base_handler = base_handler
        self.steps = {
            "admin-get-user-info": self.user_info,
            "admin-get-session-string": self.add_session_string,
            "admin-get-session-file": self.add_session_file,
            "admin-get-session-phone": self.add_session_phone,
            "admin-get-api-id-hash": self.get_api_id_and_hash,
            "admin-get-proxy": self.get_proxy,
            "admin-get-login-code-app": self.get_login_code_app_signin,
            "admin-get-login-code-sms": self.get_login_code_sms_signup,
            "admin-get-login-password": self.get_login_password,
        }

    def __getattr__(self, name):
        attribute = getattr(self.base_handler, name, None)
        if attribute is not None:
            return attribute

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def retrive_msg_and_keys(self, step):
        msg = MessageService(self.user_obj).get(step)
        keys = self.generate_keyboards(msg)
        return msg, keys

    def update_cached_data(self, key, **kwargs):
        cached_data = cache.get(f"{self.chat_id}:{key}", {})
        for key_, value in kwargs.items():
            cached_data[key_] = value
        cache.set(f"{self.chat_id}:{key}", cached_data)

    def user_info(self):
        user = self.text
        user = User.objects.filter(Q(username=user) | Q(user_id=user)).first()
        if user:
            msg = MessageService(self.user_obj).get(step="admin-user-info")
            text_msg = msg.text.format(
                user_id=user.user_id,
                name=user.first_name,
                last_name=user.last_name,
                username=user.username,
                balance=user.balance,
                total_session=0,
                total_pay=user.calculate_total_paid,
                created=user.date_joined.strftime("%Y-%m-%d %H:%M:%S"),
                total_orders_cnt=OrderService().get_total_cnt_user_order(user.id),
            )
        else:
            text_msg = "❌ User not found"
        self.bot.send_message(self.chat_id, text_msg)

    @validators.validate_session_string_format
    def add_session_string(self):
        key = f"{self.chat_id}:add:session:country:code"
        country_code = cache.get(key)
        product = Product.objects.get(country_code=country_code)
        session = AccountSessionService().create_session(
            phone="", product=product, session_string=self.text
        )
        status, phone_number = asyncio.run(
            TMAccountManager(session.id).check_session_status()
        )
        if not status:
            msg = MessageService(self.user_obj).get(step="general-format-error").text
            return self.bot.send_message(self.chat_id, msg)

        AccountSessionService().update_session(session.id, phone=phone_number)
        msg, keys = self.retrive_msg_and_keys("admin-get-api-id-hash")
        self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
        self.update_cached_data("add:session", session_id=session.id, type="add-string")
        self.user_qs.update(step="admin-get-api-id-hash")

    def download_archive_session_file(self, content):
        bytes_io = io.BytesIO(content)
        session_string = None

        if "rar" in self.file_mime_type:
            archive_type = rarfile.RarFile
        else:
            archive_type = zipfile.ZipFile

        with archive_type(bytes_io, "r") as rf:
            files = rf.namelist()
            if not any(map(lambda file: "tdata" in file, files)):
                return False, False

            extract_output_path = "ecommerce/bot/sessions/"
            rf.extractall(path=extract_output_path)
            try:
                session_name = files[-1].strip("/")
                tdata_path = files[-2]
                table_status, session_string, phone = asyncio.run(
                    TdataSessionManager().run(tdata_path, session_name)
                )
                self.bot.send_message(self.chat_id, table_status)
            except Exception as error:
                print(error)
                shutil.rmtree(f"{extract_output_path}/{session_name}")
                return False, False
            finally:
                shutil.rmtree(f"{extract_output_path}/{session_name}")

        return session_string, phone

    def download_normal_session_file(self, content):
        download_path = f"ecommerce/bot/sessions/{self.file_name}"
        with open(download_path, "wb") as of:
            of.write(content)

        session_string, phone = asyncio.run(
            TMAccountManager().extract_session_string(download_path)
        )
        if not session_string:
            os.rmdir(download_path)

        return session_string, phone

    @validators.validate_file_format
    def add_session_file(self):
        content = self.bot.download_file(self.file_id)
        if "rar" in self.file_mime_type or "zip" in self.file_mime_type:
            session_string, phone = self.download_archive_session_file(content)
        else:
            session_string, phone = self.download_normal_session_file(content)

        if not session_string:
            msg = MessageService(self.user_obj).get(step="general-format-error").text
            return self.bot.send_message(self.chat_id, msg)

        key = f"{self.chat_id}:add:session:country:code"
        country_code = cache.get(key)
        product = Product.objects.get(country_code=country_code)
        # TODO: Use session metatdata insted random
        session = AccountSessionService().create_session(
            phone=phone,
            product=product,
            session_string=session_string,
            status=AccountSession.StatusChoices.active,
        )
        msg, keys = self.retrive_msg_and_keys("admin-get-api-id-hash")
        self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
        self.update_cached_data("add:session", session_id=session.id, type="add-file")
        self.user_qs.update(step="admin-get-api-id-hash")

    @validators.validate_phone_number
    @validators.validate_phone_country_code
    def add_session_phone(self, product=None):
        phone = self.text.strip()
        session = AccountSessionService().create_session(phone, product)
        msg, keys = self.retrive_msg_and_keys("admin-get-api-id-hash")
        self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
        self.update_cached_data("add:session", session_id=session.id, type="add-phone")
        self.user_qs.update(step="admin-get-api-id-hash")

    @validators.validate_api_id_and_api_hash
    def get_api_id_and_hash(self):
        session_id = cache.get(f"{self.chat_id}:add:session")["session_id"]
        if "دیفالت" not in self.text:
            api_id, api_hash = self.text.split("\n")
            AccountSessionService().update_session(
                session_id, api_id=api_id, api_hash=api_hash
            )
        msg, keys = self.retrive_msg_and_keys("admin-get-proxy")
        self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
        self.user_qs.update(step="admin-get-proxy")

    def _handel_send_login_code(self, session_type, session_id):
        global session_loop
        if session_type == "add-phone":
            wait_msg = self.bot.send_message(self.chat_id, "⏳")
            # Create new event loop
            session_loop = asyncio.new_event_loop()
            status, account, result = session_loop.run_until_complete(
                SignInSignUpSessionManager(session_id).send_login_code()
            )
            if not status:
                self.bot.delete_message(self.chat_id, wait_msg["result"]["message_id"])
                msg = MessageService(self.user_obj).get(step="invalid-phone-error")
                return self.bot.send_message(self.chat_id, msg.text)

            # Cache the client object
            cached_accounts[self.chat_id] = account
            self.update_cached_data(
                key="add:session", phone_code_hash=result.phone_code_hash
            )
            if result.type == SentCodeType.SMS:
                msg, keys = self.retrive_msg_and_keys("admin-get-login-code-sms")
            else:
                msg, keys = self.retrive_msg_and_keys("admin-get-login-code-app")
            self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
            self.user_qs.update(step=msg.current_step)
        else:
            msg, keys = self.retrive_msg_and_keys("admin-add-session-success")
            self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)

        self.user_qs.update(step=msg.current_step)

    @validators.validate_input_proxy
    def get_proxy(self):
        session_data = cache.get(f"{self.chat_id}:add:session")
        session_id = session_data["session_id"]
        session_type = session_data["type"]
        if "دیفالت" not in self.text:
            AccountSessionService().update_session(session_id, proxy=self.text)
        self._handel_send_login_code(session_type, session_id)

    @validators.validate_login_code
    @validators.validate_cached_account_exists(cached_accounts)
    def get_login_code_sms_signup(self):
        account = cached_accounts[self.chat_id]
        data = cache.get(f"{self.chat_id}:add:session")
        phone_code_hash = data["phone_code_hash"]
        session_id = data["session_id"]
        status, msg, _ = session_loop.run_until_complete(
            SignInSignUpSessionManager(session_id).sign_up_account(
                account, phone_code_hash
            )
        )
        if status:
            msg, keys = self.retrive_msg_and_keys("admin-add-session-success")
            self.user_qs.update(step="admin-add-session")
            self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
            return

        self.bot.send_message(self.chat_id, msg)

    @validators.validate_login_code
    @validators.validate_cached_account_exists(cached_accounts)
    def get_login_code_app_signin(self):
        account = cached_accounts[self.chat_id]
        data = cache.get(f"{self.chat_id}:add:session")
        phone_code_hash = data["phone_code_hash"]
        login_code = self.text
        session_id = data["session_id"]
        status, msg, action = session_loop.run_until_complete(
            SignInSignUpSessionManager(session_id).sign_in_account(
                account, phone_code_hash, login_code
            )
        )
        if status:
            msg, keys = self.retrive_msg_and_keys("admin-add-session-success")
            self.user_qs.update(step="admin-add-session")
            self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
            session_loop.close()
            return

        if action == errors.SessionPasswordNeeded:
            msg_obj, keys = self.retrive_msg_and_keys("admin-get-login-password")
            self.user_qs.update(step=msg_obj.current_step)
            self.bot.send_message(self.chat_id, msg_obj.text.format(hint=msg))
            return

        self.bot.send_message(self.chat_id, msg)

    @validators.validate_cached_account_exists(cached_accounts)
    def get_login_password(self):
        account = cached_accounts[self.chat_id]
        data = cache.get(f"{self.chat_id}:add:session")
        session_id = data["session_id"]
        password = self.text
        status, msg, action = session_loop.run_until_complete(
            SignInSignUpSessionManager(session_id).confirm_password(account, password)
        )
        if status:
            session_loop.close()
            msg, keys = self.retrive_msg_and_keys("admin-add-session-success")
            self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
            cached_accounts.pop(self.chat_id)
            return

        if action == errors.PasswordHashInvalid:
            msg_obj, keys = self.retrive_msg_and_keys("admin-get-login-password")
            self.bot.send_message(self.chat_id, msg_obj.text.format(hint=msg))
            return

        self.bot.send_message(self.chat_id, msg)

    def respond_to_ticket(self):
        user_id = self.reply_to_msg["text"].split("\n")[0].split(":")[1].strip()
        self.bot.copy_message(user_id, self.chat_id, self.message_id)
        msg = MessageService(self.user_obj).get(step="admin-respond-success-ticket")
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
            "add-session-country-": self.admin_choice_country,
        }

    def __getattr__(self, name):
        attribute = getattr(self.base_handler, name, None)
        if attribute is not None:
            return attribute

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def admin_choice_country(self):
        add_session_type = cache.get(f"{self.chat_id}:add:session:type")
        country_code, phone_code = self.callback_data.split("-")[3:]

        self.bot.delete_message(self.chat_id, self.message_id)

        msg = MessageService(self.user_obj).get(
            step=f"admin-get-session-{add_session_type}"
        )
        text = msg.text.format(country_phone_code=phone_code)
        keys = self.generate_keyboards(msg)
        self.bot.send_message(self.chat_id, text, reply_markup=keys)

        key = f"{self.chat_id}:add:session:country:code"
        cache.set(key, country_code)
        self.user_qs.update(step=msg.current_step)

    def _get_ticket_user_id(self):
        pattern = r"user.+(\d+)\n"
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

        for key in self.callback_handlers.keys():
            if callback_data.startswith(key):
                self.callback_handlers.get(key)()
