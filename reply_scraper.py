"""
Reply Scraper - Scrape replies without Twitter API

Uses Nitter (open-source Twitter frontend) to scrape replies to our tweets.
No API limits, no authentication required.

Workflow:
1. Scrape our profile for recent tweets
2. For each tweet, scrape the replies
3. Use unified ReplyTracker to check/record replies
4. AI decides which to respond to
5. Post replies via Twitter API (clearly marked as REPLY not POST)

IMPORTANT: This creates REPLIES, not POSTS. Replies are tracked separately.
"""

import logging
import requests
import re
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup
from google.cloud import firestore

logger = logging.getLogger(__name__)

# Log prefix for clarity
LOG_PREFIX = "[SCRAPE-REPLY]"

# Working Nitter instances (as of 2024-2025)
# These change frequently - we try multiple
NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.unixfox.eu",
]


class ReplyScraper:
    """Scrapes replies to our tweets using Nitter."""

    def __init__(self, username: str, project_id: str):
        """
        Args:
            username: Twitter username (without @)
            project_id: GCP project ID for Firestore
        """
        self.username = username.lstrip('@')
        self.project_id = project_id
        self.db = firestore.Client(project=project_id)
        self.replies_collection = self.db.collection("scraped_replies")

        # Use unified reply tracker
        from reply_tracker import get_reply_tracker
        self.reply_tracker = get_reply_tracker(project_id)

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.working_instance = None

    def _find_working_nitter(self) -> Optional[str]:
        """Find a working Nitter instance."""
        if self.working_instance:
            return self.working_instance

        for instance in NITTER_INSTANCES:
            try:
                resp = self.session.get(f"{instance}/{self.username}", timeout=10)
                if resp.status_code == 200 and 'timeline' in resp.text.lower():
                    logger.info(f"✅ Found working Nitter: {instance}")
                    self.working_instance = instance
                    return instance
            except Exception as e:
                logger.debug(f"Nitter {instance} failed: {e}")
                continue

        logger.warning("❌ No working Nitter instances found")
        return None

    def _get_reply_id(self, reply: Dict) -> str:
        """Generate unique ID for a reply."""
        content = f"{reply['author']}:{reply['text']}:{reply['tweet_id']}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _is_reply_seen(self, reply_id: str) -> bool:
        """Check if we've already processed this reply."""
        doc = self.replies_collection.document(reply_id).get()
        return doc.exists

    def _mark_reply_seen(self, reply_id: str, reply: Dict, response: str = None):
        """Mark a reply as seen/processed."""
        self.replies_collection.document(reply_id).set({
            "reply_id": reply_id,
            "author": reply["author"],
            "text": reply["text"],
            "tweet_id": reply["tweet_id"],
            "our_response": response,
            "scraped_at": firestore.SERVER_TIMESTAMP,
            "responded": response is not None
        })

    def get_our_recent_tweets(self, limit: int = 10) -> List[Dict]:
        """Get our recent tweets to check for replies."""
        nitter = self._find_working_nitter()
        if not nitter:
            return []

        tweets = []
        try:
            resp = self.session.get(f"{nitter}/{self.username}", timeout=15)
            if resp.status_code != 200:
                logger.error(f"Failed to fetch profile: {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Find tweet containers
            tweet_elements = soup.select('.timeline-item, .tweet-body')

            for elem in tweet_elements[:limit]:
                try:
                    # Extract tweet link/ID
                    link = elem.select_one('a.tweet-link, .tweet-date a')
                    if not link:
                        continue

                    href = link.get('href', '')
                    tweet_id_match = re.search(r'/status/(\d+)', href)
                    if not tweet_id_match:
                        continue

                    tweet_id = tweet_id_match.group(1)

                    # Extract tweet text
                    text_elem = elem.select_one('.tweet-content, .media-body')
                    text = text_elem.get_text(strip=True) if text_elem else ""

                    # Extract stats
                    replies_elem = elem.select_one('.icon-comment + span, .tweet-stat:first-child')
                    reply_count = 0
                    if replies_elem:
                        count_text = replies_elem.get_text(strip=True)
                        reply_count = int(re.sub(r'[^\d]', '', count_text) or 0)

                    tweets.append({
                        "tweet_id": tweet_id,
                        "text": text[:200],
                        "reply_count": reply_count,
                        "url": f"https://twitter.com/{self.username}/status/{tweet_id}"
                    })

                except Exception as e:
                    logger.debug(f"Error parsing tweet: {e}")
                    continue

            logger.info(f"📝 Found {len(tweets)} recent tweets")
            return tweets

        except Exception as e:
            logger.error(f"Error fetching tweets: {e}")
            return []

    def get_replies_to_tweet(self, tweet_id: str) -> List[Dict]:
        """Get replies to a specific tweet."""
        nitter = self._find_working_nitter()
        if not nitter:
            return []

        replies = []
        try:
            url = f"{nitter}/{self.username}/status/{tweet_id}"
            resp = self.session.get(url, timeout=15)

            if resp.status_code != 200:
                logger.warning(f"Failed to fetch tweet {tweet_id}: {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Find reply containers (replies are in a different section)
            reply_elements = soup.select('.reply, .timeline-item.thread')

            for elem in reply_elements:
                try:
                    # Get reply author
                    author_elem = elem.select_one('.username, .tweet-name-row a')
                    if not author_elem:
                        continue

                    author = author_elem.get_text(strip=True).lstrip('@')

                    # Skip our own replies
                    if author.lower() == self.username.lower():
                        continue

                    # Get reply text
                    text_elem = elem.select_one('.tweet-content, .media-body')
                    text = text_elem.get_text(strip=True) if text_elem else ""

                    if not text:
                        continue

                    # Get reply ID if available
                    reply_link = elem.select_one('a.tweet-link, .tweet-date a')
                    reply_id = ""
                    if reply_link:
                        href = reply_link.get('href', '')
                        id_match = re.search(r'/status/(\d+)', href)
                        if id_match:
                            reply_id = id_match.group(1)

                    replies.append({
                        "author": author,
                        "text": text[:500],
                        "tweet_id": tweet_id,  # The tweet they replied to
                        "reply_tweet_id": reply_id,  # Their reply's tweet ID
                    })

                except Exception as e:
                    logger.debug(f"Error parsing reply: {e}")
                    continue

            logger.info(f"💬 Found {len(replies)} replies to tweet {tweet_id}")
            return replies

        except Exception as e:
            logger.error(f"Error fetching replies: {e}")
            return []

    def scrape_new_replies(self, max_tweets: int = 5) -> List[Dict]:
        """
        Main method: Scrape for new replies we haven't seen.

        Returns list of new replies ready for AI processing.
        """
        new_replies = []

        # Get our recent tweets
        tweets = self.get_our_recent_tweets(limit=max_tweets)

        for tweet in tweets:
            # Only check tweets that have replies
            if tweet.get("reply_count", 0) == 0:
                continue

            # Get replies to this tweet
            replies = self.get_replies_to_tweet(tweet["tweet_id"])

            for reply in replies:
                reply_id = self._get_reply_id(reply)

                # Skip if we've seen this reply
                if self._is_reply_seen(reply_id):
                    continue

                # Add context about our original tweet
                reply["our_tweet_text"] = tweet["text"]
                reply["our_tweet_url"] = tweet["url"]
                reply["reply_id"] = reply_id

                new_replies.append(reply)
                logger.info(f"🆕 New reply from @{reply['author']}: {reply['text'][:50]}...")

        logger.info(f"📊 Found {len(new_replies)} new replies to process")
        return new_replies

    def mark_replied(self, reply_id: str, reply: Dict, our_response: str):
        """Mark that we responded to a reply."""
        self._mark_reply_seen(reply_id, reply, our_response)

    def mark_skipped(self, reply_id: str, reply: Dict):
        """Mark that we saw but chose not to respond to a reply."""
        self._mark_reply_seen(reply_id, reply, response=None)


class AIReplyDecider:
    """AI decides which replies are worth responding to."""

    def __init__(self, project_id: str):
        self.project_id = project_id

    def _get_model(self):
        """Initialize Vertex AI model."""
        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=self.project_id, location="us-central1")
        return GenerativeModel("gemini-1.5-flash-002")

    def evaluate_replies(self, replies: List[Dict], max_responses: int = 3) -> List[Dict]:
        """
        AI evaluates which replies are worth responding to.

        Args:
            replies: List of new replies
            max_responses: Max number of replies to respond to

        Returns:
            List of replies to respond to, with generated responses
        """
        if not replies:
            return []

        model = self._get_model()

        # Format replies for AI evaluation
        replies_text = "\n\n".join([
            f"REPLY #{i+1}:\n"
            f"From: @{r['author']}\n"
            f"Their reply: {r['text']}\n"
            f"(Replying to our tweet: {r.get('our_tweet_text', 'N/A')[:100]})"
            for i, r in enumerate(replies[:10])  # Max 10 at a time
        ])

        prompt = f"""You control a tech Twitter account (@PatriotxSystem). You're a cynical tech veteran with dry wit.

Here are new replies to your tweets. Decide which ones to respond to.

CRITERIA FOR RESPONDING:
- Thoughtful engagement (not just "nice" or spam)
- Opportunities for witty banter
- Tech/crypto discussions worth engaging
- Building community with real users
- Skip: bots, spam, low-effort, trolls, just emojis

{replies_text}

TASK:
1. Pick up to {max_responses} replies worth responding to
2. Generate a response for each (short, punchy, in character)

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:
RESPOND_TO: #1
RESPONSE: [your witty reply under 200 chars]

RESPOND_TO: #3
RESPONSE: [your witty reply under 200 chars]

SKIP_REST: [brief reason why others aren't worth it]

If none are worth responding to, just say:
SKIP_ALL: [reason]"""

        try:
            response = model.generate_content(prompt)
            result_text = response.text

            # Parse AI decisions
            to_respond = []

            # Find all RESPOND_TO blocks
            respond_pattern = r'RESPOND_TO:\s*#(\d+)\s*\nRESPONSE:\s*(.+?)(?=\n\n|RESPOND_TO:|SKIP|$)'
            matches = re.findall(respond_pattern, result_text, re.DOTALL)

            for match in matches:
                reply_num = int(match[0]) - 1  # Convert to 0-indexed
                response_text = match[1].strip()

                if 0 <= reply_num < len(replies):
                    reply = replies[reply_num].copy()
                    reply["ai_response"] = response_text
                    to_respond.append(reply)
                    logger.info(f"✅ AI chose to reply to @{reply['author']}")

            return to_respond

        except Exception as e:
            logger.error(f"AI evaluation failed: {e}")
            return []


def scrape_and_respond(username: str, project_id: str, twitter_api_v1, max_responses: int = 3) -> int:
    """
    Main entry point: Scrape replies and respond.

    IMPORTANT: This sends REPLIES, not POSTS. They are tracked separately.

    Args:
        username: Our Twitter username
        project_id: GCP project ID
        twitter_api_v1: Tweepy API v1 instance for posting
        max_responses: Max replies to send

    Returns:
        Number of replies sent
    """
    logger.info(f"{LOG_PREFIX} Starting reply scrape cycle...")

    # Initialize components
    scraper = ReplyScraper(username, project_id)
    decider = AIReplyDecider(project_id)

    # Get unified reply tracker
    from reply_tracker import get_reply_tracker
    reply_tracker = get_reply_tracker(project_id)

    # Scrape for new replies
    new_replies = scraper.scrape_new_replies(max_tweets=10)

    if not new_replies:
        logger.info(f"{LOG_PREFIX} No new replies found")
        return 0

    # Filter out replies we've already responded to (using unified tracker)
    filtered_replies = []
    for reply in new_replies:
        target_id = reply.get("reply_tweet_id") or reply.get("tweet_id", "")
        if reply_tracker.has_replied_to(target_id, reply["author"]):
            logger.debug(f"{LOG_PREFIX} Already replied to @{reply['author']}, skipping")
            continue
        if reply_tracker.has_seen_mention(reply["author"], reply["text"], target_id):
            logger.debug(f"{LOG_PREFIX} Already seen this mention, skipping")
            continue
        filtered_replies.append(reply)

    if not filtered_replies:
        logger.info(f"{LOG_PREFIX} All replies already processed")
        return 0

    logger.info(f"{LOG_PREFIX} {len(filtered_replies)} new replies to evaluate")

    # AI decides which to respond to
    to_respond = decider.evaluate_replies(filtered_replies, max_responses=max_responses)

    # Mark skipped replies in unified tracker
    responded_ids = {r["reply_id"] for r in to_respond}
    for reply in filtered_replies:
        if reply["reply_id"] not in responded_ids:
            target_id = reply.get("reply_tweet_id") or reply.get("tweet_id", "")
            reply_tracker.record_mention_seen(
                author=reply["author"],
                text=reply["text"],
                tweet_id=target_id,
                responded=False,
                skip_reason="AI decided not to engage"
            )
            scraper.mark_skipped(reply["reply_id"], reply)

    # Post responses
    responses_sent = 0
    for reply in to_respond:
        try:
            # Build reply text
            response_text = f"@{reply['author']} {reply['ai_response']}"

            # Truncate if needed (280 char limit)
            if len(response_text) > 280:
                max_response = 280 - len(f"@{reply['author']} ") - 3
                response_text = f"@{reply['author']} {reply['ai_response'][:max_response]}..."

            target_id = reply.get("reply_tweet_id") or reply.get("tweet_id", "")

            # Post REPLY (not post) using v1 API
            logger.info(f"{LOG_PREFIX} Sending REPLY to @{reply['author']}...")

            if reply.get("reply_tweet_id"):
                result = twitter_api_v1.update_status(
                    status=response_text,
                    in_reply_to_status_id=reply["reply_tweet_id"],
                    auto_populate_reply_metadata=True
                )
                our_reply_id = str(result.id) if result else None
            else:
                # Fallback: post mentioning them (still a reply, just orphaned)
                result = twitter_api_v1.update_status(status=response_text)
                our_reply_id = str(result.id) if result else None

            # Record in unified tracker (this is the source of truth)
            reply_tracker.record_reply_sent(
                target_tweet_id=target_id,
                target_author=reply["author"],
                target_text=reply["text"],
                our_reply=reply["ai_response"],
                our_reply_tweet_id=our_reply_id,
                source="scraper"
            )

            # Also mark in scraper's own collection (for backward compatibility)
            scraper.mark_replied(reply["reply_id"], reply, reply["ai_response"])

            responses_sent += 1
            logger.info(f"{LOG_PREFIX} REPLY sent to @{reply['author']}: {reply['ai_response'][:50]}...")

        except Exception as e:
            logger.error(f"{LOG_PREFIX} Failed to send REPLY to @{reply['author']}: {e}")
            # Mark as seen to avoid retry loops
            target_id = reply.get("reply_tweet_id") or reply.get("tweet_id", "")
            reply_tracker.record_mention_seen(
                author=reply["author"],
                text=reply["text"],
                tweet_id=target_id,
                responded=False,
                skip_reason=f"Error: {str(e)[:100]}"
            )
            scraper.mark_skipped(reply["reply_id"], reply)

    logger.info(f"{LOG_PREFIX} Reply cycle complete: {responses_sent} REPLIES sent (not posts)")
    return responses_sent
