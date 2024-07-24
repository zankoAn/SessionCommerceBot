import asyncio

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils.translation import gettext, override

from ecommerce.bot.models import Message
from ecommerce.bot.services import MessageService
from ecommerce.payment.services import PerfectMoneyPaymentService
from ecommerce.payment.views import (
    CryptomusCreateTransaction,
    ZarinpalCreateTransaction,
)
from ecommerce.product.services import (
    AccountSessionService,
    OrderService,
    ProductService,
)
from ecommerce.telegram.account_manager import TMAccountManager
from ecommerce.telegram.validators import Validators
from utils.load_env import config as CONFIG

User = get_user_model()


class UserTextHandler:
    """Handel the normal user keyboard text,
    When normal user press the any KeyboardMarkup, handeld in this class,
    methods-name are definded base on the keyboard-name in Message model.
    """

    validators = Validators()

    def __init__(self, base_handler):
        self.base_handler = base_handler

    def __getattr__(self, name):
        attribute = getattr(self.base_handler, name, None)
        if attribute is not None:
            return attribute

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def user_profile(self, msg_obj):
        text = msg_obj.text.strip()
        return text.format(
            user_id=self.chat_id,
            total_order=self.user_obj.orders.count(),
            total_pay=self.user_obj.calculate_total_paid,
            balance=self.user_obj.balance,
        )

    @validators.validate_user_balance
    @validators.validate_exists_product
    def buy_phone_number(self, msg_obj):
        products = ProductService().get_active_countries()
        keys = ""
        for product in products:
            with override(self.user_obj.language):
                product_name = gettext(product.name)
            keys += (
                f"\n{product.price:,} | {product_name}:country-{product.country_code}:"
            )
        msg_obj.keys = keys.strip()
        return msg_obj

    def select_payment_method(self, ـ):
        msg = MessageService(self.user_obj).get(step="select_payment_method")
        self.user_qs.update(step="select_amount")
        return msg.text

    def handler(self):
        if "/start" in self.text:
            self.text = "/start"

        messages = MessageService(self.user_obj).filter_user_msgs(key=self.text)
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


class UserInputHandler:
    """Get the user input base on the step"""

    validators = Validators()

    def __init__(self, base_handler=None):
        self.base_handler = base_handler
        self.steps = {
            "perfectmoney-get-evoucher": self.perfectmoney_get_evoucher,
            "perfectmoney-get-activation-code": self.perfectmoney_get_activation_code,
            "crypto-get-amount": self.cryptomus_get_amount,
            "rial-get-amount": self.zarinpal_get_rial_amount,
        }

    def __getattr__(self, name):
        attribute = getattr(self.base_handler, name, None)
        if attribute is not None:
            return attribute

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def add_dynamic_admin_user_ticket_step(self):
        admin_user_ids = User.objects.filter(is_staff=True).values_list(
            "user_id", flat=True
        )
        admin_user_steps = {
            f"ticket-admin-{user_id}": self.ticket_msg for user_id in admin_user_ids
        }
        self.steps.update(admin_user_steps)

    def convert_ir_num_to_en(self, number):
        trans_table = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
        english_string = number.translate(trans_table)
        return english_string

    def ticket_msg(self):
        # Get admin-id from step
        user_id = int(self.user_obj.step.split("-")[-1])
        admin_user = User.objects.get(is_staff=True, user_id=user_id)
        # Get and forward success msg
        msg = MessageService(self.user_obj).get(step="send-success-ticket-msg")
        resp = self.bot.forward_message(
            admin_user.user_id, self.chat_id, self.message_id
        )
        self.bot.send_message(self.chat_id, msg.text)
        # Send ticket info to admin(block/unblock)
        msg = MessageService(self.user_obj).get(step="admin-ticket-info")
        keys = self.generate_keyboards(msg)
        self.bot.send_message(
            admin_user,
            msg.text.format(
                user_id=self.chat_id,
                name=self.user_obj.first_name,
                username=self.user_obj.username,
            ),
            reply_to_message_id=resp["result"]["message_id"],
            reply_markup=keys,
        )

    @validators.validate_evoucher_length
    def perfectmoney_get_evoucher(self):
        evoucher = self.convert_ir_num_to_en(self.text)
        payment = PerfectMoneyPaymentService().create_payment(
            self.user_obj, evoucher=evoucher
        )
        key = f"{self.chat_id}:perfectmoney:payment:id"
        cache.set(key, payment.id)  # TODO: Add timout.
        msg = MessageService(self.user_obj).get(step="perfectmoney-get-evcode").text
        self.user_qs.update(step="perfectmoney-get-activation-code")
        self.bot.send_message(self.chat_id, msg)

    @validators.validate_activation_code_length
    def perfectmoney_get_activation_code(self):
        key = f"{self.chat_id}:perfectmoney:payment:id"
        payment_id = cache.get(key)
        activation_code = self.convert_ir_num_to_en(self.text)
        PerfectMoneyPaymentService().update_payment(
            payment_id, activation_code=activation_code
        )
        msg = MessageService(self.user_obj).get(step="perfectmoney-success-recive-data")
        reply_markup = self.generate_keyboards(msg)
        self.user_qs.update(step="home_page")
        self.bot.send_message(self.chat_id, msg.text, reply_markup=reply_markup)

    @validators.validate_min_max_pay_amount(CONFIG.MIN_DOLLAR_PAY_LIMIT, "دلار")
    def cryptomus_get_amount(self):
        amount = self.convert_ir_num_to_en(self.text)
        wait_msg = self.bot.send_message(self.chat_id, "⏳")
        status, data = CryptomusCreateTransaction(
            self.user_obj, amount
        ).create_transaction()
        if not status:
            msg = MessageService(self.user_obj).get(step="create-payment-error").text
            return self.bot.send_message(self.chat_id, msg)

        msg = MessageService(self.user_obj).get(step="crypto-payment")
        msg.keys = msg.keys.format(url=data, callback="")
        reply_markup = self.generate_keyboards(msg)
        text = msg.text.format(user_id=self.chat_id)
        self.bot.delete_message(self.chat_id, wait_msg["result"]["message_id"])
        self.bot.send_message(self.chat_id, text, reply_markup=reply_markup)

    @validators.validate_min_max_pay_amount(CONFIG.MIN_RIAL_PAY_LIMIT, "ریال")
    def zarinpal_get_rial_amount(self):
        amount = self.convert_ir_num_to_en(self.text)
        wait_msg = self.bot.send_message(self.chat_id, "⏳")
        status, data = ZarinpalCreateTransaction(
            self.user_obj, amount
        ).create_transaction()
        if not status:
            msg = MessageService(self.user_obj).get(step="create-payment-error").text
            return self.bot.send_message(self.chat_id, msg)

        msg = MessageService(self.user_obj).get(step="rial-payment")
        msg.keys = msg.keys.format(url=data, callback="")
        reply_markup = self.generate_keyboards(msg)
        text = msg.text.format(user_id=self.chat_id)
        self.bot.delete_message(self.chat_id, wait_msg["result"]["message_id"])
        self.bot.send_message(self.chat_id, text, reply_markup=reply_markup)

    def handlers(self):
        self.add_dynamic_admin_user_ticket_step()
        if callback := self.steps.get(self.user_obj.step):
            callback()

    def run(self):
        self.handlers()


