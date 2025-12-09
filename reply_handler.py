"""
Reply Handler - FREE Tier Mention Monitoring & Replies

Works within FREE tier constraints:
- GET /2/users/:id/mentions: 1 request per 15 minutes
- POST /2/tweets: 17 per day (shared with posts)

AI decides:
- Which mentions are worth replying to
- What to say in response
- When to stay silent

ZERO WASTE:
- Only generate reply if AI approves engagement
- Store interactions for memory/learning
"""

import logging
import tweepy
from typing import List, Dict, Optional
from datetime import datetime
from google.cloud import firestore
from config import Config
from ai_agent_controller import AIAgentController

logger = logging.getLogger(__name__)


class ReplyHandler:
    """
    Handles Twitter mentions and replies within FREE tier limits.
    AI decides what's worth engaging with.
    """

    def __init__(
        self,
        api_v1: tweepy.API,
        client_v2: tweepy.Client,
        controller: AIAgentController,
        ai_generate_func,
        bot_username: str = "PatriotxSystem"
    ):
        """
        Initialize reply handler.

        Args:
            api_v1: Tweepy v1 API
            client_v2: Tweepy v2 API
            controller: AIAgentController for budget tracking
            ai_generate_func: Function to generate AI responses
            bot_username: Bot's Twitter username
        """
        self.api_v1 = api_v1
        self.client_v2 = client_v2
        self.controller = controller
        self.generate_ai = ai_generate_func
        self.bot_username = bot_username

        self.db = firestore.Client(project=Config.PROJECT_ID)
        self.interactions_collection = self.db.collection("ai_memory")

        # Use vector memory from controller for rich context
        self.vector_memory = controller.vector_memory
        logger.info("🧠 Reply handler using vector memory for context")

        # Get bot user ID
        self._bot_user_id = None

    def _get_bot_user_id(self) -> Optional[str]:
        """Get bot's Twitter user ID."""
        if self._bot_user_id:
            return self._bot_user_id

        try:
            me = self.client_v2.get_user(username=self.bot_username)
            if me and me.data:
                self._bot_user_id = me.data.id
                logger.info(f"Bot user ID: {self._bot_user_id}")
                return self._bot_user_id
        except Exception as e:
            logger.error(f"Failed to get bot user ID: {e}")

        return None

    def _get_last_mention_id(self) -> Optional[str]:
        """Get the ID of the last mention we processed."""
        try:
            doc = self.db.collection("system_state").document("last_mention").get()
            if doc.exists:
                return doc.to_dict().get("tweet_id")
        except Exception as e:
            logger.error(f"Failed to get last mention ID: {e}")

        return None

    def _save_last_mention_id(self, tweet_id: str):
        """Save the ID of the last mention we processed."""
        try:
            self.db.collection("system_state").document("last_mention").set({
                "tweet_id": tweet_id,
                "timestamp": firestore.SERVER_TIMESTAMP
            })
        except Exception as e:
            logger.error(f"Failed to save last mention ID: {e}")

    def check_mentions(self) -> List[Dict]:
        """
        Check for new mentions (FREE tier: 1 call per 15 min).

        Returns:
            List of new mention dicts
        """
        # Check if we can make the API call
        can_check, reason = self.controller.can_check_mentions()
        if not can_check:
            logger.info(f"⏸️ Skipping mention check: {reason}")
            return []

        user_id = self._get_bot_user_id()
        if not user_id:
            logger.error("Cannot check mentions without user ID")
            return []

        try:
            # Get last processed mention ID
            since_id = self._get_last_mention_id()

            params = {
                "id": user_id,
                "max_results": 5,  # Conservative for FREE tier
                "tweet_fields": ["created_at", "author_id", "conversation_id", "text"],
                "expansions": ["author_id"],
                "user_fields": ["username", "name", "public_metrics"]
            }

            if since_id:
                params["since_id"] = since_id

            response = self.client_v2.get_users_mentions(**params)

            # Record that we made the API call
            self.controller.record_mention_check()

            if not response or not response.data:
                logger.info("No new mentions found")
                return []

            # Parse mentions
            mentions = []
            users_map = {}

            # Build user map
            if hasattr(response, 'includes') and 'users' in response.includes:
                for user in response.includes['users']:
                    users_map[user.id] = {
                        "username": user.username,
                        "name": user.name,
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
                }

                mentions.append(mention)

            if mentions:
                # Save last mention ID
                self._save_last_mention_id(mentions[0]["tweet_id"])
                logger.info(f"📬 Found {len(mentions)} new mentions")

            return mentions

        except tweepy.errors.TooManyRequests:
            logger.warning("Rate limited by Twitter API")
            return []
        except Exception as e:
            logger.error(f"Failed to check mentions: {e}")
            return []

    def ai_should_reply(self, mention: Dict) -> Tuple[bool, str]:
        """
        AI decides if this mention is worth replying to.

        Args:
            mention: Mention dict

        Returns:
            (should_reply, reason)
        """
        # Check if we've already interacted with this tweet (using vector memory)
        if self.vector_memory.has_interacted_with(mention["tweet_id"]):
            return False, "Already interacted with this tweet"

        # Get rich context from vector memory
        from memory_system import ConversationContext
        context_builder = ConversationContext(self.vector_memory)

        rich_context = context_builder.build_reply_context(
            tweet_id=mention["tweet_id"],
            author=mention["author_username"],
            content=mention["text"]
        )

        prompt = f"""You control @{self.bot_username}. Someone mentioned you. Decide if you should reply.

{rich_context}

YOUR PERSONA: BIG BOSS - war-weary tech veteran, dry wit, cynical but not bitter.

CONSIDER:
- Is this a genuine question or comment worth engaging with?
- Or is it spam, low-effort, or trying to start an argument?
- Does this person seem real and worth talking to?
- Would your reply add value or just be noise?

You're selective. You don't reply to everything. Quality over quantity.

Respond:
SHOULD_REPLY: <YES or NO>
REASON: <one sentence why>"""

        try:
            response = self.generate_ai(prompt)

            # Parse decision
            import re
            should_match = re.search(r'SHOULD_REPLY:\s*(YES|NO)', response, re.IGNORECASE)
            reason_match = re.search(r'REASON:\s*(.+)', response)

            if should_match:
                should_reply = should_match.group(1).upper() == "YES"
                reason = reason_match.group(1) if reason_match else "AI decision"

                logger.info(f"🤔 AI decision for @{mention['author_username']}: {should_reply}")
                logger.info(f"   Reason: {reason}")

                return should_reply, reason

        except Exception as e:
            logger.error(f"AI decision failed: {e}")

        # Conservative fallback: don't reply
        return False, "AI decision failed, defaulting to no reply"

    def generate_reply(self, mention: Dict) -> Optional[str]:
        """
        AI generates a reply to the mention with full context awareness.

        Args:
            mention: Mention dict

        Returns:
            Reply text or None
        """
        # Get rich context from vector memory
        from memory_system import ConversationContext
        context_builder = ConversationContext(self.vector_memory)

        rich_context = context_builder.build_reply_context(
            tweet_id=mention["tweet_id"],
            author=mention["author_username"],
            content=mention["text"]
        )

        prompt = f"""Generate a reply to this mention as @{self.bot_username}.

{rich_context}

YOUR PERSONA: BIG BOSS - war-weary tech veteran. Dry wit. Short and punchy.

REPLY REQUIREMENTS:
- Direct and conversational
- 100-250 characters (leave room for username)
- No hashtags, no emojis
- Sound HUMAN, not robotic
- Stay in character

Generate ONLY the reply text, nothing else:"""

        try:
            response = self.generate_ai(prompt)

            # Clean response
            reply = response.strip().strip('"').strip("'")

            # Remove any prefixes
            prefixes = ["REPLY:", "OUTPUT:", "@" + mention["author_username"]]
            for prefix in prefixes:
                if reply.startswith(prefix):
                    reply = reply[len(prefix):].strip()

            # Validate length
            if len(reply) < 10:
                logger.warning("Reply too short, skipping")
                return None

            if len(reply) > 250:
                logger.warning(f"Reply too long ({len(reply)}), truncating")
                reply = reply[:247] + "..."

            logger.info(f"💬 Generated reply: {reply[:60]}...")
            return reply

        except Exception as e:
            logger.error(f"Reply generation failed: {e}")
            return None

    def post_reply(self, mention: Dict, reply_text: str) -> bool:
        """
        Post reply to Twitter.

        Args:
            mention: Mention dict
            reply_text: Reply text

        Returns:
            Success status
        """
        try:
            response = self.client_v2.create_tweet(
                text=reply_text,
                in_reply_to_tweet_id=mention["tweet_id"]
            )

            if response and response.data:
                posted_id = response.data['id']
                logger.info(f"✅ Posted reply {posted_id} to @{mention['author_username']}")

                # Record the interaction
                self._store_interaction(mention, reply_text, posted_id)

                # Update controller stats
                self.controller.record_reply_created()

                return True

        except tweepy.errors.TooManyRequests:
            logger.error("Rate limited when posting reply")
        except Exception as e:
            logger.error(f"Failed to post reply: {e}")

        return False

    def _store_interaction(self, mention: Dict, reply: str, reply_id: str):
        """Store interaction in vector memory with embeddings."""
        try:
            # Store in vector memory with embedding for similarity search
            success = self.vector_memory.store_interaction(
                tweet_id=mention["tweet_id"],
                author=mention["author_username"],
                content=mention["text"],
                interaction_type="reply",
                ai_response=reply,
                metadata={
                    "author_id": mention["author_id"],
                    "ai_response_id": reply_id,
                    "author_followers": mention.get("author_followers", 0)
                }
            )

            if success:
                logger.info(f"💾 Stored interaction with @{mention['author_username']} (with vector embedding)")
            else:
                logger.warning(f"Failed to store vector embedding, but interaction saved")

        except Exception as e:
            logger.error(f"Failed to store interaction: {e}")

    def _get_user_context(self, username: str) -> str:
        """Get context about past interactions with this user."""
        try:
            # Query past interactions
            interactions = (
                self.interactions_collection
                .where("author", "==", username)
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(3)
                .stream()
            )

            history = [doc.to_dict() for doc in interactions]

            if not history:
                return "HISTORY: No prior interactions with this user."

            context_parts = [f"HISTORY with @{username}:"]
            for i, interaction in enumerate(history[:2], 1):
                their_msg = interaction.get("content", "")[:80]
                your_reply = interaction.get("ai_response", "")[:80]
                context_parts.append(
                    f"{i}. They said: \"{their_msg}\"\n   You replied: \"{your_reply}\""
                )

            return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Failed to get user context: {e}")
            return "HISTORY: Unknown"

    def process_mentions_and_reply(self) -> int:
        """
        Main function: Check mentions and reply to worthy ones.

        Returns:
            Number of replies sent
        """
        # Check mentions
        mentions = self.check_mentions()

        if not mentions:
            return 0

        replies_sent = 0

        for mention in mentions:
            # Check if we can still reply
            can_reply, reason = self.controller.can_reply()
            if not can_reply:
                logger.info(f"⏸️ Stopping replies: {reason}")
                break

            # AI decides if worth replying
            should_reply, decision_reason = self.ai_should_reply(mention)

            if not should_reply:
                logger.info(f"⏭️ Skipping @{mention['author_username']}: {decision_reason}")
                # Still store that we saw it (to avoid re-processing)
                try:
                    self.vector_memory.store_interaction(
                        tweet_id=mention["tweet_id"],
                        author=mention["author_username"],
                        content=mention["text"],
                        interaction_type="mention_ignored",
                        ai_response=None,
                        metadata={"ai_decision": decision_reason}
                    )
                except:
                    pass
                continue

            # Generate reply
            reply_text = self.generate_reply(mention)

            if not reply_text:
                logger.warning(f"❌ Failed to generate reply for @{mention['author_username']}")
                continue

            # Post reply
            success = self.post_reply(mention, reply_text)

            if success:
                replies_sent += 1

        return replies_sent
