from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from .models import User


class AccountApiTests(APITestCase):
    def test_registration_and_profile(self):
        response = self.client.post(reverse("register"), {
            "username": "new-customer",
            "email": "customer@example.com",
            "password": "Strong-pass-928!",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["email"], "customer@example.com")
        user = User.objects.get(email="customer@example.com")
        self.assertTrue(user.check_password("Strong-pass-928!"))
        self.client.force_authenticate(user)
        profile = self.client.get(reverse("profile"))
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data["balance"], "0.00")

    def test_user_can_demo_top_up_own_balance(self):
        user = User.objects.create_user("buyer", email="buyer@example.com", password="strong-pass-928")
        self.client.force_authenticate(user)
        response = self.client.post(reverse("balance-top-up"), {"amount": "250.00"}, format="json")
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.balance, Decimal("250.00"))

    def test_top_up_rejects_non_positive_amount(self):
        user = User.objects.create_user("buyer", email="buyer@example.com", password="strong-pass-928")
        self.client.force_authenticate(user)
        response = self.client.post(reverse("balance-top-up"), {"amount": "0"}, format="json")
        self.assertEqual(response.status_code, 400)
        user.refresh_from_db()
        self.assertEqual(user.balance, Decimal("0.00"))
