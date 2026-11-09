from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User

from .models import Cart, CartItem
from .serializers import (
    MAX_CART_QUANTITY,
    AddCartItemSerializer,
    CartSerializer,
    UpdateCartItemSerializer,
)


def get_user_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def get_locked_user_cart(user):
    User.objects.select_for_update().get(pk=user.pk)
    return get_user_cart(user)


def serialize_cart(cart):
    cart = Cart.objects.prefetch_related(
        Prefetch("items", queryset=CartItem.objects.select_related("product"))
    ).get(pk=cart.pk)
    return CartSerializer(cart).data


class CartView(APIView):
    @extend_schema(responses=CartSerializer)
    def get(self, request):
        cart = get_user_cart(request.user)
        return Response(serialize_cart(cart))


class CartItemListCreateView(APIView):
    @extend_schema(request=AddCartItemSerializer, responses={201: CartSerializer})
    @transaction.atomic
    def post(self, request):
        serializer = AddCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = get_locked_user_cart(request.user)
        product = serializer.validated_data["product_id"]
        quantity = serializer.validated_data["quantity"]
        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, defaults={"quantity": quantity}
        )
        if not created:
            if item.quantity > MAX_CART_QUANTITY - quantity:
                raise ValidationError({"quantity": "Количество товара слишком велико."})
            item.quantity += quantity
            item.save(update_fields=["quantity"])
        cart.save(update_fields=["updated_at"])
        return Response(serialize_cart(cart), status=status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    @extend_schema(request=UpdateCartItemSerializer, responses=CartSerializer)
    @transaction.atomic
    def patch(self, request, item_id):
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = get_locked_user_cart(request.user)
        item = get_object_or_404(CartItem, pk=item_id, cart=cart)
        item.quantity = serializer.validated_data["quantity"]
        item.save(update_fields=["quantity"])
        cart.save(update_fields=["updated_at"])
        return Response(serialize_cart(cart))

    @extend_schema(responses={204: None})
    @transaction.atomic
    def delete(self, request, item_id):
        cart = get_locked_user_cart(request.user)
        item = get_object_or_404(CartItem, pk=item_id, cart=cart)
        item.delete()
        cart.save(update_fields=["updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
