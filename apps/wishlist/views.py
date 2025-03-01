from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Wishlist, WishlistItem
from .serializers import (
    WishlistSerializer,
    WishlistItemSerializer,
    AddToWishlistSerializer,
)
from apps.products.models import Product
from apps.core.cache import (
    cached_user_wishlist,
    cache_user_wishlist,
    invalidate_user_wishlist,
    invalidate_user_cart,
)


class WishlistViewSet(viewsets.GenericViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user)

    def get_or_create_wishlist(self):
        wishlist, created = Wishlist.objects.get_or_create(user=self.request.user)
        return wishlist

    @action(detail=False, methods=["get"])
    def my_wishlist(self, request):
        # Check cache first
        user_id = request.user.id
        cached_data = cached_user_wishlist(user_id)

        if cached_data:
            return Response(cached_data)

        # If not in cache, get from database
        wishlist = self.get_or_create_wishlist()
        serializer = self.get_serializer(wishlist)
        data = serializer.data

        # Cache result
        cache_user_wishlist(user_id, data)

        return Response(data)

    @action(detail=False, methods=["post"])
    def add_item(self, request):
        wishlist = self.get_or_create_wishlist()
        serializer = AddToWishlistSerializer(data=request.data)

        if serializer.is_valid():
            product_id = serializer.validated_data["product_id"]
            product = Product.objects.get(id=product_id)

            # Check if product is already in wishlist
            wishlist_item, created = WishlistItem.objects.get_or_create(
                wishlist=wishlist, product=product
            )

            if not created:
                return Response(
                    {"detail": "Product already in wishlist"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Invalidate wishlist cache
            invalidate_user_wishlist(request.user.id)

            # Get updated wishlist
            wishlist_serializer = self.get_serializer(wishlist)
            return Response(wishlist_serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["delete"])
    def clear(self, request):
        wishlist = self.get_or_create_wishlist()
        wishlist.items.all().delete()

        # Invalidate wishlist cache
        invalidate_user_wishlist(request.user.id)

        return Response(
            {"detail": "Wishlist cleared"}, status=status.HTTP_204_NO_CONTENT
        )

    @action(detail=False, methods=["post"])
    def move_to_cart(self, request):
        from apps.cart.models import Cart, CartItem

        product_id = request.data.get("product_id")
        if not product_id:
            return Response(
                {"detail": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        wishlist = self.get_or_create_wishlist()

        try:
            wishlist_item = wishlist.items.get(product_id=product_id)
        except WishlistItem.DoesNotExist:
            return Response(
                {"detail": "Product not found in wishlist"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Add to cart
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, product=wishlist_item.product, defaults={"quantity": 1}
        )

        if not created:
            cart_item.quantity += 1
            cart_item.save()

        # Remove from wishlist
        wishlist_item.delete()

        # Invalidate caches
        invalidate_user_wishlist(request.user.id)
        invalidate_user_cart(request.user.id)

        wishlist_serializer = self.get_serializer(wishlist)
        return Response(
            {"detail": "Product moved to cart", "wishlist": wishlist_serializer.data}
        )


class WishlistItemViewSet(viewsets.GenericViewSet):
    serializer_class = WishlistItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user_wishlist = Wishlist.objects.filter(user=self.request.user).first()
        if not user_wishlist:
            return WishlistItem.objects.none()
        return WishlistItem.objects.filter(wishlist=user_wishlist)

    @action(detail=True, methods=["delete"])
    def remove(self, request, pk=None):
        wishlist_item = self.get_object()
        wishlist_item.delete()

        # Invalidate wishlist cache
        invalidate_user_wishlist(request.user.id)

        return Response(status=status.HTTP_204_NO_CONTENT)
