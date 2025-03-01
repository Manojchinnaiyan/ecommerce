from rest_framework import serializers
from decimal import Decimal
from django.db.models import Q
from .models import Order, OrderItem
from apps.products.serializers import ProductSerializer
from apps.accounts.serializers import AddressSerializer
from apps.accounts.models import Address
from apps.cart.models import Cart


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        source="product",
        queryset=ProductSerializer.Meta.model.objects.all(),
        write_only=True,
    )

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_id",
            "quantity",
            "unit_price",
            "total_price",
        ]
        read_only_fields = ["unit_price", "total_price"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    shipping_address_details = AddressSerializer(
        source="shipping_address", read_only=True
    )
    billing_address_details = AddressSerializer(
        source="billing_address", read_only=True
    )

    class Meta:
        model = Order
        fields = "__all__"
        read_only_fields = [
            "order_number",
            "subtotal",
            "total",
            "payment_status",
            "payment_id",
            "created_at",
            "updated_at",
        ]


class OrderCreateSerializer(serializers.ModelSerializer):
    shipping_address_id = serializers.IntegerField(write_only=True)
    billing_address_id = serializers.IntegerField(write_only=True)
    use_shipping_for_billing = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = Order
        fields = [
            "shipping_address_id",
            "billing_address_id",
            "use_shipping_for_billing",
            "shipping_cost",
        ]

    def to_representation(self, instance):
        """
        Return complete order data after creation, including id and order_number.
        """
        return OrderSerializer(instance, context=self.context).data

    def validate(self, attrs):
        # Request context is crucial here to get the user
        user = self.context.get("request").user

        # Validate shipping address belongs to user
        shipping_address_id = attrs.get("shipping_address_id")
        try:
            shipping_address = Address.objects.get(
                id=shipping_address_id, user=user, address_type="shipping"
            )
            attrs["shipping_address"] = shipping_address
            attrs["shipping_name"] = f"{user.first_name} {user.last_name}"
            attrs["shipping_address_line"] = shipping_address.street_address
            attrs["shipping_city"] = shipping_address.city
            attrs["shipping_state"] = shipping_address.state
            attrs["shipping_postal_code"] = shipping_address.postal_code
            attrs["shipping_country"] = shipping_address.country
        except Address.DoesNotExist:
            raise serializers.ValidationError(
                {"shipping_address_id": "Invalid shipping address"}
            )

        # Handle billing address
        if attrs.get("use_shipping_for_billing"):
            attrs["billing_address"] = shipping_address
            attrs["billing_name"] = attrs["shipping_name"]
            attrs["billing_address_line"] = attrs["shipping_address_line"]
            attrs["billing_city"] = attrs["shipping_city"]
            attrs["billing_state"] = attrs["shipping_state"]
            attrs["billing_postal_code"] = attrs["shipping_postal_code"]
            attrs["billing_country"] = attrs["shipping_country"]
        else:
            billing_address_id = attrs.get("billing_address_id")
            try:
                billing_address = Address.objects.get(
                    id=billing_address_id, user=user, address_type="billing"
                )
                attrs["billing_address"] = billing_address
                attrs["billing_name"] = f"{user.first_name} {user.last_name}"
                attrs["billing_address_line"] = billing_address.street_address
                attrs["billing_city"] = billing_address.city
                attrs["billing_state"] = billing_address.state
                attrs["billing_postal_code"] = billing_address.postal_code
                attrs["billing_country"] = billing_address.country
            except Address.DoesNotExist:
                raise serializers.ValidationError(
                    {"billing_address_id": "Invalid billing address"}
                )

        # Remove temporary fields
        attrs.pop("use_shipping_for_billing", None)
        attrs.pop("shipping_address_id", None)
        attrs.pop("billing_address_id", None)

        return attrs

    def create(self, validated_data):
        # Get the user from the context
        user = self.context.get("request").user

        # Get the cart - user OneToOneField relationship with related_name="cart"
        try:
            cart = user.cart
        except Cart.DoesNotExist:
            # Create a cart if it doesn't exist
            cart = Cart.objects.create(user=user)

        if not cart or not cart.items.exists():
            raise serializers.ValidationError({"cart": "Cart is empty"})

        # Calculate order totals
        subtotal = cart.subtotal
        shipping_cost = validated_data.pop("shipping_cost", 0)

        # Use Decimal instead of float for tax calculation to avoid type error
        tax = subtotal * Decimal("0.1")
        total = subtotal + shipping_cost + tax

        # Create order with user explicitly passed
        order = Order.objects.create(
            user=user,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            tax=tax,
            total=total,
            **validated_data,
        )

        # Create order items from cart
        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=cart_item.quantity,
                unit_price=cart_item.unit_price,
                total_price=cart_item.total_price,
            )

        # Clear cart after order creation
        cart.items.all().delete()

        return order