class UserCallbackHandler(UserTextHandler):
    validators = Validators()

    def __init__(self, base_handler=None) -> None:
        self.base_handler = base_handler
        self.callback_handlers = {
            "country-": self.select_country,
            "back_to_show_countrys": self.back_to_show_countrys,
            "login_code": self.get_login_code,
        }

    def __getattr__(self, name):
        attribute = getattr(self.base_handler, name, None)
        if attribute is not None:
            return attribute

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    @validators.validate_exists_product
    def back_to_show_countrys(self):
        msg = MessageService(self.user_obj).get(step="buy_phone_number")
        text = self.buy_phone_number(msg)
        reply_markup = self.generate_keyboards(text)
        self.bot.edit_message_text(
            self.chat_id, self.message_id, text.text, reply_markup=reply_markup
        )

    def select_country(self):
        """Get the related country session and return phone number"""
        country_code = self.callback_data.split("-")[1]
        session = AccountSessionService().get_random_session(country_code)
        if not session:
            return self.back_to_show_countrys()

        status, _ = asyncio.run(
            TMAccountManager(session_id=session.id).check_session_status()
        )
        if not status:
            self.bot.send_answer_callback_query(
                self.callback_query_id, "❌ Session Problem"
            )
            return self.back_to_show_countrys()

        order = OrderService().create_order(session, self.user_obj)
        if not order:
            self.bot.send_answer_callback_query(
                self.callback_query_id, "❌ Order problem"
            )
            return self.back_to_show_countrys()

        # Cache phone-number for get-login-code rate limit
        cache.set(f"{self.chat_id}:order:get:login:code:{session.phone}", 1)

        msg = MessageService(self.user_obj).get(step="show-phone-number")
        msg.keys = msg.keys.format(phone=session.phone)
        keys = self.generate_keyboards(msg)
        self.bot.edit_message_text(
            self.chat_id,
            self.message_id,
            msg.text.format(phone=session.phone),
            reply_markup=keys,
        )

    def get_login_code(self):
        phone = self.callback_data.split("-")[1]
        msg = MessageService(self.user_obj).get(step="show-login-code")

        # Check get code rate limit
        rate_limit_key = f"{self.chat_id}:order:get:login:code:{phone}"
        if int(cache.get(rate_limit_key) or 0) > int(CONFIG.GET_LOGIN_CODE_LIMIT):
            msg = MessageService(self.user_obj).get(step="limit-login-code-error").text
            return self.bot.send_answer_callback_query(
                self.callback_query_id, msg, show_alert=True
            )

        session = AccountSessionService().get_session(phone)
        if not session:
            return self.bot.send_answer_callback_query(
                self.callback_query_id, "❌ شماره یافت نشد ❌"
            )
        code = asyncio.run(TMAccountManager(session.id).retrieve_login_code(phone))
        if not code:
            return self.bot.send_answer_callback_query(
                self.callback_query_id, "❌ کد یافت نشد ❌"
            )

        # Store login code
        OrderService().update_order(session.order.id, login_code=code)
        msg.keys = msg.keys.format(phone=phone)
        keys = self.generate_keyboards(msg)
        self.bot.send_message(
            self.chat_id,
            msg.text.format(code=code, password=session.password),
            reply_markup=keys,
        )
        self.bot.send_answer_callback_query(self.callback_query_id, "✅")
        cache.incr(rate_limit_key)

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
