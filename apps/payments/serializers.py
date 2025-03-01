from rest_framework import serializers
from .models import Payment, Refund
from apps.orders.serializers import OrderSerializer


class PaymentSerializer(serializers.ModelSerializer):
    order_details = OrderSerializer(source="order", read_only=True)

    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class PaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "order",
            "payment_id",
            "amount",
            "currency",
            "status",
            "razorpay_order_id",
            "razorpay_signature",
        ]

    def validate(self, attrs):
        # Ensure order belongs to the current user
        request = self.context.get("request")
        if request and request.user:
            order = attrs.get("order")
            if order.user != request.user:
                raise serializers.ValidationError(
                    {"order": "Order doesn't belong to the current user"}
                )
        return attrs


class PaymentVerifySerializer(serializers.Serializer):
    razorpay_payment_id = serializers.CharField()
    razorpay_order_id = serializers.CharField()
    razorpay_signature = serializers.CharField()


class RefundSerializer(serializers.ModelSerializer):
    payment_details = PaymentSerializer(source="payment", read_only=True)

    class Meta:
        model = Refund
        fields = "__all__"
        read_only_fields = ["refund_id", "created_at", "updated_at"]


class RefundCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ["payment", "amount", "reason"]

    def validate(self, attrs):
        # Ensure payment belongs to the current user
        request = self.context.get("request")
        if request and request.user:
            payment = attrs.get("payment")
            if payment.order.user != request.user:
                raise serializers.ValidationError(
                    {"payment": "Payment doesn't belong to the current user"}
                )

            # Ensure amount is not greater than payment amount
            if attrs.get("amount") > payment.amount:
                raise serializers.ValidationError(
                    {"amount": "Refund amount cannot be greater than payment amount"}
                )
        return attrs
