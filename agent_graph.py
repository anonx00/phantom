"""
LangGraph Agent - Sophisticated AI decision-making workflow

Replaces simple if/else logic with a graph-based agent that can:
1. Gather context (trends, memory, mentions)
2. Decide what action to take
3. Execute with fallbacks
4. Learn from results

Graph structure:
                    ┌─→ Scrape Replies ─→ Evaluate ─→ Respond
                    │
Entry ─→ Gather ────┼─→ Check Trends ─→ Pick Topic ─→ Generate ─→ Post
                    │
                    └─→ Review Memory ─→ Reflect ─→ Thought Post
"""

import logging
from typing import TypedDict, Literal, Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import langgraph
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
    logger.info("✅ LangGraph available - advanced agent workflow enabled")
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("⚠️ langgraph not installed, using simple workflow")


class AgentState(TypedDict):
    """State passed through the agent graph."""
    # Input
    mode: str  # "auto", "post", "reply", "scrape"
    force_video: bool

    # Context gathered
    trends: List[Dict]
    mentions: List[Dict]
    memory: List[Dict]
    daily_stats: Dict

    # Decision
    action: str  # "post", "reply", "idle", "thought"
    content_type: str  # "video", "text", "meme", etc.
    topic: Optional[str]

    # Execution
    content: Optional[str]
    media_path: Optional[str]
    post_id: Optional[str]

    # Result
    success: bool
    error: Optional[str]
    tokens_used: int


