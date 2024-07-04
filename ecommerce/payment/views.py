import base64
import json
import traceback

import requests
from django.contrib.auth import get_user_model
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.bot.models import Message
from ecommerce.payment.exception import TransactionPaidBefore
from ecommerce.payment.models import CryptoPayment, Transaction, ZarinPalPayment
from ecommerce.payment.permission import WhitelistIPPermission
from ecommerce.payment.services import TransactionService, ZarinPalPaymentService
from ecommerce.payment.utils.crypto_symbol_price import Nobitex
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


#########################
# ZarinPal Transaction
#
class ZarinpalCreateTransaction(APIView, ZarinpalMetaData, TransactionUtils):
    error_template_name = "payment/transaction_error.html"

    def get(self, request, *args, **kwargs):
        txn = kwargs.get("txn")
        decoded_data = self.deobfuscate_url_params(txn)
        self.user_id, self.amount = self.extract_data_params(decoded_data)
        authority = None
        response = {}

        if self.is_valid():
            data = self.serialize_send_data()
            response = self.send_data(data)
            if not response or response.get("errors"):
                return self.render_error_template(response, authority)
            authority = response["data"]["authority"]
            is_save = self.save_transaction(authority)
            if is_save:
                success_url = self.zarinpal_api_startpay.format(authority=authority)
                return redirect(success_url)

        return self.render_error_template(response, authority)

    def extract_data_params(self, data):
        try:
            user_id, amount = data.split("&")[1:]
            return user_id, amount
        except Exception:
            return 0, 0

    def is_valid(self) -> bool:
        try:
            amount = int(self.amount)
            if not self.validate_min_amount_limit(amount):
                return False

            user = User.objects.filter(user_id=self.user_id)
            if not user:
                return False

            self.user = user.first()
            return True
        except Exception:
            msg = traceback.format_exc().strip()
            print(msg)
            return False

    def serialize_send_data(self):
        data = {
            "merchant_id": self.zarinpal_merchant,
            "description": "description",
            "callback_url": self.zarinpal_callback,
            "amount": self.amount,
            "metadata": {"mobile": "phone", "email": self.user_id},
        }
        return json.dumps(data)

    def send_data(self, data: dict):
        """Send transaction data to ``zarinpal`` and return the response."""
        try:
            return requests.post(
                url=self.zarinpal_api_request, data=data, headers=self.zarinpal_headers
            ).json()
        except Exception:
            msg = traceback.format_exc().strip()
            print(msg)
            return {}

    def save_transaction(self, authority):
        status = Transaction.StatusChoices.IN_PROGRESS
        method = Transaction.PaymentMethodChoices.ZARINPAL
        try:
            last_transaction = TransactionService().get_payment(
                payer=self.user, payment_method=method, status=status
            )
            TransactionService().update_payment(
                payment_id=last_transaction.id,
                payer=self.user,
                amount_rial=self.amount,
            )
            ZarinPalPaymentService().update_payment(
                payment_id=last_transaction.zarinpalpayment.id,
                transaction=last_transaction.id,
                authority=authority,
            )
            return True
        except Exception:
            return False

    def render_error_template(self, response, authority):
        return render(
            request=self.request,
            template_name=self.error_template_name,
            context={
                "message": _(response.get("errors", {}).get("message", "Bad Data")),
                "authority": authority,
                "user_id": self.user_id,
            },
        )


