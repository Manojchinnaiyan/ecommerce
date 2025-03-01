from django.contrib import admin
from .models import Payment, Refund


class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0
    readonly_fields = (
        "refund_id",
        "amount",
        "reason",
        "status",
        "created_at",
        "updated_at",
    )
    can_delete = False

    def has_add_permission(self, request, obj):
        return False


class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "payment_id",
        "order",
        "amount",
        "status",
        "payment_method",
        "created_at",
    )
    list_filter = ("status", "payment_method", "created_at")
    search_fields = ("payment_id", "order__order_number", "order__user__email")
    readonly_fields = (
        "payment_id",
        "order",
        "amount",
        "currency",
        "razorpay_order_id",
        "razorpay_signature",
        "created_at",
        "updated_at",
    )
    inlines = [RefundInline]

    def has_add_permission(self, request):
        return False


class RefundAdmin(admin.ModelAdmin):
    list_display = ("refund_id", "payment", "amount", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("refund_id", "payment__payment_id", "payment__order__order_number")
    readonly_fields = (
        "refund_id",
        "payment",
        "amount",
        "reason",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False


admin.site.register(Payment, PaymentAdmin)
admin.site.register(Refund, RefundAdmin)
