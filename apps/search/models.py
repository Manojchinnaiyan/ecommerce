from django.db import models
from django.contrib.auth import get_user_model
from apps.products.models import Product

User = get_user_model()


class SearchQuery(models.Model):
    """Store user search queries for analytics and recommendations"""

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="search_queries",
    )
    query_text = models.CharField(max_length=255)
    session_id = models.CharField(
        max_length=255, null=True, blank=True
    )  # For anonymous users
    created_at = models.DateTimeField(auto_now_add=True)
    results_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "Search Queries"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.query_text} ({self.created_at})"


class ProductView(models.Model):
    """Track product views for recommendations"""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_id = models.CharField(
        max_length=255, null=True, blank=True
    )  # For anonymous users
    viewed_at = models.DateTimeField(auto_now_add=True)
    viewed_from_search = models.BooleanField(default=False)
    search_query = models.ForeignKey(
        SearchQuery,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_views",
    )

    class Meta:
        ordering = ["-viewed_at"]

    def __str__(self):
        user_info = self.user.email if self.user else self.session_id
        return f"{self.product.name} viewed by {user_info}"


class RecommendationEvent(models.Model):
    """Track recommendations shown to users and if they were clicked"""

    EVENT_TYPES = (
        ("impression", "Impression"),
        ("click", "Click"),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_id = models.CharField(
        max_length=255, null=True, blank=True
    )  # For anonymous users
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="recommendation_events"
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    source = models.CharField(
        max_length=50,
        help_text="Source of recommendation (e.g., similar_products, recently_viewed)",
    )
    position = models.PositiveSmallIntegerField(
        help_text="Position in recommendation list"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        user_info = self.user.email if self.user else self.session_id
        return f"{self.event_type} for {self.product.name} to {user_info}"


class ProductSimilarity(models.Model):
    """Store pre-computed product similarity scores"""

    product_a = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="similarities_as_a"
    )
    product_b = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="similarities_as_b"
    )
    similarity_score = models.FloatField(
        help_text="Similarity score between products (0-1)"
    )
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["product_a", "product_b"]]
        ordering = ["-similarity_score"]

    def __str__(self):
        return f"Similarity between {self.product_a.name} and {self.product_b.name}: {self.similarity_score}"
