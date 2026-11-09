import builtins
import threading
from decimal import Decimal
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from carts.models import Cart, CartItem
from catalog.models import Product

from . import services
from .models import Order


class CheckoutApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "buyer",
            email="buyer@example.com",
            password="strong-pass-928",
            balance=Decimal("500.00"),
        )
        self.product = Product.objects.create(
            name="Keyboard", price=Decimal("100.00"), stock=3
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)
        self.client.force_authenticate(self.user)

    def test_checkout_deducts_balance_stock_and_clears_cart(self):
        previous_cart_update = self.cart.updated_at
        response = self.client.post(reverse("checkout"), {}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["total"], "200.00")
        self.user.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("300.00"))
        self.assertEqual(self.product.stock, 1)
        self.assertFalse(CartItem.objects.filter(cart=self.cart).exists())
        self.cart.refresh_from_db()
        self.assertGreater(self.cart.updated_at, previous_cart_update)
        self.assertEqual(Order.objects.get().items.get().quantity, 2)

    def test_checkout_with_insufficient_balance_is_atomic(self):
        self.user.balance = Decimal("10.00")
        self.user.save(update_fields=["balance"])
        response = self.client.post(reverse("checkout"), {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("10.00"))
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(Order.objects.count(), 0)
        self.assertTrue(CartItem.objects.filter(cart=self.cart).exists())

    def test_checkout_with_insufficient_stock_is_atomic(self):
        self.product.stock = 1
        self.product.save(update_fields=["stock"])
        response = self.client.post(reverse("checkout"), {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("500.00"))
        self.assertEqual(Order.objects.count(), 0)
        self.assertTrue(CartItem.objects.filter(cart=self.cart).exists())

    def test_order_list_only_contains_current_users_orders(self):
        response = self.client.post(reverse("checkout"), {}, format="json")
        self.assertEqual(response.status_code, 201)
        other = User.objects.create_user(
            "other", email="other@example.com", password="strong-pass-928"
        )
        self.client.force_authenticate(other)
        response = self.client.get(reverse("order-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row locks")
class CheckoutConcurrencyTests(TransactionTestCase):
    def test_cart_change_cannot_be_lost_during_checkout(self):
        user = User.objects.create_user(
            "buyer",
            email="buyer@example.com",
            password="strong-pass-928",
            balance=Decimal("500.00"),
        )
        product = Product.objects.create(
            name="Keyboard", price=Decimal("100.00"), stock=5
        )
        cart = Cart.objects.create(user=user)
        item = CartItem.objects.create(cart=cart, product=product, quantity=2)
        snapshot_ready = threading.Event()
        resume_checkout = threading.Event()
        patch_started = threading.Event()
        patch_finished = threading.Event()
        results = {}

        def pause_after_snapshot(queryset):
            rows = builtins.list(queryset)
            if queryset.model is CartItem:
                snapshot_ready.set()
                if not resume_checkout.wait(10):
                    raise TimeoutError("Checkout did not resume")
            return rows

        def run_checkout():
            try:
                results["order"] = services.checkout(user.pk)
            except Exception as error:
                results["checkout_error"] = error
            finally:
                connections.close_all()

        def run_patch():
            client = APIClient()
            client.force_authenticate(user)
            patch_started.set()
            try:
                results["patch"] = client.patch(
                    reverse("cart-item-detail", args=[item.pk]),
                    {"quantity": 3},
                    format="json",
                )
            except Exception as error:
                results["patch_error"] = error
            finally:
                patch_finished.set()
                connections.close_all()

        with patch.object(services, "list", pause_after_snapshot, create=True):
            checkout_thread = threading.Thread(target=run_checkout)
            patch_thread = threading.Thread(target=run_patch)
            checkout_thread.start()
            try:
                self.assertTrue(snapshot_ready.wait(10))
                patch_thread.start()
                self.assertTrue(patch_started.wait(10))
                self.assertFalse(patch_finished.wait(0.2))
            finally:
                resume_checkout.set()
                checkout_thread.join(10)
                if patch_thread.ident is not None:
                    patch_thread.join(10)

        self.assertFalse(checkout_thread.is_alive())
        self.assertFalse(patch_thread.is_alive())
        self.assertNotIn("checkout_error", results)
        self.assertNotIn("patch_error", results)
        self.assertEqual(results["patch"].status_code, 404)
        self.assertEqual(results["order"].items.get().quantity, 2)
        self.assertFalse(CartItem.objects.filter(cart=cart).exists())
