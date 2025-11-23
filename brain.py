import logging
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import firestore
from config import Config
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentBrain:
    def __init__(self):
        self.project_id = Config.PROJECT_ID
        self.location = Config.REGION
        
        vertexai.init(project=self.project_id, location=self.location)
        self.model = GenerativeModel("gemini-1.5-flash-001")
        self.db = firestore.Client(project=self.project_id)
        self.collection = self.db.collection(Config.COLLECTION_NAME)

    def _get_trending_topic(self) -> str:
        """
        Asks Gemini to identify a trending tech topic.
        """
        prompt = "Identify a single, specific, currently trending technology topic or news item suitable for a tech influencer tweet. Return ONLY the topic name."
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Failed to get trending topic: {e}")
            return "Artificial Intelligence" # Safe fallback

    def _check_history(self, topic: str) -> bool:
        """
        Checks Firestore to see if we've recently posted about this topic.
        Returns True if we should SKIP this topic (duplicate), False otherwise.
        """
        # Check last 20 posts
        docs = self.collection.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(20).stream()
        
        for doc in docs:
            data = doc.to_dict()
            if data.get("topic", "").lower() == topic.lower():
                logger.info(f"Topic '{topic}' was recently covered. Skipping.")
                return True
        return False

    def get_strategy(self):
        """
        Decides on the content strategy: Thread (Text) or Video.
        Returns a dict with 'type', 'content', 'topic', and optional 'video_prompt'.
        """
        topic = self._get_trending_topic()
        
        if self._check_history(topic):
            # If duplicate, try to find a sub-niche or different angle
            logger.info("Duplicate topic detected. Requesting alternative.")
            prompt = f"The topic '{topic}' was already covered. Give me a DIFFERENT trending tech topic. Return ONLY the topic name."
            try:
                response = self.model.generate_content(prompt)
                topic = response.text.strip()
            except Exception:
                topic = "Coding Best Practices" # Fallback
        
        logger.info(f"Selected Topic: {topic}")

        # Decide format
        if Config.BUDGET_MODE:
            post_type = "thread"
        else:
            # Ask Gemini if this topic is better for video or text
            decision_prompt = f"For the tech topic '{topic}', is it better to make a short video or a text thread? Reply with 'VIDEO' or 'THREAD'."
            try:
                decision = self.model.generate_content(decision_prompt).text.strip().upper()
                post_type = "video" if "VIDEO" in decision else "thread"
            except Exception:
                post_type = "thread" # Default to thread on error

        strategy = {
            "topic": topic,
            "type": post_type,
            "timestamp": datetime.datetime.utcnow()
        }

        if post_type == "video":
            # Generate Video Prompt and Tweet Text
            script_prompt = f"Write a tweet caption for a video about '{topic}'. Also provide a visual prompt for an AI video generator. Format: CAPTION: <text> | PROMPT: <visual description>"
            try:
                response = self.model.generate_content(script_prompt).text.strip()
                parts = response.split("|")
                caption = parts[0].replace("CAPTION:", "").strip()
                visual_prompt = parts[1].replace("PROMPT:", "").strip()
            except Exception as e:
                logger.error(f"Failed to generate video script: {e}")
                # Fallback
                caption = f"Check out this update on {topic}! #tech #ai"
                visual_prompt = f"Futuristic technology visualization of {topic}, cinematic lighting, 4k"
            
            strategy["content"] = caption
            strategy["video_prompt"] = visual_prompt
            
        else:
            # Generate Thread
            thread_prompt = f"Write a 3-tweet thread about '{topic}' for a tech audience. Separate tweets with '|||'."
            try:
                response = self.model.generate_content(thread_prompt).text.strip()
                tweets = response.split("|||")
                strategy["content"] = [t.strip() for t in tweets if t.strip()]
            except Exception as e:
                logger.error(f"Failed to generate thread: {e}")
                strategy["content"] = [f"Exciting news about {topic}! Stay tuned for more updates. #tech"]

        return strategy

    def log_post(self, strategy: dict, success: bool, error: str = None):
        """Logs the attempt to Firestore."""
        try:
            doc_ref = self.collection.document()
            data = strategy.copy()
            data["success"] = success
            if error:
                data["error"] = error
            doc_ref.set(data)
        except Exception as e:
            logger.error(f"Failed to log post to Firestore: {e}")
