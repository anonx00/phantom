"""
Unified Reply Tracker - Single source of truth for all reply tracking

Ensures:
1. No duplicate replies (whether from scraper or API)
2. Clear separation between our posts and our replies
3. Deduplication across both reply systems
4. Proper tracking in Firestore

Used by:
- reply_scraper.py (Nitter-based)
- reply_handler.py (API-based)
- main.py (for stats)
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from google.cloud import firestore

logger = logging.getLogger(__name__)


class ReplyTracker:
    """
    Unified tracking for all reply operations.
    Prevents duplicate replies and tracks our response history.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.db = firestore.Client(project=project_id)

        # Collections
        self.sent_replies = self.db.collection("sent_replies")  # Our replies
        self.seen_mentions = self.db.collection("seen_mentions")  # Things we've seen

    def _generate_reply_key(self, target_tweet_id: str, target_author: str) -> str:
        """Generate unique key for a reply target."""
        content = f"{target_tweet_id}:{target_author}"
        return hashlib.sha256(content.encode()).hexdigest()[:24]

    def _generate_mention_key(self, author: str, text: str, tweet_id: str = "") -> str:
        """Generate unique key for a mention/reply we received."""
        # Include tweet_id if available, otherwise hash author+text
        if tweet_id:
            content = f"{tweet_id}"
        else:
            content = f"{author}:{text[:100]}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def has_replied_to(self, target_tweet_id: str, target_author: str) -> bool:
        """
        Check if we've already replied to this specific tweet/author combo.

        Args:
            target_tweet_id: The tweet ID we might reply to
            target_author: The author we might reply to

        Returns:
            True if we've already replied
        """
        try:
            reply_key = self._generate_reply_key(target_tweet_id, target_author)
            doc = self.sent_replies.document(reply_key).get()

            if doc.exists:
                logger.debug(f"Already replied to @{target_author}'s tweet {target_tweet_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error checking reply status: {e}")
            return False  # Allow reply on error (conservative)

    def has_seen_mention(self, author: str, text: str, tweet_id: str = "") -> bool:
        """
        Check if we've already seen/processed this mention.

        Args:
            author: Who mentioned us
            text: What they said
            tweet_id: Their tweet ID (if available)

        Returns:
            True if we've already processed this
        """
        try:
            mention_key = self._generate_mention_key(author, text, tweet_id)
            doc = self.seen_mentions.document(mention_key).get()
            return doc.exists

        except Exception as e:
            logger.error(f"Error checking mention status: {e}")
            return False

    def record_reply_sent(
        self,
        target_tweet_id: str,
        target_author: str,
        target_text: str,
        our_reply: str,
        our_reply_tweet_id: str = None,
        source: str = "api"  # "api" or "scraper"
    ) -> bool:
        """
        Record that we sent a reply.

        Args:
            target_tweet_id: Tweet we replied to
            target_author: Who we replied to
            target_text: What they said
            our_reply: What we said
            our_reply_tweet_id: Our reply's tweet ID (if available)
            source: "api" (reply_handler) or "scraper" (reply_scraper)

        Returns:
            True if recorded successfully
        """
        try:
            reply_key = self._generate_reply_key(target_tweet_id, target_author)

            self.sent_replies.document(reply_key).set({
                "reply_key": reply_key,
                "target_tweet_id": target_tweet_id,
                "target_author": target_author,
                "target_text": target_text[:500],
                "our_reply": our_reply[:300],
                "our_reply_tweet_id": our_reply_tweet_id,
                "source": source,
                "sent_at": firestore.SERVER_TIMESTAMP,
                "type": "reply"  # Clearly mark as reply, not post
            })

            logger.info(f"[REPLY] Recorded reply to @{target_author} via {source}")
            return True

        except Exception as e:
            logger.error(f"Error recording reply: {e}")
            return False

    def record_mention_seen(
        self,
        author: str,
        text: str,
        tweet_id: str = "",
        responded: bool = False,
        skip_reason: str = None
    ) -> bool:
        """
        Record that we saw a mention (whether we replied or not).

        Args:
            author: Who mentioned us
            text: What they said
            tweet_id: Their tweet ID
            responded: Did we reply?
            skip_reason: Why we didn't reply (if applicable)

        Returns:
            True if recorded successfully
        """
        try:
            mention_key = self._generate_mention_key(author, text, tweet_id)

            self.seen_mentions.document(mention_key).set({
                "mention_key": mention_key,
                "author": author,
                "text": text[:500],
                "tweet_id": tweet_id,
                "responded": responded,
                "skip_reason": skip_reason,
                "seen_at": firestore.SERVER_TIMESTAMP
            })

            return True

        except Exception as e:
            logger.error(f"Error recording mention: {e}")
            return False

    def get_recent_replies(self, hours: int = 24) -> List[Dict]:
        """Get replies we've sent in the last N hours."""
        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            query = (self.sent_replies
                    .where("sent_at", ">=", cutoff)
                    .order_by("sent_at", direction=firestore.Query.DESCENDING)
                    .limit(50))

            replies = []
            for doc in query.stream():
                replies.append(doc.to_dict())

            return replies

        except Exception as e:
            logger.error(f"Error getting recent replies: {e}")
            return []

    def get_reply_stats(self) -> Dict:
        """Get reply statistics for today."""
        try:
            # Count replies sent today
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            query = self.sent_replies.where("sent_at", ">=", today_start)

            replies_today = 0
            by_source = {"api": 0, "scraper": 0}

            for doc in query.stream():
                replies_today += 1
                source = doc.to_dict().get("source", "unknown")
                by_source[source] = by_source.get(source, 0) + 1

            return {
                "replies_today": replies_today,
                "by_source": by_source,
                "api_replies": by_source.get("api", 0),
                "scraper_replies": by_source.get("scraper", 0)
            }

        except Exception as e:
            logger.error(f"Error getting reply stats: {e}")
            return {"replies_today": 0, "by_source": {}}

    def cleanup_old_records(self, days: int = 7) -> int:
        """Clean up old seen_mentions records (replies are kept longer)."""
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)

            deleted = 0
            batch = self.db.batch()
            batch_count = 0

            query = self.seen_mentions.where("seen_at", "<", cutoff).limit(100)

            for doc in query.stream():
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
                logger.info(f"Cleaned up {deleted} old mention records")

            return deleted

        except Exception as e:
            logger.error(f"Error cleaning up records: {e}")
            return 0


# Global instance for easy access
_tracker_instance = None


def get_reply_tracker(project_id: str) -> ReplyTracker:
    """Get or create the global ReplyTracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = ReplyTracker(project_id)
    return _tracker_instance
