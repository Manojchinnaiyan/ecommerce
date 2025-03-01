from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings
import razorpay
import uuid
import hmac
import hashlib

from .models import Payment, Refund
from .serializers import (
    PaymentSerializer,
    PaymentCreateSerializer,
    PaymentVerifySerializer,
    RefundSerializer,
    RefundCreateSerializer,
)
from apps.orders.models import Order


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Payment.objects.all()
        return Payment.objects.filter(order__user=user)

    def get_serializer_class(self):
        if self.action == "create":
            return PaymentCreateSerializer
        return PaymentSerializer

    @action(detail=False, methods=["post"])
    def create_razorpay_order(self, request):
        order_id = request.data.get("order_id")

        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Check if order already has a payment
        if hasattr(order, "payment"):
            return Response(
                {"detail": "Payment for this order already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Initialize Razorpay client
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        # Convert decimal to integer (paise)
        amount_in_paise = int(order.total * 100)

        # Create Razorpay order
        razorpay_order = client.order.create(
            {
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": order.order_number,
                "payment_capture": 1,  # Auto capture payment
                "notes": {"order_id": str(order.id), "user_email": request.user.email},
            }
        )

        # Return order details
        return Response(
            {
                "order_id": order.id,
                "razorpay_order_id": razorpay_order["id"],
                "amount": amount_in_paise,
                "currency": "INR",
                "key": settings.RAZORPAY_KEY_ID,
                "name": "E-commerce Store",
                "description": f"Payment for Order #{order.order_number}",
                "prefill": {
                    "name": f"{request.user.first_name} {request.user.last_name}",
                    "email": request.user.email,
                    "contact": request.user.phone_number or "",
                },
            }
        )

    @action(detail=False, methods=["post"])
    def verify_payment(self, request):
        serializer = PaymentVerifySerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Get the validated data
        razorpay_payment_id = serializer.validated_data["razorpay_payment_id"]
        razorpay_order_id = serializer.validated_data["razorpay_order_id"]
        razorpay_signature = serializer.validated_data["razorpay_signature"]

        # Initialize Razorpay client
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        # Verify signature
        params_dict = {
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_order_id": razorpay_order_id,
            "razorpay_signature": razorpay_signature,
        }

        try:
            client.utility.verify_payment_signature(params_dict)
        except Exception as e:
            return Response(
                {"detail": "Invalid payment signature", "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the Razorpay order
        razorpay_order = client.order.fetch(razorpay_order_id)

        # Get the payment
        razorpay_payment = client.payment.fetch(razorpay_payment_id)

        # Get order from the notes
        try:
            order_id = razorpay_order["notes"]["order_id"]
            order = Order.objects.get(id=order_id, user=request.user)
        except (KeyError, Order.DoesNotExist):
            return Response(
                {"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Create payment record
        payment = Payment.objects.create(
            order=order,
            payment_id=razorpay_payment_id,
            amount=order.total,
            currency=razorpay_payment["currency"],
            status="completed",
            razorpay_order_id=razorpay_order_id,
            razorpay_signature=razorpay_signature,
        )

        # Update order payment status
        order.payment_status = "paid"
        order.payment_id = razorpay_payment_id
        order.status = "processing"
        order.save()

        # Return payment details
        return Response(PaymentSerializer(payment).data)


class RefundViewSet(viewsets.ModelViewSet):
    serializer_class = RefundSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Refund.objects.all()
        return Refund.objects.filter(payment__order__user=user)

    def get_serializer_class(self):
        if self.action == "create":
            return RefundCreateSerializer
        return RefundSerializer

    def perform_create(self, serializer):
        # Generate unique refund ID
        refund_id = f"refund_{uuid.uuid4().hex[:10]}"
        serializer.save(refund_id=refund_id)

    @action(detail=False, methods=["post"])
    def request_refund(self, request):
        payment_id = request.data.get("payment_id")
        amount = request.data.get("amount")
        reason = request.data.get("reason")

        if not payment_id or not amount or not reason:
            return Response(
                {"detail": "Payment ID, amount, and reason are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = Payment.objects.get(
                payment_id=payment_id, order__user=request.user
            )
        except Payment.DoesNotExist:
            return Response(
                {"detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Initialize Razorpay client
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        try:
            # Initiate refund
            refund = client.payment.refund(
                payment_id,
                {
                    "amount": int(float(amount) * 100),  # Convert to paise
                    "notes": {"reason": reason, "order_id": str(payment.order.id)},
                },
            )

            # Create refund record
            refund_obj = Refund.objects.create(
                payment=payment,
                refund_id=refund["id"],
                amount=amount,
                reason=reason,
                status="processed",
            )

            # Update payment status if fully refunded
            if float(amount) >= float(payment.amount):
                payment.status = "refunded"
                payment.save()

                # Update order status
                payment.order.status = "cancelled"
                payment.order.save()

            return Response(RefundSerializer(refund_obj).data)

        except Exception as e:
            return Response(
                {"detail": "Refund failed", "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
