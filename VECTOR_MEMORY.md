# Vector Memory System - AI Context Awareness

## Overview

Your AI now has **FULL MEMORY** of everything it posts and everyone it interacts with using **Vertex AI text-embedding-004** and vector similarity search.

## What AI Remembers

### 1. **Posts** (What AI said)
- Every tweet/video/meme posted
- Topic and content with vector embedding
- Similar past posts (prevents repetition)

### 2. **Replies** (Conversations)
- Who mentioned the AI
- What they said
- How AI replied
- Full conversation history per user

### 3. **Context** (Smart decisions)
- Similar past conversations
- User interaction patterns
- Topic freshness (already posted?)
- Conversation quality (worth engaging?)

## How It Works

### Vector Embeddings

```python
# When AI posts
"Bitcoin hits $90K" → [0.234, -0.891, 0.456, ...] (768 dimensions)

# Later, new topic
"BTC reaches new high" → [0.245, -0.883, 0.461, ...]

# AI calculates similarity
cosine_similarity = 0.92 (92% similar!)
→ "⚠️ Too similar to recent post, skip or reframe"
```

### Memory Collections (Firestore)

**ai_memory/{tweet_id}:**
```json
{
  "tweet_id": "123...",
  "author": "username",
  "content": "Their message or our post",
  "interaction_type": "reply" | "posted" | "mention_ignored",
  "ai_response": "Our reply (if any)",
  "timestamp": "2025-12-09T...",
  "embedding": [0.234, -0.891, ...],  // 768D vector
  "metadata": {...}
}
```

## AI Features Enabled

### 1. **Anti-Repetition** (Posting)

```python
# Before posting about "Bitcoin rally"
similar_posts = memory.find_similar("Bitcoin rally", min_similarity=0.85)

if similar_posts:
  # AI sees: "You posted about this 2 days ago (87% similar)"
  → Skip or choose different angle
```

**Prevents**:
- Posting same topic multiple times
- Redundant content
- Boring repetition

### 2. **Conversation Awareness** (Replies)

```python
# When someone mentions AI
context = memory.build_reply_context(tweet_id, author, content)

# AI sees:
# - Past 3 interactions with this user
# - Similar conversations (vector search)
# - Full conversation history

→ Informed, contextual replies
```

**Enables**:
- Remembering past conversations
- Not repeating same answers
- Building relationships

### 3. **Selective Engagement**

```python
# AI decides if mention is worth replying to
context_includes:
  - Have we talked before?
  - What did we discuss?
  - Are they genuine or spam?

→ Quality engagement only
```

## Usage in Code

### Storing Posts

```python
from post_memory_tracker import PostMemoryTracker

memory_tracker = PostMemoryTracker(controller.vector_memory)

# After posting
memory_tracker.store_post(
    post_id="123...",
    content="Bitcoin hits $90K",
    post_type="video",
    topic="Bitcoin rally",
    metadata={"video_prompt": "..."}
)
```

### Checking for Repetition

```python
# Before creating content
similar = memory_tracker.check_similar_recent_posts(
    topic="Bitcoin rally",
    min_similarity=0.85,
    days_back=7
)

if similar:
    # Too repetitive, skip or reframe
```

### Building Reply Context

```python
from memory_system import ConversationContext

context_builder = ConversationContext(vector_memory)

rich_context = context_builder.build_reply_context(
    tweet_id="123...",
    author="username",
    content="Their mention"
)

# rich_context includes:
# - Past interactions with this user
# - Similar conversations
# - Full history
```

## Example Scenarios

### Scenario 1: Avoiding Repetition

```
Day 1:
AI posts: "Bitcoin at $90K. Fragile setup."
→ Stored with embedding

Day 3:
News: "BTC reaches new all-time high"
AI checks memory: 92% similar to Day 1 post
→ ⚠️ Skip (too repetitive)

Day 7:
News: "Bitcoin crashes to $70K"
AI checks memory: 35% similar (different angle!)
→ ✅ Post (fresh perspective)
```

