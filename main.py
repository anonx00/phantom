import os
import sys
import logging
import tweepy
from tenacity import retry, stop_after_attempt, wait_exponential
from config import Config, get_secret

# Lazy imports for cold start optimization - only import heavy modules when needed
# from brain import AgentBrain  # Moved to after scheduler check
# from veo_client import VeoClient  # Imported when needed

# Check for operational mode
FORCE_POST = os.getenv("FORCE_POST", "false").lower() == "true"
# Force video generation (bypasses format selection, useful for manual testing)
FORCE_VIDEO = os.getenv("FORCE_VIDEO", "false").lower() == "true"
# AI Mode: "post", "reply", or "auto" (AI decides)
AI_MODE = os.getenv("AI_MODE", "auto").lower()
# Enable reply functionality
ENABLE_REPLIES = os.getenv("ENABLE_REPLIES", "true").lower() == "true"
# Use CivitAI videos instead of Vertex AI (saves $$$)
USE_CIVITAI_VIDEOS = os.getenv("USE_CIVITAI_VIDEOS", "false").lower() == "true"

# Configure logging - will be enhanced with structured logging below
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Try to enable structured logging for GCP Cloud Logging
try:
    import google.cloud.logging
    from google.cloud.logging.handlers import StructuredLogHandler

    # Setup structured logging for GCP
    client = google.cloud.logging.Client()
    client.setup_logging()
    logger.info("Structured logging enabled for GCP Cloud Logging")
except ImportError:
    logger.debug("google-cloud-logging not available, using standard logging")
except Exception as e:
    logger.warning(f"Could not setup GCP structured logging: {e}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=4, max=60))
def post_tweet_v2(client, text, **kwargs):
    return client.create_tweet(text=text, **kwargs)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=4, max=60))
def upload_media_v1(api, filename, **kwargs):
    return api.media_upload(filename, **kwargs)


def get_twitter_api():
    """Authenticates with X (Twitter) API."""
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

    # Create clients
    api_v1 = tweepy.API(auth)
    client_v2 = tweepy.Client(
        consumer_key=secrets["TWITTER_CONSUMER_KEY"],
        consumer_secret=secrets["TWITTER_CONSUMER_SECRET"],
        access_token=secrets["TWITTER_ACCESS_TOKEN"],
        access_token_secret=secrets["TWITTER_ACCESS_TOKEN_SECRET"]
    )

    # Verify credentials
    try:
        api_v1.verify_credentials()
    except Exception as e:
        raise ValueError(f"Twitter authentication failed: {e}")

    return api_v1, client_v2


