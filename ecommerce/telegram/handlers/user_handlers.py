import asyncio
from uuid import uuid4
import base64
from django.contrib.auth import get_user_model
from django.core.cache import cache

from ecommerce.bot.models import Message
from ecommerce.telegram.account_manager import TMAccountManager
from ecommerce.product.models import AccountSession, Order, Product
from ecommerce.payment.services import (
    ZarinPalPaymentService,
    PerfectMoneyPaymentService,
    CryptoPaymentService,
)
from ecommerce.product.services import (
    OrderService,
    ProductService,
    AccountSessionService,
)
from ecommerce.telegram.validators import Validators
from utils.load_env import config as CONFIG
from cryptomus import Client
from django.urls import reverse

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
        return msg_obj.text.format(
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
            keys += (
                f"\n{product.price:,} | {product.name}:country-{product.country_code}:"
            )
        msg_obj.keys = keys.strip()
        return msg_obj

    def select_payment_method(self, ـ):
        msg = Message.objects.get(current_step="select_payment_method")
        self.user_qs.update(step="select_amount")
        return msg.text

    def handler(self):
        if "/start" in self.text:
            self.text = "/start"

        messages = Message.objects.filter(key=self.text).exclude(
            current_step__startswith="admin"
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
        msg = Message.objects.get(current_step="send-success-ticket-msg")
        resp = self.bot.forward_message(
            admin_user.user_id, self.chat_id, self.message_id
        )
        self.bot.send_message(self.chat_id, msg.text)
        # Send ticket info to admin(block/unblock)
        msg = Message.objects.get(current_step="admin-ticket-info")
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
        msg = Message.objects.get(current_step="perfectmoney-get-evcode").text
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
        msg = Message.objects.get(current_step="perfectmoney-success-recive-data")
        reply_markup = self.generate_keyboards(msg)
        self.user_qs.update(step="home_page")
        self.bot.send_message(self.chat_id, msg.text, reply_markup=reply_markup)

    @validators.validate_minimum_pay_amount(CONFIG.MIN_DOLLAR_PAY_LIMIT, "دلار")
    def cryptomus_get_amount(self):
        url = self._cryptomus_create_payment()
        msg = Message.objects.get(current_step="crypto-payment")
        msg.keys = msg.keys.format(url=url, callback="")
        reply_markup = self.generate_keyboards(msg)
        text = msg.text.format(user_id=self.chat_id)
        self.bot.send_message(self.chat_id, text, reply_markup=reply_markup)

    def _cryptomus_create_payment(self):
        amount = self.convert_ir_num_to_en(self.text)
        payment = CryptoPaymentService().create_payment(
            user=self.user_obj, order_id=str(uuid4())
        )
        payment.transaction.amount_usd = amount
        payment.transaction.save(update_fields=["amount_usd"])
        url_params = self._obfuscate_url_params(payment.order_id)
        payload = {
            "amount": amount,
            "currency": "USD",
            "order_id": payment.order_id,
            "subtract": "100",
            "lifetime": CONFIG.CRYPTOMUS_LIFETIME,
            "url_callback": f"{CONFIG.BASE_SITE_URL}{reverse('payment:verify-cryptomus-txn')}",
            "url_success": f"{CONFIG.BASE_SITE_URL}{reverse('payment:success-cryptomus-txn', args=[url_params])}",
        }
        payment = Client.payment(CONFIG.CRYPTOMUS_API_KEY, CONFIG.CRYPTOMUS_MERCHANT)
        response = payment.create(payload)
        url = response["url"]
        return url

    @validators.validate_minimum_pay_amount(CONFIG.MIN_RIAL_PAY_LIMIT, "ریال")
    def zarinpal_get_rial_amount(self):
        ZarinPalPaymentService().create_payment(self.user_obj)
        amount = self.convert_ir_num_to_en(self.text)
        txn = self._obfuscate_url_params(
            f"{self.user_obj.username}&{self.chat_id}&{amount}"
        )
        url = f"{CONFIG.BASE_SITE_URL}{reverse('payment:create-zarinpal-txn', args=[txn])}"
        msg = Message.objects.get(current_step="rial-payment")
        msg.keys = msg.keys.format(url=url, callback="")
        reply_markup = self.generate_keyboards(msg)
        text = msg.text.format(user_id=self.chat_id)
        self.bot.send_message(self.chat_id, text, reply_markup=reply_markup)

    def _obfuscate_url_params(self, data):
        key = 0x5F
        obfuscated_data = "".join(chr(ord(char) ^ key) for char in data)
        encoded_data = base64.urlsafe_b64encode(obfuscated_data.encode())
        return encoded_data.decode()

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
            "country_": self.get_phone_number,
            "back_to_show_countrys": self.back_to_show_countrys,
            "login_code": self.get_login_code,
            "add_session_phone_code_": self.admin_choice_country,
        }

    def __getattr__(self, name):
        attribute = getattr(self.base_handler, name, None)
        if attribute is not None:
            return attribute

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

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

    @validators.validate_exists_product
    def back_to_show_countrys(self):
        msg = Message.objects.get(current_step="buy_phone_number")
        # msg_obj = UserTextHandler(self).buy_phone_number(msg)
        text = self.buy_phone_number(msg)  # TODO: why previse we create instance?
        reply_markup = self.generate_keyboards(text)
        self.bot.edit_message_text(
            self.chat_id, self.message_id, text.text, reply_markup=reply_markup
        )

    def get_phone_number(self):
        _, cr_code = self.callback_data.split("_")
        product = Product.objects.get(country_code=cr_code)

        session = self.get_active_account_session(product)
        if not session:
            return self.send_no_phone_error()

        # Check session to see is connect
        status, _, __ = asyncio.run(
            TMAccountManager(session_id=session.id).check_session_status()
        )
        if not status:
            return self.back_to_show_countrys()

        session.status = AccountSession.StatusChoices.purchased
        session.save()

        self.create_order_and_decrease_inventory(session, product)

        msg = Message.objects.filter(current_step="show-phone-number").first()
        keys = self.generate_keyboards(msg)
        self.bot.edit_message_text(
            self.chat_id,
            self.message_id,
            msg.text.format(phone=session.phone),
            reply_markup=keys,
        )

    def get_active_account_session(self, product):
        return (
            AccountSession.objects.filter(
                product=product, status=AccountSession.StatusChoices.active
            )
            .order_by("?")
            .first()
        )

    def send_no_phone_error(self):
        msg = Message.objects.get(current_step="no-phone-error").text
        return self.bot.send_message(self.chat_id, msg)

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
            self.bot.send_answer_callback_query(self.callback_query_id, "❌ ")
            return self.bot.send_message(self.chat_id, msg)
        else:
            session = AccountSession.objects.get(phone=phone)
            password = session.password
            status, data, err = asyncio.run(
                TMAccountManager().retrive_login_code(phone)
            )
            if status:
                Order.objects.filter(session=session.id).update(login_code=data)
            else:
                return self.bot.send_answer_callback_query(
                    self.callback_query_id, "❌ کد یافت نشد ❌"
                )

        keys = self.generate_keyboards(msg)
        self.bot.send_message(
            self.chat_id,
            msg.text.format(code=str(data), password=password),
            reply_markup=keys,
        )
        self.bot.send_answer_callback_query(self.callback_query_id, "✅")
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
