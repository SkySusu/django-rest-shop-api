from django.urls import path
from .views import BalanceTopUpView, ProfileView, RegistrationView

urlpatterns = [
    path("auth/register/", RegistrationView.as_view(), name="register"),
    path("users/me/", ProfileView.as_view(), name="profile"),
    path("users/me/top-up/", BalanceTopUpView.as_view(), name="balance-top-up"),
]
