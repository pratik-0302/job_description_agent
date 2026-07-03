import unittest
import time
from unittest.mock import MagicMock

from src.config import AppConfig
from src.retrieval.query_cache import QueryResultCache
from src.ingestion.automatic_indexer import AutomaticIndexingModule
from src.ingestion.models import PipelineEvent


class TestPerformanceCache(unittest.TestCase):
    def test_lru_eviction(self):
        # Cache capacity limit of 3
        cache = QueryResultCache(max_size=3, ttl_seconds=60.0)
        cache.set("key1", "val1")
        cache.set("key2", "val2")
        cache.set("key3", "val3")

        # Verify all keys exist
        self.assertEqual(cache.get("key1"), "val1")
        self.assertEqual(cache.get("key2"), "val2")
        self.assertEqual(cache.get("key3"), "val3")

        # Adding a 4th key triggers LRU eviction.
        # Since we recently accessed key1, key2 is the oldest (LRU).
        cache.set("key4", "val4")
        
        # Verify oldest key (key1) was evicted
        self.assertIsNone(cache.get("key1"))
        self.assertEqual(cache.get("key2"), "val2")
        self.assertEqual(cache.get("key3"), "val3")
        self.assertEqual(cache.get("key4"), "val4")

    def test_ttl_expiry(self):
        # Cache with 0.05 seconds TTL
        cache = QueryResultCache(max_size=10, ttl_seconds=0.05)
        cache.set("key", "value")
        self.assertEqual(cache.get("key"), "value")

        # Wait for TTL to expire
        time.sleep(0.06)
        self.assertIsNone(cache.get("key"))

    def test_cache_invalidation_upon_indexing_event(self):
        query_cache = QueryResultCache(max_size=10, ttl_seconds=60.0)
        analytics_cache = QueryResultCache(max_size=10, ttl_seconds=60.0)

        query_cache.set("q1", "result1")
        analytics_cache.set("summary", "stats1")

        # Instantiate indexer with caches
        indexer = AutomaticIndexingModule(
            cfg=AppConfig(),
            db_manager=MagicMock(),
            chroma_manager=MagicMock(),
            embedding_pipeline=MagicMock(),
            event_queue=MagicMock(),
            query_cache=query_cache,
            analytics_cache=analytics_cache
        )

        # Confirm caches are populated initially
        self.assertEqual(query_cache.get("q1"), "result1")
        self.assertEqual(analytics_cache.get("summary"), "stats1")

        # Trigger invalidation method
        indexer._invalidate_caches()

        # Verify caches are empty
        self.assertIsNone(query_cache.get("q1"))
        self.assertIsNone(analytics_cache.get("summary"))


if __name__ == "__main__":
    unittest.main()
