import os
import sys
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
    logger.info("Starting Tech Influencer Agent...")
    
    # 1. Validate Environment & Secrets FIRST (Fail Fast)
    try:
        Config.validate()
        api_v1, client_v2 = get_twitter_api()
    except Exception as e:
        logger.critical(f"Initialization Error: {e}")
        sys.exit(1) # Exit with error code

    # 2. Initialize Brain
    try:
        brain = AgentBrain()
    except Exception as e:
        logger.critical(f"Failed to initialize Brain: {e}")
        sys.exit(1)

    # 3. Get Strategy
    try:
        strategy = brain.get_strategy()
        logger.info(f"Strategy decided: {strategy}")
    except Exception as e:
        logger.error(f"Failed to generate strategy: {e}")
        sys.exit(1)

    # 4. Execute Strategy
    try:
from tenacity import retry, stop_after_attempt, wait_exponential

# ... (imports)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=4, max=60))
def post_tweet_v2(client, text, **kwargs):
    return client.create_tweet(text=text, **kwargs)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=4, max=60))
def upload_media_v1(api, filename, **kwargs):
    return api.media_upload(filename, **kwargs)

# ... (inside main function)

        if strategy["type"] == "video":
            # ... (veo generation)
                
                # Upload Video (requires v1.1 API)
                media = upload_media_v1(api_v1, video_path, chunked=True, media_category="tweet_video")
                
                # Post Tweet with Video (requires v2 API)
                post_tweet_v2(client_v2, text=strategy["content"], media_ids=[media.media_id])
                logger.info("Video posted successfully!")
                brain.log_post(strategy, success=True)
                
            # ... (error handling)

        elif strategy["type"] == "image":
            # ... (image generation)
                
                image_path = brain.generate_image(strategy["image_prompt"])
                
                # Upload Image
                media = upload_media_v1(api_v1, image_path)
                
                # Post Tweet with Image
                post_tweet_v2(client_v2, text=strategy["content"], media_ids=[media.media_id])
                logger.info("Image posted successfully!")
                brain.log_post(strategy, success=True)
                
            # ... (error handling)

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
            except Exception as e:
                logger.error(f"Failed to post text: {e}")
                brain.log_post(strategy, success=False, error=f"Partial failure. Posted: {len(posted_tweets)}. Error: {e}")
                sys.exit(1)

    except Exception as e:
        logger.critical(f"Critical execution error: {e}")
        # Try to log to Firestore if possible
        try:
             brain.log_post(strategy, success=False, error=f"Critical Error: {e}")
        except:
             pass
        sys.exit(1)

if __name__ == "__main__":
    main()