def main():
    logger.info("🤖 Starting AI Agent (BIG BOSS)...")
    logger.info(f"Mode: {AI_MODE} | Replies: {'enabled' if ENABLE_REPLIES else 'disabled'}")
    logger.info(f"Video source: {'CivitAI (FREE)' if USE_CIVITAI_VIDEOS else 'Vertex AI (PAID)'}")

    # 1. Validate Environment & Secrets
    try:
        Config.validate()
        api_v1, client_v2 = get_twitter_api()
    except Exception as e:
        logger.critical(f"Initialization Error: {e}")
        sys.exit(1)

    # 2. Initialize AI Agent Controller (budget & quota management + vector memory)
    logger.info("Initializing AI Agent Controller with vector memory...")
    try:
        from ai_agent_controller import AIAgentController
        controller = AIAgentController(project_id=Config.PROJECT_ID)

        # Show daily summary
        summary = controller.get_daily_summary()
        logger.info(f"📊 Today's activity: {summary['posts']} posts, {summary['replies']} replies")
        logger.info(f"   Twitter quota: {summary['twitter_quota_used']}")
        logger.info(f"   Video budget: {summary['video_budget_used']}")

        # Show memory stats
        memory_stats = controller.vector_memory.get_interaction_stats()
        logger.info(f"🧠 AI Memory: {memory_stats.get('total_interactions', 0)} total interactions stored")
        logger.info(f"   Recent (24h): {memory_stats.get('recent_count_24h', 0)} interactions")
    except Exception as e:
        logger.critical(f"Failed to initialize controller: {e}")
        sys.exit(1)

    # 3. Decide what to do (AI-driven decision)
    if AI_MODE == "auto":
        # AI decides based on quotas and time of day
        mode = controller.should_engage_mode()
        logger.info(f"🧠 AI decided: {mode.upper()} mode")
    elif AI_MODE in ["post", "reply"]:
        mode = AI_MODE
        logger.info(f"🎯 Forced mode: {mode.upper()}")
    else:
        mode = "post"  # Default
        logger.info(f"⚠️ Unknown mode '{AI_MODE}', defaulting to POST")

    # 4. Handle REPLY mode
    if mode == "reply" and ENABLE_REPLIES:
        return handle_reply_mode(api_v1, client_v2, controller)

    # 5. Handle POST mode (original functionality)
    if mode == "idle":
        logger.info("😴 Idle mode - quotas exhausted or off-peak hours")
        logger.info("Will try again later")
        sys.exit(0)

    # COLD START OPTIMIZATION: Check scheduler before heavy Brain initialization
    if not FORCE_POST:
        from scheduler import should_post_lightweight
        should_post, reason = should_post_lightweight()
        if not should_post:
            logger.info(f"⏸️ Skipping post: {reason}")
            logger.info("Set FORCE_POST=true to override scheduler")
            sys.exit(0)
        logger.info(f"✅ Scheduler approved: {reason}")
    else:
        logger.info("🚀 FORCE_POST enabled, bypassing scheduler")

    # Check if we can post
    can_post, post_reason = controller.can_create_post()
    if not can_post:
        logger.info(f"❌ Cannot post: {post_reason}")
        sys.exit(0)

    # 6. Initialize Brain (LAZY - only when actually posting)
    logger.info("Initializing AgentBrain (heavy initialization)...")
    try:
        from brain import AgentBrain
        brain = AgentBrain()
    except Exception as e:
        logger.critical(f"Failed to initialize Brain: {e}")
        sys.exit(1)

    # 7. Handle POST mode with zero-waste content generation
    return handle_post_mode(api_v1, client_v2, brain, controller, FORCE_VIDEO)


def handle_reply_mode(api_v1, client_v2, controller):
    """
    Handle reply mode: Check mentions and reply to worthy ones.

    Returns:
        Exit code
    """
    logger.info("💬 REPLY MODE: Checking mentions...")

    try:
        # Initialize Brain for AI responses (lightweight - no video models)
        from brain import AgentBrain
        brain = AgentBrain()

        # Initialize reply handler
        from reply_handler import ReplyHandler
        reply_handler = ReplyHandler(
            api_v1=api_v1,
            client_v2=client_v2,
            controller=controller,
            ai_generate_func=brain._generate_with_fallback,
            bot_username="PatriotxSystem"
        )

        # Check mentions and reply
        replies_sent = reply_handler.process_mentions_and_reply()

        if replies_sent > 0:
            logger.info(f"✅ Sent {replies_sent} replies")
        else:
            logger.info("No replies sent (no worthy mentions or quota exhausted)")

        return 0

    except Exception as e:
        logger.error(f"Reply mode failed: {e}")
        return 1


