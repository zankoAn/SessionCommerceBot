import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from pytest_mock.plugin import MockerFixture
from rest_framework.response import Response
from rest_framework.test import RequestsClient

from ecommerce.bot.models import Message
from ecommerce.payment.models import Transaction
from ecommerce.payment.services import CryptoPaymentService, ZarinPalPaymentService
from ecommerce.payment.views import (
    CryptomusCreateTransaction,
    ZarinpalCreateTransaction,
)

User = get_user_model()


@pytest.fixture(autouse=True)
def default_msg_objs():
    Message.objects.bulk_create(
        objs=[
            Message(
                text="💰 <b>شارژ حساب</b> 💰\r\n\r\n💰 لطفا میزان مورد نیاز شارژ خود را ارسال نمایید \r\n\r\n⚠️ عدد ارسال شده باید به ریال باشد.\r\n⚠️ عدد وارد شده باید بیشتر از  20 هزار تومان باشد.\r\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖",
                current_step="rial-get-amount",
                key="💰 پرداخت ریالی",
                keys="🏛 برگشت و انتخاب روش پرداخت",
            ),
            Message(
                text="💰 <b>شارژ حساب</b> 💰\r\n\r\n💳 برای شارژ حساب خود لطفا بر روی دکمه زیر کلیک نمایید تا به صفحه درگاه منتقل شوید.\r\n\r\n⚠️ برای کند نبودن روند پرداخت بانکی لطفا VPN  خود را خاموش کنید.\r\n⚠️ لطفا تا پایان پرداخت و مشاهده تایید تراکنش از صفحه خارج نشوید. \r\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖",
                current_step="rial-payment",
                keys="💳 درگاه پرداخت :{callback}:{url}",
                is_inline_keyboard=True,
            ),
            Message(
                text="🪙 <b>شارژ حساب</b> 🪙\r\n\r\n💰 لطفا میزان مورد نیاز شارژ خود را ارسال نمایید \r\n\r\n⚠️ عدد ارسال شده باید به دلار باشد.\r\n⚠️ عدد وارد شده باید بیشتر از 1 دلار  باشد.\r\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖",
                current_step="crypto-get-amount",
                key="🪙 پرداخت با کریپتو",
                keys="🏛 برگشت و انتخاب روش پرداخت",
            ),
            Message(
                text="🪙 <b>شارژ حساب</b> 🪙\r\n\r\n💳 برای شارژ حساب خود لطفا بر روی دکمه زیر کلیک نمایید تا به صفحه درگاه منتقل شوید.\r\n\r\n⚠️ لطفا تا پایان پرداخت و مشاهده تایید تراکنش از صفحه خارج نشوید. \r\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖",
                current_step="crypto-payment",
                keys="💳 درگاه پرداخت :{callback}:{url}",
                is_inline_keyboard=True,
            ),
            Message(
                text="💶 <b>شارژ حساب</b> 💶\r\n\r\n🔘 لطفا شماره 10 رقمی ووچر(e-voucher) خود را ارسال کنید\r\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖",
                current_step="perfectmoney-get-evoucher",
                key="💶 پرداخت با پرفکت مانی",
                keys="🏛 برگشت و انتخاب روش پرداخت",
            ),
            Message(
                text="💶 <b>شارژ حساب</b> 💶\r\n\r\n🔑 لطفا کد فعال سازی(Activation Code) خود را ارسال کنید\r\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖",
                current_step="perfectmoney-get-evcode",
                keys="🏛 برگشت و انتخاب روش پرداخت",
                is_inline_keyboard=True,
            ),
            Message(
                text="💶 شارژ حساب 💶\r\n\r\nاطلاعات شما ثبت شد، طی 1 الی 2 دقیقه آینده در صورت معتبر بودن اطالعات ارسال شده،‌ حساب شما شارژ می شود. ✅\r\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖",
                current_step="perfectmoney-success-recive-data",
                keys="👤 پروفایل\r\n🛍 خرید شماره\r\n💰 شارژحساب\r\n☎️ پشتیبانی",
            ),
            Message(
                text="❌ <b>شارژ حساب</b> ❌\r\n\r\n❌ فرمت دیتای ارسال شده صحیح نمی باشد، لطفا به فرمت گفت شده دقت کنید.\r\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖",
                current_step="invalid-amount-format-error",
            ),
            Message(
                text="❌ <b>شارژ حساب </b> ❌\r\n\r\n❌ مقدار پرداختی شما باید بیشتر از {min_amount:,} {pay_type} باشد.\r\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖",
                current_step="min-amount-limit-error",
            ),
            Message(
                text="❌ <b>دریافت کد فعال سازی</b> ❌\r\n\r\n❌ کد فعال سازی ووچر نامعتبر می باشد، لطفا کد 16 رقمی ووچر خود را ارسال نمایید.\r\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖",
                current_step="activation-code-length-error",
            ),
            Message(
                text="❌ <b>دریافت ووچر</b> ❌\r\n\r\n❌ ووچر ارسالی نامعتبر میباشد، لطفا شماره 10 رقمی ووچر خود را ارسال نمایید.\r\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖",
                current_step="evoucher-length-error",
            ),
            Message(
                text="💳 Success Pay ✅\r\n🎗 payment: <code>{method}</code>\r\n👤 user : <code>{user_id}</code>\r\n👤first name : <code>{first_name}</code>\r\n👤last name : <code>{last_name}</code>\r\n👤username : <code>{username}</code>\r\n💸 amount : <code>{amount:,}</code>\r\n⏰ time : <code>{time}</code>\r\n〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️",
                current_step="admin-success-pay",
            ),
            Message(
                text="⚡️ <b>افزایش موجودی</b> ⚡️\r\n\r\nپرداخت شما با موفقیت انجام شد. ✅\r\n\r\n💳 <b>موجودی جدید:‌‌</b> {balance:,}\r\n〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️",
                current_step="user-success-pay",
            ),
        ]
    )


