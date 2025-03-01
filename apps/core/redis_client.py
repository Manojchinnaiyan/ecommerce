from django_redis.client import DefaultClient


class CustomRedisClient(DefaultClient):
    """
    Custom Redis client that adds support for pattern-based key deletion
    """

    def delete_pattern(self, pattern):
        """
        Delete all keys matching pattern
        """
        pattern = self.make_key(pattern)
        keys = self.get_client().keys(pattern)
        if keys:
            self.get_client().delete(*keys)
        return len(keys)