### Scenario 2: Smart Replies

```
Week 1:
@user1: "What do you think about AI regulation?"
AI: "Same cycle. They don't understand it yet."
→ Stored in memory

Week 2:
@user1: "AI regulation news again"
AI sees past conversation:
  - We already discussed this
  - User seems interested in topic
  - Can build on previous reply
AI: "Told you. Predictable."
→ Contextual, not repetitive
```

### Scenario 3: Spam Detection

```
@spambot: "Check out my crypto! 🚀🚀🚀"
AI checks memory:
  - No prior interactions
  - Content looks like spam pattern
  - Vector similarity to known spam
→ ❌ Ignore (saves quota)
```

## Memory Stats

### View Current Memory

```python
stats = controller.vector_memory.get_interaction_stats()

# Returns:
{
  "total_interactions": 247,
  "by_type": {
    "posted": 89,
    "reply": 12,
    "mention_ignored": 146
  },
  "recent_count_24h": 15
}
```

### Startup Logs

```
🧠 AI Memory: 247 total interactions stored
   Recent (24h): 15 interactions
```

## Cost & Performance

### Embedding Generation

- **Cost**: ~$0.000025 per embedding (Vertex AI text-embedding-004)
- **Per interaction**: ~$0.000025
- **100 interactions/day**: ~$0.0025/day = **$0.075/month**

**Total Memory Cost**: < $1/month (negligible!)

### Storage

- **Firestore**: ~$0.06/GB/month
- **Each embedding**: ~3KB (768 floats)
- **1000 interactions**: ~3MB = **$0.0002/month**

**Total Storage Cost**: < $0.10/month

### Performance

- **Embedding generation**: ~100ms
- **Similarity search**: ~50ms (up to 100 vectors)
- **Total overhead**: ~150ms per interaction

**Impact**: Minimal, acceptable for async posting

## Limitations & Optimizations

### Current Setup (Good for Small Scale)

- Stores embeddings in Firestore
- In-memory similarity search (up to ~1000 vectors)
- Works great for: <500 interactions/week

### For Scale (Future)

If you grow to >10K interactions:

1. **Use Vertex AI Vector Search**
   - Dedicated vector database
   - Sub-10ms similarity search
   - Scales to millions of vectors

2. **Implement Caching**
   - Cache recent embeddings in memory
   - Reduce Firestore reads

3. **Archive Old Interactions**
   - Move >30 day old data to cold storage
   - Keep only recent in active memory

## Cleanup & Maintenance

### Auto-Cleanup

```python
# Delete memories older than 30 days
deleted = controller.vector_memory.cleanup_old_memories(days_old=30)
# Returns: 45 memories deleted
```

### Manual Check

```python
# Get user interaction history
history = controller.vector_memory.get_user_interaction_history(
    username="some_user",
    limit=10
)

# Check specific interaction
interaction = controller.vector_memory.get_interaction("tweet_id")
```

## Integration Status

✅ **ai_agent_controller.py** - Initializes vector memory
✅ **reply_handler.py** - Uses memory for reply context
✅ **post_memory_tracker.py** - Tracks posts with embeddings
✅ **main.py** - Stores posts in memory after publishing

## Environment

No new environment variables needed! Works automatically with:
- `PROJECT_ID` (existing)
- Vertex AI enabled (existing)
- Firestore enabled (existing)

## Summary

**What Changed:**
- AI now remembers EVERYTHING it posts and everyone it talks to
- Vector embeddings enable smart similarity detection
- Prevents repetitive content automatically
- Enables contextual, informed conversations
- Costs < $1/month (negligible)

**Benefits:**
- 🧠 Context-aware AI (knows its own history)
- 🎯 Anti-repetition (no boring duplicate posts)
- 💬 Smart conversations (remembers past interactions)
- 📊 Quality engagement (ignores spam/low-value)
- 💰 Budget-friendly (< $1/month overhead)

**Status**: ✅ Production-ready and integrated!
