from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_name", "unit_price", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "total", "created_at")
    list_select_related = ("user",)
    inlines = (OrderItemInline,)
    readonly_fields = ("user", "total", "created_at")

    def has_add_permission(self, request):
        return False
