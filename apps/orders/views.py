from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Order, OrderItem
from .serializers import OrderSerializer, OrderCreateSerializer, OrderItemSerializer


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "payment_status"]
    ordering_fields = ["created_at", "updated_at", "total"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Order.objects.all()
        return Order.objects.filter(user=user)

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        return OrderSerializer

    # Simply call save() without passing context parameter
    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()

        # Only pending and processing orders can be cancelled
        if order.status not in ["pending", "processing"]:
            return Response(
                {"detail": "Cannot cancel this order as it is already processed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update order status
        order.status = "cancelled"
        order.save()

        # Return updated order
        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def my_orders(self, request):
        queryset = self.get_queryset().filter(user=request.user)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class OrderItemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return OrderItem.objects.all()

        order_id = self.kwargs.get("order_pk")
        if order_id:
            try:
                order = Order.objects.get(id=order_id, user=user)
                return OrderItem.objects.filter(order=order)
            except Order.DoesNotExist:
                return OrderItem.objects.none()

        return OrderItem.objects.filter(order__user=user)
