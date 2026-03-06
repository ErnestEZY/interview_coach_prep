import os
import diskcache

# Initialize disk cache in the backend/cache_data directory
# We set a size limit to prevent it from filling up the disk in the Render container
# size_limit is in bytes. 500MB = 500 * 1024 * 1024
cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache_data")
os.makedirs(cache_dir, exist_ok=True)

cache = diskcache.Cache(cache_dir, size_limit=500 * 1024 * 1024)

def memoize(expire=3600):
    """
    Decorator to cache function results on disk.
    Defaults to 1 hour expiration.
    """
    return cache.memoize(expire=expire)

def clear_cache():
    """Clear all cached data."""
    cache.clear()
