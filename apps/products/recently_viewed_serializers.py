from rest_framework import serializers
from .recently_viewed_models import RecentlyViewed
from .serializers import ProductSerializer


class RecentlyViewedSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = RecentlyViewed
        fields = ["id", "product", "viewed_at"]
        read_only_fields = ["viewed_at"]
