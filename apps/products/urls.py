from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, ProductImageViewSet, ReviewViewSet
from .recently_viewed_views import RecentlyViewedViewSet

router = DefaultRouter()
router.register(r"categories", CategoryViewSet)
router.register(r"products", ProductViewSet)
router.register(r"images", ProductImageViewSet)
router.register(r"reviews", ReviewViewSet, basename="review")
router.register(r"recently-viewed", RecentlyViewedViewSet, basename="recently-viewed")

urlpatterns = [
    path("", include(router.urls)),
]
