from rest_framework import serializers
from .models import Cart, CartItem
from apps.products.serializers import ProductSerializer


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        source="product",
        queryset=ProductSerializer.Meta.model.objects.all(),
        write_only=True,
    )
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "product_id",
            "quantity",
            "unit_price",
            "total_price",
            "created_at",
        ]
        read_only_fields = ["unit_price", "created_at"]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = [
            "id",
            "user",
            "items",
            "total_items",
            "subtotal",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "created_at", "updated_at"]


class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate_product_id(self, value):
        try:
            product = ProductSerializer.Meta.model.objects.get(pk=value)

            # Detailed product availability check
            if not product.is_active:
                raise serializers.ValidationError(
                    {"detail": "This product is not available."}
                )

            if product.stock <= 0:
                raise serializers.ValidationError(
                    {"detail": "This product is out of stock."}
                )

            return value
        except ProductSerializer.Meta.model.DoesNotExist:
            raise serializers.ValidationError({"detail": "Product not found."})

    def validate(self, attrs):
        product = ProductSerializer.Meta.model.objects.get(pk=attrs["product_id"])
        quantity = attrs["quantity"]

        # Validate quantity against available stock
        if quantity > product.stock:
            raise serializers.ValidationError(
                {
                    "detail": f"Requested quantity exceeds available stock. Only {product.stock} items available."
                }
            )

        return attrs


class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)

    def validate_quantity(self, value):
        cart_item = self.context.get("cart_item")

        if cart_item:
            # Check if requested quantity exceeds product stock
            if value > cart_item.product.stock:
                raise serializers.ValidationError(
                    f"Only {cart_item.product.stock} items available."
                )

        return value
