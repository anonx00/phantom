import logging
import requests
from typing import Dict, List, Optional
from config import Config, get_secret

logger = logging.getLogger(__name__)

class YouTubeFetcher:
    """
    Fetches trending tech/educational videos from YouTube for content inspiration.
    Uses YouTube Data API v3 to find infographic-worthy topics.
    """

    def __init__(self):
        self.session = requests.Session()
        self.api_key = None

        # Try to get YouTube API key from Secret Manager
        try:
            self.api_key = get_secret("YOUTUBE_API_KEY")
            logger.info("YouTube API key loaded from Secret Manager")
        except Exception as e:
            logger.warning(f"YouTube API key not available: {e}")
            logger.warning("YouTube fetcher will use fallback search")

        self.base_url = "https://www.googleapis.com/youtube/v3"

        # Tech/Educational channel IDs for curated content
        self.curated_channels = {
            'ai_explained': [
                'UCWN3xxRkmTPmbKwht9FuE5A',  # Siraj Raval
                'UCbfYPyITQ-7l4upoX8nvctg',  # Two Minute Papers
                'UCZHmQk67mSJgfCCTn7xBfew',  # Lex Fridman
                'UCYO_jab_esuFRV4b17AJtAw',  # 3Blue1Brown
                'UCvjgXvBlFQRa8hNlaDpHjIQ',  # Yannic Kilcher
            ],
            'tech_news': [
                'UCBcRF18a7Qf58cCRy5xuWwQ',  # MKBHD
                'UCXuqSBlHAE6Xw-yeJA0Tunw',  # Linus Tech Tips
                'UCdBK94H6oZT2Q7l0-b0xmMg',  # Short Circuit
            ],
            'infographics': [
                'UCsXVk37bltHxD1rDPwtNM8Q',  # Kurzgesagt
                'UC6nSFpj9HTCZ5t-N3Rm3-HA',  # Vsauce
                'UCsooa4yRKGN_zEE8iknghZA',  # TED-Ed
            ]
        }

        # Search queries for finding infographic-worthy content
        self.search_queries = [
            "AI explained infographic 2024",
            "machine learning visualization tutorial",
            "tech trends explained 2024",
            "how neural networks work visual",
            "cryptocurrency explained animation",
            "blockchain technology infographic",
            "tech startup explained",
            "silicon valley news explained",
            "coding tutorial visualization",
            "algorithm explained animation",
            "data science infographic",
            "future technology explained",
        ]

    def search_videos(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Searches YouTube for videos matching the query.
        Returns list of video metadata.
        """
        if not self.api_key:
            logger.warning("No YouTube API key, returning empty results")
            return []

        try:
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'maxResults': max_results,
                'order': 'relevance',
                'videoDuration': 'medium',  # 4-20 minutes (educational content)
                'key': self.api_key,
                'relevanceLanguage': 'en',
            }

            response = self.session.get(
                f"{self.base_url}/search",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            videos = []
            for item in data.get('items', []):
                snippet = item.get('snippet', {})
                videos.append({
                    'video_id': item['id']['videoId'],
                    'title': snippet.get('title', ''),
                    'description': snippet.get('description', '')[:500],
                    'channel': snippet.get('channelTitle', ''),
                    'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                    'published_at': snippet.get('publishedAt', ''),
                    'url': f"https://youtube.com/watch?v={item['id']['videoId']}",
                    'source': 'youtube_search',
                    'category': self._categorize_video(snippet.get('title', ''), snippet.get('description', ''))
                })

            logger.info(f"Found {len(videos)} videos for query: {query[:30]}...")
            return videos

        except Exception as e:
            logger.error(f"YouTube search failed: {e}")
            return []

    def get_channel_videos(self, channel_id: str, max_results: int = 5) -> List[Dict]:
        """
        Gets recent videos from a specific channel.
        """
        if not self.api_key:
            return []

        try:
            params = {
                'part': 'snippet',
                'channelId': channel_id,
                'type': 'video',
                'maxResults': max_results,
                'order': 'date',
                'key': self.api_key,
            }

            response = self.session.get(
                f"{self.base_url}/search",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            videos = []
            for item in data.get('items', []):
                snippet = item.get('snippet', {})
                videos.append({
                    'video_id': item['id']['videoId'],
                    'title': snippet.get('title', ''),
                    'description': snippet.get('description', '')[:500],
                    'channel': snippet.get('channelTitle', ''),
                    'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                    'url': f"https://youtube.com/watch?v={item['id']['videoId']}",
                    'source': 'youtube_channel',
                    'category': self._categorize_video(snippet.get('title', ''), snippet.get('description', ''))
                })

            return videos

        except Exception as e:
            logger.warning(f"Failed to fetch channel {channel_id}: {e}")
            return []

    def get_trending_tech_videos(self) -> List[Dict]:
        """
        Gets trending tech/educational videos from curated sources.
        Combines search results and channel content.
        """
        all_videos = []

        # 1. Search for infographic-worthy content
        import random
        selected_queries = random.sample(self.search_queries, min(3, len(self.search_queries)))

        for query in selected_queries:
            videos = self.search_videos(query, max_results=5)
            all_videos.extend(videos)

        # 2. Get content from curated channels
        for category, channels in self.curated_channels.items():
            for channel_id in random.sample(channels, min(2, len(channels))):
                videos = self.get_channel_videos(channel_id, max_results=3)
                all_videos.extend(videos)

        # 3. Deduplicate by video_id
        seen_ids = set()
        unique_videos = []
        for video in all_videos:
            if video.get('video_id') not in seen_ids:
                seen_ids.add(video['video_id'])
                unique_videos.append(video)

        logger.info(f"Fetched {len(unique_videos)} unique tech/educational videos")
        return unique_videos

    def _categorize_video(self, title: str, description: str) -> str:
        """
        Categorizes video based on title and description.
        """
        text = (title + " " + description).lower()

        ai_keywords = ['ai', 'artificial intelligence', 'machine learning', 'neural', 'gpt',
                      'llm', 'deep learning', 'transformer', 'openai', 'anthropic']
        crypto_keywords = ['crypto', 'bitcoin', 'ethereum', 'blockchain', 'web3', 'defi', 'nft']
        finance_keywords = ['stock', 'market', 'investment', 'trading', 'economy', 'finance']

        for kw in ai_keywords:
            if kw in text:
                return 'ai'
        for kw in crypto_keywords:
            if kw in text:
                return 'crypto'
        for kw in finance_keywords:
            if kw in text:
                return 'finance'

        return 'tech'

    def get_infographic_topic(self) -> Optional[Dict]:
        """
        Gets a single trending video topic suitable for creating an infographic.
        Returns video metadata with extracted key concepts.
        """
        videos = self.get_trending_tech_videos()

        if not videos:
            logger.warning("No YouTube videos found, using fallback topics")
            return self._get_fallback_topic()

        # Score videos by infographic potential
        scored_videos = []

        infographic_keywords = [
            'explained', 'how', 'what is', 'guide', 'tutorial',
            'visualization', 'infographic', 'breakdown', 'deep dive',
            'understand', 'learn', 'beginner', 'introduction', 'basics'
        ]

        for video in videos:
            title_lower = video['title'].lower()
            score = 0

            # Higher score for educational content
            for kw in infographic_keywords:
                if kw in title_lower:
                    score += 20

            # Prefer AI/tech content
            if video['category'] == 'ai':
                score += 30
            elif video['category'] == 'tech':
                score += 20

            # Prefer curated channels
            if video['source'] == 'youtube_channel':
                score += 15

            scored_videos.append({**video, 'infographic_score': score})

        # Sort by score and pick from top 5
        scored_videos.sort(key=lambda x: x['infographic_score'], reverse=True)

        import random
        top_videos = scored_videos[:5]
        selected = random.choice(top_videos) if top_videos else None

        if selected:
            logger.info(f"Selected infographic topic: {selected['title'][:60]}... (score: {selected['infographic_score']})")

        return selected

    def _get_fallback_topic(self) -> Dict:
        """
        Returns a fallback topic when YouTube API is unavailable.
        """
        import random
        fallback_topics = [
            {
                'title': 'How Transformer Neural Networks Work',
                'description': 'Visual explanation of transformer architecture, attention mechanisms, and why they revolutionized AI',
                'category': 'ai',
                'url': None,
                'source': 'fallback'
            },
            {
                'title': 'The Evolution of Programming Languages',
                'description': 'Timeline infographic showing the development of major programming languages from 1950s to today',
                'category': 'tech',
                'url': None,
                'source': 'fallback'
            },
            {
                'title': 'How Bitcoin Mining Actually Works',
                'description': 'Visual breakdown of proof-of-work, hash functions, and the mining reward system',
                'category': 'crypto',
                'url': None,
                'source': 'fallback'
            },
            {
                'title': 'AI Model Sizes: From GPT-1 to GPT-4',
                'description': 'Comparative infographic showing parameter counts, training data, and capabilities across model generations',
                'category': 'ai',
                'url': None,
                'source': 'fallback'
            },
            {
                'title': 'Tech Company Market Caps 2024',
                'description': 'Visual comparison of top tech companies by market capitalization and growth',
                'category': 'finance',
                'url': None,
                'source': 'fallback'
            },
        ]

        return random.choice(fallback_topics)

    def extract_key_concepts(self, video: Dict) -> List[str]:
        """
        Extracts key concepts from video metadata for infographic generation.
        Returns list of concepts to visualize.
        """
        title = video.get('title', '')
        description = video.get('description', '')

        # Simple keyword extraction (could be enhanced with NLP)
        text = f"{title} {description}".lower()

        # Common tech concepts to look for
        concept_patterns = {
            'neural network': 'Neural Networks',
            'machine learning': 'Machine Learning',
            'deep learning': 'Deep Learning',
            'transformer': 'Transformer Architecture',
            'attention mechanism': 'Attention Mechanism',
            'gpu': 'GPU Computing',
            'training data': 'Training Data',
            'model': 'AI Model',
            'algorithm': 'Algorithm',
            'api': 'API',
            'cloud': 'Cloud Computing',
            'data': 'Data Processing',
            'security': 'Cybersecurity',
            'blockchain': 'Blockchain',
            'smart contract': 'Smart Contracts',
        }

        found_concepts = []
        for pattern, concept in concept_patterns.items():
            if pattern in text and concept not in found_concepts:
                found_concepts.append(concept)

        # Ensure we have at least some concepts
        if not found_concepts:
            found_concepts = ['Technology', 'Innovation', 'Digital']

        return found_concepts[:5]  # Max 5 concepts
