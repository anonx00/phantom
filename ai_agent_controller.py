"""
AI Agent Controller - Budget-Conscious Decision Engine

Gives AI FULL control while respecting:
- FREE Twitter tier limits (17 posts/day, 1 mention check/15min)
- GCP budget constraints ($60 AUD limit)
- No wasted API calls or content generation

AI decides:
- Which content to create (from 2 researched options)
- Which mentions to reply to (2-3/day max)
- When to engage vs. stay silent
- All creative decisions (format, style, tone)

ZERO WASTE POLICY:
- Generate 2 story options → AI picks 1 → Create only that 1
- For videos: 1 prompt generated → 1 video created → 1 posted
- For replies: AI decides worth replying → Only then generate response
"""

import logging
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from google.cloud import firestore
from config import Config

logger = logging.getLogger(__name__)


class AIAgentController:
    """
    Budget-conscious AI agent controller.
    Makes smart decisions about what content to create and when to engage.
    """

    # FREE TIER CONSTRAINTS
    FREE_TIER_LIMITS = {
        "posts_per_day": 17,  # Twitter API limit
        "mentions_check_interval_minutes": 15,  # 1 check every 15 min
        "replies_per_day_target": 3,  # Conservative to save quota
        "posts_retrieved_per_month": 100,  # Twitter API limit
    }

    # BUDGET CONSTRAINTS (GCP)
    BUDGET_LIMITS = {
        "monthly_budget_usd": 40,  # $60 AUD ≈ $40 USD
        "vertex_ai_calls_per_day_max": 50,  # Conservative limit
        "video_generations_per_day_max": 2,  # Expensive, limit strictly
        "image_generations_per_day_max": 4,  # Cheaper than video
    }

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.db = firestore.Client(project=project_id)

        # Collections
        self.posts_collection = self.db.collection("post_history")
        self.interactions_collection = self.db.collection("ai_memory")
        self.budget_collection = self.db.collection("budget_tracking")

        # Initialize vector memory for AI context
        from memory_system import VectorMemory
        self.vector_memory = VectorMemory(project_id=project_id)
        logger.info("✅ Vector memory initialized - AI has context awareness")

        # Daily counters (reset at midnight)
        self._today_str = self._get_today_str()
        self._daily_stats = self._load_daily_stats()

    def _get_today_str(self) -> str:
        """Get today's date string in configured timezone."""
        import pytz
        tz = pytz.timezone(Config.TIMEZONE)
        return datetime.now(tz).strftime("%Y-%m-%d")

    def _load_daily_stats(self) -> Dict:
        """Load today's usage stats from Firestore."""
        try:
            doc_ref = self.budget_collection.document(f"daily_{self._today_str}")
            doc = doc_ref.get()

            if doc.exists:
                return doc.to_dict()
            else:
                # Initialize new day
                initial_stats = {
                    "date": self._today_str,
                    "posts_created": 0,
                    "replies_created": 0,
                    "mentions_checked": 0,
                    "vertex_ai_calls": 0,
                    "videos_generated": 0,
                    "images_generated": 0,
                    "last_updated": firestore.SERVER_TIMESTAMP
                }
                doc_ref.set(initial_stats)
                return initial_stats

        except Exception as e:
            logger.error(f"Failed to load daily stats: {e}")
            return {
                "posts_created": 0,
                "replies_created": 0,
                "mentions_checked": 0,
                "vertex_ai_calls": 0,
                "videos_generated": 0,
                "images_generated": 0,
            }

    def _update_daily_stat(self, stat_name: str, increment: int = 1):
        """Update a daily stat counter in Firestore."""
        try:
            doc_ref = self.budget_collection.document(f"daily_{self._today_str}")
            doc_ref.update({
                stat_name: firestore.Increment(increment),
                "last_updated": firestore.SERVER_TIMESTAMP
            })
            # Update local cache
            self._daily_stats[stat_name] = self._daily_stats.get(stat_name, 0) + increment
        except Exception as e:
            logger.error(f"Failed to update stat {stat_name}: {e}")

    def can_create_post(self) -> Tuple[bool, str]:
        """
        Check if we can create a post today.

        Returns:
            (allowed, reason)
        """
        posts_today = self._daily_stats.get("posts_created", 0)

        if posts_today >= self.FREE_TIER_LIMITS["posts_per_day"]:
            return False, f"Daily post limit reached ({posts_today}/17)"

        return True, f"OK to post ({posts_today}/17 today)"

    def can_create_video(self) -> Tuple[bool, str]:
        """
        Check if we can generate a video today (expensive operation).

        Returns:
            (allowed, reason)
        """
        videos_today = self._daily_stats.get("videos_generated", 0)
        max_videos = self.BUDGET_LIMITS["video_generations_per_day_max"]

        if videos_today >= max_videos:
            return False, f"Daily video limit reached ({videos_today}/{max_videos}) - budget protection"

        return True, f"OK to create video ({videos_today}/{max_videos} today)"

    def can_create_image(self) -> Tuple[bool, str]:
        """
        Check if we can generate an image today.

        Returns:
            (allowed, reason)
        """
        images_today = self._daily_stats.get("images_generated", 0)
        max_images = self.BUDGET_LIMITS["image_generations_per_day_max"]

        if images_today >= max_images:
            return False, f"Daily image limit reached ({images_today}/{max_images})"

        return True, f"OK to create image ({images_today}/{max_images} today)"

    def can_check_mentions(self) -> Tuple[bool, str]:
        """
        Check if we can check mentions now (FREE tier: 1 per 15 min).

        Returns:
            (allowed, reason)
        """
        mentions_today = self._daily_stats.get("mentions_checked", 0)

        # Check last mention check time
        try:
            doc_ref = self.budget_collection.document(f"daily_{self._today_str}")
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                last_check = data.get("last_mention_check")

                if last_check:
                    # Convert to datetime
                    if isinstance(last_check, datetime):
                        last_check_time = last_check
                    else:
                        last_check_time = last_check

                    time_since = datetime.now(last_check_time.tzinfo) - last_check_time
                    minutes_since = time_since.total_seconds() / 60

                    if minutes_since < 15:
                        wait_minutes = 15 - int(minutes_since)
                        return False, f"Rate limit: wait {wait_minutes} more minutes"

        except Exception as e:
            logger.warning(f"Could not check last mention time: {e}")

        return True, f"OK to check mentions ({mentions_today} checks today)"

    def can_reply(self) -> Tuple[bool, str]:
        """
        Check if we can send a reply today.

        Returns:
            (allowed, reason)
        """
        replies_today = self._daily_stats.get("replies_created", 0)
        posts_today = self._daily_stats.get("posts_created", 0)
        total_tweets_today = replies_today + posts_today

        # Check Twitter daily limit (replies count as posts)
        if total_tweets_today >= self.FREE_TIER_LIMITS["posts_per_day"]:
            return False, f"Daily tweet limit reached ({total_tweets_today}/17 total)"

        # Check our conservative reply target
        target_replies = self.FREE_TIER_LIMITS["replies_per_day_target"]
        if replies_today >= target_replies:
            return False, f"Daily reply target reached ({replies_today}/{target_replies}) - saving quota"

        return True, f"OK to reply ({replies_today}/{target_replies} replies, {total_tweets_today}/17 total)"

    def record_post_created(self, post_type: str):
        """Record that a post was created."""
        self._update_daily_stat("posts_created", 1)

        if post_type == "video":
            self._update_daily_stat("videos_generated", 1)
        elif post_type in ["image", "infographic"]:
            self._update_daily_stat("images_generated", 1)

        logger.info(f"📊 Daily stats: {self._daily_stats.get('posts_created', 0)} posts, "
                   f"{self._daily_stats.get('videos_generated', 0)} videos, "
                   f"{self._daily_stats.get('images_generated', 0)} images")

    def record_reply_created(self):
        """Record that a reply was sent."""
        self._update_daily_stat("replies_created", 1)
        logger.info(f"📊 Daily replies: {self._daily_stats.get('replies_created', 0)}")

    def record_mention_check(self):
        """Record that we checked mentions."""
        try:
            doc_ref = self.budget_collection.document(f"daily_{self._today_str}")
            doc_ref.update({
                "mentions_checked": firestore.Increment(1),
                "last_mention_check": firestore.SERVER_TIMESTAMP
            })
            self._daily_stats["mentions_checked"] = self._daily_stats.get("mentions_checked", 0) + 1
        except Exception as e:
            logger.error(f"Failed to record mention check: {e}")

    def record_vertex_ai_call(self):
        """Record that we made a Vertex AI API call."""
        self._update_daily_stat("vertex_ai_calls", 1)

    def get_daily_summary(self) -> Dict:
        """Get summary of today's activity."""
        return {
            "date": self._today_str,
            "posts": self._daily_stats.get("posts_created", 0),
            "replies": self._daily_stats.get("replies_created", 0),
            "mentions_checked": self._daily_stats.get("mentions_checked", 0),
            "vertex_ai_calls": self._daily_stats.get("vertex_ai_calls", 0),
            "videos_generated": self._daily_stats.get("videos_generated", 0),
            "images_generated": self._daily_stats.get("images_generated", 0),
            "twitter_quota_used": f"{self._daily_stats.get('posts_created', 0) + self._daily_stats.get('replies_created', 0)}/17",
            "video_budget_used": f"{self._daily_stats.get('videos_generated', 0)}/{self.BUDGET_LIMITS['video_generations_per_day_max']}",
        }

    def should_engage_mode(self) -> str:
        """
        Decide what the AI should do right now.

        Returns:
            "post" - Create and post content
            "reply" - Check mentions and reply
            "idle" - Do nothing (quota exhausted)
        """
        can_post, post_reason = self.can_create_post()
        can_reply_check, reply_reason = self.can_reply()
        can_check, check_reason = self.can_check_mentions()

        # Check time of day for smart scheduling
        import pytz
        tz = pytz.timezone(Config.TIMEZONE)
        current_hour = datetime.now(tz).hour

        # Peak engagement hours: 9am-9pm local time
        is_peak_hours = 9 <= current_hour <= 21

        # Decision logic
        if not can_post and not can_reply_check:
            return "idle"  # Quota exhausted

        # Prioritize posting during peak hours if we haven't posted much
        posts_today = self._daily_stats.get("posts_created", 0)
        replies_today = self._daily_stats.get("replies_created", 0)

        if can_post and is_peak_hours and posts_today < 7:
            # Post during peak hours, up to 7 posts/day
            return "post"

        if can_check and can_reply_check and replies_today < 3:
            # Check for mentions to reply to (if we haven't hit reply limit)
            return "reply"

        if can_post and posts_today < 12:
            # Continue posting if under 12 posts/day
            return "post"

        # Default to idle if quotas are getting tight
        return "idle"


