from rest_framework import serializers
from apps.products.serializers import ProductSerializer
from .models import SearchQuery, ProductView, RecommendationEvent, ProductSimilarity


class SearchQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchQuery
        fields = ["id", "query_text", "results_count", "created_at"]
        read_only_fields = ["id", "created_at"]


class ProductViewSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = ProductView
        fields = ["id", "product", "viewed_at", "viewed_from_search"]
        read_only_fields = ["id", "viewed_at"]


class RecommendationRequestSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=False)
    category_id = serializers.IntegerField(required=False)
    limit = serializers.IntegerField(required=False, default=5)

    def validate(self, attrs):
        if not attrs.get("product_id") and not attrs.get("category_id"):
            raise serializers.ValidationError(
                "Either product_id or category_id must be provided"
            )
        return attrs


class RecommendationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecommendationEvent
        fields = ["id", "product", "event_type", "source", "position", "created_at"]
        read_only_fields = ["id", "created_at"]


class AdvancedSearchSerializer(serializers.Serializer):
    query = serializers.CharField(required=False, allow_blank=True)
    category_id = serializers.IntegerField(required=False, allow_null=True)
    min_price = serializers.DecimalField(
        required=False, max_digits=10, decimal_places=2, min_value=0, allow_null=True
    )
    max_price = serializers.DecimalField(
        required=False, max_digits=10, decimal_places=2, min_value=0, allow_null=True
    )
    in_stock = serializers.BooleanField(required=False)
    rating = serializers.IntegerField(
        required=False, min_value=1, max_value=5, allow_null=True
    )
    sort_by = serializers.ChoiceField(
        required=False,
        choices=[
            "price_asc",
            "price_desc",
            "name_asc",
            "name_desc",
            "rating",
            "newest",
            "popularity",
        ],
        default="relevance",
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    limit = serializers.IntegerField(
        required=False, min_value=1, max_value=50, default=20
    )
