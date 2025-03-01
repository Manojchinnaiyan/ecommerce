from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from .views import OrderViewSet, OrderItemViewSet

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="order")

# Nested router for order items
order_items_router = routers.NestedSimpleRouter(router, r"orders", lookup="order")
order_items_router.register(r"items", OrderItemViewSet, basename="order-items")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(order_items_router.urls)),
]