class ZeroWasteContentStrategy:
    """
    Ensures ZERO wasted content generation.

    Strategy:
    1. Research 2 story options (cheap - just API calls)
    2. AI picks 1 best story
    3. Generate content ONLY for that 1 story
    4. For videos: 1 prompt → 1 video → 1 post
    """

    @staticmethod
    def pick_best_story(stories: List[Dict], ai_generate_func) -> Optional[Dict]:
        """
        AI picks the BEST story from options.
        Only the chosen story will have content generated.

        Args:
            stories: List of story dicts with title, url, context
            ai_generate_func: Function to call AI

        Returns:
            Chosen story dict or None
        """
        if not stories:
            return None

        if len(stories) == 1:
            return stories[0]

        # Present options to AI
        options_text = "\n\n".join([
            f"OPTION {i+1}:\n"
            f"Title: {s.get('title', 'Unknown')}\n"
            f"Context: {s.get('context', '')[:200]}...\n"
            f"Category: {s.get('category', 'tech')}"
            for i, s in enumerate(stories[:2])  # Max 2 options
        ])

        prompt = f"""You control a tech Twitter account. Choose the BEST story to post.

{options_text}

DECIDE:
- Which story is more interesting/valuable to your audience?
- Which has better visual potential?
- Which fits your persona (cynical tech veteran)?

Respond ONLY with:
CHOICE: <1 or 2>
REASON: <one sentence why>"""

        try:
            response = ai_generate_func(prompt)

            # Parse choice
            import re
            match = re.search(r'CHOICE:\s*(\d)', response)
            if match:
                choice = int(match.group(1)) - 1  # Convert to 0-indexed

                if 0 <= choice < len(stories):
                    chosen = stories[choice]
                    reason_match = re.search(r'REASON:\s*(.+)', response)
                    reason = reason_match.group(1) if reason_match else "AI preference"

                    logger.info(f"✅ AI chose story {choice + 1}: {chosen.get('title', '')[:50]}")
                    logger.info(f"   Reason: {reason}")

                    return chosen

        except Exception as e:
            logger.error(f"AI story selection failed: {e}")

        # Fallback: return first story
        logger.warning("Falling back to first story")
        return stories[0]

    @staticmethod
    def should_create_media(post_type: str, controller: AIAgentController) -> bool:
        """
        Check if we should actually generate media (video/image).

        Args:
            post_type: "video", "image", "infographic", etc.
            controller: AIAgentController instance

        Returns:
            True if we should generate, False to skip
        """
        if post_type == "video":
            can_create, reason = controller.can_create_video()
            if not can_create:
                logger.warning(f"❌ Skipping video generation: {reason}")
                return False

        elif post_type in ["image", "infographic"]:
            can_create, reason = controller.can_create_image()
            if not can_create:
                logger.warning(f"❌ Skipping image generation: {reason}")
                return False

        return True
