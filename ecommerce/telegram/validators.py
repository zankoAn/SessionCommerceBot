from django.core.cache import cache

from ecommerce.bot.models import Message
from ecommerce.product.models import AccountSession, Product


class Validators:
    def validate_user_balance(self, func):
        def wrapper(self, msg_obj):
            if self.user_obj.is_staff:
                return func(self, msg_obj)

            # cache_key = f"limit-product-purchases:{self.chat_id}" # TODO: limit user to purchases the 3 account per 5 minute...;
            product = Product.objects.order_by("price").first()
            if self.user_obj.balance < product.price:
                text = Message.objects.get(
                    current_step="insufficient-balance-message"
                ).text
                self.bot.send_message(self.chat_id, text)
                return
            return func(self, msg_obj)

        return wrapper

    def validate_exists_product(self, func):
        def wrapper(self, *args):
            active_status = AccountSession.StatusChoices.active
            product = Product.objects.filter(accounts__status=active_status).exists()
            if product:
                return func(self, *args)

            text = Message.objects.get(current_step="product-not-found-error").text
            # Check to see msg has inlinekeyboard.
            if getattr(self, "msg_reply_markup", None):
                # Show list country keyboard
                key = self.msg_reply_markup["inline_keyboard"][0]
                self.bot.remove_inline_keyboard(self.chat_id, self.message_id, key)

            self.bot.delete_message(self.chat_id, self.message_id)
            self.bot.send_message(self.chat_id, text)

        return wrapper

    @staticmethod
    def validate_min_max_pay_amount(min_limit, currency_type):
        def decorator(func):
            def wrapper(self):
                try:
                    amount = float(self.text)
                    if amount >= float(min_limit) and len(self.text) <= 10:
                        return func(self)
                    else:
                        error_msg = "min-amount-limit-error"
                        text = Message.objects.get(current_step=error_msg).text.format(
                            min_amount=float(min_limit), pay_type=currency_type
                        )
                except ValueError:
                    error_msg = "invalid-amount-format-error"
                    text = Message.objects.get(current_step=error_msg).text

                self.bot.send_message(self.chat_id, text)

            return wrapper

        return decorator

    def validate_evoucher_length(self, func):
        def wrapper(self):
            try:
                int(self.text)
                evoucher_length = 10
                if len(self.text) == evoucher_length:
                    return func(self)
                error_msg = "evoucher-length-error"
            except ValueError:
                error_msg = "invalid-amount-format-error"

            text = Message.objects.get(current_step=error_msg).text
            self.bot.send_message(self.chat_id, text)

        return wrapper

    def validate_activation_code_length(self, func):
        def wrapper(self):
            try:
                int(self.text)
                activation_code_length = 16
                if len(self.text) == activation_code_length:
                    return func(self)
                error_msg = "activation-code-length-error"
            except ValueError:
                error_msg = "invalid-amount-format-error"

            text = Message.objects.get(current_step=error_msg).text
            self.bot.send_message(self.chat_id, text)

        return wrapper

    def validate_phone_number(self, func):
        def wrapper(self, product=None):
            msg = Message.objects.get(current_step="phone-number-fmt-error").text
            user_phone = self.text.replace(" ", "").replace("-", "").strip()
            if not (10 < len(user_phone) < 15):  # phone length is not between 10...15
                return self.bot.send_message(self.chat_id, msg)
            return func(self)

        return wrapper

    def validate_phone_country_code(self, func):
        def wrapper(self, product=None) -> Product:
            msg = Message.objects.get(current_step="phone-number-country-error").text
            key = f"{self.chat_id}:add:session:country:code"
            country_code = cache.get(key)
            user_phone = self.text.replace(" ", "").replace("-", "").strip()
            try:
                product = Product.objects.get(country_code=country_code)
                if user_phone[:2] != product.phone_code[:2]:
                    return self.bot.send_message(self.chat_id, msg)
                return func(self, product)
            except Product.DoesNotExist:
                return self.bot.send_message(self.chat_id, msg)

        return wrapper

    def validate_api_id_and_api_hash(self, func):
        def wrapper(self):
            if "دیفالت" in self.text:
                return func(self)

            msg = Message.objects.get(current_step="input-apis-format-error").text
            apis = self.text.split("\n")
            if len(apis) != 2:
                return self.bot.send_message(self.chat_id, msg)
            try:
                int(apis[0])
            except Exception:
                return self.bot.send_message(self.chat_id, msg)
            return func(self)

        return wrapper

    def validate_input_proxy(self, func):
        def wrapper(self):
            if "دیفالت" in self.text:
                return func(self)

            msg = Message.objects.get(current_step="general-format-error").text
            proxy = self.text.split(":")
            if len(proxy) not in (2, 4):
                return self.bot.send_message(self.chat_id, msg)

            return func(self)

        return wrapper

    def validate_login_code(self, func):
        def wrapper(self):
            error = False
            if len(self.text.strip()) != 5:
                error = True
            try:
                int(self.text)
            except ValueError:
                error = True

            if error:
                msg = Message.objects.get(current_step="general-format-error").text
                return self.bot.send_message(self.chat_id, msg)
            return func(self)

        return wrapper

    @staticmethod
    def validate_cached_account_exists(cached_accounts):
        def decorator(func):
            def wrapper(self):
                if not cached_accounts.get(self.chat_id):
                    msg, keys = self.retrive_msg_and_keys("admin_back_to_add_session")
                    self.bot.send_message(self.chat_id, msg.text, reply_markup=keys)
                    self.user_qs.update(step="admin-home")
                    return
                return func(self)

            return wrapper

        return decorator

    def validate_file_format(self, func):
        def wrapper(self):
            if (
                self.file_id
                and self.file_size > 1
                and (
                    "rar" in self.file_mime_type
                    or "zip" in self.file_mime_type
                    or self.file_name.endswith(".session")
                )
            ):
                return func(self)
            else:
                msg = Message.objects.get(current_step="general-format-error").text
                return self.bot.send_message(self.chat_id, msg)

        return wrapper

    def validate_session_string_format(self, func):
        def wrapper(self):
            msg = Message.objects.get(current_step="general-format-error").text
            if len(self.text) < 300:
                return self.bot.send_message(self.chat_id, msg)
            return func(self)
        return wrapper