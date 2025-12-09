"""
Post Memory Tracker - Helps AI remember what it posted

Uses vector memory to:
- Avoid posting similar content repeatedly
- Give AI context about its recent posts
- Track content themes and patterns
"""

import logging
from typing import List, Dict, Optional
from memory_system import VectorMemory

logger = logging.getLogger(__name__)


class PostMemoryTracker:
    """
    Tracks what the AI has posted to provide context for future decisions.
    """

    def __init__(self, vector_memory: VectorMemory):
        self.vector_memory = vector_memory

    def store_post(
        self,
        post_id: str,
        content: str,
        post_type: str,
        topic: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Store a post in memory with vector embedding.

        Args:
            post_id: Tweet ID
            content: Tweet text
            post_type: video, image, text, etc.
            topic: Optional topic/headline
            metadata: Additional context

        Returns:
            Success status
        """
        try:
            full_metadata = metadata or {}
            full_metadata.update({
                "post_type": post_type,
                "topic": topic or "general"
            })

            success = self.vector_memory.store_interaction(
                tweet_id=post_id,
                author="PatriotxSystem",  # Self
                content=content,
                interaction_type="posted",
                ai_response=None,  # It's our own post
                metadata=full_metadata
            )

            if success:
                logger.info(f"📝 Stored post in memory: {content[:50]}...")

            return success

        except Exception as e:
            logger.error(f"Failed to store post in memory: {e}")
            return False

    def check_similar_recent_posts(
        self,
        topic: str,
        min_similarity: float = 0.80,
        days_back: int = 7
    ) -> List[Dict]:
        """
        Check if we've posted similar content recently.

        Args:
            topic: Topic to check
            min_similarity: Similarity threshold (0-1)
            days_back: How many days to look back

        Returns:
            List of similar posts
        """
        try:
            similar = self.vector_memory.find_similar_interactions(
                query_text=topic,
                limit=5,
                min_similarity=min_similarity
            )

            # Filter to only our own posts from recent days
            from datetime import datetime, timedelta
            cutoff = datetime.now() - timedelta(days=days_back)

            recent_similar = []
            for post in similar:
                if post.get("interaction_type") == "posted":
                    # Check if recent enough
                    timestamp = post.get("timestamp")
                    if timestamp and timestamp > cutoff:
                        recent_similar.append(post)

            if recent_similar:
                logger.info(f"⚠️ Found {len(recent_similar)} similar posts in last {days_back} days")
                for i, post in enumerate(recent_similar[:3], 1):
                    similarity = post.get("similarity_score", 0)
                    content = post.get("content", "")[:60]
                    logger.info(f"   {i}. ({similarity:.2f}) {content}...")

            return recent_similar

        except Exception as e:
            logger.error(f"Failed to check similar posts: {e}")
            return []

    def get_posting_context(self, current_topic: str, days_back: int = 3) -> str:
        """
        Build context string about recent posts for AI decision-making.

        Args:
            current_topic: Topic being considered
            days_back: Days of history to include

        Returns:
            Formatted context string
        """
        try:
            # Check for similar posts
            similar = self.check_similar_recent_posts(
                topic=current_topic,
                min_similarity=0.75,
                days_back=days_back
            )

            if not similar:
                return f"RECENT POSTS: No similar content found about '{current_topic}' in last {days_back} days. Topic is FRESH."

            context_parts = [
                f"RECENT POSTS: Similar content detected (last {days_back} days):",
                ""
            ]

            for i, post in enumerate(similar[:3], 1):
                similarity = post.get("similarity_score", 0)
                content = post.get("content", "")[:80]
                post_type = post.get("metadata", {}).get("post_type", "unknown")

                context_parts.append(
                    f"{i}. ({similarity:.0%} similar) [{post_type.upper()}] \"{content}\""
                )

            context_parts.append("")
            context_parts.append(
                f"⚠️ WARNING: You may be repeating yourself. Consider a different angle or skip this topic."
            )

            return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Failed to build posting context: {e}")
            return "RECENT POSTS: Could not retrieve (memory system error)"

    def get_daily_post_summary(self) -> str:
        """
        Get summary of what we posted today for context.

        Returns:
            Summary string
        """
        try:
            from datetime import datetime, timedelta
            import pytz
            from config import Config

            # Get today's posts
            tz = pytz.timezone(Config.TIMEZONE)
            today_start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)

            # Get our own posts from today
            stats = self.vector_memory.get_interaction_stats()

            # Build summary
            context_parts = [
                "TODAY'S POSTING ACTIVITY:",
                f"- Total posts created: {stats.get('recent_count_24h', 0)}",
                ""
            ]

            # Get breakdown by type
            by_type = stats.get("by_type", {})
            posted_count = by_type.get("posted", 0)

            if posted_count > 0:
                context_parts.append(f"You've been active today ({posted_count} posts).")
            else:
                context_parts.append("Haven't posted yet today - field is open!")

            return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Failed to get daily summary: {e}")
            return "TODAY: Could not retrieve summary"

    def should_post_topic(
        self,
        topic: str,
        similarity_threshold: float = 0.85
    ) -> tuple[bool, str]:
        """
        Check if we should post about this topic (not too repetitive).

        Args:
            topic: Topic to check
            similarity_threshold: Max similarity before rejecting

        Returns:
            (should_post, reason)
        """
        similar = self.check_similar_recent_posts(
            topic=topic,
            min_similarity=similarity_threshold,
            days_back=3
        )

        if not similar:
            return True, "Topic is fresh, no recent similar posts"

        # Found very similar content
        highest_similarity = max(p.get("similarity_score", 0) for p in similar)

        if highest_similarity >= similarity_threshold:
            return False, f"Too similar to recent post ({highest_similarity:.0%} match) - avoid repetition"

        return True, f"Somewhat similar ({highest_similarity:.0%}) but acceptable"
