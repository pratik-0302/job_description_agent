import time
import logging
from collections import OrderedDict
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class QueryResultCache:
    def __init__(self, max_size: int = 100, ttl_seconds: float = 300.0):
        self.max_size = max_size
        self.ttl = ttl_seconds
        self.cache: OrderedDict = OrderedDict()  # key -> (value, expiry_time)

    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
            
        value, expiry = self.cache[key]
        if time.time() > expiry:
            del self.cache[key]
            logger.debug(f"Cache expired for key: {key}")
            return None
            
        # Move to end (LRU)
        self.cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any):
        if key in self.cache:
            del self.cache[key]
        elif len(self.cache) >= self.max_size:
            # Evict oldest (first item in OrderedDict)
            oldest_key, _ = self.cache.popitem(last=False)
            logger.debug(f"Cache eviction triggered. Evicted key: {oldest_key}")
            
        expiry = time.time() + self.ttl
        self.cache[key] = (value, expiry)

    def clear(self):
        self.cache.clear()
        logger.info("In-memory result cache cleared successfully.")
