from django.urls import path
from ecommerce.payment.views import (
    ZarinpalVerifyTransaction,
    CryptomusVerifyTransaction,
    CryptomusSuccessTransaction,
)


app_name = "payment"
urlpatterns = [
    path(
        "verify_transaction/zarinpal/",
        ZarinpalVerifyTransaction.as_view(),
        name="verify-zarinpal-txn",
    ),
    path(
        "verify_transaction/cryptomus/",
        CryptomusVerifyTransaction.as_view(),
        name="verify-cryptomus-txn",
    ),
    path(
        "success_transaction/cryptomus/<str:oi>",
        CryptomusSuccessTransaction.as_view(),
        name="success-cryptomus-txn",
    ),
]
