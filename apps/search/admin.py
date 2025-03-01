from django.contrib import admin
from .models import SearchQuery, ProductView, RecommendationEvent, ProductSimilarity


class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ("query_text", "user", "results_count", "created_at")
    list_filter = ("created_at",)
    search_fields = ("query_text", "user__email")
    readonly_fields = ("created_at",)


class ProductViewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "viewed_at", "viewed_from_search")
    list_filter = ("viewed_at", "viewed_from_search")
    search_fields = ("product__name", "user__email")
    readonly_fields = ("viewed_at",)


class RecommendationEventAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "event_type", "source", "position", "created_at")
    list_filter = ("event_type", "source", "created_at")
    search_fields = ("product__name", "user__email")
    readonly_fields = ("created_at",)


class ProductSimilarityAdmin(admin.ModelAdmin):
    list_display = ("product_a", "product_b", "similarity_score", "last_updated")
    list_filter = ("last_updated",)
    search_fields = ("product_a__name", "product_b__name")
    readonly_fields = ("last_updated",)


admin.site.register(SearchQuery, SearchQueryAdmin)
admin.site.register(ProductView, ProductViewAdmin)
admin.site.register(RecommendationEvent, RecommendationEventAdmin)
admin.site.register(ProductSimilarity, ProductSimilarityAdmin)
