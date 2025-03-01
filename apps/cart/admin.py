from django.contrib import admin
from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    raw_id_fields = ("product",)


class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "total_items", "subtotal", "created_at", "updated_at")
    search_fields = ("user__email",)
    inlines = [CartItemInline]
    readonly_fields = ("created_at", "updated_at")


class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cart",
        "product",
        "quantity",
        "unit_price",
        "total_price",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("cart__user__email", "product__name")
    readonly_fields = ("unit_price", "total_price", "created_at", "updated_at")


admin.site.register(Cart, CartAdmin)
admin.site.register(CartItem, CartItemAdmin)
