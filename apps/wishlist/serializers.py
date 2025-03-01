from rest_framework import serializers
from .models import Wishlist, WishlistItem
from apps.products.serializers import ProductSerializer


class WishlistItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        source="product",
        queryset=ProductSerializer.Meta.model.objects.all(),
        write_only=True,
    )

    class Meta:
        model = WishlistItem
        fields = ["id", "product", "product_id", "created_at"]
        read_only_fields = ["created_at"]


class WishlistSerializer(serializers.ModelSerializer):
    items = WishlistItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Wishlist
        fields = ["id", "user", "items", "total_items", "created_at", "updated_at"]
        read_only_fields = ["user", "created_at", "updated_at"]


class AddToWishlistSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()

    def validate_product_id(self, value):
        try:
            product = ProductSerializer.Meta.model.objects.get(pk=value)
            if not product.is_active:
                raise serializers.ValidationError("This product is not available.")
            return value
        except ProductSerializer.Meta.model.DoesNotExist:
            raise serializers.ValidationError("Product not found.")
