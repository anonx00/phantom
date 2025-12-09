"""
Vector Memory System for AI Twitter Agent

Stores and retrieves conversation context using Vertex AI embeddings.
Enables the AI to:
- Remember past interactions
- Learn from conversations
- Build context about users and topics
- Make informed engagement decisions
"""

import logging
from typing import List, Dict, Optional
from google.cloud import firestore
from vertexai.language_models import TextEmbeddingModel
import datetime
import numpy as np

logger = logging.getLogger(__name__)


class VectorMemory:
    """
    Vector-based memory system for the AI agent.
    Uses Vertex AI Text Embeddings to store and retrieve contextual memories.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.db = firestore.Client(project=project_id)
        self.collection_name = "ai_memory"

        # Initialize embedding model
        try:
            self.embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
            logger.info("Initialized text-embedding-004 model for memory system")
        except Exception as e:
            logger.warning(f"Could not initialize embedding model: {e}")
            self.embedding_model = None

    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding vector for text."""
        if not self.embedding_model:
            return None

        try:
            embeddings = self.embedding_model.get_embeddings([text])
            return embeddings[0].values
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)

        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def store_interaction(
        self,
        tweet_id: str,
        author: str,
        content: str,
        interaction_type: str,  # "reply", "mention", "outreach"
        ai_response: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Store an interaction in memory with vector embedding.

        Args:
            tweet_id: Twitter tweet ID
            author: Tweet author username
            content: Tweet text content
            interaction_type: Type of interaction
            ai_response: AI's response (if any)
            metadata: Additional context

        Returns:
            Success status
        """
        try:
            # Generate embedding for the content
            embedding = self._generate_embedding(content)

            memory_doc = {
                "tweet_id": tweet_id,
                "author": author,
                "content": content,
                "interaction_type": interaction_type,
                "ai_response": ai_response,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "metadata": metadata or {},
            }

            if embedding:
                memory_doc["embedding"] = embedding
                memory_doc["embedding_dim"] = len(embedding)

            # Store in Firestore
            doc_ref = self.db.collection(self.collection_name).document(tweet_id)
            doc_ref.set(memory_doc)

            logger.info(f"Stored memory for tweet {tweet_id} by @{author}")
            return True

        except Exception as e:
            logger.error(f"Failed to store interaction: {e}")
            return False

    def get_interaction(self, tweet_id: str) -> Optional[Dict]:
        """Retrieve a specific interaction by tweet ID."""
        try:
            doc = self.db.collection(self.collection_name).document(tweet_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve interaction: {e}")
            return None

    def has_interacted_with(self, tweet_id: str) -> bool:
        """Check if we've already interacted with this tweet."""
        return self.get_interaction(tweet_id) is not None

    def find_similar_interactions(
        self,
        query_text: str,
        limit: int = 5,
        min_similarity: float = 0.7
    ) -> List[Dict]:
        """
        Find similar past interactions using vector similarity.

        Args:
            query_text: Text to find similar interactions for
            limit: Max number of results
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of similar interactions with similarity scores
        """
        if not self.embedding_model:
            logger.warning("Embedding model not available, cannot find similar interactions")
            return []

        try:
            # Generate query embedding
            query_embedding = self._generate_embedding(query_text)
            if not query_embedding:
                return []

            # Retrieve all memories with embeddings
            # Note: In production, use Vertex AI Vector Search for scale
            memories_ref = self.db.collection(self.collection_name).where(
                "embedding_dim", ">", 0
            ).limit(100)  # Limit to recent 100 for performance

            results = []
            for doc in memories_ref.stream():
                memory = doc.to_dict()
                if "embedding" in memory:
                    similarity = self._cosine_similarity(query_embedding, memory["embedding"])

                    if similarity >= min_similarity:
                        memory["similarity_score"] = similarity
                        results.append(memory)

            # Sort by similarity and return top N
            results.sort(key=lambda x: x["similarity_score"], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Failed to find similar interactions: {e}")
            return []

    def get_user_interaction_history(
        self,
        username: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get interaction history with a specific user.

        Args:
            username: Twitter username
            limit: Max number of interactions to return

        Returns:
            List of past interactions with this user
        """
        try:
            interactions = (
                self.db.collection(self.collection_name)
                .where("author", "==", username)
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )

            return [doc.to_dict() for doc in interactions]

        except Exception as e:
            logger.error(f"Failed to get user history: {e}")
            return []

    def get_interaction_stats(self) -> Dict:
        """Get statistics about stored interactions."""
        try:
            total_ref = self.db.collection(self.collection_name)
            total_count = len(list(total_ref.limit(1000).stream()))

            # Count by type
            stats = {
                "total_interactions": total_count,
                "by_type": {},
                "recent_count_24h": 0
            }

            # Get type breakdown
            for interaction_type in ["reply", "mention", "outreach"]:
                count = len(list(
                    total_ref.where("interaction_type", "==", interaction_type).limit(100).stream()
                ))
                stats["by_type"][interaction_type] = count

            # Count recent interactions (last 24 hours)
            yesterday = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
            recent = total_ref.where("timestamp", ">=", yesterday).stream()
            stats["recent_count_24h"] = len(list(recent))

            return stats

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}

    def get_context_for_user(self, username: str) -> str:
        """
        Build a context string about past interactions with a user.
        Used to inform AI decision-making.
        """
        history = self.get_user_interaction_history(username, limit=5)

        if not history:
            return f"No prior interactions with @{username}"

        context_parts = [f"Past interactions with @{username}:"]

        for i, interaction in enumerate(history[:3], 1):
            interaction_type = interaction.get("interaction_type", "unknown")
            content_preview = interaction.get("content", "")[:100]
            ai_response = interaction.get("ai_response", "")

            context_parts.append(
                f"{i}. [{interaction_type}] They said: \"{content_preview}\""
            )
            if ai_response:
                context_parts.append(f"   We replied: \"{ai_response[:100]}\"")

        return "\n".join(context_parts)

    def cleanup_old_memories(self, days_old: int = 30) -> int:
        """
        Delete memories older than specified days.
        Returns count of deleted memories.
        """
        try:
            cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_old)

            old_docs = (
                self.db.collection(self.collection_name)
                .where("timestamp", "<", cutoff_date)
                .stream()
            )

            deleted_count = 0
            batch = self.db.batch()

            for doc in old_docs:
                batch.delete(doc.reference)
                deleted_count += 1

                # Commit in batches of 500 (Firestore limit)
                if deleted_count % 500 == 0:
                    batch.commit()
                    batch = self.db.batch()

            # Commit remaining
            if deleted_count % 500 != 0:
                batch.commit()

            logger.info(f"Cleaned up {deleted_count} old memories (>{days_old} days)")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old memories: {e}")
            return 0


class ConversationContext:
    """
    Maintains context for ongoing conversations.
    Helps AI understand conversation flow and history.
    """

    def __init__(self, memory: VectorMemory):
        self.memory = memory

    def build_reply_context(
        self,
        tweet_id: str,
        author: str,
        content: str
    ) -> str:
        """
        Build comprehensive context for replying to a tweet.

        Returns formatted context string for AI decision-making.
        """
        context_parts = [
            "=== CONVERSATION CONTEXT ===",
            f"Tweet ID: {tweet_id}",
            f"Author: @{author}",
            f"Content: {content}",
            ""
        ]

        # Add user history
        user_context = self.memory.get_context_for_user(author)
        context_parts.append(user_context)
        context_parts.append("")

        # Find similar past conversations
        similar = self.memory.find_similar_interactions(content, limit=3, min_similarity=0.75)

        if similar:
            context_parts.append("Similar past conversations:")
            for i, interaction in enumerate(similar, 1):
                similarity = interaction.get("similarity_score", 0)
                past_content = interaction.get("content", "")[:80]
                past_response = interaction.get("ai_response", "")[:80]

                context_parts.append(
                    f"{i}. (similarity: {similarity:.2f}) \"{past_content}\""
                )
                if past_response:
                    context_parts.append(f"   We said: \"{past_response}\"")

        context_parts.append("=== END CONTEXT ===")

        return "\n".join(context_parts)
