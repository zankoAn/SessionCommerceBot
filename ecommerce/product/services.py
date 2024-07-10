import random
import traceback

from django.db import transaction
from django.db.models import Q

from ecommerce.product.models import AccountSession, Order, Product
from fixtures.app_info import fake_info_list
from utils.load_env import config as CONFIG


class OrderService:
    def create_order(self, session, user_obj):
        """Update session status and create order,
        also update the user balance
        """
        try:
            with transaction.atomic():
                AccountSessionService().update_session_status(session, "purchased")
                order = Order.objects.create(
                    user=user_obj, session=session, price=session.product.price
                )
                user_obj.balance -= session.product.price
                user_obj.save()
        except Exception:
            AccountSessionService().update_session_status(session, "disable")
            msg = traceback.format_exc().strip()
            print(msg)
            return False

        return order

    def get_total_cnt_user_order(self, user: int):
        return Order.objects.filter(user=user).count()

    def get_success_order_count(self):
        order_count = Order.objects.filter(
            Q(status=Order.StatusChoices.down) & Q(status=Order.StatusChoices.waiting)
        ).count()
        return order_count

    def update_order(self, order_id, **kwargs) -> None:
        Order.objects.filter(id=order_id).update(**kwargs)


class ProductService:
    def get_active_countries(self):
        products = Product.objects.filter(
            accounts__status=AccountSession.StatusChoices.active
        ).distinct()
        return products


class AccountSessionService:
    def update_session_status(self, session, new_status):
        status = {
            "wait": AccountSession.StatusChoices.wait,
            "active": AccountSession.StatusChoices.active,
            "disable": AccountSession.StatusChoices.disable,
            "limit": AccountSession.StatusChoices.limit,
            "purchased": AccountSession.StatusChoices.purchased,
            "unknown": AccountSession.StatusChoices.unknown,
        }
        session.status = status.get(new_status)
        session.save(update_fields=["status"])

    def get_random_session(self, country_code):
        try:
            session = (
                AccountSession.objects.select_related("product")
                .select_for_update()
                .filter(
                    status=AccountSession.StatusChoices.active,
                    product__country_code=country_code,
                )
                .order_by("?")
                .first()
            )
            with transaction.atomic():
                if session:
                    self.update_session_status(session, "wait")
                else:
                    return False
        except Exception:
            msg = traceback.format_exc().strip()
            print(msg)
            return False

        return session

    def get_session(self, phone):
        session = AccountSession.objects.filter(phone=phone).first()
        if not session:
            return False
        return session

    def get_active_session_count(self):
        active_session_count = AccountSession.objects.filter(
            Q(status=AccountSession.StatusChoices.disable)
            & Q(status=AccountSession.StatusChoices.purchased)
        ).count()
        return active_session_count

    def get_deactive_session_count(self):
        active_session_count = AccountSession.objects.filter(
            status=AccountSession.StatusChoices.active
        ).count()
        return active_session_count

    def create_session(self, phone, product, **kwargs) -> AccountSession:
        random_info = random.choice(fake_info_list)
        session, _ = AccountSession.objects.get_or_create(
            phone=phone,
            product=product,
            app_version=random_info["app_version"],
            device_model=random_info["device_model"],
            system_version=random_info["system_version"],
            proxy=CONFIG.PROXY_SOCKS,
            api_id=CONFIG.API_ID,
            api_hash=CONFIG.API_HASH,
            **kwargs
        )
        return session

    def update_session(self, session_id, **kwargs) -> None:
        AccountSession.objects.filter(id=session_id).update(**kwargs)
