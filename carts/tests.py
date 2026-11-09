from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Product

from .models import Cart, CartItem


class CartApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "buyer", email="buyer@example.com", password="strong-pass-928"
        )
        self.product = Product.objects.create(
            name="Keyboard", price=Decimal("100.00"), stock=3
        )
        self.client.force_authenticate(self.user)

    def test_add_and_view_cart(self):
        response = self.client.post(
            reverse("cart-item-list-create"),
            {
                "product_id": self.product.pk,
                "quantity": 2,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["total"], Decimal("200.00"))
        self.assertEqual(CartItem.objects.get().quantity, 2)

    def test_cart_item_is_scoped_to_current_user(self):
        self.client.post(
            reverse("cart-item-list-create"),
            {
                "product_id": self.product.pk,
                "quantity": 1,
            },
            format="json",
        )
        item = CartItem.objects.get()
        other = User.objects.create_user(
            "other", email="other@example.com", password="strong-pass-928"
        )
        self.client.force_authenticate(other)
        response = self.client.delete(reverse("cart-item-detail", args=[item.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(CartItem.objects.filter(pk=item.pk).exists())

    def test_cart_changes_update_timestamp(self):
        self.client.get(reverse("cart"))
        cart = Cart.objects.get(user=self.user)
        original_time = cart.updated_at
        self.client.post(
            reverse("cart-item-list-create"),
            {
                "product_id": self.product.pk,
                "quantity": 1,
            },
            format="json",
        )
        cart.refresh_from_db()
        self.assertGreater(cart.updated_at, original_time)
        added_time = cart.updated_at
        item = CartItem.objects.get(cart=cart)
        self.client.patch(
            reverse("cart-item-detail", args=[item.pk]),
            {
                "quantity": 2,
            },
            format="json",
        )
        cart.refresh_from_db()
        self.assertGreater(cart.updated_at, added_time)
        changed_time = cart.updated_at
        self.client.delete(reverse("cart-item-detail", args=[item.pk]))
        cart.refresh_from_db()
        self.assertGreater(cart.updated_at, changed_time)

    def test_quantity_validation_and_form_input(self):
        add_url = reverse("cart-item-list-create")
        response = self.client.post(
            add_url,
            {
                "product_id": self.product.pk,
                "quantity": 2_147_483_648,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            add_url,
            {
                "product_id": self.product.pk,
                "quantity": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        item = CartItem.objects.get(cart__user=self.user)
        item_url = reverse("cart-item-detail", args=[item.pk])
        response = self.client.patch(item_url, {"quantity": "3"}, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CartItem.objects.get(pk=item.pk).quantity, 3)
        response = self.client.patch(
            item_url, {"quantity": 2_147_483_648}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        item.quantity = 2_147_483_647
        item.save(update_fields=["quantity"])
        response = self.client.post(
            add_url,
            {
                "product_id": self.product.pk,
                "quantity": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(CartItem.objects.get(pk=item.pk).quantity, 2_147_483_647)

    def test_cart_query_count_does_not_grow_with_items(self):
        products = [
            Product(name=f"Product {index}", price=Decimal("1.00"), stock=1)
            for index in range(30)
        ]
        Product.objects.bulk_create(products)
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.bulk_create(
            [
                CartItem(cart=cart, product=product, quantity=1)
                for product in Product.objects.all()
            ]
        )
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("cart"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 31)
        self.assertLessEqual(len(queries), 6)
