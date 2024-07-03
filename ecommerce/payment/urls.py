from django.urls import path
from ecommerce.payment.views import (
    ZarinpalCreateTransaction,
    ZarinpalVerifyTransaction,
    CryptoMusVerifyTransaction,
    CryptoMusSuccessTransaction
)


app_name = "payment"
urlpatterns = [
    path(
        "create_transaction/zarinpal/<str:txn>",
        ZarinpalCreateTransaction.as_view(),
        name="create-zarinpal-txn",
    ),
    path(
        "verify_transaction/zarinpal/",
        ZarinpalVerifyTransaction.as_view(),
        name="verify-zarinpal-txn",
    ),
    path(
        "verify_transaction/cryptomus/",
        CryptoMusVerifyTransaction.as_view(),
        name="verify-cryptomus-txn",
    ),
     path(
        "success_transaction/cryptomus/<str:oi>",
        CryptoMusSuccessTransaction.as_view(),
        name="success-cryptomus-txn",
    ),
]