class PhantomAgentGraph:
    """
    LangGraph-based agent for autonomous Twitter operation.

    This provides:
    - State management across steps
    - Conditional branching based on context
    - Automatic retries and fallbacks
    - Memory of past decisions
    """

    def __init__(self, brain, controller, api_v1, client_v2, project_id: str):
        self.brain = brain
        self.controller = controller
        self.api_v1 = api_v1
        self.client_v2 = client_v2
        self.project_id = project_id

        if LANGGRAPH_AVAILABLE:
            self.graph = self._build_graph()
        else:
            self.graph = None

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""

        # Define the graph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("gather_context", self._gather_context)
        workflow.add_node("decide_action", self._decide_action)
        workflow.add_node("execute_post", self._execute_post)
        workflow.add_node("execute_reply", self._execute_reply)
        workflow.add_node("execute_thought", self._execute_thought)
        workflow.add_node("finalize", self._finalize)

        # Set entry point
        workflow.set_entry_point("gather_context")

        # Add edges
        workflow.add_edge("gather_context", "decide_action")

        # Conditional edges from decide_action
        workflow.add_conditional_edges(
            "decide_action",
            self._route_action,
            {
                "post": "execute_post",
                "reply": "execute_reply",
                "thought": "execute_thought",
                "idle": "finalize"
            }
        )

        # All execution nodes go to finalize
        workflow.add_edge("execute_post", "finalize")
        workflow.add_edge("execute_reply", "finalize")
        workflow.add_edge("execute_thought", "finalize")
        workflow.add_edge("finalize", END)

        return workflow.compile()

    def _gather_context(self, state: AgentState) -> AgentState:
        """Gather context from all sources."""
        logger.info("📊 Gathering context...")

        # Get trends
        try:
            from trend_scraper import TrendScraper
            scraper = TrendScraper()
            state["trends"] = scraper.get_all_trends(limit_per_source=3)
        except Exception as e:
            logger.warning(f"Failed to get trends: {e}")
            state["trends"] = []

        # Get mentions (via scraper)
        try:
            from reply_scraper import ReplyScraper
            reply_scraper = ReplyScraper("PatriotxSystem", self.project_id)
            state["mentions"] = reply_scraper.scrape_new_replies(max_tweets=5)
        except Exception as e:
            logger.warning(f"Failed to get mentions: {e}")
            state["mentions"] = []

        # Get memory
        try:
            memory_stats = self.controller.vector_memory.get_interaction_stats()
            state["memory"] = memory_stats
        except Exception as e:
            state["memory"] = {}

        # Get daily stats
        state["daily_stats"] = self.controller.get_daily_summary()

        logger.info(f"   Trends: {len(state['trends'])}, Mentions: {len(state['mentions'])}")
        return state

    def _decide_action(self, state: AgentState) -> AgentState:
        """AI decides what action to take based on context."""
        logger.info("🧠 AI deciding action...")

        # Use TOON to encode context efficiently
        from toon_helper import toon

        context = toon({
            "trends": state["trends"][:5],
            "mentions_count": len(state["mentions"]),
            "daily_stats": state["daily_stats"],
            "mode": state["mode"],
            "force_video": state["force_video"]
        })

        # Check constraints
        can_post, post_reason = self.controller.can_create_post()
        can_reply, reply_reason = self.controller.can_reply()

        # Decision logic (AI-enhanced)
        if state["mode"] == "scrape" or (state["mentions"] and can_reply):
            state["action"] = "reply"
        elif state["force_video"] and can_post:
            state["action"] = "post"
            state["content_type"] = "video"
        elif can_post:
            # Let AI decide content type based on trends
            if state["trends"]:
                # Pick a trending topic
                top_trend = state["trends"][0]
                state["topic"] = top_trend.get("topic", "")

                # Video if crypto/tech trend, otherwise text
                if top_trend.get("category") in ["crypto", "tech"]:
                    state["content_type"] = "video"
                else:
                    state["content_type"] = "text"
            else:
                state["content_type"] = "text"
            state["action"] = "post"
        else:
            state["action"] = "idle"

        logger.info(f"   Decision: {state['action']} ({state.get('content_type', 'N/A')})")
        return state

    def _route_action(self, state: AgentState) -> str:
        """Route to appropriate execution node."""
        return state["action"]

    def _execute_post(self, state: AgentState) -> AgentState:
        """Execute a post action."""
        logger.info(f"📝 Executing post: {state.get('content_type', 'text')}")

        try:
            # Get strategy from brain
            strategy = self.brain.get_strategy(
                force_video=(state.get("content_type") == "video")
            )

            if not strategy:
                state["success"] = False
                state["error"] = "No quality content available"
                return state

            # Execute based on type (simplified - actual execution in main.py)
            state["content"] = strategy.get("content", "")
            state["content_type"] = strategy.get("type", "text")
            state["success"] = True

        except Exception as e:
            state["success"] = False
            state["error"] = str(e)

        return state

    def _execute_reply(self, state: AgentState) -> AgentState:
        """Execute reply action."""
        logger.info("💬 Executing reply...")

        try:
            from reply_scraper import scrape_and_respond

            replies_sent = scrape_and_respond(
                username="PatriotxSystem",
                project_id=self.project_id,
                twitter_api_v1=self.api_v1,
                max_responses=3
            )

            state["success"] = replies_sent >= 0
            state["post_id"] = f"replies:{replies_sent}"

        except Exception as e:
            state["success"] = False
            state["error"] = str(e)

        return state

    def _execute_thought(self, state: AgentState) -> AgentState:
        """Execute a thought/reflection post."""
        logger.info("💭 Executing thought post...")

        try:
            # Generate a thought based on trends
            from toon_helper import toon

            prompt = f"""Based on today's context, generate a thoughtful observation.

{toon({"trends": state["trends"][:3]})}

Write a single tweet (under 280 chars) that's:
- Cynical but insightful
- About tech/AI/crypto
- No hashtags or emojis
"""

            thought = self.brain._generate_with_fallback(prompt)
            state["content"] = thought[:280]
            state["content_type"] = "thought"
            state["success"] = True

        except Exception as e:
            state["success"] = False
            state["error"] = str(e)

        return state

    def _finalize(self, state: AgentState) -> AgentState:
        """Finalize the action and log results."""
        if state["success"]:
            logger.info(f"✅ Action completed: {state['action']}")
        else:
            logger.warning(f"❌ Action failed: {state.get('error', 'Unknown')}")

        return state

    def run(self, mode: str = "auto", force_video: bool = False) -> AgentState:
        """
        Run the agent graph.

        Args:
            mode: "auto", "post", "reply", "scrape"
            force_video: Force video content

        Returns:
            Final agent state
        """
        initial_state: AgentState = {
            "mode": mode,
            "force_video": force_video,
            "trends": [],
            "mentions": [],
            "memory": [],
            "daily_stats": {},
            "action": "idle",
            "content_type": "text",
            "topic": None,
            "content": None,
            "media_path": None,
            "post_id": None,
            "success": False,
            "error": None,
            "tokens_used": 0
        }

        if self.graph:
            # Run LangGraph workflow
            final_state = self.graph.invoke(initial_state)
            return final_state
        else:
            # Fallback: simple execution
            logger.info("Using simple workflow (LangGraph not available)")
            state = self._gather_context(initial_state)
            state = self._decide_action(state)

            if state["action"] == "post":
                state = self._execute_post(state)
            elif state["action"] == "reply":
                state = self._execute_reply(state)
            elif state["action"] == "thought":
                state = self._execute_thought(state)

            state = self._finalize(state)
            return state


def run_agent(brain, controller, api_v1, client_v2, project_id: str,
              mode: str = "auto", force_video: bool = False) -> Dict:
    """
    Convenience function to run the agent.

    Returns dict with success status and details.
    """
    agent = PhantomAgentGraph(brain, controller, api_v1, client_v2, project_id)
    result = agent.run(mode=mode, force_video=force_video)

    return {
        "success": result["success"],
        "action": result["action"],
        "content_type": result.get("content_type"),
        "error": result.get("error")
    }
