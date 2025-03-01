from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .recently_viewed_models import RecentlyViewed
from .recently_viewed_serializers import RecentlyViewedSerializer
from apps.core.cache import (
    cached_recently_viewed,
    cache_recently_viewed,
    invalidate_recently_viewed,
)


class RecentlyViewedViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RecentlyViewedSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RecentlyViewed.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get"])
    def list_products(self, request):
        # Check cache first
        user_id = request.user.id
        cached_data = cached_recently_viewed(user_id)

        if cached_data:
            return Response(cached_data)

        # If not in cache, get from database
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        # Cache results
        cache_recently_viewed(user_id, data)

        return Response(data)

    @action(detail=False, methods=["delete"])
    def clear(self, request):
        self.get_queryset().delete()

        # Invalidate cache
        invalidate_recently_viewed(request.user.id)

        return Response(
            {"detail": "Recently viewed products cleared"},
            status=status.HTTP_204_NO_CONTENT,
        )
