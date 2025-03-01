from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, AddressViewSet
from .jwt_views import (
    DecoratedTokenObtainPairView,
    DecoratedTokenRefreshView,
    DecoratedTokenVerifyView,
)

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"addresses", AddressViewSet, basename="address")

urlpatterns = [
    path("", include(router.urls)),
    # JWT Token endpoints with Swagger documentation
    path("token/", DecoratedTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", DecoratedTokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", DecoratedTokenVerifyView.as_view(), name="token_verify"),
]