def handle_post_mode(api_v1, client_v2, brain, controller, force_video=False):
    """
    Handle post mode: Create and post content (original functionality).
    Now with zero-waste optimization.

    Returns:
        Exit code
    """
    logger.info("📝 POST MODE: Creating content...")

    # 3. Get Strategy (may return None if no quality content available)
    try:
        # Pass FORCE_VIDEO flag and controller for budget checks
        if force_video:
            logger.info("🎬 FORCE_VIDEO enabled")

        strategy = brain.get_strategy(force_video=force_video)

        if strategy is None:
            logger.info("No quality content available - skipping this post cycle")
            logger.info("This is normal - we only post when we have good content")
            return 0

        logger.info(f"Strategy decided: {strategy}")

        # ZERO WASTE CHECK: Verify we can create media before generating
        from ai_agent_controller import ZeroWasteContentStrategy
        post_type = strategy.get("type")

        if post_type in ["video", "image", "infographic"]:
            if not ZeroWasteContentStrategy.should_create_media(post_type, controller):
                # Budget limit hit - fall back to text
                logger.warning(f"⚠️ {post_type.upper()} budget limit - falling back to text with URL")
                strategy["type"] = "text"
                post_type = "text"

    except Exception as e:
        logger.error(f"Failed to generate strategy: {e}")
        return 1

    # 4. Execute Strategy (existing code continues...)
    try:
        if strategy["type"] == "video":
            video_path = None
            try:
                # Check if we should use CivitAI (free) or Vertex AI (paid)
                if USE_CIVITAI_VIDEOS:
                    # Use CivitAI - download free AI-generated videos
                    logger.info("Using CivitAI for video (free, saves Vertex AI costs)")
                    from civitai_downloader import CivitAIVideoDownloader
                    downloader = CivitAIVideoDownloader()
                    video_path = downloader.get_video_for_prompt(strategy.get("video_prompt", ""))
                    if not video_path:
                        raise RuntimeError("Failed to download video from CivitAI")
                else:
                    # Use Vertex AI Veo (paid)
                    from veo_client import VeoClient
                    veo = VeoClient(project_id=Config.PROJECT_ID, region=Config.REGION)
                    video_path = veo.generate_video(strategy["video_prompt"])

                # Upload Video (requires v1.1 API)
                media = upload_media_v1(api_v1, video_path, chunked=True, media_category="tweet_video")

                # Post Tweet with Video (requires v2 API)
                response = post_tweet_v2(client_v2, text=strategy["content"], media_ids=[media.media_id])
                posted_id = response.data['id']
                logger.info(f"Video posted successfully! ID: {posted_id}")
                brain.log_post(strategy, success=True)

                # Record in controller
                controller.record_post_created("video")

                # Store in vector memory for AI context
                from post_memory_tracker import PostMemoryTracker
                memory_tracker = PostMemoryTracker(controller.vector_memory)
                memory_tracker.store_post(
                    post_id=posted_id,
                    content=strategy["content"],
                    post_type="video",
                    topic=strategy.get("topic"),
                    metadata={"video_prompt": strategy.get("video_prompt", "")[:100]}
                )

            except Exception as e:
                logger.error(f"Video generation or upload failed: {e}")
                logger.info("Falling back to text with URL...")

                # Fallback logic - post text with URL (if available)
                try:
                    caption = strategy['content']
                    source_url = strategy.get('source_url')

                    # If we have a URL, create proper fallback with citation
                    if source_url:
                        fallback_text = f"{caption}\n\n{source_url}"
                        # Ensure under 280 chars
                        if len(fallback_text) > 280:
                            max_caption = 280 - len(source_url) - 4  # -4 for \n\n spacing
                            fallback_text = f"{caption[:max_caption]}...\n\n{source_url}"
                    else:
                        fallback_text = caption

                    post_tweet_v2(client_v2, text=fallback_text)
                    logger.info("Posted text with URL after video failure")
                    brain.log_post(strategy, success=True, error=f"Video failed but posted text with URL. Error: {e}")
                    controller.record_post_created("text")
                except Exception as fallback_error:
                    logger.error(f"Fallback tweet also failed: {fallback_error}")
                    brain.log_post(strategy, success=False, error=f"Video and Fallback failed. Error: {e} | Fallback: {fallback_error}")
                    return 1

            finally:
                # Cleanup video file
                if video_path and os.path.exists(video_path):
                    try:
                        os.remove(video_path)
                        logger.info(f"Cleaned up video file: {video_path}")
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup video file: {cleanup_error}")

        elif strategy["type"] == "infographic":
            # Handle infographic posts (educational content)
            image_path = None
            try:
                # Use infographic generator with topic and key points
                topic = strategy.get("topic", "Tech Trends")
                key_points = strategy.get("key_points", [])
                source_url = strategy.get("source_url")
                image_prompt = strategy.get("image_prompt")

                if brain.infographic_generator and not image_prompt:
                    # Use dedicated infographic generator
                    infographic_result = brain.generate_infographic(
                        topic=topic,
                        key_points=key_points,
                        source_url=source_url
                    )
                    image_path = infographic_result.get('image_path')
                    # Update caption if infographic generator provided one
                    if infographic_result.get('content'):
                        strategy['content'] = infographic_result['content']
                else:
                    # Use the image_prompt from strategy (generated by brain.get_strategy)
                    # This uses the regular Imagen generator with infographic-specific prompt
                    logger.info("Using Imagen with infographic prompt from strategy")
                    prompt = image_prompt or f"Professional tech infographic about {topic}. Clean diagram, data visualization, educational content."
                    image_path = brain.generate_image(prompt)

                # Upload Image
                media = upload_media_v1(api_v1, image_path)

                # Post Tweet with Infographic
                post_tweet_v2(client_v2, text=strategy["content"], media_ids=[media.media_id])
                logger.info("Infographic posted successfully!")
                brain.log_post(strategy, success=True)
                controller.record_post_created("infographic")

            except Exception as e:
                logger.error(f"Infographic generation or upload failed: {e}")
                logger.info("Falling back to text with URL...")

                # Fallback to text with URL
                try:
                    caption = strategy.get('content', strategy.get('topic', 'Tech update'))
                    source_url = strategy.get('source_url')

                    if source_url:
                        fallback_text = f"{caption}\n\n{source_url}"
                        if len(fallback_text) > 280:
                            max_caption = 280 - len(source_url) - 4
                            fallback_text = f"{caption[:max_caption]}...\n\n{source_url}"
                    else:
                        fallback_text = caption if len(caption) <= 280 else caption[:277] + "..."

                    post_tweet_v2(client_v2, text=fallback_text)
                    logger.info("Posted text with URL after infographic failure")
                    brain.log_post(strategy, success=True, error=f"Infographic failed but posted text with URL. Error: {e}")
                    controller.record_post_created("text")
                except Exception as fallback_error:
                    logger.error(f"Fallback tweet also failed: {fallback_error}")
                    brain.log_post(strategy, success=False, error=f"Infographic and Fallback failed. Error: {e}")
                    sys.exit(1)
            finally:
                if image_path and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except Exception:
                        pass

        elif strategy["type"] == "meme":
            # MEME: Use fetched meme from Reddit (meme_local_path) or fallback to text
            image_path = strategy.get("meme_local_path")  # Pre-downloaded meme
            try:
                if image_path and os.path.exists(image_path):
                    # We have a fetched meme - upload and post
                    logger.info(f"Posting fetched meme from: {strategy.get('meme_source', 'Reddit')}")
                    file_size = os.path.getsize(image_path)
                    logger.info(f"Uploading meme file: {image_path} ({file_size} bytes)")

                    # Upload media - use chunked upload for GIFs
                    is_gif = image_path.lower().endswith('.gif')
                    if is_gif:
                        logger.info("Using chunked upload for GIF...")
                        media = upload_media_v1(api_v1, image_path, chunked=True, media_category="tweet_gif")
                    else:
                        media = upload_media_v1(api_v1, image_path)

                    logger.info(f"Media upload complete. media_id: {media.media_id}, media_id_string: {getattr(media, 'media_id_string', 'N/A')}")

                    # Post tweet with media
                    response = post_tweet_v2(client_v2, text=strategy["content"], media_ids=[media.media_id])
                    logger.info(f"Tweet posted! Response: {response.data if hasattr(response, 'data') else response}")
                    logger.info(f"Meme posted successfully! Source: {strategy.get('meme_title', '')[:50]}")
                    brain.log_post(strategy, success=True)
                    controller.record_post_created("meme")
                else:
                    # No meme image - post as text (brain.py already set content)
                    logger.info("No meme image, posting as text")
                    content = strategy["content"]
                    if isinstance(content, list):
                        content = content[0]
                    post_tweet_v2(client_v2, text=content)
                    logger.info("Posted meme-style text successfully!")
                    brain.log_post(strategy, success=True)
                    controller.record_post_created("text")

            except Exception as e:
                logger.error(f"Meme posting failed: {e}")
                # Fallback to text
                try:
                    content = strategy["content"]
                    if isinstance(content, list):
                        content = content[0]
                    post_tweet_v2(client_v2, text=content)
                    logger.info("Posted text fallback after meme failure")
                    brain.log_post(strategy, success=True, error=f"Meme failed, posted text. Error: {e}")
                    controller.record_post_created("text")
                except Exception as fallback_error:
                    logger.error(f"Fallback also failed: {fallback_error}")
                    brain.log_post(strategy, success=False, error=str(e))
                    sys.exit(1)
            finally:
                # Cleanup downloaded meme
                if image_path and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                        logger.info(f"Cleaned up meme file: {image_path}")
                    except Exception as cleanup_err:
                        logger.warning(f"Failed to cleanup meme file: {cleanup_err}")

        elif strategy["type"] == "image":
            # IMAGE: AI-generated image with Imagen
            image_path = None
            try:
                image_prompt = strategy.get("image_prompt")
                if not image_prompt:
                    raise ValueError("Missing image_prompt for image post")

                image_path = brain.generate_image(image_prompt)

                # Upload Image
                media = upload_media_v1(api_v1, image_path)

                # Post Tweet with Image
                post_tweet_v2(client_v2, text=strategy["content"], media_ids=[media.media_id])
                logger.info("Image posted successfully!")
                brain.log_post(strategy, success=True)
                controller.record_post_created("image")

            except Exception as e:
                logger.error(f"Image generation or upload failed: {e}")
                logger.info("Falling back to text with URL...")

                # Fallback to text with URL
                try:
                    caption = strategy['content']
                    source_url = strategy.get('source_url')

                    if source_url:
                        fallback_text = f"{caption}\n\n{source_url}"
                        if len(fallback_text) > 280:
                            max_caption = 280 - len(source_url) - 4
                            fallback_text = f"{caption[:max_caption]}...\n\n{source_url}"
                    else:
                        fallback_text = caption

                    post_tweet_v2(client_v2, text=fallback_text)
                    logger.info("Posted text with URL after image failure")
                    brain.log_post(strategy, success=True, error=f"Image failed but posted text. Error: {e}")
                    controller.record_post_created("text")
                except Exception as fallback_error:
                    logger.error(f"Fallback tweet also failed: {fallback_error}")
                    brain.log_post(strategy, success=False, error=str(e))
                    sys.exit(1)
            finally:
                if image_path and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except Exception:
                        pass

        elif strategy["type"] == "thought":
            # THOUGHT: AI musings/reflections - simple text post
            thought_text = strategy["content"]
            if isinstance(thought_text, list):
                thought_text = thought_text[0]

            try:
                # Basic length check
                if len(thought_text) > 280:
                    logger.warning(f"Thought too long, truncating: {thought_text[:50]}...")
                    thought_text = thought_text[:277] + "..."

                response = post_tweet_v2(client_v2, text=thought_text)
                logger.info(f"💭 AI Thought posted! ID: {response.data['id']}")
                brain.log_post(strategy, success=True)
                controller.record_post_created("text")
            except Exception as e:
                logger.error(f"Failed to post AI thought: {e}")
                brain.log_post(strategy, success=False, error=str(e))
                sys.exit(1)

        elif strategy["type"] in ["thread", "text"]:
            tweets = strategy["content"]
            # Ensure it's a list
            if isinstance(tweets, str):
                tweets = [tweets]
                
            previous_tweet_id = None
            posted_tweets = []
            
            try:
                for tweet_text in tweets:
                    # Basic length check
                    if len(tweet_text) > 280:
                        logger.warning(f"Tweet too long, truncating: {tweet_text[:50]}...")
                        tweet_text = tweet_text[:277] + "..."
                    
                    if previous_tweet_id:
                        response = post_tweet_v2(client_v2, text=tweet_text, in_reply_to_tweet_id=previous_tweet_id)
                    else:
                        response = post_tweet_v2(client_v2, text=tweet_text)
                    
                    previous_tweet_id = response.data['id']
                    posted_tweets.append(previous_tweet_id)
                
                logger.info(f"Post successful! IDs: {posted_tweets}")
                brain.log_post(strategy, success=True)
                controller.record_post_created("text")
            except Exception as e:
                logger.error(f"Failed to post text: {e}")
                brain.log_post(strategy, success=False, error=f"Partial failure. Posted: {len(posted_tweets)}. Error: {e}")
                return 1

    except Exception as e:
        logger.critical(f"Critical execution error: {e}")
        # Try to log to Firestore if possible
        try:
            brain.log_post(strategy, success=False, error=f"Critical Error: {e}")
        except Exception as log_err:
            logger.warning(f"Failed to log error to Firestore: {log_err}")
        return 1

    # Success!
    return 0

if __name__ == "__main__":
    main()
