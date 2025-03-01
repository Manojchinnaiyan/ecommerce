from django.core.cache import cache
from django.conf import settings
import hashlib
import json

# Cache timeouts (in seconds)
CACHE_TTL = {
    "product_detail": 60 * 15,  # 15 minutes
    "product_list": 60 * 10,  # 10 minutes
    "category_products": 60 * 10,  # 10 minutes
    "search_results": 60 * 5,  # 5 minutes
    "recommendations": 60 * 30,  # 30 minutes
    "user_wishlist": 60 * 5,  # 5 minutes
    "user_cart": 60 * 2,  # 2 minutes
    "recently_viewed": 60 * 5,  # 5 minutes
}


def get_cache_key(prefix, identifier, params=None):
    """
    Generate a consistent cache key

    Args:
        prefix: String prefix for the key
        identifier: Primary identifier (e.g., product_id, user_id)
        params: Optional dictionary of parameters that affect the result

    Returns:
        A string cache key
    """
    key = f"{prefix}:{identifier}"

    if params:
        # Sort params to ensure consistent key generation
        serialized_params = json.dumps(params, sort_keys=True)
        param_hash = hashlib.md5(serialized_params.encode()).hexdigest()
        key = f"{key}:{param_hash}"

    return key


def cached_product_detail(product_id):
    """Get cached product detail or None if not in cache"""
    cache_key = get_cache_key("product", product_id)
    return cache.get(cache_key)


def cache_product_detail(product_id, data):
    """Cache product detail"""
    cache_key = get_cache_key("product", product_id)
    cache.set(cache_key, data, CACHE_TTL["product_detail"])


def invalidate_product_cache(product_id):
    """Invalidate all product-related caches for a specific product"""
    # Invalidate product detail
    cache_key = get_cache_key("product", product_id)
    cache.delete(cache_key)

    # Invalidate product list caches - using wildcard deletion
    cache.delete_pattern("product_list:*")
    cache.delete_pattern("category_products:*")
    cache.delete_pattern("search_results:*")
    cache.delete_pattern("recommendations:*")


def cached_product_list(filters=None):
    """Get cached product list or None if not in cache"""
    cache_key = get_cache_key("product_list", "all", filters)
    return cache.get(cache_key)


def cache_product_list(data, filters=None):
    """Cache product list"""
    cache_key = get_cache_key("product_list", "all", filters)
    cache.set(cache_key, data, CACHE_TTL["product_list"])


def cached_category_products(category_id, filters=None):
    """Get cached category products or None if not in cache"""
    cache_key = get_cache_key("category_products", category_id, filters)
    return cache.get(cache_key)


def cache_category_products(category_id, data, filters=None):
    """Cache category products"""
    cache_key = get_cache_key("category_products", category_id, filters)
    cache.set(cache_key, data, CACHE_TTL["category_products"])


def cached_search_results(query, filters=None):
    """Get cached search results or None if not in cache"""
    # Generate a hash of the query to use as part of the key
    query_hash = hashlib.md5(query.encode()).hexdigest()
    cache_key = get_cache_key("search_results", query_hash, filters)
    return cache.get(cache_key)


def cache_search_results(query, data, filters=None):
    """Cache search results"""
    query_hash = hashlib.md5(query.encode()).hexdigest()
    cache_key = get_cache_key("search_results", query_hash, filters)
    cache.set(cache_key, data, CACHE_TTL["search_results"])


def cached_recommendations(key_type, key_id, limit=5):
    """Get cached recommendations or None if not in cache"""
    filters = {"limit": limit}
    cache_key = get_cache_key(f"recommendations_{key_type}", key_id, filters)
    return cache.get(cache_key)


def cache_recommendations(key_type, key_id, data, limit=5):
    """Cache recommendations"""
    filters = {"limit": limit}
    cache_key = get_cache_key(f"recommendations_{key_type}", key_id, filters)
    cache.set(cache_key, data, CACHE_TTL["recommendations"])


def cached_user_wishlist(user_id):
    """Get cached user wishlist or None if not in cache"""
    cache_key = get_cache_key("wishlist", user_id)
    return cache.get(cache_key)


def cache_user_wishlist(user_id, data):
    """Cache user wishlist"""
    cache_key = get_cache_key("wishlist", user_id)
    cache.set(cache_key, data, CACHE_TTL["user_wishlist"])


def invalidate_user_wishlist(user_id):
    """Invalidate user wishlist cache"""
    cache_key = get_cache_key("wishlist", user_id)
    cache.delete(cache_key)


def cached_user_cart(user_id):
    """Get cached user cart or None if not in cache"""
    cache_key = get_cache_key("cart", user_id)
    return cache.get(cache_key)


def cache_user_cart(user_id, data):
    """Cache user cart"""
    cache_key = get_cache_key("cart", user_id)
    cache.set(cache_key, data, CACHE_TTL["user_cart"])


def invalidate_user_cart(user_id):
    """Invalidate user cart cache"""
    cache_key = get_cache_key("cart", user_id)
    cache.delete(cache_key)


def cached_recently_viewed(user_id):
    """Get cached recently viewed products or None if not in cache"""
    cache_key = get_cache_key("recently_viewed", user_id)
    return cache.get(cache_key)


def cache_recently_viewed(user_id, data):
    """Cache recently viewed products"""
    cache_key = get_cache_key("recently_viewed", user_id)
    cache.set(cache_key, data, CACHE_TTL["recently_viewed"])


def invalidate_recently_viewed(user_id):
    """Invalidate recently viewed products cache"""
    cache_key = get_cache_key("recently_viewed", user_id)
    cache.delete(cache_key)
