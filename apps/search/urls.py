from django.urls import path
from .views import SearchAPIView, RecommendationAPIView, RecommendationEventAPIView

urlpatterns = [
    path("search/", SearchAPIView.as_view(), name="advanced-search"),
    path("recommendations/", RecommendationAPIView.as_view(), name="recommendations"),
    path(
        "recommendation-event/",
        RecommendationEventAPIView.as_view(),
        name="recommendation-event",
    ),
]
