from django.db import models
from django.contrib.auth import get_user_model
from apps.products.models import Product

User = get_user_model()


class RecentlyViewed(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="recently_viewed"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "product"]
        ordering = ["-viewed_at"]
        verbose_name = "Recently Viewed Product"
        verbose_name_plural = "Recently Viewed Products"

    def __str__(self):
        return f"{self.product.name} viewed by {self.user.email}"

    @classmethod
    def add_product_view(cls, user, product, max_items=10):
        """
        Record that a user viewed a product.
        Keep only the most recent max_items for each user.
        """
        if not user.is_authenticated:
            return None

        # Update or create the viewed product record
        viewed_item, created = cls.objects.update_or_create(
            user=user, product=product, defaults={"viewed_at": models.functions.Now()}
        )

        # Limit the number of recently viewed items
        if created and cls.objects.filter(user=user).count() > max_items:
            # Delete the oldest viewed item
            oldest = cls.objects.filter(user=user).order_by("viewed_at").first()
            if oldest:
                oldest.delete()

        return viewed_item
