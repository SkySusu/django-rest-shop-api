from django.urls import path

from .views import CartItemDetailView, CartItemListCreateView, CartView

urlpatterns = [
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/items/", CartItemListCreateView.as_view(), name="cart-item-list-create"),
    path(
        "cart/items/<int:item_id>/",
        CartItemDetailView.as_view(),
        name="cart-item-detail",
    ),
]
