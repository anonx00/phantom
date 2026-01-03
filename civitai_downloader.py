"""
CivitAI Video Downloader - Download AI-generated videos from CivitAI for free.

This is a cost-saving alternative to Vertex AI video generation.
CivitAI hosts community-created AI videos that we can use for our X/Twitter posts.

Usage:
    from civitai_downloader import CivitAIVideoDownloader

    downloader = CivitAIVideoDownloader()
    video_path = downloader.get_video()  # Returns path to downloaded video
    # or
    video_path = downloader.get_video(category="anime")  # By category
"""

import os
import time
import logging
import requests
import tempfile
import random
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CivitAIVideoDownloader:
    """
    Downloads AI-generated videos from CivitAI.

    CivitAI has a free API for browsing and downloading community content.
    This saves significant costs compared to generating videos with Vertex AI.
    """

    BASE_URL = "https://civitai.com/api/v1"

    # Map our categories to CivitAI tags
    CATEGORY_TAGS = {
        'ai': ['ai', 'artificial intelligence', 'robot', 'futuristic', 'sci-fi'],
        'tech': ['technology', 'cyber', 'digital', 'neon', 'cyberpunk'],
        'nature': ['nature', 'landscape', 'water', 'sky', 'forest'],
        'abstract': ['abstract', 'surreal', 'psychedelic', 'trippy'],
        'anime': ['anime', 'manga', 'japanese animation'],
        'cinematic': ['cinematic', 'film', 'movie', 'dramatic'],
        'fantasy': ['fantasy', 'magical', 'dragon', 'mythical'],
        'space': ['space', 'cosmic', 'galaxy', 'stars', 'nebula'],
        'art': ['art', 'artistic', 'creative', 'visual'],
        'general': []  # No filter, get trending
    }

    # Popular categories on CivitAI videos page
    TRENDING_CATEGORIES = [
        'anime', 'cinematic', 'nature', 'abstract',
        'fantasy', 'space', 'art', 'cyberpunk'
    ]

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize CivitAI downloader.

        Args:
            api_key: Optional CivitAI API key for higher rate limits.
                     Works without key but with lower limits.
        """
        self.api_key = api_key or os.getenv("CIVITAI_API_KEY")
        self._cache: Dict[str, List[Dict]] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_duration = timedelta(minutes=30)

        if self.api_key:
            self.HEADERS['Authorization'] = f'Bearer {self.api_key}'
            logger.info("CivitAI initialized with API key")
        else:
            logger.info("CivitAI initialized without API key (rate limited)")

    def _get_cached(self, key: str) -> Optional[List[Dict]]:
        """Get cached results if still valid."""
        if key in self._cache:
            cache_age = datetime.now() - self._cache_time.get(key, datetime.min)
            if cache_age < self._cache_duration:
                return self._cache[key]
        return None

    def _set_cache(self, key: str, data: List[Dict]):
        """Cache results."""
        self._cache[key] = data
        self._cache_time[key] = datetime.now()

    def fetch_videos(
        self,
        category: str = 'general',
        limit: int = 20,
        sort: str = 'Most Reactions',
        period: str = 'Week'
    ) -> List[Dict]:
        """
        Fetch videos from CivitAI.

        Args:
            category: Category to filter by (see CATEGORY_TAGS)
            limit: Max videos to fetch
            sort: Sort order - 'Most Reactions', 'Most Comments', 'Newest'
            period: Time period - 'AllTime', 'Year', 'Month', 'Week', 'Day'

        Returns:
            List of video metadata dicts with 'url', 'id', 'stats', etc.
        """
        cache_key = f"{category}_{sort}_{period}"
        cached = self._get_cached(cache_key)
        if cached:
            logger.info(f"Using cached videos for {category} ({len(cached)} videos)")
            return cached

        # CivitAI images API (videos are a type of image/media)
        url = f"{self.BASE_URL}/images"

        # Request more items since we'll filter for videos only
        # Videos are mixed with images in the API response
        params = {
            'limit': min(limit * 5, 100),  # Request more to find enough videos
            'sort': sort,
            'period': period,
            'nsfw': 'None',  # Safe content only
        }

        # Add category tags if specified
        tags = self.CATEGORY_TAGS.get(category, [])
        if tags:
            # Pick a random tag from the category
            params['tag'] = random.choice(tags)

        try:
            logger.info(f"Fetching CivitAI videos: category={category}, sort={sort}")
            response = requests.get(
                url,
                params=params,
                headers=self.HEADERS,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()

            items = data.get('items', [])

            # Filter for video content only
            # Videos have type='video' and URLs ending in .mp4, .webm, etc.
            videos = []
            for item in items:
                item_url = item.get('url', '')
                item_type = item.get('type', '')

                # Check if it's a video by type field or URL extension
                is_video = (
                    item_type == 'video' or
                    any(ext in item_url.lower() for ext in ['.mp4', '.webm', '.mov'])
                )

                if is_video:
                    videos.append({
                        'id': item.get('id'),
                        'url': item_url,
                        'width': item.get('width'),
                        'height': item.get('height'),
                        'hash': item.get('hash'),
                        'stats': item.get('stats', {}),
                        'meta': item.get('meta', {}),
                        'username': item.get('username'),
                        'nsfw_level': item.get('nsfwLevel', 'None'),
                        'type': item_type,
                    })

            logger.info(f"Found {len(videos)} videos from CivitAI (filtered from {len(items)} items)")

            if videos:
                self._set_cache(cache_key, videos)

            return videos

        except requests.exceptions.RequestException as e:
            logger.error(f"CivitAI API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching CivitAI videos: {e}")
            return []

    def fetch_trending_videos(self, limit: int = 50) -> List[Dict]:
        """
        Fetch trending videos across multiple categories.

        Returns a diverse set of trending videos.
        """
        cache_key = "trending_mixed"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        all_videos = []

        # Fetch from multiple categories for diversity
        for category in random.sample(self.TRENDING_CATEGORIES, min(4, len(self.TRENDING_CATEGORIES))):
            videos = self.fetch_videos(
                category=category,
                limit=limit // 4,
                sort='Most Reactions',
                period='Week'
            )
            all_videos.extend(videos)

            # Small delay to avoid rate limiting
            time.sleep(0.5)

        # Also fetch general trending
        general_videos = self.fetch_videos(
            category='general',
            limit=limit // 2,
            sort='Most Reactions',
            period='Week'
        )
        all_videos.extend(general_videos)

        # Remove duplicates by ID
        seen_ids = set()
        unique_videos = []
        for video in all_videos:
            vid = video.get('id')
            if vid and vid not in seen_ids:
                seen_ids.add(vid)
                unique_videos.append(video)

        # Sort by reactions
        unique_videos.sort(
            key=lambda x: x.get('stats', {}).get('likeCount', 0) +
                         x.get('stats', {}).get('heartCount', 0) * 2,
            reverse=True
        )

        logger.info(f"Fetched {len(unique_videos)} unique trending videos")
        self._set_cache(cache_key, unique_videos)

        return unique_videos

    # Allowed domains for video downloads (security)
    ALLOWED_VIDEO_DOMAINS = [
        'civitai.com',
        'cdn.civitai.com',
        'image.civitai.com',
        'video.civitai.com',
    ]

    def download_video(self, video_url: str) -> Optional[str]:
        """
        Download a video to a temporary file.

        Args:
            video_url: Direct URL to the video file

        Returns:
            Path to downloaded video file, or None on failure
        """
        try:
            # Validate domain for security (prevent SSRF)
            from urllib.parse import urlparse
            parsed = urlparse(video_url)
            if not any(domain in parsed.netloc for domain in self.ALLOWED_VIDEO_DOMAINS):
                logger.warning(f"Untrusted video domain rejected: {parsed.netloc}")
                return None

            # Log URL without query params for security
            safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path[:50]}..."
            logger.info(f"Downloading video: {safe_url}")

            response = requests.get(
                video_url,
                headers=self.HEADERS,
                timeout=60,
                stream=True
            )
            response.raise_for_status()

            # Determine extension from URL or content-type
            content_type = response.headers.get('content-type', '')
            if 'webm' in content_type or video_url.lower().endswith('.webm'):
                ext = '.webm'
            elif 'mov' in content_type or video_url.lower().endswith('.mov'):
                ext = '.mov'
            else:
                ext = '.mp4'

            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                file_path = f.name

            file_size = os.path.getsize(file_path)

            # Twitter video limits: 512MB max, but let's be conservative
            max_size = 100 * 1024 * 1024  # 100MB
            if file_size > max_size:
                logger.warning(f"Video too large ({file_size} bytes), skipping")
                os.remove(file_path)
                return None

            if file_size < 10000:  # Less than 10KB is suspicious
                logger.warning(f"Video too small ({file_size} bytes), might be corrupt")
                os.remove(file_path)
                return None

            logger.info(f"Downloaded video: {file_path} ({file_size / 1024 / 1024:.2f} MB)")
            return file_path

        except requests.exceptions.RequestException as e:
            logger.error(f"Video download failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            return None

    def get_video(
        self,
        category: str = 'general',
        prefer_trending: bool = True
    ) -> Optional[Dict]:
        """
        Get a random video and download it.

        This is the main interface - returns both path AND metadata for caption generation.

        Args:
            category: Category to filter by
            prefer_trending: If True, prefer trending videos

        Returns:
            Dict with 'path' and 'metadata', or None on failure
            metadata includes: id, stats, meta, username, category
        """
        videos = []

        if prefer_trending:
            videos = self.fetch_trending_videos()

        if not videos:
            videos = self.fetch_videos(category=category)

        if not videos:
            logger.warning(f"No videos found for category: {category}")
            return None

        # Try up to 5 videos in case of download failures
        random.shuffle(videos)

        for video in videos[:5]:
            video_url = video.get('url')
            if not video_url:
                continue

            video_path = self.download_video(video_url)
            if video_path:
                # Log some metadata
                stats = video.get('stats', {})
                logger.info(f"Selected video - Likes: {stats.get('likeCount', 0)}, "
                           f"Hearts: {stats.get('heartCount', 0)}, "
                           f"Creator: {video.get('username', 'unknown')}")

                # Return both path AND metadata for caption generation
                return {
                    'path': video_path,
                    'metadata': {
                        'id': video.get('id'),
                        'stats': stats,
                        'meta': video.get('meta', {}),
                        'username': video.get('username', 'unknown'),
                        'category': category,
                        'url': video_url,
                    }
                }

        logger.error("Failed to download any video from CivitAI")
        return None

    def get_video_for_prompt(self, prompt: str) -> Optional[Dict]:
        """
        Get a video that somewhat matches a prompt.

        This provides compatibility with VeoClient.generate_video(prompt).
        Since we can't generate custom videos, we try to match keywords.

        Args:
            prompt: The video prompt (used to guess category)

        Returns:
            Dict with 'path' and 'metadata', or None on failure
        """
        prompt_lower = prompt.lower()

        # Try to match prompt to a category
        category = 'general'

        category_keywords = {
            'anime': ['anime', 'manga', 'japanese', 'cartoon'],
            'space': ['space', 'galaxy', 'stars', 'cosmic', 'nebula', 'universe'],
            'nature': ['nature', 'forest', 'water', 'ocean', 'mountain', 'landscape', 'sky'],
            'abstract': ['abstract', 'surreal', 'trippy', 'psychedelic', 'kaleidoscope'],
            'fantasy': ['fantasy', 'magic', 'dragon', 'mythical', 'fairy'],
            'cinematic': ['cinematic', 'dramatic', 'epic', 'film'],
            'tech': ['cyber', 'tech', 'digital', 'neon', 'cyberpunk', 'futuristic'],
            'art': ['art', 'artistic', 'creative', 'painting'],
        }

        for cat, keywords in category_keywords.items():
            if any(kw in prompt_lower for kw in keywords):
                category = cat
                logger.info(f"Matched prompt to category: {category}")
                break

        return self.get_video(category=category)


# Convenience function matching VeoClient interface
def download_civitai_video(prompt: str = "") -> Optional[Dict]:
    """
    Download a video from CivitAI.

    Drop-in replacement for VeoClient.generate_video().

    Args:
        prompt: Optional prompt to guide category selection

    Returns:
        Dict with 'path' and 'metadata', or None on failure
    """
    downloader = CivitAIVideoDownloader()

    if prompt:
        return downloader.get_video_for_prompt(prompt)
    else:
        return downloader.get_video()


if __name__ == "__main__":
    # Test the downloader
    logging.basicConfig(level=logging.INFO)

    print("Testing CivitAI Video Downloader...")

    downloader = CivitAIVideoDownloader()

    # Test fetching videos
    print("\n1. Fetching trending videos...")
    videos = downloader.fetch_trending_videos(limit=10)
    print(f"   Found {len(videos)} trending videos")

    if videos:
        print(f"   Top video: {videos[0].get('url', 'N/A')[:60]}...")
        print(f"   Stats: {videos[0].get('stats', {})}")

    # Test downloading
    print("\n2. Testing download...")
    video_path = downloader.get_video()

    if video_path:
        print(f"   Downloaded: {video_path}")
        file_size = os.path.getsize(video_path)
        print(f"   Size: {file_size / 1024 / 1024:.2f} MB")

        # Cleanup
        os.remove(video_path)
        print("   Cleaned up test file")
    else:
        print("   Download failed")

    print("\nTest complete!")
