"""
Twitter Interaction Manager

Handles:
- Monitoring mentions
- Finding relevant conversations (outreach)
- Replying to tweets
- Rate limit management
"""

import logging
import tweepy
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)


class TwitterInteractionManager:
    """
    Manages Twitter interactions including mentions, searches, and replies.
    Handles rate limiting intelligently based on API tier.
    """

    def __init__(
        self,
        api_v1: tweepy.API,
        client_v2: tweepy.Client,
        bot_username: str = "PatriotxSystem"
    ):
        """
        Initialize interaction manager.

        Args:
            api_v1: Tweepy v1 API client
            client_v2: Tweepy v2 API client
            bot_username: Bot's Twitter username (without @)
        """
        self.api_v1 = api_v1
        self.client_v2 = client_v2
        self.bot_username = bot_username
        self.rate_limits = {}

    def _check_rate_limit(self, endpoint: str, max_calls: int, window_minutes: int) -> bool:
        """
        Check if we're within rate limits for an endpoint.

        Args:
            endpoint: Name of the endpoint
            max_calls: Maximum calls allowed
            window_minutes: Time window in minutes

        Returns:
            True if we can make the call, False if rate limited
        """
        now = datetime.now()

        if endpoint not in self.rate_limits:
            self.rate_limits[endpoint] = []

        # Clean old timestamps
        cutoff = now - timedelta(minutes=window_minutes)
        self.rate_limits[endpoint] = [
            ts for ts in self.rate_limits[endpoint] if ts > cutoff
        ]

        # Check if we're at limit
        if len(self.rate_limits[endpoint]) >= max_calls:
            logger.warning(
                f"Rate limit reached for {endpoint}: "
                f"{len(self.rate_limits[endpoint])}/{max_calls} in {window_minutes}min"
            )
            return False

        # Record this call
        self.rate_limits[endpoint].append(now)
        return True

    def get_mentions(
        self,
        since_id: Optional[str] = None,
        max_results: int = 10
    ) -> List[Dict]:
        """
        Fetch recent mentions of the bot.

        FREE TIER LIMITS:
        - GET /2/users/:id/mentions: 1 request per 15 minutes PER USER

        Args:
            since_id: Only get mentions after this tweet ID
            max_results: Maximum mentions to fetch (max 100)

        Returns:
            List of mention dictionaries
        """
        # Rate limit check for free tier
        if not self._check_rate_limit("mentions", max_calls=1, window_minutes=15):
            logger.info("Mentions rate limit reached, skipping")
            return []

        try:
            # Get our own user ID first (cached after first call)
            if not hasattr(self, '_bot_user_id'):
                me = self.client_v2.get_user(username=self.bot_username)
                if not me or not me.data:
                    logger.error("Could not fetch bot user info")
                    return []
                self._bot_user_id = me.data.id
                logger.info(f"Bot user ID: {self._bot_user_id}")

            # Fetch mentions
            params = {
                "id": self._bot_user_id,
                "max_results": min(max_results, 10),  # Free tier: be conservative
                "tweet_fields": ["created_at", "author_id", "conversation_id", "in_reply_to_user_id"],
                "expansions": ["author_id"],
                "user_fields": ["username", "name", "description", "public_metrics"]
            }

            if since_id:
                params["since_id"] = since_id

            response = self.client_v2.get_users_mentions(**params)

            if not response or not response.data:
                logger.info("No new mentions found")
                return []

            # Parse mentions
            mentions = []
            users_map = {}

            # Build user map from includes
            if hasattr(response, 'includes') and 'users' in response.includes:
                for user in response.includes['users']:
                    users_map[user.id] = {
                        "username": user.username,
                        "name": user.name,
                        "description": user.description,
                        "followers": user.public_metrics.get("followers_count", 0) if hasattr(user, 'public_metrics') else 0
                    }

            for tweet in response.data:
                author_info = users_map.get(tweet.author_id, {})

                mention = {
                    "tweet_id": tweet.id,
                    "author_id": tweet.author_id,
                    "author_username": author_info.get("username", "unknown"),
                    "author_name": author_info.get("name", "Unknown"),
                    "author_followers": author_info.get("followers", 0),
                    "text": tweet.text,
                    "created_at": tweet.created_at.isoformat() if hasattr(tweet, 'created_at') else None,
                    "conversation_id": tweet.conversation_id if hasattr(tweet, 'conversation_id') else None,
                    "is_reply": hasattr(tweet, 'in_reply_to_user_id') and tweet.in_reply_to_user_id is not None
                }

                mentions.append(mention)

            logger.info(f"Found {len(mentions)} new mentions")
            return mentions

        except tweepy.errors.TooManyRequests as e:
            logger.warning(f"Rate limited by Twitter API: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch mentions: {e}")
            return []

    def search_tweets(
        self,
        query: str,
        max_results: int = 10,
        exclude_replies: bool = True,
        exclude_retweets: bool = True
    ) -> List[Dict]:
        """
        Search for tweets matching a query (for outreach).

        FREE TIER LIMITS:
        - GET /2/tweets/search/recent: 1 request per 15 minutes

        Args:
            query: Search query (Twitter search syntax)
            max_results: Maximum results (max 100, but use 10 for free tier)
            exclude_replies: Skip reply tweets
            exclude_retweets: Skip retweets

        Returns:
            List of tweet dictionaries
        """
        # Rate limit check
        if not self._check_rate_limit("search_recent", max_calls=1, window_minutes=15):
            logger.info("Search rate limit reached, skipping")
            return []

        try:
            # Build query with filters
            search_query = query

            if exclude_replies:
                search_query += " -is:reply"

            if exclude_retweets:
                search_query += " -is:retweet"

            # Add language and quality filters
            search_query += " lang:en -is:quote"

            logger.info(f"Searching tweets: {search_query}")

            response = self.client_v2.search_recent_tweets(
                query=search_query,
                max_results=min(max_results, 10),  # Conservative for free tier
                tweet_fields=["created_at", "author_id", "public_metrics", "conversation_id"],
                expansions=["author_id"],
                user_fields=["username", "name", "description", "public_metrics"]
            )

            if not response or not response.data:
                logger.info("No tweets found for search query")
                return []

            # Parse results
            tweets = []
            users_map = {}

            # Build user map
            if hasattr(response, 'includes') and 'users' in response.includes:
                for user in response.includes['users']:
                    users_map[user.id] = {
                        "username": user.username,
                        "name": user.name,
                        "description": user.description,
                        "followers": user.public_metrics.get("followers_count", 0) if hasattr(user, 'public_metrics') else 0
                    }

            for tweet in response.data:
                author_info = users_map.get(tweet.author_id, {})
                metrics = tweet.public_metrics if hasattr(tweet, 'public_metrics') else {}

                tweet_data = {
                    "tweet_id": tweet.id,
                    "author_id": tweet.author_id,
                    "author_username": author_info.get("username", "unknown"),
                    "author_name": author_info.get("name", "Unknown"),
                    "author_followers": author_info.get("followers", 0),
                    "text": tweet.text,
                    "created_at": tweet.created_at.isoformat() if hasattr(tweet, 'created_at') else None,
                    "likes": metrics.get("like_count", 0),
                    "retweets": metrics.get("retweet_count", 0),
                    "replies": metrics.get("reply_count", 0),
                    "conversation_id": tweet.conversation_id if hasattr(tweet, 'conversation_id') else None
                }

                tweets.append(tweet_data)

            logger.info(f"Found {len(tweets)} tweets for outreach")
            return tweets

        except tweepy.errors.TooManyRequests as e:
            logger.warning(f"Rate limited by Twitter API: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to search tweets: {e}")
            return []

    def post_reply(
        self,
        tweet_id: str,
        reply_text: str,
        retry_count: int = 3
    ) -> Tuple[bool, Optional[str]]:
        """
        Post a reply to a tweet.

        FREE TIER LIMITS:
        - POST /2/tweets: 17 requests per 24 hours

        Args:
            tweet_id: ID of tweet to reply to
            reply_text: Reply text (max 280 chars)
            retry_count: Number of retries on failure

        Returns:
            (success, posted_tweet_id)
        """
        # Rate limit check
        if not self._check_rate_limit("post_tweet", max_calls=17, window_minutes=1440):
            logger.warning("Daily tweet limit reached!")
            return False, None

        # Validate reply length
        if len(reply_text) > 280:
            logger.warning(f"Reply too long ({len(reply_text)} chars), truncating")
            reply_text = reply_text[:277] + "..."

        for attempt in range(retry_count):
            try:
                response = self.client_v2.create_tweet(
                    text=reply_text,
                    in_reply_to_tweet_id=tweet_id
                )

                if response and response.data:
                    posted_id = response.data['id']
                    logger.info(f"✅ Posted reply {posted_id} to tweet {tweet_id}")
                    return True, posted_id

            except tweepy.errors.TooManyRequests as e:
                logger.error(f"Rate limited when posting reply: {e}")
                return False, None

            except tweepy.errors.Forbidden as e:
                logger.error(f"Forbidden to reply (blocked/private user?): {e}")
                return False, None

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{retry_count} failed: {e}")
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to post reply after {retry_count} attempts")
                    return False, None

        return False, None

    def get_outreach_topics(self) -> List[str]:
        """
        Get list of topics to search for outreach.
        Big Boss persona: Military tech, AI, geopolitics, crypto, surveillance.

        Returns:
            List of search queries
        """
        return [
            # AI & Technology
            "AI artificial intelligence",
            "machine learning ML",
            "large language model LLM",
            "autonomous weapons",
            "military AI",

            # Crypto & Finance
            "bitcoin BTC",
            "cryptocurrency crypto",
            "blockchain",
            "digital currency",

            # Geopolitics & Security
            "cyber warfare",
            "surveillance state",
            "data privacy",
            "encryption",
            "information warfare",

            # Philosophy & Society
            "posthuman",
            "transhumanism",
            "digital consciousness",
            "simulation theory",

            # Tech Companies
            "OpenAI",
            "Anthropic Claude",
            "Google AI",
            "Meta AI",
        ]

    def get_rate_limit_status(self) -> Dict:
        """
        Get current rate limit status for all endpoints.

        Returns:
            Dictionary with rate limit info
        """
        status = {}

        for endpoint, timestamps in self.rate_limits.items():
            status[endpoint] = {
                "recent_calls": len(timestamps),
                "oldest_call": min(timestamps).isoformat() if timestamps else None,
                "newest_call": max(timestamps).isoformat() if timestamps else None
            }

        return status


