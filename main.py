import os
import logging
import tweepy
from config import Config, get_secret
from brain import AgentBrain
from veo_client import VeoClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    return tweepy.API(auth), tweepy.Client(
        consumer_key=secrets["TWITTER_CONSUMER_KEY"],
        consumer_secret=secrets["TWITTER_CONSUMER_SECRET"],
        access_token=secrets["TWITTER_ACCESS_TOKEN"],
        access_token_secret=secrets["TWITTER_ACCESS_TOKEN_SECRET"]
    )

def main():
    logger.info("Starting Tech Influencer Agent...")
    
    # Validate Environment
    try:
        Config.validate()
    except ValueError as e:
        logger.critical(f"Configuration Error: {e}")
        return

    # Initialize components
    try:
        brain = AgentBrain()
    except Exception as e:
        logger.critical(f"Failed to initialize Brain: {e}")
        return

    # Get Strategy
    try:
        strategy = brain.get_strategy()
        logger.info(f"Strategy decided: {strategy}")
    except Exception as e:
        logger.error(f"Failed to generate strategy: {e}")
        return

    # Execute Strategy
    try:
        api_v1, client_v2 = get_twitter_api()
        
        if strategy["type"] == "video":
            video_path = None
            try:
                veo = VeoClient(project_id=Config.PROJECT_ID, region=Config.REGION)
                video_path = veo.generate_video(strategy["video_prompt"])
                
                # Upload Video (requires v1.1 API)
                media = api_v1.media_upload(video_path, chunked=True, media_category="tweet_video")
                
                # Post Tweet with Video (requires v2 API)
                client_v2.create_tweet(text=strategy["content"], media_ids=[media.media_id])
                logger.info("Video posted successfully!")
                brain.log_post(strategy, success=True)
                
            except Exception as e:
                logger.error(f"Video generation or upload failed: {e}")
                logger.info("Falling back to text thread...")
                # Fallback logic: Mask internal error
                fallback_text = f"{strategy['content']} (Check back later for the video!)"
                client_v2.create_tweet(text=fallback_text)
                brain.log_post(strategy, success=False, error=str(e))
            finally:
                # Cleanup video file
                if video_path and os.path.exists(video_path):
                    try:
                        os.remove(video_path)
                        logger.info(f"Cleaned up video file: {video_path}")
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup video file: {cleanup_error}")

        elif strategy["type"] == "thread":
            tweets = strategy["content"]
            previous_tweet_id = None
            
            for tweet_text in tweets:
                # Basic length check
                if len(tweet_text) > 280:
                    logger.warning(f"Tweet too long, truncating: {tweet_text[:50]}...")
                    tweet_text = tweet_text[:277] + "..."
                
                if previous_tweet_id:
                    response = client_v2.create_tweet(text=tweet_text, in_reply_to_tweet_id=previous_tweet_id)
                else:
                    response = client_v2.create_tweet(text=tweet_text)
                previous_tweet_id = response.data['id']
            
            logger.info("Thread posted successfully!")
            brain.log_post(strategy, success=True)

    except Exception as e:
        logger.critical(f"Critical execution error: {e}")
        brain.log_post(strategy, success=False, error=str(e))

if __name__ == "__main__":
    main()