@pytest.fixture()
def sample_user():
    user = User.objects.create(username="test-user", user_id=11111111)
    return user


@pytest.fixture()
def payment_type_update(request):
    payment_type = getattr(request, "param", {}).get("type")
    return {
        "message": {
            "chat": {
                "id": 111111111,
            },
            "text": payment_type,
        }
    }


@pytest.fixture()
def payment_amount_update(request):
    param = request.param
    amount = param.get("rial-amount") or param.get("usd-amount")
    return {
        "message": {
            "chat": {
                "id": 111111111,
            },
            "text": amount,
        }
    }


@pytest.fixture()
def payment_evoucher_update(request):
    evoucher = getattr(request, "param", {}).get("evoucher")
    return {
        "message": {
            "chat": {
                "id": 111111111,
            },
            "text": evoucher,
        }
    }


@pytest.fixture()
def payment_active_code_update(request):
    code = getattr(request, "param", {}).get("active-code")
    return {
        "message": {
            "chat": {
                "id": 111111111,
            },
            "text": code,
        }
    }


@pytest.fixture()
def zarinpal_create_txn_response():
    return {
        "data": {
            "authority": "A000000000000000000000000000yd6onmw6",
            "fee": 6500,
            "fee_type": "Payer",
            "code": 100,
            "message": "Success",
        },
        "errors": [],
    }


@pytest.fixture()
def zarinpal_txn(mocker: MockerFixture, zarinpal_create_txn_response, sample_user):
    mocker.patch(
        "ecommerce.payment.views.ZarinpalCreateTransaction.send_data",
        return_value=zarinpal_create_txn_response,
    )
    ZarinpalCreateTransaction(
        user_obj=sample_user, amount="300000"
    ).create_transaction()


@pytest.fixture()
def success_zarinpal_txn_response():
    return {
        "data": {
            "wages": [],
            "code": 100,
            "message": "Verified",
            "card_hash": "6229BF9653CD76D1F7155B5EA07D18F13C718202ED6DBEBF73D83F8F9E24CCB5",
            "card_pan": "589463******1060",
            "ref_id": 55685209701,
            "fee_type": "Payer",
            "fee": 7000,
            "shaparak_fee": "1200",
            "order_id": None,
        },
        "errors": [],
    }


@pytest.fixture()
def prepaid_zarinpal_txn_response():
    return {
        "data": {
            "wages": [],
            "code": 101,
            "message": "Verified",
            "card_hash": "6229BF9653CD76D1F7155B5EA07D18F13C718202ED6DBEBF73D83F8F9E24CCB5",
            "card_pan": "589463******1060",
            "ref_id": 55685209701,
            "fee_type": "Payer",
            "fee": 7000,
            "shaparak_fee": "1200",
            "order_id": None,
        },
        "errors": [],
    }


@pytest.fixture()
def failed_zarinpal_txn_response(request):
    if request.param == "":
        return ""

    return {
        "data": [],
        "errors": {
            "message": "Session is not valid, session is not active paid try.",
            "code": -51,
            "validations": [],
        },
    }


