from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Count, Avg, F
from django.db import transaction
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

from apps.products.models import Product, Category
from apps.products.serializers import ProductSerializer
from .models import (
    SearchQuery as UserSearchQuery,
    ProductView,
    RecommendationEvent,
    ProductSimilarity,
)
from .serializers import (
    SearchQuerySerializer,
    ProductViewSerializer,
    RecommendationRequestSerializer,
    RecommendationEventSerializer,
    AdvancedSearchSerializer,
)
from apps.core.cache import (
    cached_search_results,
    cache_search_results,
    cached_recommendations,
    cache_recommendations,
)


class SearchAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = AdvancedSearchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        query_text = data.get("query", "")
        category_id = data.get("category_id")
        min_price = data.get("min_price")
        max_price = data.get("max_price")
        in_stock = data.get("in_stock")
        rating = data.get("rating")
        sort_by = data.get("sort_by", "relevance")
        page = data.get("page", 1)
        limit = data.get("limit", 20)

        # Check cache first
        cache_filters = {
            "category_id": category_id,
            "min_price": str(min_price) if min_price else None,
            "max_price": str(max_price) if max_price else None,
            "in_stock": in_stock,
            "rating": rating,
            "sort_by": sort_by,
            "page": page,
            "limit": limit,
        }

        cached_results = None
        if query_text:
            cached_results = cached_search_results(query_text, cache_filters)

        if cached_results:
            return Response(cached_results)

        # If not in cache, perform the search
        # Start with all active products
        queryset = Product.objects.filter(is_active=True)

        # Filter by text search if provided
        if query_text:
            # Create a basic search filter
            search_filter = Q(name__icontains=query_text) | Q(
                description__icontains=query_text
            )

            # If PostgreSQL full-text search is available, use it
            try:
                search_vector = SearchVector("name", weight="A") + SearchVector(
                    "description", weight="B"
                )
                search_query = SearchQuery(query_text)
                rank = SearchRank(search_vector, search_query)

                queryset = queryset.annotate(search=search_vector, rank=rank).filter(
                    search=search_query
                )

                # If sorting by relevance, apply rank
                if sort_by == "relevance":
                    queryset = queryset.order_by("-rank")
            except:
                # Fallback to basic search
                queryset = queryset.filter(search_filter)

        # Apply filters
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        if min_price is not None:
            queryset = queryset.filter(price__gte=min_price)

        if max_price is not None:
            queryset = queryset.filter(price__lte=max_price)

        if in_stock:
            queryset = queryset.filter(stock__gt=0)

        if rating is not None:
            queryset = queryset.annotate(avg_rating=Avg("reviews__rating")).filter(
                avg_rating__gte=rating
            )

        # Apply sorting
        if sort_by == "price_asc":
            queryset = queryset.order_by("price")
        elif sort_by == "price_desc":
            queryset = queryset.order_by("-price")
        elif sort_by == "name_asc":
            queryset = queryset.order_by("name")
        elif sort_by == "name_desc":
            queryset = queryset.order_by("-name")
        elif sort_by == "rating":
            queryset = queryset.annotate(avg_rating=Avg("reviews__rating")).order_by(
                "-avg_rating"
            )
        elif sort_by == "newest":
            queryset = queryset.order_by("-created_at")
        elif sort_by == "popularity":
            queryset = queryset.annotate(view_count=Count("views")).order_by(
                "-view_count"
            )

        # Calculate result count
        total_results = queryset.count()

        # Paginate results
        offset = (page - 1) * limit
        queryset = queryset[offset : offset + limit]

        # Serialize results
        results = ProductSerializer(queryset, many=True).data

        # Prepare response
        response_data = {
            "results": results,
            "total": total_results,
            "page": page,
            "limit": limit,
            "pages": (total_results + limit - 1) // limit,  # Ceiling division
        }

        # Cache the search results
        if query_text:
            cache_search_results(query_text, response_data, cache_filters)

        # Record search query for analytics (if authenticated)
        if request.user.is_authenticated and query_text:
            UserSearchQuery.objects.create(
                user=request.user, query_text=query_text, results_count=total_results
            )
        # For anonymous users, we could store search with session_id

        return Response(response_data)


class RecommendationAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RecommendationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        product_id = data.get("product_id")
        category_id = data.get("category_id")
        limit = data.get("limit", 5)

        # Check cache first
        if product_id:
            cached_data = cached_recommendations("product", product_id, limit)
            if cached_data:
                # Record impressions even for cached results
                self._record_recommendation_events(
                    request, cached_data, "similar_products"
                )
                return Response(cached_data)
        elif category_id:
            cached_data = cached_recommendations("category", category_id, limit)
            if cached_data:
                self._record_recommendation_events(
                    request, cached_data, "category_recommendations"
                )
                return Response(cached_data)

        # If not in cache, get recommendations
        if product_id:
            return self.get_similar_products(request, product_id, limit)
        elif category_id:
            return self.get_category_recommendations(request, category_id, limit)

    def get_similar_products(self, request, product_id, limit):
        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response(
                {"detail": "Product not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # First, try to get pre-computed similar products
        similar_products = (
            Product.objects.filter(
                Q(similarities_as_b__product_a=product)
                | Q(similarities_as_a__product_b=product),
                is_active=True,
            )
            .distinct()
            .annotate(similarity=F("similarities_as_b__similarity_score"))
            .order_by("-similarity")[:limit]
        )

        # If no pre-computed similarities, use category and attributes
        if not similar_products:
            similar_products = (
                Product.objects.filter(category=product.category, is_active=True)
                .exclude(id=product.id)
                .order_by("-created_at")[:limit]
            )

        # Serialize results
        results = ProductSerializer(similar_products, many=True).data

        # Cache results
        cache_recommendations("product", product_id, results, limit)

        # Record recommendation impressions
        self._record_recommendation_events(request, results, "similar_products")

        return Response(results)

    def get_category_recommendations(self, request, category_id, limit):
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response(
                {"detail": "Category not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Get top-rated products in category
        top_products = (
            Product.objects.filter(category=category, is_active=True)
            .annotate(avg_rating=Avg("reviews__rating"))
            .order_by("-avg_rating")[:limit]
        )

        # Serialize results
        results = ProductSerializer(top_products, many=True).data

        # Cache results
        cache_recommendations("category", category_id, results, limit)

        # Record recommendation impressions
        self._record_recommendation_events(request, results, "category_recommendations")

        return Response(results)

    def _record_recommendation_events(self, request, results, source):
        """Record recommendation impression events"""
        if not results:
            return

        events = []
        for position, product_data in enumerate(results):
            event = RecommendationEvent(
                user=request.user if request.user.is_authenticated else None,
                session_id=(
                    request.session.session_key if hasattr(request, "session") else None
                ),
                product_id=product_data["id"],
                event_type="impression",
                source=source,
                position=position,
            )
            events.append(event)

        # Bulk create events
        if events:
            RecommendationEvent.objects.bulk_create(events)


class RecommendationEventAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RecommendationEventSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Create a click event
        event = serializer.save(
            user=request.user if request.user.is_authenticated else None,
            session_id=(
                request.session.session_key if hasattr(request, "session") else None
            ),
            event_type="click",
        )

        return Response({"detail": "Event recorded"}, status=status.HTTP_201_CREATED)
        results = ProductSerializer(queryset, many=True).data

        # Prepare response
        response_data = {
            "results": results,
            "total": total_results,
            "page": page,
            "limit": limit,
            "pages": (total_results + limit - 1) // limit,  # Ceiling division
        }

        # Cache the search results
        if query_text:
            cache_search_results(query_text, response_data, cache_filters)

        # Record search query for analytics (if authenticated)
        if request.user.is_authenticated and query_text:
            UserSearchQuery.objects.create(
                user=request.user, query_text=query_text, results_count=total_results
            )
        # For anonymous users, we could store search with session_id

        return Response(response_data)


class RecommendationAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RecommendationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        product_id = data.get("product_id")
        category_id = data.get("category_id")
        limit = data.get("limit", 5)

        # Check cache first
        if product_id:
            cached_data = cached_recommendations("product", product_id, limit)
            if cached_data:
                # Record impressions even for cached results
                self._record_recommendation_events(
                    request, cached_data, "similar_products"
                )
                return Response(cached_data)
        elif category_id:
            cached_data = cached_recommendations("category", category_id, limit)
            if cached_data:
                self._record_recommendation_events(
                    request, cached_data, "category_recommendations"
                )
                return Response(cached_data)

        # If not in cache, get recommendations
        if product_id:
            return self.get_similar_products(request, product_id, limit)
        elif category_id:
            return self.get_category_recommendations(request, category_id, limit)

    def get_similar_products(self, request, product_id, limit):
        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response(
                {"detail": "Product not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # First, try to get pre-computed similar products
        similar_products = (
            Product.objects.filter(
                Q(similarities_as_b__product_a=product)
                | Q(similarities_as_a__product_b=product),
                is_active=True,
            )
            .distinct()
            .annotate(similarity=F("similarities_as_b__similarity_score"))
            .order_by("-similarity")[:limit]
        )

        # If no pre-computed similarities, use category and attributes
        if not similar_products:
            similar_products = (
                Product.objects.filter(category=product.category, is_active=True)
                .exclude(id=product.id)
                .order_by("-created_at")[:limit]
            )

        # Serialize results
        results = ProductSerializer(similar_products, many=True).data

        # Cache results
        cache_recommendations("product", product_id, results, limit)

        # Record recommendation impressions
        self._record_recommendation_events(request, results, "similar_products")

        return Response(results)

    def get_category_recommendations(self, request, category_id, limit):
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response(
                {"detail": "Category not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Get top-rated products in category
        top_products = (
            Product.objects.filter(category=category, is_active=True)
            .annotate(avg_rating=Avg("reviews__rating"))
            .order_by("-avg_rating")[:limit]
        )

        # Serialize results
