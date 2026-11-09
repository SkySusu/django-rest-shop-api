from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Product
from .models import CartItem


class CartApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("buyer", email="buyer@example.com", password="strong-pass-928")
        self.product = Product.objects.create(name="Keyboard", price=Decimal("100.00"), stock=3)
        self.client.force_authenticate(self.user)

    def test_add_and_view_cart(self):
        response = self.client.post(reverse("cart-item-list-create"), {
            "product_id": self.product.pk, "quantity": 2,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["total"], Decimal("200.00"))
        self.assertEqual(CartItem.objects.get().quantity, 2)

    def test_cart_item_is_scoped_to_current_user(self):
        self.client.post(reverse("cart-item-list-create"), {
            "product_id": self.product.pk, "quantity": 1,
        }, format="json")
        item = CartItem.objects.get()
        other = User.objects.create_user("other", email="other@example.com", password="strong-pass-928")
        self.client.force_authenticate(other)
        response = self.client.delete(reverse("cart-item-detail", args=[item.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(CartItem.objects.filter(pk=item.pk).exists())
