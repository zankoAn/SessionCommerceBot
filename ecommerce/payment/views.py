import base64

from django.contrib.auth import get_user_model


from ecommerce.bot.models import Message
from ecommerce.payment.models import Transaction
from ecommerce.telegram.telegram import Telegram
from utils.load_env import config as CONFIG

User = get_user_model()


class ZarinpalMetaData:
    zarinpal_merchant = CONFIG.ZARINPAL_MERCHANT
    zarinpal_api_request = "https://api.zarinpal.com/pg/v4/payment/request.json"
    zarinpal_api_verify = "https://api.zarinpal.com/pg/v4/payment/verify.json"
    zarinpal_api_startpay = "https://www.zarinpal.com/pg/StartPay/{authority}"
    zarinpal_callback = f"{CONFIG.BASE_SITE_URL}/{CONFIG.ZARINPAL_VERIFY_TXN_URL}"
    zarinpal_headers = {
        "accept": "application/json",
        "content-type": "application/json",
    }


class TransactionUtils:
    def validate_min_amount_limit(self, payment_amount):
        try:
            if int(payment_amount) >= int(CONFIG.MIN_RIAL_PAY_LIMIT):
                return True
        except Exception:
            return False
        return False

    def upgrade_user_balance(self, pay_amount, user):
        user.balance += pay_amount
        user.save(update_fields=["balance"])

    @staticmethod
    def deobfuscate_url_params(encoded_data):
        """Decode url params that send for create transaction"""
        decoded_data = base64.urlsafe_b64decode(encoded_data).decode()
        key = 0x5F
        deobfuscate_data = "".join(chr(ord(char) ^ key) for char in decoded_data)
        return deobfuscate_data


    @staticmethod
    def log_telegram_and_notify(transaction: Transaction):
        transaction_time = transaction.created.strftime("%y-%m-%d %H:%M:%S")
        with open("logs/payments.txt", "a") as log_file:
            log_file.write(
                f"[{transaction_time}] - User Id : {transaction.payer.user_id} - Pay Amount : [{transaction.amount_rial:,}]\n"
            )

        admins = User.objects.filter(is_staff=True)
        payer = transaction.payer
        for admin in admins:
            msg = Message.objects.get(current_step="admin-success-pay")
            text = msg.text.format(
                method=transaction.payment_method,
                user_id=payer.user_id,
                first_name=payer.first_name if payer.first_name else "❌",
                last_name=payer.last_name if payer.first_name else "❌",
                username=payer.username,
                amount=transaction.amount_rial,
                time=transaction_time,
            )
            Telegram().send_message(admin.user_id, text)

        user_success_msg = Message.objects.get(current_step="user-success-pay")
        Telegram().send_message(
            payer.user_id, user_success_msg.text.format(balance=payer.balance)
        )

