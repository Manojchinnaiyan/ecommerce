from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price", "total_price")
    can_delete = False

    def has_add_permission(self, request, obj):
        return False


class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "user",
        "status",
        "payment_status",
        "total",
        "created_at",
    )
    list_filter = ("status", "payment_status", "created_at")
    search_fields = ("order_number", "user__email", "shipping_name")
    readonly_fields = (
        "order_number",
        "user",
        "created_at",
        "updated_at",
        "subtotal",
        "shipping_cost",
        "tax",
        "total",
        "shipping_address",
        "billing_address",
        "shipping_name",
        "shipping_address_line",
        "shipping_city",
        "shipping_state",
        "shipping_postal_code",
        "shipping_country",
        "billing_name",
        "billing_address_line",
        "billing_city",
        "billing_state",
        "billing_postal_code",
        "billing_country",
        "payment_id",
    )
    fieldsets = (
        (
            "Order Information",
            {"fields": ("order_number", "user", "status", "created_at", "updated_at")},
        ),
        (
            "Payment Details",
            {"fields": ("payment_status", "payment_method", "payment_id")},
        ),
        (
            "Financial Details",
            {"fields": ("subtotal", "shipping_cost", "tax", "total")},
        ),
        (
            "Shipping Information",
            {
                "fields": (
                    "shipping_address",
                    "shipping_name",
                    "shipping_address_line",
                    "shipping_city",
                    "shipping_state",
                    "shipping_postal_code",
                    "shipping_country",
                )
            },
        ),
        (
            "Billing Information",
            {
                "fields": (
                    "billing_address",
                    "billing_name",
                    "billing_address_line",
                    "billing_city",
                    "billing_state",
                    "billing_postal_code",
                    "billing_country",
                )
            },
        ),
    )
    inlines = [OrderItemInline]

    def has_add_permission(self, request):
        return False


admin.site.register(Order, OrderAdmin)
