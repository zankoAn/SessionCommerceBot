from ecommerce.product.models import Product, AccountSession
from ecommerce.bot.models import Message


class Validator:
    def validate_user_balance(self, func):
        def wrapper(self, msg_obj):
            if self.user_obj.is_staff:
                return func(self, msg_obj)

            # cache_key = f"limit-product-purchases:{self.chat_id}" # TODO: limit user to purchases the 3 account per 5 minute...;
            product = Product.objects.order_by("price").first()
            if self.user_obj.balance < product.price:
                text = Message.objects.get(current_step="insufficient-balance-message").text
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
                key = self.msg_reply_markup["inline_keyboard"][0] # Show country list key
                self.bot.remove_inline_keyboard(self.chat_id, self.message_id, key)

            self.bot.send_message(self.chat_id, text)

        return wrapper