from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from carts.models import Cart, CartItem
from catalog.models import Product
from .models import Order


class CheckoutApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "buyer", email="buyer@example.com", password="strong-pass-928", balance=Decimal("500.00")
        )
        self.product = Product.objects.create(name="Keyboard", price=Decimal("100.00"), stock=3)
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)
        self.client.force_authenticate(self.user)

    def test_checkout_deducts_balance_stock_and_clears_cart(self):
        response = self.client.post(reverse("checkout"), {}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["total"], "200.00")
        self.user.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("300.00"))
        self.assertEqual(self.product.stock, 1)
        self.assertFalse(CartItem.objects.filter(cart=self.cart).exists())
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
        other = User.objects.create_user("other", email="other@example.com", password="strong-pass-928")
        self.client.force_authenticate(other)
        response = self.client.get(reverse("order-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
