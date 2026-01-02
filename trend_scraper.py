"""
Trend Scraper - Robust multi-source trend aggregator

Sources (all FREE, no auth):
1. Hacker News - Tech/startup news
2. CoinGecko - Crypto trends
3. Reddit - Multiple subreddits
4. GitHub Trending - Popular repos
5. Lobsters - Tech community
6. Dev.to - Developer content
7. TechCrunch RSS - Tech news
8. AI News - Hugging Face papers

All sources have:
- Timeout handling
- Error recovery
- 30-min caching
- Fallback to empty list on failure
"""

import logging
import requests
import feedparser
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


class TrendScraper:
    """Robust multi-source trend aggregator."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/html, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self.cache = {}
        self.cache_ttl = timedelta(minutes=30)
        self.timeout = 10

    def _safe_request(self, url: str, **kwargs) -> Optional[requests.Response]:
        """Make a safe HTTP request with error handling."""
        try:
            kwargs.setdefault('timeout', self.timeout)
            resp = self.session.get(url, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout fetching {url}")
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTP error {e.response.status_code} for {url}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed for {url}: {e}")
        return None

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

    def get_hackernews_trends(self, limit: int = 10) -> List[Dict]:
        """
        Get top stories from Hacker News.
        API: https://github.com/HackerNews/API
        """
        cached = self._get_cached("hackernews")
        if cached:
            return cached[:limit]

        trends = []
        try:
            # Get top story IDs
            resp = self._safe_request("https://hacker-news.firebaseio.com/v0/topstories.json")
            if not resp:
                return trends

            story_ids = resp.json()[:limit]

            # Fetch each story (parallel would be better but keeping simple)
            for story_id in story_ids:
                story_resp = self._safe_request(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                    timeout=5
                )
                if story_resp:
                    story = story_resp.json()
                    if story and story.get("title"):
                        trends.append({
                            "topic": story.get("title", "")[:150],
                            "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                            "score": story.get("score", 0),
                            "comments": story.get("descendants", 0),
                            "category": "tech",
                            "source": "hackernews",
                            "time": datetime.fromtimestamp(story.get("time", 0)).isoformat() if story.get("time") else None
                        })

            self._set_cache("hackernews", trends)
            logger.info(f"🔶 Got {len(trends)} stories from Hacker News")

        except Exception as e:
            logger.error(f"HackerNews scraper failed: {e}")

        return trends

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
            resp = self._safe_request("https://api.coingecko.com/api/v3/search/trending")
            if not resp:
                return trends

            data = resp.json()
            for coin in data.get("coins", [])[:limit]:
                item = coin.get("item", {})
                trends.append({
                    "topic": f"{item.get('name', 'Unknown')} ({item.get('symbol', '').upper()})",
                    "symbol": item.get("symbol", ""),
                    "category": "crypto",
                    "rank": item.get("market_cap_rank", 0),
                    "price_change_24h": item.get("data", {}).get("price_change_percentage_24h", {}).get("usd", 0),
                    "source": "coingecko"
                })

            self._set_cache("crypto", trends)
            logger.info(f"📈 Got {len(trends)} crypto trends from CoinGecko")

        except Exception as e:
            logger.error(f"CoinGecko scraper failed: {e}")

        return trends

    def get_reddit_trends(self, subreddit: str = "technology", limit: int = 10) -> List[Dict]:
        """
        Get hot posts from Reddit (public JSON endpoint).
        """
        cache_key = f"reddit_{subreddit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached[:limit]

        trends = []
        try:
            resp = self._safe_request(
                f"https://www.reddit.com/r/{subreddit}/hot.json",
                params={"limit": limit, "raw_json": 1}
            )
            if not resp:
                return trends

            data = resp.json()
            for post in data.get("data", {}).get("children", []):
                post_data = post.get("data", {})
                # Skip stickied posts
                if post_data.get("stickied"):
                    continue
                trends.append({
                    "topic": post_data.get("title", "")[:150],
                    "score": post_data.get("score", 0),
                    "comments": post_data.get("num_comments", 0),
                    "url": post_data.get("url", ""),
                    "permalink": f"https://reddit.com{post_data.get('permalink', '')}",
                    "category": subreddit,
                    "source": "reddit",
                    "created": datetime.fromtimestamp(post_data.get("created_utc", 0)).isoformat()
                })

            self._set_cache(cache_key, trends)
            logger.info(f"🔥 Got {len(trends)} posts from r/{subreddit}")

        except Exception as e:
            logger.error(f"Reddit scraper failed for r/{subreddit}: {e}")

        return trends

    def get_github_trending(self, limit: int = 10) -> List[Dict]:
        """
        Get trending repositories from GitHub.
        Scrapes the trending page (no API auth needed).
        """
        cached = self._get_cached("github")
        if cached:
            return cached[:limit]

        trends = []
        try:
            resp = self._safe_request("https://github.com/trending")
            if not resp:
                return trends

            soup = BeautifulSoup(resp.text, 'html.parser')
            articles = soup.select('article.Box-row')[:limit]

            for article in articles:
                # Get repo name
                h2 = article.select_one('h2')
                if not h2:
                    continue

                repo_link = h2.select_one('a')
                if not repo_link:
                    continue

                repo_path = repo_link.get('href', '').strip('/')
                repo_name = repo_path.split('/')[-1] if '/' in repo_path else repo_path

                # Get description
                desc_p = article.select_one('p')
                description = desc_p.get_text(strip=True) if desc_p else ""

                # Get stars today
                stars_span = article.select_one('span.d-inline-block.float-sm-right')
                stars_today = 0
                if stars_span:
                    stars_text = stars_span.get_text(strip=True)
                    stars_match = re.search(r'([\d,]+)', stars_text)
                    if stars_match:
                        stars_today = int(stars_match.group(1).replace(',', ''))

                # Get language
                lang_span = article.select_one('span[itemprop="programmingLanguage"]')
                language = lang_span.get_text(strip=True) if lang_span else "Unknown"

                trends.append({
                    "topic": f"{repo_name}: {description[:80]}..." if len(description) > 80 else f"{repo_name}: {description}",
                    "repo": repo_path,
                    "url": f"https://github.com/{repo_path}",
                    "language": language,
                    "stars_today": stars_today,
                    "category": "github",
                    "source": "github"
                })

            self._set_cache("github", trends)
            logger.info(f"⭐ Got {len(trends)} trending repos from GitHub")

        except Exception as e:
            logger.error(f"GitHub trending scraper failed: {e}")

        return trends

    def get_lobsters_trends(self, limit: int = 10) -> List[Dict]:
        """
        Get top stories from Lobsters (tech community).
        """
        cached = self._get_cached("lobsters")
        if cached:
            return cached[:limit]

        trends = []
        try:
            resp = self._safe_request("https://lobste.rs/hottest.json")
            if not resp:
                return trends

            stories = resp.json()[:limit]
            for story in stories:
                trends.append({
                    "topic": story.get("title", "")[:150],
                    "url": story.get("url", story.get("short_id_url", "")),
                    "score": story.get("score", 0),
                    "comments": story.get("comment_count", 0),
                    "tags": story.get("tags", []),
                    "category": "tech",
                    "source": "lobsters"
                })

            self._set_cache("lobsters", trends)
            logger.info(f"🦞 Got {len(trends)} stories from Lobsters")

        except Exception as e:
            logger.error(f"Lobsters scraper failed: {e}")

        return trends

    def get_devto_trends(self, limit: int = 10) -> List[Dict]:
        """
        Get top articles from Dev.to.
        """
        cached = self._get_cached("devto")
        if cached:
            return cached[:limit]

        trends = []
        try:
            resp = self._safe_request(
                "https://dev.to/api/articles",
                params={"per_page": limit, "top": 1}  # top=1 means past day
            )
            if not resp:
                return trends

            articles = resp.json()[:limit]
            for article in articles:
                trends.append({
                    "topic": article.get("title", "")[:150],
                    "url": article.get("url", ""),
                    "reactions": article.get("public_reactions_count", 0),
                    "comments": article.get("comments_count", 0),
                    "tags": article.get("tag_list", []),
                    "category": "dev",
                    "source": "devto"
                })

            self._set_cache("devto", trends)
            logger.info(f"👩‍💻 Got {len(trends)} articles from Dev.to")

        except Exception as e:
            logger.error(f"Dev.to scraper failed: {e}")

        return trends

    def get_techcrunch_rss(self, limit: int = 10) -> List[Dict]:
        """
        Get latest from TechCrunch RSS.
        """
        cached = self._get_cached("techcrunch")
        if cached:
            return cached[:limit]

        trends = []
        try:
            feed = feedparser.parse("https://techcrunch.com/feed/")

            for entry in feed.entries[:limit]:
                trends.append({
                    "topic": entry.get("title", "")[:150],
                    "url": entry.get("link", ""),
                    "summary": entry.get("summary", "")[:200] if entry.get("summary") else "",
                    "published": entry.get("published", ""),
                    "category": "news",
                    "source": "techcrunch"
                })

            self._set_cache("techcrunch", trends)
            logger.info(f"📰 Got {len(trends)} articles from TechCrunch")

        except Exception as e:
            logger.error(f"TechCrunch RSS failed: {e}")

        return trends

    def get_ai_papers(self, limit: int = 5) -> List[Dict]:
        """
        Get trending AI papers from Hugging Face Daily Papers.
        """
        cached = self._get_cached("ai_papers")
        if cached:
            return cached[:limit]

        trends = []
        try:
            resp = self._safe_request("https://huggingface.co/api/daily_papers")
            if not resp:
                return trends

            papers = resp.json()[:limit]
            for paper in papers:
                trends.append({
                    "topic": paper.get("title", "")[:150],
                    "url": f"https://huggingface.co/papers/{paper.get('id', '')}",
                    "upvotes": paper.get("upvotes", 0),
                    "category": "ai",
                    "source": "huggingface"
                })

            self._set_cache("ai_papers", trends)
            logger.info(f"🤖 Got {len(trends)} AI papers from HuggingFace")

        except Exception as e:
            logger.error(f"HuggingFace papers failed: {e}")

        return trends

    def get_all_trends(self, limit_per_source: int = 5) -> List[Dict]:
        """
        Get trends from ALL sources combined.
        Returns a diverse mix of content.
        """
        all_trends = []

        # Tech news (high priority)
        all_trends.extend(self.get_hackernews_trends(limit_per_source))
        all_trends.extend(self.get_lobsters_trends(limit_per_source // 2))

        # Crypto (always relevant)
        all_trends.extend(self.get_crypto_trends(limit_per_source))

        # Developer content
        all_trends.extend(self.get_github_trending(limit_per_source))
        all_trends.extend(self.get_devto_trends(limit_per_source // 2))

        # News
        all_trends.extend(self.get_techcrunch_rss(limit_per_source))

        # AI specific
        all_trends.extend(self.get_ai_papers(limit_per_source // 2))

        # Reddit (various subreddits)
        for sub in ["technology", "cryptocurrency", "MachineLearning", "programming"]:
            all_trends.extend(self.get_reddit_trends(sub, limit_per_source // 2))

        # Sort by score/engagement where available
        def get_score(item):
            return item.get("score", 0) + item.get("reactions", 0) + item.get("upvotes", 0)

        all_trends.sort(key=get_score, reverse=True)

        logger.info(f"📊 Total trends collected: {len(all_trends)} from {self._count_sources(all_trends)} sources")
        return all_trends

    def _count_sources(self, trends: List[Dict]) -> int:
        """Count unique sources."""
        return len(set(t.get("source", "unknown") for t in trends))

    def get_trending_for_content(self) -> Dict:
        """
        Get trends formatted for content creation.
        Returns a dict with categorized trends.
        """
        return {
            "hackernews": self.get_hackernews_trends(5),
            "crypto": self.get_crypto_trends(5),
            "github": self.get_github_trending(5),
            "ai": self.get_ai_papers(3),
            "reddit_tech": self.get_reddit_trends("technology", 3),
            "reddit_ml": self.get_reddit_trends("MachineLearning", 3),
            "news": self.get_techcrunch_rss(3),
            "timestamp": datetime.now().isoformat(),
            "sources_status": self._get_sources_status()
        }

    def _get_sources_status(self) -> Dict:
        """Get status of each source (cached or live)."""
        sources = ["hackernews", "crypto", "github", "lobsters", "devto", "techcrunch", "ai_papers"]
        return {s: "cached" if self._is_cached(s) else "not_cached" for s in sources}


def get_trends_for_prompt() -> str:
    """
    Get trends encoded for LLM prompt using TOON.
    """
    try:
        from toon_helper import encode_trends_for_prompt
        scraper = TrendScraper()
        all_trends = scraper.get_all_trends(limit_per_source=5)
        return encode_trends_for_prompt(all_trends)
    except Exception as e:
        logger.error(f"Failed to get trends for prompt: {e}")
        return "Trends unavailable."


def test_all_sources():
    """Test all sources and print results."""
    scraper = TrendScraper()

    print("\n=== Testing All Trend Sources ===\n")

    sources = [
        ("Hacker News", scraper.get_hackernews_trends, 3),
        ("CoinGecko", scraper.get_crypto_trends, 3),
        ("GitHub Trending", scraper.get_github_trending, 3),
        ("Lobsters", scraper.get_lobsters_trends, 3),
        ("Dev.to", scraper.get_devto_trends, 3),
        ("TechCrunch", scraper.get_techcrunch_rss, 3),
        ("HuggingFace Papers", scraper.get_ai_papers, 3),
        ("Reddit r/technology", lambda n: scraper.get_reddit_trends("technology", n), 3),
    ]

    for name, func, limit in sources:
        print(f"\n--- {name} ---")
        try:
            results = func(limit)
            if results:
                for r in results:
                    print(f"  • {r.get('topic', 'N/A')[:60]}...")
            else:
                print("  (no results)")
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\n=== Test Complete ===")


if __name__ == "__main__":
    test_all_sources()
