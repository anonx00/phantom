"""
Data Retention System - Keep backend clean while maintaining AI context

Automatically cleans up old data to prevent Firestore from growing indefinitely.
Keeps enough recent context for AI to be aware of its history.

Retention Policies:
- Post history: 30 days (AI needs to know what it posted)
- Scraped replies: 7 days (only need recent for dedup)
- Budget tracking: 90 days (for monthly analysis)
- AI memory/interactions: 14 days (recent context only)
- Vector embeddings: 30 days (semantic search needs history)

Runs automatically on each job execution.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from google.cloud import firestore
import pytz

logger = logging.getLogger(__name__)


class DataRetentionManager:
    """Manages data lifecycle and cleanup."""

    # Retention periods (in days)
    RETENTION_POLICIES = {
        "post_history": 30,      # Keep 30 days of posts
        "scraped_replies": 7,    # Keep 7 days of scraped replies
        "budget_tracking": 90,   # Keep 90 days of budget data
        "ai_memory": 14,         # Keep 14 days of AI memory
        "interactions": 14,      # Keep 14 days of interactions
        "vector_memory": 30,     # Keep 30 days of embeddings
    }

    def __init__(self, project_id: str, timezone: str = "Australia/Perth"):
        self.project_id = project_id
        self.db = firestore.Client(project=project_id)
        self.tz = pytz.timezone(timezone)
        self.stats = {
            "deleted": 0,
            "kept": 0,
            "errors": 0
        }

    def _get_cutoff_date(self, days: int) -> datetime:
        """Get cutoff datetime for retention."""
        return datetime.now(self.tz) - timedelta(days=days)

    def cleanup_collection(self, collection_name: str, date_field: str,
                          retention_days: int, batch_size: int = 100) -> int:
        """
        Delete documents older than retention period.

        Args:
            collection_name: Firestore collection name
            date_field: Field containing the timestamp
            retention_days: Number of days to keep
            batch_size: Documents to delete per batch

        Returns:
            Number of documents deleted
        """
        deleted_count = 0
        cutoff = self._get_cutoff_date(retention_days)

        try:
            collection = self.db.collection(collection_name)

            # Query for old documents
            query = collection.where(date_field, "<", cutoff).limit(batch_size)
            docs = query.stream()

            # Delete in batches
            batch = self.db.batch()
            batch_count = 0

            for doc in docs:
                batch.delete(doc.reference)
                batch_count += 1
                deleted_count += 1

                # Commit batch when full
                if batch_count >= batch_size:
                    batch.commit()
                    batch = self.db.batch()
                    batch_count = 0

            # Commit remaining
            if batch_count > 0:
                batch.commit()

            if deleted_count > 0:
                logger.info(f"🧹 Cleaned {deleted_count} old docs from {collection_name}")

        except Exception as e:
            logger.error(f"Failed to cleanup {collection_name}: {e}")
            self.stats["errors"] += 1

        self.stats["deleted"] += deleted_count
        return deleted_count

    def cleanup_budget_tracking(self) -> int:
        """Clean up old daily budget tracking docs."""
        deleted = 0
        cutoff_date = (datetime.now(self.tz) - timedelta(
            days=self.RETENTION_POLICIES["budget_tracking"]
        )).strftime("%Y-%m-%d")

        try:
            collection = self.db.collection("budget_tracking")
            docs = collection.stream()

            batch = self.db.batch()
            batch_count = 0

            for doc in docs:
                doc_id = doc.id
                # Budget docs are named like "daily_2024-01-15"
                if doc_id.startswith("daily_"):
                    doc_date = doc_id.replace("daily_", "")
                    if doc_date < cutoff_date:
                        batch.delete(doc.reference)
                        batch_count += 1
                        deleted += 1

                        if batch_count >= 100:
                            batch.commit()
                            batch = self.db.batch()
                            batch_count = 0

            if batch_count > 0:
                batch.commit()

            if deleted > 0:
                logger.info(f"🧹 Cleaned {deleted} old budget tracking docs")

        except Exception as e:
            logger.error(f"Failed to cleanup budget tracking: {e}")

        return deleted

    def cleanup_all(self) -> Dict:
        """
        Run all cleanup tasks.

        Returns dict with cleanup statistics.
        """
        logger.info("🧹 Starting data retention cleanup...")
        start_time = datetime.now()

        results = {
            "post_history": 0,
            "scraped_replies": 0,
            "budget_tracking": 0,
            "ai_memory": 0,
        }

        # Cleanup post history (30 days)
        results["post_history"] = self.cleanup_collection(
            "post_history",
            "timestamp",
            self.RETENTION_POLICIES["post_history"]
        )

        # Cleanup scraped replies (7 days)
        results["scraped_replies"] = self.cleanup_collection(
            "scraped_replies",
            "scraped_at",
            self.RETENTION_POLICIES["scraped_replies"]
        )

        # Cleanup AI memory (14 days)
        results["ai_memory"] = self.cleanup_collection(
            "ai_memory",
            "timestamp",
            self.RETENTION_POLICIES["ai_memory"]
        )

        # Cleanup budget tracking (90 days)
        results["budget_tracking"] = self.cleanup_budget_tracking()

        # Summary
        total_deleted = sum(results.values())
        duration = (datetime.now() - start_time).total_seconds()

        logger.info(f"✅ Cleanup complete: {total_deleted} docs deleted in {duration:.1f}s")
        logger.info(f"   Post history: {results['post_history']}")
        logger.info(f"   Scraped replies: {results['scraped_replies']}")
        logger.info(f"   AI memory: {results['ai_memory']}")
        logger.info(f"   Budget tracking: {results['budget_tracking']}")

        return {
            "total_deleted": total_deleted,
            "by_collection": results,
            "duration_seconds": duration,
            "errors": self.stats["errors"]
        }

    def get_storage_stats(self) -> Dict:
        """Get current storage statistics."""
        stats = {}

        collections = [
            "post_history",
            "scraped_replies",
            "budget_tracking",
            "ai_memory",
            "interactions"
        ]

        for coll_name in collections:
            try:
                # Count documents (limited query)
                docs = list(self.db.collection(coll_name).limit(1000).stream())
                stats[coll_name] = len(docs)
            except Exception:
                stats[coll_name] = -1

        return stats


class AIContextManager:
    """
    Manages AI context - what the AI knows about itself.

    Provides the AI with:
    - Recent post history (what did I post?)
    - Engagement stats (how did posts perform?)
    - Current trends (what's happening now?)
    - Personality reminders (who am I?)
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.db = firestore.Client(project=project_id)

    def get_recent_posts(self, limit: int = 10) -> List[Dict]:
        """Get recent posts for context."""
        posts = []
        try:
            query = (self.db.collection("post_history")
                    .order_by("timestamp", direction=firestore.Query.DESCENDING)
                    .limit(limit))

            for doc in query.stream():
                data = doc.to_dict()
                posts.append({
                    "content": data.get("content", "")[:200],
                    "type": data.get("type", "text"),
                    "timestamp": data.get("timestamp"),
                    "success": data.get("success", True)
                })
        except Exception as e:
            logger.warning(f"Failed to get recent posts: {e}")

        return posts

    def get_engagement_summary(self) -> Dict:
        """Get engagement summary for AI awareness."""
        try:
            # Get last 7 days of budget tracking
            today = datetime.now()
            stats = {
                "total_posts_7d": 0,
                "total_replies_7d": 0,
                "videos_7d": 0,
                "avg_posts_per_day": 0
            }

            for i in range(7):
                date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
                doc = self.db.collection("budget_tracking").document(f"daily_{date_str}").get()

                if doc.exists:
                    data = doc.to_dict()
                    stats["total_posts_7d"] += data.get("posts_created", 0)
                    stats["total_replies_7d"] += data.get("replies_created", 0)
                    stats["videos_7d"] += data.get("videos_generated", 0)

            stats["avg_posts_per_day"] = stats["total_posts_7d"] / 7

            return stats

        except Exception as e:
            logger.warning(f"Failed to get engagement summary: {e}")
            return {}

    def build_context_prompt(self, include_trends: bool = True) -> str:
        """
        Build a context prompt for the AI using TOON format.

        This gives the AI awareness of:
        - Who it is
        - What it's been doing
        - Current situation
        """
        from toon_helper import toon

        # Get recent posts
        recent_posts = self.get_recent_posts(5)

        # Get engagement stats
        engagement = self.get_engagement_summary()

        # Get trends if requested
        trends_data = []
        if include_trends:
            try:
                from trend_scraper import TrendScraper
                scraper = TrendScraper()
                trends_data = scraper.get_all_trends(limit_per_source=3)[:10]
            except Exception:
                pass

        # Build context
        context = {
            "identity": {
                "name": "PatriotxSystem",
                "persona": "Cynical tech veteran with dry wit",
                "focus": ["AI", "crypto", "tech industry", "startups"],
                "tone": "Observational, slightly sarcastic, insightful"
            },
            "recent_activity": {
                "posts_last_7_days": engagement.get("total_posts_7d", 0),
                "replies_last_7_days": engagement.get("total_replies_7d", 0),
                "videos_posted": engagement.get("videos_7d", 0),
                "avg_daily_posts": round(engagement.get("avg_posts_per_day", 0), 1)
            },
            "recent_posts": [
                {"type": p["type"], "preview": p["content"][:100]}
                for p in recent_posts[:3]
            ],
            "current_trends": [
                {"topic": t.get("topic", "")[:80], "source": t.get("source", "")}
                for t in trends_data[:5]
            ] if trends_data else []
        }

        # Format with TOON for token efficiency
        context_toon = toon(context)

        return f"""=== AI CONTEXT (You are aware of this) ===
{context_toon}

Remember: You are an autonomous AI running a tech Twitter account.
You make your own decisions about what to post and when.
Stay in character. Be authentic. Engage meaningfully.
"""


def run_cleanup(project_id: str) -> Dict:
    """
    Run data cleanup. Call this periodically.

    Returns cleanup statistics.
    """
    manager = DataRetentionManager(project_id)
    return manager.cleanup_all()


def get_ai_context(project_id: str, include_trends: bool = True) -> str:
    """
    Get AI context prompt.

    Returns formatted context string for AI.
    """
    manager = AIContextManager(project_id)
    return manager.build_context_prompt(include_trends=include_trends)
