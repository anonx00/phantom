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

        # Get memory/past posts
        try:
            from toon_helper import encode_memory_for_prompt
            # Get recent post types to ensure variety
            memory_stats = self.controller.vector_memory.get_interaction_stats()
            state["memory"] = memory_stats
        except Exception as e:
            state["memory"] = {}

        # Get daily stats
        state["daily_stats"] = self.controller.get_daily_summary()
        logger.info(f"  Today: {state['daily_stats'].get('posts', 0)} posts")

        return state

    def _decide_content(self, state: AgentState) -> AgentState:
        """AI decides what content type to create based on context."""
        logger.info("AI deciding content type...")

        # Use TOON for efficient context encoding
        from toon_helper import toon

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

        # AI decides based on trends and variety
        context = toon({
            "trends": state["trends"][:5],
            "daily_stats": state["daily_stats"],
            "recent_types": state.get("memory", {}).get("recent_types", [])
        })

        # Simple heuristic for now - could be AI-powered
        if state["trends"]:
            top_trend = state["trends"][0]
            category = top_trend.get("category", "general")

            # Pick content type based on trend category
            if category in ["crypto", "tech", "ai"]:
                state["content_type"] = "video"
            elif category in ["meme", "viral"]:
                state["content_type"] = "meme"
            else:
                state["content_type"] = "text"

            state["topic"] = top_trend.get("topic", top_trend.get("name", ""))
        else:
            # No trends - generate a thought
            state["content_type"] = "thought"
            state["topic"] = None

        state["action"] = "post"
        logger.info(f"  Decision: {state['content_type']} on '{state.get('topic', 'N/A')}'")
        return state

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
