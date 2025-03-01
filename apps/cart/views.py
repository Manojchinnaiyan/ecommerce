from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Cart, CartItem
from .serializers import (
    CartSerializer,
    CartItemSerializer,
    AddToCartSerializer,
    UpdateCartItemSerializer,
)
from apps.products.models import Product
from apps.core.cache import cached_user_cart, cache_user_cart, invalidate_user_cart


class CartViewSet(viewsets.GenericViewSet):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

    def get_or_create_cart(self):
        cart, created = Cart.objects.get_or_create(user=self.request.user)
        return cart

    @action(detail=False, methods=["get"])
    def my_cart(self, request):
        # Check cache first
        user_id = request.user.id
        cached_data = cached_user_cart(user_id)

        if cached_data:
            return Response(cached_data)

        # If not in cache, get from database
        cart = self.get_or_create_cart()
        serializer = self.get_serializer(cart)
        data = serializer.data

        # Cache result
        cache_user_cart(user_id, data)

        return Response(data)

    @action(detail=False, methods=["post"])
    def add_item(self, request):
        cart = self.get_or_create_cart()
        serializer = AddToCartSerializer(data=request.data)

        if serializer.is_valid():
            product_id = serializer.validated_data["product_id"]
            quantity = serializer.validated_data["quantity"]

            product = Product.objects.get(id=product_id)

            # Check if product is in stock
            if quantity > product.stock:
                return Response(
                    {"detail": f"Only {product.stock} items available"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if item is already in cart
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart, product=product, defaults={"quantity": quantity}
            )

            # If item exists, update quantity
            if not created:
                cart_item.quantity += quantity
                if cart_item.quantity > product.stock:
                    return Response(
                        {
                            "detail": f"Only {product.stock} items available. You already have {cart_item.quantity - quantity} in your cart."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                cart_item.save()

            # Invalidate cart cache
            invalidate_user_cart(request.user.id)

            # Get updated cart
            cart_serializer = self.get_serializer(cart)
            return Response(cart_serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["delete"])
    def clear(self, request):
        cart = self.get_or_create_cart()
        cart.items.all().delete()

        # Invalidate cart cache
        invalidate_user_cart(request.user.id)

        return Response({"detail": "Cart cleared"}, status=status.HTTP_204_NO_CONTENT)


class CartItemViewSet(viewsets.GenericViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user_cart = Cart.objects.filter(user=self.request.user).first()
        if not user_cart:
            return CartItem.objects.none()
        return CartItem.objects.filter(cart=user_cart)

    @action(detail=True, methods=["patch"])
    def update_quantity(self, request, pk=None):
        cart_item = self.get_object()

        # Add cart_item to serializer context for validation
        serializer_context = {"cart_item": cart_item}
        serializer = UpdateCartItemSerializer(
            data=request.data, context=serializer_context
        )

        if serializer.is_valid():
            new_quantity = serializer.validated_data["quantity"]

            # Check if requested quantity is available
            if new_quantity > cart_item.product.stock:
                return Response(
                    {"detail": f"Only {cart_item.product.stock} items available"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            cart_item.quantity = new_quantity
            cart_item.save()

            # Invalidate cart cache
            invalidate_user_cart(request.user.id)

            return Response(CartItemSerializer(cart_item).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["delete"])
    def remove(self, request, pk=None):
        cart_item = self.get_object()
        cart_item.delete()

        # Invalidate cart cache
        invalidate_user_cart(request.user.id)

        return Response(status=status.HTTP_204_NO_CONTENT)
