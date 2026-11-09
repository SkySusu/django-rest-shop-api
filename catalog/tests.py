from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Product


class ProductApiTests(APITestCase):
    def test_product_list_is_public(self):
        product = Product.objects.create(
            name="Keyboard", price=Decimal("99.90"), stock=3
        )
        response = self.client.get(reverse("product-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["id"], product.id)

    def test_only_staff_can_change_products(self):
        user = User.objects.create_user(
            "buyer", email="buyer@example.com", password="strong-pass-928"
        )
        self.client.force_authenticate(user)
        response = self.client.post(
            reverse("product-list"),
            {
                "name": "Keyboard",
                "description": "",
                "price": "99.90",
                "stock": 3,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Product.objects.count(), 0)
