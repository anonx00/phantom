"""
Phantom AI Agent - Agentic POST Mode

AI-powered posting with LangGraph workflow:
- Gathers trends/context automatically
- AI decides content type based on trends
- Quality checks before posting
- TOON format for efficient token usage

Video source: CivitAI (FREE)
"""

import os
import sys
import logging
import tweepy
from tenacity import retry, stop_after_attempt, wait_exponential
from config import Config, get_secret

# Configuration
FORCE_POST = os.getenv("FORCE_POST", "false").lower() == "true"
FORCE_VIDEO = os.getenv("FORCE_VIDEO", "false").lower() == "true"
RUN_CLEANUP = os.getenv("RUN_CLEANUP", "true").lower() == "true"
USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "true").lower() == "true"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Try GCP structured logging
try:
    import google.cloud.logging
    client = google.cloud.logging.Client()
    client.setup_logging()
except Exception:
    pass  # Fall back to standard logging


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=4, max=60))
def post_tweet_v2(client, text, **kwargs):
    """Post tweet with retry logic."""
    return client.create_tweet(text=text, **kwargs)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=4, max=60))
def upload_media_v1(api, filename, **kwargs):
    """Upload media with retry logic."""
    return api.media_upload(filename, **kwargs)


def get_twitter_api():
    """Authenticate with Twitter API."""
    required_secrets = [
        "TWITTER_CONSUMER_KEY",
        "TWITTER_CONSUMER_SECRET",
        "TWITTER_ACCESS_TOKEN",
        "TWITTER_ACCESS_TOKEN_SECRET"
    ]

    secrets = {}
    for secret_id in required_secrets:
        val = get_secret(secret_id)
        if not val:
            raise ValueError(f"Missing required secret: {secret_id}")
        secrets[secret_id] = val

    auth = tweepy.OAuth1UserHandler(
        secrets["TWITTER_CONSUMER_KEY"],
        secrets["TWITTER_CONSUMER_SECRET"],
        secrets["TWITTER_ACCESS_TOKEN"],
        secrets["TWITTER_ACCESS_TOKEN_SECRET"]
    )

    api_v1 = tweepy.API(auth)
    client_v2 = tweepy.Client(
        consumer_key=secrets["TWITTER_CONSUMER_KEY"],
        consumer_secret=secrets["TWITTER_CONSUMER_SECRET"],
        access_token=secrets["TWITTER_ACCESS_TOKEN"],
        access_token_secret=secrets["TWITTER_ACCESS_TOKEN_SECRET"]
    )

    api_v1.verify_credentials()
    return api_v1, client_v2