@pytest.fixture()
def cryptomus_create_txn_response():
    return {"url": "https://pay.cryptomus.com/pay/6dabc257-8eb2-4713-ac93-1bb5064305b4"}


@pytest.fixture
def cryptomus_txn(mocker: MockerFixture, cryptomus_create_txn_response, sample_user):
    mocker.patch(
        "ecommerce.payment.views.CryptomusCreateTransaction.send_data",
        return_value=cryptomus_create_txn_response,
    )
    mocker.patch(
        "ecommerce.payment.views.uuid4",
        return_value="d67ab81b-f78b-4e75-8a0e-5fb4b30a77de",
    )
    CryptomusCreateTransaction(user_obj=sample_user, amount="1").create_transaction()


@pytest.fixture
def sucess_cryptomus_txn_response():
    return {
        "order_id": "d67ab81b-f78b-4e75-8a0e-5fb4b30a77de",
        "payment_amount_usd": "1",
        "status": "paid",
        "from": "TSdSJKknRVQjys....",
        "txid": "6b863b17e331b15a8bc3380ffe0247....",
        "network": "tron",
        "currency": "USD",
        "payer_currency": "TRX",
        "payment_amount": "2.768",
    }


class TestCreateZarinPalPayment:
    pytestmark = pytest.mark.django_db
    send_msg_path = "ecommerce.telegram.telegram.Telegram.send_message"
    send_data_path = "ecommerce.payment.views.ZarinpalCreateTransaction.send_data"

    @pytest.mark.parametrize(
        "payment_amount_update", [{"rial-amount": "200000"}], indirect=True
    )
    @pytest.mark.parametrize(
        "payment_type_update", [{"type": "💰 پرداخت ریالی"}], indirect=True
    )
    def test_create_payment_with_valid_data(
        self,
        payment_type_update,
        payment_amount_update,
        zarinpal_create_txn_response,
        mocker: MockerFixture,
        client: RequestsClient,
    ):
        mocked_send_msg = mocker.patch(self.send_msg_path)
        mocked_post = mocker.patch(
            self.send_data_path, return_value=zarinpal_create_txn_response
        )

        url = reverse("bot:webhook")
        client.post(url, data=payment_type_update, content_type="application/json")
        client.post(url, data=payment_amount_update, content_type="application/json")

        _, send_msg_kwargs = mocked_send_msg.call_args
        post_request_args, _ = mocked_post.call_args
        payment = ZarinPalPaymentService().get_payment(
            authority=zarinpal_create_txn_response["data"]["authority"]
        )
        assert payment
        assert payment.transaction.amount_rial == int(post_request_args[0]["amount"])
        assert send_msg_kwargs["reply_markup"]
        assert send_msg_kwargs["reply_markup"]["inline_keyboard"][0][0]["url"]

    @pytest.mark.parametrize(
        "payment_amount_update",
        [
            {"rial-amount": "test"},
            {"rial-amount": "190000"},
            {"rial-amount": "-1"},
            {"rial-amount": "10000000000"},
            {"rial-amount": "0.1"},
            {"rial-amount": "01"},
        ],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "payment_type_update", [{"type": "💰 پرداخت ریالی"}], indirect=True
    )
    def test_create_payment_with_invalid_data(
        self,
        payment_type_update,
        payment_amount_update,
        mocker: MockerFixture,
        client: RequestsClient,
    ):
        mocked_send_msg = mocker.patch(self.send_msg_path)

        url = reverse("bot:webhook")
        client.post(url, data=payment_type_update, content_type="application/json")
        client.post(url, data=payment_amount_update, content_type="application/json")

        send_msg_args, send_msg_kwargs = mocked_send_msg.call_args
        _, error_msg = send_msg_args
        assert send_msg_kwargs == {}
        assert "❌" in error_msg


