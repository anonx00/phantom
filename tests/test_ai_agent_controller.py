"""
Tests for AIAgentController - Budget and quota enforcement.

These tests ensure the agent respects Twitter API limits and GCP budget constraints.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock environment variables before importing
os.environ["PROJECT_ID"] = "test-project"
os.environ["REGION"] = "us-central1"
os.environ["TIMEZONE"] = "UTC"

# Mock GCP dependencies
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.firestore"] = MagicMock()
sys.modules["google.cloud.secretmanager"] = MagicMock()

# Mock memory_system
mock_vector_memory = MagicMock()
sys.modules["memory_system"] = MagicMock()
sys.modules["memory_system"].VectorMemory = mock_vector_memory


class TestTTLCache(unittest.TestCase):
    """Test the TTL cache implementation."""

    def test_cache_set_and_get(self):
        from ai_agent_controller import TTLCache
        cache = TTLCache(ttl_seconds=60)

        cache.set("key1", "value1")
        self.assertEqual(cache.get("key1"), "value1")

    def test_cache_miss(self):
        from ai_agent_controller import TTLCache
        cache = TTLCache(ttl_seconds=60)

        self.assertIsNone(cache.get("nonexistent"))

    def test_cache_expiry(self):
        from ai_agent_controller import TTLCache
        import time

        cache = TTLCache(ttl_seconds=0.1)  # 100ms TTL
        cache.set("key1", "value1")

        # Should be cached immediately
        self.assertEqual(cache.get("key1"), "value1")

        # Wait for expiry
        time.sleep(0.15)
        self.assertIsNone(cache.get("key1"))

    def test_cache_invalidate_specific(self):
        from ai_agent_controller import TTLCache
        cache = TTLCache(ttl_seconds=60)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.invalidate("key1")

        self.assertIsNone(cache.get("key1"))
        self.assertEqual(cache.get("key2"), "value2")

    def test_cache_invalidate_all(self):
        from ai_agent_controller import TTLCache
        cache = TTLCache(ttl_seconds=60)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.invalidate()

        self.assertIsNone(cache.get("key1"))
        self.assertIsNone(cache.get("key2"))


class TestAIAgentController(unittest.TestCase):
    """Test the AIAgentController budget enforcement."""

    def setUp(self):
        # Import after mocking
        from ai_agent_controller import AIAgentController

        # Create controller with mocked dependencies
        with patch("ai_agent_controller.firestore.Client") as mock_firestore:
            self.mock_db = mock_firestore.return_value
            self.mock_collection = MagicMock()
            self.mock_db.collection.return_value = self.mock_collection

            # Mock document that doesn't exist (new day)
            mock_doc = MagicMock()
            mock_doc.exists = False
            mock_doc_ref = MagicMock()
            mock_doc_ref.get.return_value = mock_doc
            self.mock_collection.document.return_value = mock_doc_ref

            self.controller = AIAgentController("test-project")

    def test_can_create_post_under_limit(self):
        """Should allow posting when under daily limit."""
        self.controller._daily_stats = {"posts_created": 5}

        can_post, reason = self.controller.can_create_post()

        self.assertTrue(can_post)
        self.assertIn("5/17", reason)

    def test_can_create_post_at_limit(self):
        """Should deny posting when at daily limit."""
        self.controller._daily_stats = {"posts_created": 17}

        can_post, reason = self.controller.can_create_post()

        self.assertFalse(can_post)
        self.assertIn("17", reason)

    def test_can_create_video_under_limit(self):
        """Should allow video generation when under limit."""
        self.controller._daily_stats = {"videos_generated": 3}

        can_create, reason = self.controller.can_create_video()

        self.assertTrue(can_create)
        self.assertIn("3/10", reason)

    def test_can_create_video_at_limit(self):
        """Should deny video generation when at limit."""
        self.controller._daily_stats = {"videos_generated": 10}

        can_create, reason = self.controller.can_create_video()

        self.assertFalse(can_create)
        self.assertIn("10", reason)

    def test_can_create_image_under_limit(self):
        """Should allow image generation when under limit."""
        self.controller._daily_stats = {"images_generated": 2}

        can_create, reason = self.controller.can_create_image()

        self.assertTrue(can_create)
        self.assertIn("2/4", reason)

    def test_can_create_image_at_limit(self):
        """Should deny image generation when at limit."""
        self.controller._daily_stats = {"images_generated": 4}

        can_create, reason = self.controller.can_create_image()

        self.assertFalse(can_create)
        self.assertIn("4", reason)

    def test_can_reply_under_limit(self):
        """Should allow reply when under limits."""
        self.controller._daily_stats = {
            "replies_created": 1,
            "posts_created": 5
        }

        can_reply, reason = self.controller.can_reply()

        self.assertTrue(can_reply)

    def test_can_reply_at_reply_target(self):
        """Should deny reply when at reply target."""
        self.controller._daily_stats = {
            "replies_created": 3,
            "posts_created": 5
        }

        can_reply, reason = self.controller.can_reply()

        self.assertFalse(can_reply)
        self.assertIn("3/3", reason)

    def test_can_reply_at_total_limit(self):
        """Should deny reply when total tweets at limit."""
        self.controller._daily_stats = {
            "replies_created": 2,
            "posts_created": 15
        }

        can_reply, reason = self.controller.can_reply()

        self.assertFalse(can_reply)
        self.assertIn("17", reason)

    def test_record_post_created_increments(self):
        """Should increment post count when recording."""
        self.controller._daily_stats = {"posts_created": 5}

        self.controller.record_post_created("text")

        self.assertEqual(self.controller._daily_stats["posts_created"], 6)

    def test_record_video_increments_both(self):
        """Should increment both posts and videos for video type."""
        self.controller._daily_stats = {
            "posts_created": 5,
            "videos_generated": 2
        }

        self.controller.record_post_created("video")

        self.assertEqual(self.controller._daily_stats["posts_created"], 6)
        self.assertEqual(self.controller._daily_stats["videos_generated"], 3)

    def test_get_daily_summary(self):
        """Should return formatted daily summary."""
        self.controller._daily_stats = {
            "posts_created": 5,
            "replies_created": 2,
            "videos_generated": 1,
            "images_generated": 2
        }

        summary = self.controller.get_daily_summary()

        self.assertEqual(summary["posts"], 5)
        self.assertEqual(summary["replies"], 2)
        self.assertEqual(summary["twitter_quota_used"], "7/17")
        self.assertEqual(summary["video_budget_used"], "1/10")


class TestZeroWasteContentStrategy(unittest.TestCase):
    """Test the zero-waste content strategy."""

    def test_pick_best_story_single(self):
        """Should return single story without AI call."""
        from ai_agent_controller import ZeroWasteContentStrategy

        stories = [{"title": "Only Story", "context": "Test"}]

        result = ZeroWasteContentStrategy.pick_best_story(stories, lambda x: "")

        self.assertEqual(result["title"], "Only Story")

    def test_pick_best_story_empty(self):
        """Should return None for empty list."""
        from ai_agent_controller import ZeroWasteContentStrategy

        result = ZeroWasteContentStrategy.pick_best_story([], lambda x: "")

        self.assertIsNone(result)

    def test_should_create_media_video_allowed(self):
        """Should allow video when under budget."""
        from ai_agent_controller import ZeroWasteContentStrategy

        mock_controller = MagicMock()
        mock_controller.can_create_video.return_value = (True, "OK")

        result = ZeroWasteContentStrategy.should_create_media("video", mock_controller)

        self.assertTrue(result)

    def test_should_create_media_video_denied(self):
        """Should deny video when over budget."""
        from ai_agent_controller import ZeroWasteContentStrategy

        mock_controller = MagicMock()
        mock_controller.can_create_video.return_value = (False, "Limit reached")

        result = ZeroWasteContentStrategy.should_create_media("video", mock_controller)

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
