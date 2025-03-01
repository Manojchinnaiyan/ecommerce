from rest_framework import serializers
from .models import Category, Product, ProductImage, Review


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"
        read_only_fields = ("slug",)


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "is_primary"]


class ReviewSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "user", "user_email", "rating", "comment", "created_at"]
        read_only_fields = ("user", "created_at")

    def get_user_email(self, obj):
        return obj.user.email

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "category",
            "category_name",
            "price",
            "discount_price",
            "stock",
            "is_active",
            "created_at",
            "images",
            "is_in_stock",
            "discount_percentage",
            "final_price",
            "average_rating",
        ]
        read_only_fields = ("slug", "created_at")

    def get_category_name(self, obj):
        return obj.category.name

    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if reviews:
            return sum(review.rating for review in reviews) / len(reviews)
        return 0


class ProductDetailSerializer(ProductSerializer):
    reviews = ReviewSerializer(many=True, read_only=True)

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + ["reviews"]


class ProductCreateSerializer(serializers.ModelSerializer):
    images = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    primary_image = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "category",
            "price",
            "discount_price",
            "stock",
            "is_active",
            "images",
            "primary_image",
        ]

    def create(self, validated_data):
        images = validated_data.pop("images", [])
        primary_image = validated_data.pop("primary_image", None)

        product = Product.objects.create(**validated_data)

        if primary_image:
            ProductImage.objects.create(
                product=product, image=primary_image, is_primary=True
            )

        for image in images:
            ProductImage.objects.create(product=product, image=image, is_primary=False)

        return product