class RateLimitStrategy:
    """
    Smart rate limit management for different API tiers.
    """

    # API Tier Configurations
    FREE_TIER = {
        "mentions": {"calls": 1, "window_minutes": 15},
        "search_recent": {"calls": 1, "window_minutes": 15},
        "post_tweet": {"calls": 17, "window_minutes": 1440},  # 24 hours
        "user_lookup": {"calls": 1, "window_minutes": 1440}
    }

    BASIC_TIER = {
        "mentions": {"calls": 10, "window_minutes": 15},
        "search_recent": {"calls": 60, "window_minutes": 15},
        "post_tweet": {"calls": 100, "window_minutes": 1440},
        "user_lookup": {"calls": 100, "window_minutes": 1440}
    }

    PRO_TIER = {
        "mentions": {"calls": 300, "window_minutes": 15},
        "search_recent": {"calls": 300, "window_minutes": 15},
        "post_tweet": {"calls": 100, "window_minutes": 15},
        "user_lookup": {"calls": 900, "window_minutes": 15}
    }

    @staticmethod
    def get_tier_config(tier: str = "free") -> Dict:
        """Get rate limit configuration for API tier."""
        tier_map = {
            "free": RateLimitStrategy.FREE_TIER,
            "basic": RateLimitStrategy.BASIC_TIER,
            "pro": RateLimitStrategy.PRO_TIER
        }

        return tier_map.get(tier.lower(), RateLimitStrategy.FREE_TIER)

    @staticmethod
    def should_engage(
        tier: str,
        mentions_count: int,
        outreach_count: int,
        hour_of_day: int
    ) -> Dict[str, bool]:
        """
        Decide what types of engagement to do based on tier and time.

        Args:
            tier: API tier (free, basic, pro)
            mentions_count: How many mentions we have
            outreach_count: How many outreach opportunities
            hour_of_day: Current hour (0-23)

        Returns:
            Dictionary with engagement decisions
        """
        config = RateLimitStrategy.get_tier_config(tier)

        decisions = {
            "should_check_mentions": True,  # Always check if we can
            "should_do_outreach": False,
            "should_reply_to_mentions": True,
            "max_replies": 5,
            "max_outreach": 0
        }

        if tier == "free":
            # Free tier: Very conservative
            # Only do 1-2 replies per cycle, no outreach
            decisions["max_replies"] = 2
            decisions["max_outreach"] = 0
            decisions["should_do_outreach"] = False

            # Avoid peak hours to save quota
            if 9 <= hour_of_day <= 17:  # Peak hours
                decisions["max_replies"] = 1

        elif tier == "basic":
            # Basic tier: Moderate engagement
            decisions["max_replies"] = 5
            decisions["max_outreach"] = 2
            decisions["should_do_outreach"] = outreach_count > 0

            # More active during peak hours
            if 9 <= hour_of_day <= 17:
                decisions["max_replies"] = 8
                decisions["max_outreach"] = 3

        elif tier == "pro":
            # Pro tier: Full engagement
            decisions["max_replies"] = 15
            decisions["max_outreach"] = 10
            decisions["should_do_outreach"] = True

        return decisions
