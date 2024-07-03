import traceback

from django.db import transaction

from ecommerce.payment.models import (
    CryptoPayment,
    PerfectMoneyPayment,
    Transaction,
    ZarinPalPayment,
)


class TransactionService:
    payment_model = Transaction

    def create_base_payment(self, user) -> Transaction:
        payment = Transaction.objects.create(
            payer=user,
            payment_method=self.method_type,
        )
        return payment

    def create_payment(self, user, **kwargs) -> int:
        with transaction.atomic():
            base_payment = self.create_base_payment(user)
            payment = self.payment_model.objects.create(
                transaction=base_payment, **kwargs
            )
        return payment

    def update_payment(self, payment_id, **kwargs) -> None:
        try:
            self.payment_model.objects.filter(id=payment_id).update(**kwargs)
        except self.payment_model.DoesNotExist:
            print("Payment not found")
            raise
        except Exception:
            msg = traceback.format_exc().strip()
            print(msg)
            raise

    def get_payment(self, **kwargs) -> Transaction:
        queryset = self.payment_model.objects.filter(**kwargs)
        if not queryset.exists():
            print(f"{self.payment_model} record not found")
            raise self.payment_model.DoesNotExist

        if self.payment_model == Transaction:
            payment = queryset.select_related(
                "zarinpal", "perfectmoney", "crypto"
            )
        else:
            payment = queryset.select_related("transaction")
        return payment.last()


class PerfectMoneyPaymentService(TransactionService):
    method_type = Transaction.PaymentMethodChoices.PERFECT_MONEY
    payment_model = PerfectMoneyPayment


class CryptoPaymentService(TransactionService):
    method_type = Transaction.PaymentMethodChoices.CRYPTO
    payment_model = CryptoPayment


class ZarinPalPaymentService(TransactionService):
    method_type = Transaction.PaymentMethodChoices.ZARINPAL
    payment_model = ZarinPalPayment