class TestCreatePerfectMoneyPayment:
    pytestmark = pytest.mark.django_db
    mocked_send_msg_path = "ecommerce.telegram.telegram.Telegram.send_message"

    @pytest.mark.parametrize(
        "payment_active_code_update",
        [{"active-code": "0123456789111213"}],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "payment_evoucher_update", [{"evoucher": "0123456789"}], indirect=True
    )
    @pytest.mark.parametrize(
        "payment_type_update", [{"type": "💶 پرداخت با پرفکت مانی"}], indirect=True
    )
    def test_create_payment_with_valid_data(
        self,
        payment_type_update,
        payment_evoucher_update,
        payment_active_code_update,
        mocker: MockerFixture,
        client: RequestsClient,
    ):
        send_msg_mock = mocker.patch(self.mocked_send_msg_path)
        url = reverse("bot:webhook")
        client.post(url, data=payment_type_update, content_type="application/json")
        client.post(url, data=payment_evoucher_update, content_type="application/json")

        args, kwargs = send_msg_mock.call_args
        _, msg = args
        assert "Activation Code" in msg
        assert kwargs == {}

        client.post(
            url, data=payment_active_code_update, content_type="application/json"
        )
        args, kwargs = send_msg_mock.call_args
        _, msg = args
        assert kwargs
        assert "✅" in msg

    @pytest.mark.parametrize(
        "payment_evoucher_update",
        [{"evoucher": "test"}, {"evoucher": "1"}, {"evoucher": "012345678"}],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "payment_type_update", [{"type": "💶 پرداخت با پرفکت مانی"}], indirect=True
    )
    def test_create_payment_with_invalid_evoucher(
        self,
        payment_type_update,
        payment_evoucher_update,
        mocker: MockerFixture,
        client: RequestsClient,
    ):
        send_msg_mock = mocker.patch(self.mocked_send_msg_path)
        url = reverse("bot:webhook")
        client.post(url, data=payment_type_update, content_type="application/json")
        client.post(url, data=payment_evoucher_update, content_type="application/json")

        args, kwargs = send_msg_mock.call_args
        _, msg = args
        assert "❌" in msg
        assert kwargs == {}

    @pytest.mark.parametrize(
        "payment_active_code_update",
        [
            {"active-code": "test"},
            {"active-code": "1"},
            {"active-code": "012345678911111"},
        ],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "payment_evoucher_update",
        [{"evoucher": "0123456789"}],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "payment_type_update", [{"type": "💶 پرداخت با پرفکت مانی"}], indirect=True
    )
    def test_create_payment_with_invalid_active_code(
        self,
        payment_type_update,
        payment_evoucher_update,
        payment_active_code_update,
        mocker: MockerFixture,
        client: RequestsClient,
    ):
        send_msg_mock = mocker.patch(self.mocked_send_msg_path)
        url = reverse("bot:webhook")
        client.post(url, data=payment_type_update, content_type="application/json")
        client.post(url, data=payment_evoucher_update, content_type="application/json")
        client.post(
            url, data=payment_active_code_update, content_type="application/json"
        )

        args, kwargs = send_msg_mock.call_args
        _, msg = args
        assert "❌" in msg
        assert kwargs == {}


class TestCreateCryptomusPayment:
    pytestmark = pytest.mark.django_db
    mocked_send_msg_path = "ecommerce.telegram.telegram.Telegram.send_message"

    @pytest.mark.parametrize(
        "payment_amount_update", [{"usd-amount": "1"}], indirect=True
    )
    @pytest.mark.parametrize(
        "payment_type_update", [{"type": "🪙 پرداخت با کریپتو"}], indirect=True
    )
    def test_create_payment_with_valid_data(
        self,
        payment_type_update,
        payment_amount_update,
        cryptomus_create_txn_response,
        mocker: MockerFixture,
        client: RequestsClient,
    ):
        send_msg_mock = mocker.patch(self.mocked_send_msg_path)
        mocked_send_data = mocker.patch(
            "ecommerce.payment.views.CryptomusCreateTransaction.send_data",
            return_value=cryptomus_create_txn_response,
        )
        url = reverse("bot:webhook")
        client.post(url, data=payment_type_update, content_type="application/json")
        client.post(url, data=payment_amount_update, content_type="application/json")

        args, _ = mocked_send_data.call_args
        payment = CryptoPaymentService().get_payment(order_id=args[0]["order_id"])
        _, kwargs = send_msg_mock.call_args

        assert kwargs["reply_markup"]
        assert kwargs["reply_markup"]["inline_keyboard"][0][0]["url"]
        assert payment

    @pytest.mark.parametrize(
        "payment_amount_update",
        [
            {"usd-amount": "test"},
            {"usd-amount": "0.1"},
            {"usd-amount": "-0.1"},
        ],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "payment_type_update", [{"type": "🪙 پرداخت با کریپتو"}], indirect=True
    )
    def test_create_payment_with_invalid_data(
        self,
        payment_type_update,
        payment_amount_update,
        mocker: MockerFixture,
        client: RequestsClient,
    ):
        send_msg_mock = mocker.patch(self.mocked_send_msg_path)

        url = reverse("bot:webhook")
        client.post(url, data=payment_type_update, content_type="application/json")
        client.post(url, data=payment_amount_update, content_type="application/json")

        args, kwargs = send_msg_mock.call_args
        _, msg = args
        assert kwargs == {}
        assert "❌" in msg


