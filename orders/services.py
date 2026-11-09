import logging
from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from accounts.models import User
from carts.models import Cart, CartItem
from catalog.models import Product
from .models import Order, OrderItem

logger = logging.getLogger(__name__)


@transaction.atomic
def checkout(user_id):
    user = User.objects.select_for_update().get(pk=user_id)
    cart = Cart.objects.filter(user=user).first()
    if cart is None:
        raise ValidationError({"cart": "Корзина пуста."})

    cart_items = list(CartItem.objects.filter(cart=cart).select_related("product").order_by("product_id"))
    if not cart_items:
        raise ValidationError({"cart": "Корзина пуста."})

    product_ids = [item.product_id for item in cart_items]
    locked_products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(pk__in=product_ids).order_by("pk")
    }
    prepared_items = []
    total = Decimal("0.00")
    for item in cart_items:
        product = locked_products.get(item.product_id)
        if product is None:
            raise ValidationError({"products": f"Товар {item.product_id} больше недоступен."})
        if product.stock < item.quantity:
            raise ValidationError({"products": f"Недостаточно товара «{product.name}» на складе."})
        line_total = product.price * item.quantity
        total += line_total
        prepared_items.append((product, item.quantity, product.name, product.price))

    if user.balance < total:
        raise ValidationError({"balance": "Недостаточно средств на балансе."})

    order = Order.objects.create(user=user, total=total)
    OrderItem.objects.bulk_create([
        OrderItem(order=order, product=product, product_name=name, unit_price=price, quantity=quantity)
        for product, quantity, name, price in prepared_items
    ])
    for product, quantity, _, _ in prepared_items:
        product.stock -= quantity
        product.save(update_fields=["stock"])

    user.balance -= total
    user.save(update_fields=["balance"])
    cart_items_query = CartItem.objects.filter(cart=cart)
    cart_items_query.delete()

    logger.info(
        "Order completed: order_id=%s user_id=%s total=%s",
        order.pk,
        user.pk,
        total,
    )
    return order