def main():
    logger.info("=" * 50)
    logger.info("Phantom AI Agent - POST Mode")
    logger.info("=" * 50)

    # 1. Initialize
    try:
        Config.validate()
        api_v1, client_v2 = get_twitter_api()
        logger.info("Twitter API connected")
    except Exception as e:
        logger.critical(f"Initialization failed: {e}")
        sys.exit(1)

    # 2. Data cleanup
    if RUN_CLEANUP:
        try:
            from data_retention import run_cleanup
            stats = run_cleanup(Config.PROJECT_ID)
            if stats["total_deleted"] > 0:
                logger.info(f"Cleaned up {stats['total_deleted']} old documents")
        except Exception as e:
            logger.warning(f"Cleanup failed (non-critical): {e}")

    # 3. Initialize controller
    try:
        from ai_agent_controller import AIAgentController
        controller = AIAgentController(project_id=Config.PROJECT_ID)
        summary = controller.get_daily_summary()
        logger.info(f"Today: {summary['posts']} posts, quota: {summary['twitter_quota_used']}")
    except Exception as e:
        logger.critical(f"Controller init failed: {e}")
        sys.exit(1)

    # 4. Check if we can post
    can_post, reason = controller.can_create_post()
    if not can_post:
        logger.info(f"Cannot post: {reason}")
        sys.exit(0)

    # 5. Check scheduler (unless forced)
    if not FORCE_POST:
        from scheduler import should_post_lightweight
        should_post, reason = should_post_lightweight()
        if not should_post:
            logger.info(f"Scheduler: {reason}")
            sys.exit(0)
        logger.info(f"Scheduler approved: {reason}")
    else:
        logger.info("FORCE_POST enabled")

    # 6. Initialize Brain
    logger.info("Initializing Brain...")
    try:
        from brain import AgentBrain
        brain = AgentBrain()
    except Exception as e:
        logger.critical(f"Brain init failed: {e}")
        sys.exit(1)

    # 7. Get content strategy (using LangGraph agent or direct)
    try:
        if USE_LANGGRAPH:
            logger.info("Running LangGraph agent workflow...")
            from agent_graph import run_agent
            result = run_agent(
                brain=brain,
                controller=controller,
                project_id=Config.PROJECT_ID,
                force_video=FORCE_VIDEO
            )
            if not result["success"] or not result["strategy"]:
                logger.info(f"Agent workflow: {result.get('error', 'No content')}")
                sys.exit(0)
            strategy = result["strategy"]
            logger.info(f"Agent decided: {result['content_type']} on '{result.get('topic', 'N/A')}'")
        else:
            # Direct brain call (fallback)
            strategy = brain.get_strategy(force_video=FORCE_VIDEO)
            if strategy is None:
                logger.info("No quality content available - skipping")
                sys.exit(0)
        logger.info(f"Strategy: {strategy['type']}")
    except Exception as e:
        logger.error(f"Strategy failed: {e}")
        sys.exit(1)

    # 8. Execute post
    try:
        post_type = strategy["type"]

        if post_type == "video":
            post_video(api_v1, client_v2, brain, controller, strategy)

        elif post_type == "infographic":
            post_infographic(api_v1, client_v2, brain, controller, strategy)

        elif post_type == "meme":
            post_meme(api_v1, client_v2, brain, controller, strategy)

        elif post_type == "image":
            post_image(api_v1, client_v2, brain, controller, strategy)

        elif post_type == "thought":
            post_thought(client_v2, brain, controller, strategy)

        else:  # text, thread
            post_text(client_v2, brain, controller, strategy)

        logger.info("Post complete!")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Post failed: {e}")
        sys.exit(1)


def post_video(api_v1, client_v2, brain, controller, strategy):
    """Post video content."""
    video_path = None
    try:
        from civitai_downloader import CivitAIVideoDownloader
        downloader = CivitAIVideoDownloader()
        video_path = downloader.get_video_for_prompt(strategy.get("video_prompt", ""))

        if not video_path:
            raise RuntimeError("CivitAI download failed")

        media = upload_media_v1(api_v1, video_path, chunked=True, media_category="tweet_video")
        response = post_tweet_v2(client_v2, text=strategy["content"], media_ids=[media.media_id])

        logger.info(f"Video posted: {response.data['id']}")
        brain.log_post(strategy, success=True)
        controller.record_post_created("video")

    except Exception as e:
        logger.error(f"Video failed: {e}")
        post_fallback_text(client_v2, brain, controller, strategy, e)

    finally:
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception:
                pass


def post_infographic(api_v1, client_v2, brain, controller, strategy):
    """Post infographic content."""
    image_path = None
    try:
        topic = strategy.get("topic", "Tech")
        image_prompt = strategy.get("image_prompt") or f"Professional infographic about {topic}"
        image_path = brain.generate_image(image_prompt)

        media = upload_media_v1(api_v1, image_path)
        post_tweet_v2(client_v2, text=strategy["content"], media_ids=[media.media_id])

        logger.info("Infographic posted")
        brain.log_post(strategy, success=True)
        controller.record_post_created("infographic")

    except Exception as e:
        logger.error(f"Infographic failed: {e}")
        post_fallback_text(client_v2, brain, controller, strategy, e)

    finally:
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass


def post_meme(api_v1, client_v2, brain, controller, strategy):
    """Post meme content."""
    image_path = strategy.get("meme_local_path")
    try:
        if image_path and os.path.exists(image_path):
            is_gif = image_path.lower().endswith('.gif')
            if is_gif:
                media = upload_media_v1(api_v1, image_path, chunked=True, media_category="tweet_gif")
            else:
                media = upload_media_v1(api_v1, image_path)

            post_tweet_v2(client_v2, text=strategy["content"], media_ids=[media.media_id])
            logger.info("Meme posted")
            brain.log_post(strategy, success=True)
            controller.record_post_created("meme")
        else:
            # No image - post as text
            content = strategy["content"]
            if isinstance(content, list):
                content = content[0]
            post_tweet_v2(client_v2, text=content)
            logger.info("Meme text posted")
            brain.log_post(strategy, success=True)
            controller.record_post_created("text")

    except Exception as e:
        logger.error(f"Meme failed: {e}")
        content = strategy["content"]
        if isinstance(content, list):
            content = content[0]
        try:
            post_tweet_v2(client_v2, text=content)
            brain.log_post(strategy, success=True, error=str(e))
            controller.record_post_created("text")
        except Exception:
            raise

    finally:
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass


def post_image(api_v1, client_v2, brain, controller, strategy):
    """Post AI-generated image."""
    image_path = None
    try:
        image_prompt = strategy.get("image_prompt")
        if not image_prompt:
            raise ValueError("Missing image_prompt")

        image_path = brain.generate_image(image_prompt)
        media = upload_media_v1(api_v1, image_path)
        post_tweet_v2(client_v2, text=strategy["content"], media_ids=[media.media_id])

        logger.info("Image posted")
        brain.log_post(strategy, success=True)
        controller.record_post_created("image")

    except Exception as e:
        logger.error(f"Image failed: {e}")
        post_fallback_text(client_v2, brain, controller, strategy, e)

    finally:
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass


def post_thought(client_v2, brain, controller, strategy):
    """Post AI thought/reflection."""
    text = strategy["content"]
    if isinstance(text, list):
        text = text[0]

    if len(text) > 280:
        text = text[:277] + "..."

    response = post_tweet_v2(client_v2, text=text)
    logger.info(f"Thought posted: {response.data['id']}")
    brain.log_post(strategy, success=True)
    controller.record_post_created("text")


def post_text(client_v2, brain, controller, strategy):
    """Post text/thread content."""
    tweets = strategy["content"]
    if isinstance(tweets, str):
        tweets = [tweets]

    previous_id = None
    for tweet_text in tweets:
        if len(tweet_text) > 280:
            tweet_text = tweet_text[:277] + "..."

        if previous_id:
            response = post_tweet_v2(client_v2, text=tweet_text, in_reply_to_tweet_id=previous_id)
        else:
            response = post_tweet_v2(client_v2, text=tweet_text)

        previous_id = response.data['id']

    logger.info(f"Text posted: {previous_id}")
    brain.log_post(strategy, success=True)
    controller.record_post_created("text")


def post_fallback_text(client_v2, brain, controller, strategy, original_error):
    """Fallback to text when media fails."""
    try:
        caption = strategy['content']
        source_url = strategy.get('source_url')

        if source_url:
            text = f"{caption}\n\n{source_url}"
            if len(text) > 280:
                max_len = 280 - len(source_url) - 4
                text = f"{caption[:max_len]}...\n\n{source_url}"
        else:
            text = caption if len(caption) <= 280 else caption[:277] + "..."

        post_tweet_v2(client_v2, text=text)
        logger.info("Fallback text posted")
        brain.log_post(strategy, success=True, error=f"Media failed: {original_error}")
        controller.record_post_created("text")

    except Exception as e:
        logger.error(f"Fallback also failed: {e}")
        brain.log_post(strategy, success=False, error=str(original_error))
        raise


if __name__ == "__main__":
    main()
