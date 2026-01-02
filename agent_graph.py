"""
LangGraph Agent - Agentic AI workflow for intelligent posting

Uses LangGraph for sophisticated decision-making:
1. Gather context (trends, memory, daily stats)
2. AI decides content type and topic
3. Execute with quality checks
4. Learn from results

Graph structure:
Entry -> Gather Context -> AI Decision -> Execute Post -> Finalize
                              |
                              v
                     (video/image/meme/text/thought)
"""

import logging
from typing import TypedDict, Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import langgraph
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
    logger.info("LangGraph available - agentic workflow enabled")
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = Any  # For type hints when not installed
    END = None
    logger.warning("langgraph not installed, using simple workflow")


class AgentState(TypedDict):
    """State passed through the agent graph."""
    # Input
    force_video: bool

    # Context gathered
    trends: List[Dict]
    memory: List[Dict]
    daily_stats: Dict

    # Decision
    action: str  # "post", "thought", "idle"
    content_type: str  # "video", "image", "meme", "text", "thought"
    topic: Optional[str]

    # Execution
    strategy: Optional[Dict]
    content: Optional[str]
    media_path: Optional[str]
    post_id: Optional[str]

    # Result
    success: bool
    error: Optional[str]


class PhantomAgentGraph:
    """
    LangGraph-based agent for autonomous Twitter posting.

    Provides:
    - State management across steps
    - AI-powered content decisions based on trends
    - Quality checks before posting
    - Memory of past decisions for variety
    """

    def __init__(self, brain, controller, project_id: str):
        self.brain = brain
        self.controller = controller
        self.project_id = project_id

        if LANGGRAPH_AVAILABLE:
            self.graph = self._build_graph()
        else:
            self.graph = None

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("gather_context", self._gather_context)
        workflow.add_node("decide_content", self._decide_content)
        workflow.add_node("generate_strategy", self._generate_strategy)
        workflow.add_node("quality_check", self._quality_check)
        workflow.add_node("finalize", self._finalize)

        # Set entry point
        workflow.set_entry_point("gather_context")

        # Add edges
        workflow.add_edge("gather_context", "decide_content")
        workflow.add_edge("decide_content", "generate_strategy")

        # Conditional edge from generate_strategy
        workflow.add_conditional_edges(
            "generate_strategy",
            self._route_after_strategy,
            {
                "check": "quality_check",
                "skip": "finalize"
            }
        )

        workflow.add_edge("quality_check", "finalize")
        workflow.add_edge("finalize", END)

        return workflow.compile()

    def _gather_context(self, state: AgentState) -> AgentState:
        """Gather context from all sources."""
        logger.info("Gathering context...")

        # Get trends
        try:
            from trend_scraper import TrendScraper
            scraper = TrendScraper()
            state["trends"] = scraper.get_all_trends(limit_per_source=3)
            logger.info(f"  Got {len(state['trends'])} trends")
        except Exception as e:
            logger.warning(f"Failed to get trends: {e}")
            state["trends"] = []

        # Get memory/past posts for variety
        try:
            memory_data = {"recent_types": [], "last_topics": []}
            # Get recent posts from Firestore (collection: post_history)
            from google.cloud import firestore
            db = firestore.Client(project=self.project_id)
            posts = db.collection("post_history").order_by(
                "timestamp", direction=firestore.Query.DESCENDING
            ).limit(5).stream()
            for post in posts:
                data = post.to_dict()
                if data.get("type"):
                    memory_data["recent_types"].append(data["type"])
                if data.get("topic"):
                    memory_data["last_topics"].append(data["topic"])
            state["memory"] = memory_data
            if memory_data["recent_types"]:
                logger.info(f"  Recent types: {memory_data['recent_types'][:3]}")
            else:
                logger.info("  No recent post history found")
        except Exception as e:
            logger.warning(f"Could not get recent posts: {e}")
            state["memory"] = {"recent_types": [], "last_topics": []}

        # Get daily stats
        state["daily_stats"] = self.controller.get_daily_summary()
        logger.info(f"  Today: {state['daily_stats'].get('posts', 0)} posts")

        return state

    def _decide_content(self, state: AgentState) -> AgentState:
        """AI decides what content type to create based on context."""
        logger.info("AI deciding content type...")

        from toon_helper import toon
        from datetime import datetime

        # Check if we can post
        can_post, reason = self.controller.can_create_post()
        if not can_post:
            state["action"] = "idle"
            state["error"] = reason
            logger.info(f"  Cannot post: {reason}")
            return state

        # Force video if requested
        if state["force_video"]:
            state["action"] = "post"
            state["content_type"] = "video"
            state["topic"] = self._pick_topic_for_video(state["trends"])
            logger.info(f"  Forced video on topic: {state['topic']}")
            return state

        # Get context for smart decision
        recent_types = state.get("memory", {}).get("recent_types", [])
        last_topics = state.get("memory", {}).get("last_topics", [])
        hour = datetime.now().hour

        # Smart content type selection with variety
        content_type = self._smart_content_pick(
            trends=state["trends"],
            recent_types=recent_types,
            hour=hour
        )

        # Pick topic avoiding recent ones
        topic = self._smart_topic_pick(
            trends=state["trends"],
            last_topics=last_topics,
            content_type=content_type
        )

        state["content_type"] = content_type
        state["topic"] = topic
        state["action"] = "post"

        # Log context for debugging
        logger.info(f"  Context: hour={hour}, recent={recent_types[:2]}")
        logger.info(f"  Decision: {content_type} on '{topic or 'N/A'}'")
        return state

    def _smart_content_pick(self, trends: List[Dict], recent_types: List[str], hour: int) -> str:
        """Pick content type based on trends, variety, and time."""
        # Avoid repeating last content type
        last_type = recent_types[0] if recent_types else None

        # Content type candidates based on trends
        candidates = []
        if trends:
            top_category = trends[0].get("category", "general")
            if top_category in ["crypto", "tech", "ai"]:
                candidates = ["video", "text", "thought"]
            elif top_category in ["meme", "viral"]:
                candidates = ["meme", "text", "video"]
            else:
                candidates = ["text", "video", "thought"]
        else:
            candidates = ["thought", "text"]

        # Time-based adjustments (engagement patterns)
        # Peak hours (9-11am, 7-9pm) = video/visual content
        # Off-peak = text/thoughts
        if hour in [9, 10, 11, 19, 20, 21]:
            # Boost video during peak
            if "video" in candidates:
                candidates.remove("video")
                candidates.insert(0, "video")
        elif hour in [0, 1, 2, 3, 4, 5]:
            # Late night = thoughts
            if "thought" in candidates:
                candidates.remove("thought")
                candidates.insert(0, "thought")

        # Variety: skip last type if possible
        if last_type in candidates and len(candidates) > 1:
            candidates.remove(last_type)

        return candidates[0] if candidates else "text"

    def _smart_topic_pick(self, trends: List[Dict], last_topics: List[str], content_type: str) -> Optional[str]:
        """Pick topic avoiding recent ones."""
        if not trends:
            return None

        # Filter out recently used topics
        available = [t for t in trends if t.get("topic", t.get("name", "")) not in last_topics]

        # If all filtered, use all trends
        if not available:
            available = trends

        # For video, prefer tech/crypto/ai categories
        if content_type == "video":
            tech_trends = [t for t in available if t.get("category") in ["crypto", "tech", "ai"]]
            if tech_trends:
                available = tech_trends

        # Return first available
        if available:
            return available[0].get("topic", available[0].get("name", ""))
        return None

    def _pick_topic_for_video(self, trends: List[Dict]) -> str:
        """Pick best topic for video content."""
        if not trends:
            return "AI and technology"

        # Prefer crypto/tech/ai trends for video
        for trend in trends:
            cat = trend.get("category", "")
            if cat in ["crypto", "tech", "ai"]:
                return trend.get("topic", trend.get("name", "AI"))

        # Fall back to first trend
        return trends[0].get("topic", trends[0].get("name", "technology"))

    def _generate_strategy(self, state: AgentState) -> AgentState:
        """Generate content strategy using Brain."""
        logger.info(f"Generating {state['content_type']} strategy...")

        if state["action"] == "idle":
            return state

        try:
            strategy = self.brain.get_strategy(
                force_video=(state["content_type"] == "video")
            )

            if not strategy:
                state["success"] = False
                state["error"] = "No quality content available"
                return state

            state["strategy"] = strategy
            state["content"] = strategy.get("content", "")
            state["content_type"] = strategy.get("type", state["content_type"])
            logger.info(f"  Strategy: {strategy.get('type')}")

        except Exception as e:
            state["success"] = False
            state["error"] = str(e)

        return state

    def _route_after_strategy(self, state: AgentState) -> str:
        """Route based on strategy result."""
        if state.get("strategy"):
            return "check"
        return "skip"

    def _quality_check(self, state: AgentState) -> AgentState:
        """Quality check before posting."""
        logger.info("Quality check...")

        strategy = state.get("strategy")
        if not strategy:
            return state

        content = strategy.get("content", "")

        # Check content length
        if isinstance(content, str) and len(content) > 280:
            logger.warning("  Content too long, will be truncated")

        # Check for empty content
        if not content:
            state["success"] = False
            state["error"] = "Empty content"
            return state

        # Check for duplicate (could use vector memory)
        # For now, just mark as ready
        state["success"] = True
        logger.info("  Quality check passed")
        return state

    def _finalize(self, state: AgentState) -> AgentState:
        """Finalize and log results."""
        if state.get("success") and state.get("strategy"):
            logger.info(f"Ready to post: {state.get('content_type')}")
        elif state.get("error"):
            logger.warning(f"Workflow ended: {state.get('error')}")
        else:
            logger.info("Workflow complete (no action)")

        return state

    def run(self, force_video: bool = False) -> AgentState:
        """
        Run the agent graph.

        Args:
            force_video: Force video content

        Returns:
            Final agent state with strategy if successful
        """
        initial_state: AgentState = {
            "force_video": force_video,
            "trends": [],
            "memory": [],
            "daily_stats": {},
            "action": "idle",
            "content_type": "text",
            "topic": None,
            "strategy": None,
            "content": None,
            "media_path": None,
            "post_id": None,
            "success": False,
            "error": None
        }

        if self.graph:
            # Run LangGraph workflow
            logger.info("Running LangGraph workflow...")
            final_state = self.graph.invoke(initial_state)
            return final_state
        else:
            # Fallback: simple execution without LangGraph
            logger.info("Running simple workflow (LangGraph not available)")
            state = self._gather_context(initial_state)
            state = self._decide_content(state)
            state = self._generate_strategy(state)
            if state.get("strategy"):
                state = self._quality_check(state)
            state = self._finalize(state)
            return state


def run_agent(brain, controller, project_id: str,
              force_video: bool = False) -> Dict:
    """
    Convenience function to run the agent.

    Returns dict with:
    - success: bool
    - strategy: dict (if successful)
    - error: str (if failed)
    """
    agent = PhantomAgentGraph(brain, controller, project_id)
    result = agent.run(force_video=force_video)

    return {
        "success": result.get("success", False),
        "strategy": result.get("strategy"),
        "content_type": result.get("content_type"),
        "topic": result.get("topic"),
        "error": result.get("error")
    }
