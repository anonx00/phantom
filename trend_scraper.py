"""
Trend Scraper - Scrape trending topics without Twitter API

Uses alternative sources to get trending topics:
1. Google Trends
2. Reddit trending
3. Hacker News
4. CoinGecko (crypto trends)

This helps the AI stay relevant without burning API quota.
"""

import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class TrendScraper:
    """Scrapes trending topics from various sources."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.cache = {}
        self.cache_ttl = timedelta(minutes=30)

    def _is_cached(self, key: str) -> bool:
        """Check if we have fresh cached data."""
        if key not in self.cache:
            return False
        cached_time, _ = self.cache[key]
        return datetime.now() - cached_time < self.cache_ttl

    def _get_cached(self, key: str) -> Optional[List[Dict]]:
        """Get cached data if fresh."""
        if self._is_cached(key):
            _, data = self.cache[key]
            return data
        return None

    def _set_cache(self, key: str, data: List[Dict]):
        """Cache data with timestamp."""
        self.cache[key] = (datetime.now(), data)

    def get_crypto_trends(self, limit: int = 10) -> List[Dict]:
        """
        Get trending crypto from CoinGecko.
        Free API, no auth needed.
        """
        cached = self._get_cached("crypto")
        if cached:
            return cached[:limit]

        trends = []
        try:
            # CoinGecko trending endpoint
            resp = self.session.get(
                "https://api.coingecko.com/api/v3/search/trending",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                for coin in data.get("coins", [])[:limit]:
                    item = coin.get("item", {})
                    trends.append({
                        "topic": item.get("name", "Unknown"),
                        "symbol": item.get("symbol", ""),
                        "category": "crypto",
                        "rank": item.get("market_cap_rank", 0),
                        "source": "coingecko"
                    })

            self._set_cache("crypto", trends)
            logger.info(f"📈 Got {len(trends)} crypto trends from CoinGecko")

        except Exception as e:
            logger.warning(f"Failed to get crypto trends: {e}")

        return trends

    def get_tech_trends(self, limit: int = 10) -> List[Dict]:
        """
        Get trending tech topics from Hacker News.
        """
        cached = self._get_cached("tech")
        if cached:
            return cached[:limit]

        trends = []
        try:
            # HN top stories
            resp = self.session.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                timeout=10
            )
            if resp.status_code == 200:
                story_ids = resp.json()[:limit]

                for story_id in story_ids:
                    story_resp = self.session.get(
                        f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                        timeout=5
                    )
                    if story_resp.status_code == 200:
                        story = story_resp.json()
                        if story:
                            trends.append({
                                "topic": story.get("title", "")[:100],
                                "url": story.get("url", ""),
                                "score": story.get("score", 0),
                                "category": "tech",
                                "source": "hackernews"
                            })

            self._set_cache("tech", trends)
            logger.info(f"💻 Got {len(trends)} tech trends from HN")

        except Exception as e:
            logger.warning(f"Failed to get tech trends: {e}")

        return trends

    def get_reddit_trends(self, subreddit: str = "technology", limit: int = 10) -> List[Dict]:
        """
        Get trending posts from Reddit (no auth needed for public).
        """
        cache_key = f"reddit_{subreddit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached[:limit]

        trends = []
        try:
            # Reddit JSON endpoint (no auth needed)
            resp = self.session.get(
                f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                for post in data.get("data", {}).get("children", []):
                    post_data = post.get("data", {})
                    trends.append({
                        "topic": post_data.get("title", "")[:100],
                        "score": post_data.get("score", 0),
                        "comments": post_data.get("num_comments", 0),
                        "url": f"https://reddit.com{post_data.get('permalink', '')}",
                        "category": subreddit,
                        "source": "reddit"
                    })

            self._set_cache(cache_key, trends)
            logger.info(f"🔥 Got {len(trends)} trends from r/{subreddit}")

        except Exception as e:
            logger.warning(f"Failed to get Reddit trends: {e}")

        return trends

    def get_all_trends(self, limit_per_source: int = 5) -> List[Dict]:
        """
        Get trends from all sources combined.
        """
        all_trends = []

        # Crypto trends
        all_trends.extend(self.get_crypto_trends(limit_per_source))

        # Tech trends from HN
        all_trends.extend(self.get_tech_trends(limit_per_source))

        # Reddit trends from multiple subreddits
        for sub in ["technology", "cryptocurrency", "artificial"]:
            all_trends.extend(self.get_reddit_trends(sub, limit_per_source // 2))

        logger.info(f"📊 Total trends collected: {len(all_trends)}")
        return all_trends

    def get_trending_for_content(self) -> Dict:
        """
        Get trends formatted for content creation.
        Returns a dict with categorized trends.
        """
        return {
            "crypto": self.get_crypto_trends(5),
            "tech": self.get_tech_trends(5),
            "reddit_tech": self.get_reddit_trends("technology", 3),
            "reddit_ai": self.get_reddit_trends("artificial", 3),
            "timestamp": datetime.now().isoformat()
        }


def get_trends_for_prompt() -> str:
    """
    Get trends encoded for LLM prompt using TOON.
    """
    from toon_helper import encode_trends_for_prompt

    scraper = TrendScraper()
    all_trends = scraper.get_all_trends(limit_per_source=5)

    return encode_trends_for_prompt(all_trends)
