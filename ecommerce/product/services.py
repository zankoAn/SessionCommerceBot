from ecommerce.product.models import Product, Order, AccountSession
import traceback
from django.db import transaction


class OrderService:
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

    def create_order(self, session, user_obj):
        """Update session status and create order,
        also update the user balance
        """
        try:
            with transaction.atomic():
                self.update_session_status(session, "purchased")
                order = Order.objects.create(
                    user=user_obj, session=session, price=session.product.price
                )
                user_obj.balance -= session.product.price
                user_obj.save()
        except Exception:
            self.update_session_status(session, "disable")
            msg = traceback.format_exc().strip()
            print(msg)
            return False

        return order


class ProductService:
    def get_active_countries(self):
        products = Product.objects.filter(
            accounts__status=AccountSession.StatusChoices.active
        ).distinct()
        return products


class AccountSessionService:
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