class TestVerifyZarinpalTransaction:
    pytestmark = pytest.mark.django_db

    def test_verify_txn_with_valid_data(
        self,
        sample_user,
        zarinpal_txn,
        zarinpal_create_txn_response,
        success_zarinpal_txn_response,
        client: RequestsClient,
        mocker: MockerFixture,
    ):
        authority = zarinpal_create_txn_response["data"]["authority"]
        mocker.patch(
            "ecommerce.payment.views.ZarinpalVerifyTransaction.send_verify_data",
            return_value=success_zarinpal_txn_response,
        )
        mocked_send_msg = mocker.patch(
            "ecommerce.telegram.telegram.Telegram.send_message"
        )
        mocked_open_file = mocker.patch(
            "ecommerce.payment.views.open", mocker.mock_open()
        )

        url = reverse("payment:verify-zarinpal-txn")
        url = f"{url}?Authority={authority}&Status=OK"
        response = client.get(url)

        payment = ZarinPalPaymentService().get_payment(authority=authority)
        new_user_balance = payment.transaction.payer.balance
        write_log_data = mocked_open_file.mock_calls[2][1][0]
        write_log_file_name = mocked_open_file.mock_calls[0][1]

        args, _ = mocked_send_msg.call_args
        success_telegram_msg = args[1]

        assert response.status_code == 200
        assert payment.transaction.status == Transaction.StatusChoices.PAID
        assert new_user_balance > sample_user.balance

        assert write_log_file_name == ("logs/payments.txt", "a")
        assert str(sample_user.user_id) in write_log_data
        assert f"{payment.transaction.amount_rial:,}" in write_log_data

        assert f"{new_user_balance:,}" in success_telegram_msg
        assert "✅" in success_telegram_msg

    @pytest.mark.parametrize(
        "params",
        [
            "Authority=1234&Status=OK",
            "Authority=test&Status=test",
            "Authority=11111=NOK",
            " ",
        ],
    )
    def test_verify_txn_with_invalid_url_params(
        self, params, client: RequestsClient, mocker: MockerFixture
    ):
        mocked_render = mocker.patch(
            "ecommerce.payment.views.render", return_value=Response()
        )
        url = reverse("payment:verify-zarinpal-txn")
        url = f"{url}?{params}"
        response = client.get(url)

        _, kwargs = mocked_render.call_args
        assert response.status_code == 200
        assert kwargs["template_name"] == "payment/transaction_error.html"

    def test_validate_prepaid_transaction(
        self,
        zarinpal_txn,
        zarinpal_create_txn_response,
        prepaid_zarinpal_txn_response,
        client: RequestsClient,
        mocker: MockerFixture,
    ):
        authority = zarinpal_create_txn_response["data"]["authority"]
        mocker.patch(
            "ecommerce.payment.views.ZarinpalVerifyTransaction.send_verify_data",
            return_value=prepaid_zarinpal_txn_response,
        )
        mocked_render = mocker.patch(
            "ecommerce.payment.views.render", return_value=Response()
        )
        url = reverse("payment:verify-zarinpal-txn")
        url = f"{url}?Authority={authority}&Status=OK"
        response = client.get(url)

        payment = ZarinPalPaymentService().get_payment(authority=authority)
        _, kwargs = mocked_render.call_args

        assert payment.transaction.status == Transaction.StatusChoices.PREPAID
        assert response.status_code == 200
        assert kwargs["template_name"] == "payment/transaction_error.html"

    @pytest.mark.parametrize(
        "failed_zarinpal_txn_response", ["default", ""], indirect=True
    )
    def test_verify_invalid_error_transaction(
        self,
        zarinpal_txn,
        zarinpal_create_txn_response,
        failed_zarinpal_txn_response,
        client: RequestsClient,
        mocker: MockerFixture,
    ):
        authority = zarinpal_create_txn_response["data"]["authority"]
        mocker.patch(
            "ecommerce.payment.views.ZarinpalVerifyTransaction.send_verify_data",
            return_value=failed_zarinpal_txn_response,
        )
        mocked_render = mocker.patch(
            "ecommerce.payment.views.render", return_value=Response()
        )
        url = reverse("payment:verify-zarinpal-txn")
        url = f"{url}?Authority={authority}&Status=OK"
        response = client.get(url)

        payment = ZarinPalPaymentService().get_payment(authority=authority)
        _, kwargs = mocked_render.call_args

        assert response.status_code == 200
        assert kwargs["template_name"] == "payment/transaction_error.html"
        assert payment.transaction.status == Transaction.StatusChoices.FAIL


