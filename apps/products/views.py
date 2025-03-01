from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Avg
from .models import Category, Product, ProductImage, Review
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    ProductDetailSerializer,
    ProductCreateSerializer,
    ProductImageSerializer,
    ReviewSerializer,
)
from .filters import ProductFilter
from .recently_viewed_models import RecentlyViewed
from apps.core.cache import (
    cached_product_detail,
    cache_product_detail,
    invalidate_product_cache,
    cached_product_list,
    cache_product_list,
    cached_category_products,
    cache_category_products,
    cached_recommendations,
    cache_recommendations,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = "slug"
    permission_classes = [permissions.IsAdminUser]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return super().get_permissions()

    def list(self, request, *args, **kwargs):
        # Categories rarely change, so we'll cache them for longer periods
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # Get products in this category - check cache first
        filters = request.query_params.dict()
        cached_products = cached_category_products(instance.id, filters)

        if cached_products:
            return Response({"category": serializer.data, "products": cached_products})

        # If not cached, get from database
        products = Product.objects.filter(category=instance, is_active=True).order_by(
            "-created_at"
        )

        # Apply filters
        products_serializer = ProductSerializer(products, many=True)
        products_data = products_serializer.data

        # Cache the results
        cache_category_products(instance.id, products_data, filters)

        return Response({"category": serializer.data, "products": products_data})


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(is_active=True)
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ProductFilter
    search_fields = ["name", "description", "category__name"]
    ordering_fields = ["created_at", "price", "name"]
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer
        elif self.action == "create":
            return ProductCreateSerializer
        return ProductSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "recommended"]:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def list(self, request, *args, **kwargs):
        # Check cache first
        filters = request.query_params.dict()
        cached_data = cached_product_list(filters)

        if cached_data:
            return Response(cached_data)

        # If not cached, get from database
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            # Cache the response data
            cache_product_list(response.data, filters)
            return response

        serializer = self.get_serializer(queryset, many=True)
        response_data = serializer.data
        # Cache the response data
        cache_product_list(response_data, filters)
        return Response(response_data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        # Check cache
        cached_data = cached_product_detail(instance.id)
        if cached_data:
            # Even with cached data, record the view
            if request.user.is_authenticated:
                RecentlyViewed.add_product_view(request.user, instance)
            return Response(cached_data)

        # Record this product view in recently viewed
        if request.user.is_authenticated:
            RecentlyViewed.add_product_view(request.user, instance)

        serializer = self.get_serializer(instance)
        data = serializer.data

        # Cache the data
        cache_product_detail(instance.id, data)

        return Response(data)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        # No need to invalidate cache for a new product
        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        response = super().update(request, *args, **kwargs)
        # Invalidate cache for this product
        invalidate_product_cache(instance.id)
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        response = super().destroy(request, *args, **kwargs)
        # Invalidate cache for this product
        invalidate_product_cache(instance.id)
        return response

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def review(self, request, slug=None):
        product = self.get_object()
        serializer = ReviewSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            # Check if user already reviewed this product
            if Review.objects.filter(product=product, user=request.user).exists():
                return Response(
                    {"detail": "You have already reviewed this product"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer.save(product=product)
            # Invalidate product cache as the rating may have changed
            invalidate_product_cache(product.id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def upload_images(self, request, slug=None):
        product = self.get_object()
        images = request.FILES.getlist("images")

        if not images:
            return Response(
                {"detail": "No images provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer_data = []
        for image in images:
            is_primary = request.data.get("is_primary", "false").lower() == "true"
            product_image = ProductImage.objects.create(
                product=product, image=image, is_primary=is_primary
            )
            serializer_data.append(ProductImageSerializer(product_image).data)

        # Invalidate product cache as images have changed
        invalidate_product_cache(product.id)

        return Response(serializer_data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def recommended(self, request):
        """Get recommended products based on user's purchase history or popular products"""
        user = request.user
        product_id = request.query_params.get("product_id")
        limit = int(request.query_params.get("limit", 5))

        # Check cache first
        if product_id:
            cached_data = cached_recommendations("product", product_id, limit)
            if cached_data:
                return Response(cached_data)
        elif user.is_authenticated:
            cached_data = cached_recommendations("user", user.id, limit)
            if cached_data:
                return Response(cached_data)
        else:
            cached_data = cached_recommendations("popular", "all", limit)
            if cached_data:
                return Response(cached_data)

        # If not in cache, generate recommendations
        products = []

        if product_id:
            # Get similar products for the given product
            try:
                product = Product.objects.get(id=product_id)
                # Get pre-computed similar products
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

                if not similar_products:
                    # Fallback to category-based
                    similar_products = (
                        Product.objects.filter(
                            category=product.category, is_active=True
                        )
                        .exclude(id=product.id)
                        .order_by("-created_at")[:limit]
                    )

                products = similar_products
                cache_key_type = "product"
                cache_key_id = product_id

            except Product.DoesNotExist:
                # Fallback to popular products
                products = Product.objects.filter(is_active=True).order_by(
                    "-reviews__rating"
                )[:limit]
                cache_key_type = "popular"
                cache_key_id = "all"

        elif user.is_authenticated:
            # Get products from user's purchase history
            purchased_products = Product.objects.filter(
                orderitem__order__user=user
            ).distinct()

            if purchased_products.exists():
                # Get products from the same categories
                categories = Category.objects.filter(
                    products__in=purchased_products
                ).distinct()

                products = (
                    Product.objects.filter(category__in=categories)
                    .exclude(id__in=purchased_products.values_list("id", flat=True))
                    .order_by("-created_at")[:limit]
                )

                cache_key_type = "user"
                cache_key_id = user.id
            else:
                # Fallback to popular products
                products = Product.objects.filter(is_active=True).order_by(
                    "-reviews__rating"
                )[:limit]
                cache_key_type = "popular"
                cache_key_id = "all"
        else:
            # For anonymous users, return popular products
            products = (
                Product.objects.filter(is_active=True)
                .annotate(avg_rating=Avg("reviews__rating"))
                .order_by("-avg_rating")[:limit]
            )

            cache_key_type = "popular"
            cache_key_id = "all"

        # Serialize results
        serializer = ProductSerializer(products, many=True)
        data = serializer.data

        # Cache the recommendations
        cache_recommendations(cache_key_type, cache_key_id, data, limit)

        return Response(data)


class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        instance = serializer.save()
        # Invalidate product cache
        invalidate_product_cache(instance.product.id)

    def perform_update(self, serializer):
        instance = serializer.save()
        # Invalidate product cache
        invalidate_product_cache(instance.product.id)

    def perform_destroy(self, instance):
        product_id = instance.product.id
        instance.delete()
        # Invalidate product cache
        invalidate_product_cache(product_id)

    @action(detail=True, methods=["post"])
    def set_primary(self, request, pk=None):
        image = self.get_object()
        image.is_primary = True
        image.save()
        # Invalidate product cache
        invalidate_product_cache(image.product.id)
        return Response({"detail": "Image set as primary"})


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Review.objects.all()
        return Review.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        instance = serializer.save()
        # Invalidate product cache as review affects rating
        invalidate_product_cache(instance.product.id)

    def perform_update(self, serializer):
        instance = serializer.save()
        # Invalidate product cache
        invalidate_product_cache(instance.product.id)

    def perform_destroy(self, instance):
        product_id = instance.product.id
        instance.delete()
        # Invalidate product cache
        invalidate_product_cache(product_id)