class ZarinpalVerifyTransaction(APIView, ZarinpalMetaData, TransactionUtils):
    error_template_name = "payment/transaction_error.html"
    success_template_name = "payment/transaction_success.html"

    def _get_transaction(self):
        """Get the transaction record if not paid before and authority exists
        - Raises:
            * ZarinPalPayment.DoesNotExist
            * TransactionPaidBefore
        """
        try:
            pay = ZarinPalPaymentService().get_payment(authority=self.authority)
        except ZarinPalPayment.DoesNotExist:
            raise ZarinPalPayment.DoesNotExist

        transaction = pay.transaction
        if transaction.status == Transaction.StatusChoices.PAID:
            raise TransactionPaidBefore()
        return transaction

    def get(self, request):
        self.status = request.GET.get("Status").lower()
        self.authority = request.GET.get("Authority")
        try:
            if self.status != "ok":
                raise ValueError()
            transaction = self._get_transaction()
        except TransactionPaidBefore:
            return self.render_error_template(code="paid_before")
        except Exception:
            return self.render_error_template(code="bad_input")

        response = self.send_verify_data(transaction.amount_rial)
        context_data = None
        if response:
            context_data = self.handel_verify_response(response, transaction)
            if context_data.get("code") == 100:
                self.finalize_success_payment(transaction)
                return self.render_success_template(context_data)
            if context_data.get("code") == 101:
                return self.render_error_template(code="paid_before")

        transaction.status = Transaction.StatusChoices.FAIL
        transaction.save(update_fields=["status"])
        return self.render_error_template(code="bad_connection")

    def render_error_template(self, context=None, code=""):
        if not context:
            contexts = {
                "bad_connection": {
                    "message": _("خطا در برقراری ارتباط با سرور پرداخت"),
                    "authority": self.authority,
                },
                "bad_input": {
                    "message": _("تراکنش با خطا مواجه شده است"),
                    "authority": self.authority,
                },
                "paid_before": {
                    "message": _("تراکنش قبلا تایید شده است."),
                    "authority": self.authority,
                },
            }
            context = contexts.get(code)

        return render(
            request=self.request,
            template_name=self.error_template_name,
            context=context,
        )

    def render_success_template(self, context):
        return render(
            request=self.request,
            template_name=self.success_template_name,
            context=context,
        )

    def send_verify_data(self, amount: int):
        data = {
            "merchant_id": self.zarinpal_merchant,
            "amount": amount,
            "authority": self.authority,
        }
        try:
            return requests.post(
                url=self.zarinpal_api_verify,
                data=json.dumps(data),
                headers=self.zarinpal_headers,
            ).json()
        except Exception:
            msg = traceback.format_exc().strip()
            print(msg)
            return False

    def handel_verify_response(self, response: dict, transaction: Transaction):
        """
        Handel the success verification responses and errors.
        Response Status Code:
        100:
            Code 100 that means the transaction is successful.
        101 and *:
            Code 101 that means the transaction was verified once before.
        """
        user_id = transaction.payer.user_id
        if response["errors"]:
            return {
                "message": _(response["errors"]["message"]),
                "authority": self.authority,
                "user_id": user_id,
                "code": response["errors"]["code"],
            }
        else:
            status_code = response["data"]["code"]
            if status_code == 100:
                return {
                    "txn_type": "zarinpal",
                    "user_id": user_id,
                    "amount": transaction.amount_rial,
                    "authority": self.authority,
                    "card_pan": response["data"]["card_pan"],
                    "code": 100,
                }
            elif status_code == 101:
                return {"code": 101}
            else:
                return {
                    "message": response["data"]["message"],
                    "authority": self.authority,
                    "user_id": user_id,
                    "code": status_code,
                }

    def finalize_success_payment(self, transaction: Transaction):
        transaction.status = Transaction.StatusChoices.PAID
        transaction.save(update_fields=["status"])
        self.upgrade_user_balance(transaction.amount_rial, transaction.payer)
        self.log_telegram_and_notify(transaction)


#########################
# Cryptomus Transaction
#
class CryptoMusVerifyTransaction(APIView, TransactionUtils):
    permission_classes = (WhitelistIPPermission,)
    error_template_name = "payment/transaction_error.html"

    def get_pay_amount_in_rial(self, amount_usd):
        price_per_dollar = Nobitex().get_symbol_price()
        pay_amount_rial = int(amount_usd * price_per_dollar)
        return pay_amount_rial

    def _get_transaction(self, order_id):
        try:
            transaction = TransactionService().get_payment(crypto__order_id=order_id)
            return transaction

        except Transaction.DoesNotExist:
            return False

        except CryptoPayment.DoesNotExist:
            return False

        except Exception as er:
            print(er)
            return False

    def post(self, request):
        data = request.data
        order_id = data.get("order_id")
        transaction = self._get_transaction(order_id)
        if not transaction:
            return Response("Hi")

        status = data.get("status")
        match status:
            case "paid":
                status = Transaction.StatusChoices.PAID
            case "paid_over":
                status = Transaction.StatusChoices.PAID_OVER
            case "wrong_amount_waiting":
                status = Transaction.StatusChoices.WRONG_AMOUNT
                transaction.save(update_fields=["status"])
                return Response("wrong amount")
            case _:
                transaction.status = Transaction.StatusChoices.FAIL
                transaction.save(update_fields=["status"])
                return Response("fail")

        # Transaction
        pay_amount_usd = float(data["payment_amount_usd"])
        transaction.status = status
        transaction.amount_rial = self.get_pay_amount_in_rial(pay_amount_usd)
        transaction.amount_usd = pay_amount_usd
        transaction.save(update_fields=["amount_rial", "amount_usd", "status"])
        # Payment
        transaction.crypto.from_addres = data["from"]
        transaction.crypto.tx_hash = data["txid"]
        transaction.crypto.network = data["network"]
        transaction.crypto.currency = data["currency"]
        transaction.crypto.payer_currency = data["payer_currency"]
        transaction.crypto.payment_amount_coin = data["payment_amount"]
        transaction.crypto.save()

        self.upgrade_user_balance(transaction.amount_rial, transaction.payer)
        self.log_telegram_and_notify(transaction)
        return Response("OK")


class CryptoMusSuccessTransaction(APIView, TransactionUtils):
    success_template_name = "payment/transaction_success.html"

    def get(self, request, *args, **kwargs):
        context = {}
        return render(request, self.success_template_name, context)