class TestVerifyCryptomusTransaction:
    pytestmark = pytest.mark.django_db

    @pytest.mark.parametrize("ip", ["1.1.1.1", ""])
    def test_verify_txn_rejects_disallowed_ip(self, ip, client: RequestsClient):
        url = reverse("payment:verify-cryptomus-txn")
        client.defaults["HTTP_X_FORWARDED_FOR"] = ip
        response = client.post(url, data={})
        assert response.status_code == 403

    def test_verify_txn_with_valid_response_data(
        self,
        cryptomus_txn,
        sucess_cryptomus_txn_response,
        sample_user,
        client: RequestsClient,
        mocker: MockerFixture,
    ):
        mocked_send_msg = mocker.patch(
            "ecommerce.telegram.telegram.Telegram.send_message"
        )
        mocked_open_file = mocker.patch(
            "ecommerce.payment.views.open", mocker.mock_open()
        )
        mocker.patch(
            "ecommerce.payment.views.Nobitex.get_symbol_price", return_value=520000
        )
        url = reverse("payment:verify-cryptomus-txn")
        response = client.post(url, data=sucess_cryptomus_txn_response)

        payment = CryptoPaymentService().get_payment(
            order_id=sucess_cryptomus_txn_response["order_id"]
        )
        new_user_balance = payment.transaction.payer.balance
        write_log_data = mocked_open_file.mock_calls[2][1][0]
        write_log_file_name = mocked_open_file.mock_calls[0][1]
        args, _ = mocked_send_msg.call_args
        success_telegram_msg = args[1]

        assert response.status_code == 200
        assert payment.transaction.status == Transaction.StatusChoices.PAID
        assert new_user_balance > sample_user.balance

        assert write_log_file_name == ("logs/payments.txt", "a")
        assert str(sample_user.user_id) in write_log_data
        assert f"{payment.transaction.amount_rial:,}" in write_log_data

        assert f"{new_user_balance:,}" in success_telegram_msg
        assert "✅" in success_telegram_msg

    @pytest.mark.parametrize(
        "post_data",
        [{"order_id": ""}, {"order_id": "123"}, {"order_id": "test"}],
    )
    def test_verify_txn_with_invalid_order_id(
        self, post_data, client: RequestsClient, mocker: MockerFixture
    ):
        url = reverse("payment:verify-cryptomus-txn")
        response = client.post(url, data=post_data)
        assert response.data == "no"


class TestCryptomusGatewayCallback:
    pytestmark = pytest.mark.django_db

    def test_txn_success_redirect(
        self,
        cryptomus_txn,
        sucess_cryptomus_txn_response,
        mocker: MockerFixture,
        client: RequestsClient,
    ):
        order_id = sucess_cryptomus_txn_response["order_id"]
        mocker.patch(
            "ecommerce.payment.views.Obfuscate.deobfuscate_data", return_value=order_id
        )
        mocked_render = mocker.patch(
            "ecommerce.payment.views.render", return_value=Response()
        )
        url = reverse("payment:success-cryptomus-txn", kwargs={"oi": order_id})
        response = client.get(url)

        _, kwargs = mocked_render.call_args

        assert response.status_code == 200
        assert kwargs["context"]["txn_type"]
        assert kwargs["context"]["txn_amount_usd"]
        assert kwargs["template_name"] == "payment/transaction_success.html"

    @pytest.mark.parametrize("order_id", ["test", " "])
    def test_txn_error_redirect(
        self, order_id, mocker: MockerFixture, client: RequestsClient
    ):
        mocker.patch(
            "ecommerce.payment.views.Obfuscate.deobfuscate_data", return_value=order_id
        )
        mocked_render = mocker.patch(
            "ecommerce.payment.views.render", return_value=Response()
        )
        url = reverse("payment:success-cryptomus-txn", kwargs={"oi": order_id})
        response = client.get(url)

        _, kwargs = mocked_render.call_args

        assert response.status_code == 200
        assert kwargs["context"]["txn_type"]
        assert kwargs["context"].get("txn_amount_usd") is None
        assert kwargs["context"].get("txn_amount_rial") is None
        assert kwargs["context"].get("txn_hash") is None
        assert kwargs["template_name"] == "payment/transaction_error.html"
