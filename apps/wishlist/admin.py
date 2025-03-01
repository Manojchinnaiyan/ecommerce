from django.contrib import admin
from .models import Wishlist, WishlistItem


class WishlistItemInline(admin.TabularInline):
    model = WishlistItem
    extra = 0
    raw_id_fields = ("product",)


class WishlistAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "total_items", "created_at", "updated_at")
    search_fields = ("user__email",)
    inlines = [WishlistItemInline]
    readonly_fields = ("created_at", "updated_at")


class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("id", "wishlist", "product", "created_at")
    list_filter = ("created_at",)
    search_fields = ("wishlist__user__email", "product__name")
    readonly_fields = ("created_at",)


admin.site.register(Wishlist, WishlistAdmin)
admin.site.register(WishlistItem, WishlistItemAdmin)
