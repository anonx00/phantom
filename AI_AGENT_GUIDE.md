# AI Agent Guide - Production-Ready Budget-Conscious Twitter Bot

## Overview

Your AI agent (BIG BOSS) now has **FULL AUTONOMY** while respecting FREE tier Twitter limits and your $60 AUD budget.

## What Changed

### ✅ New Features

1. **AI Agent Controller** - Budget & quota management
2. **Reply Handler** - Monitors mentions, AI decides what to reply to
3. **Dual Mode Operation** - Post mode OR reply mode
4. **Zero Waste Policy** - Never generate unused content
5. **Complete Budget Tracking** - Firestore-based usage tracking

### 📊 Constraints & Limits

**Twitter FREE Tier:**
- 17 posts/day (includes replies)
- 100 posts retrieved/month (3-4/day)
- 1 mention check every 15 minutes

**GCP Budget** ($60 AUD ≈ $40 USD/month):
- Max 2 videos/day (expensive)
- Max 4 images/day (cheaper)
- Max 50 Vertex AI calls/day

**AI Target:**
- 7-12 posts/day during peak hours (9am-9pm)
- 2-3 replies/day (selective engagement)
- Auto-idle when quota exhausted

## How To Use

### Environment Variables

```bash
# Operational Mode
AI_MODE="auto"           # auto (AI decides) | post | reply
ENABLE_REPLIES="true"    # Enable reply functionality

# Override Controls (for testing)
FORCE_POST="false"       # Force posting (bypass scheduler)
FORCE_VIDEO="false"      # Force video generation

# Existing variables
PROJECT_ID="your-project"
REGION="us-central1"
BUDGET_MODE="True"       # Skip video in budget mode
TIMEZONE="Australia/Perth"
```

### Modes of Operation

#### 1. AUTO Mode (Default - AI Decides)

```bash
export AI_MODE="auto"
python main.py
```

AI decides based on:
- Time of day (peak hours 9am-9pm)
- Remaining quotas
- Already posted today

Decision logic:
- Peak hours + <7 posts → POST
- <3 replies today → REPLY
- <12 posts today → POST
- Quotas tight → IDLE

#### 2. POST Mode (Force Posting)

```bash
export AI_MODE="post"
python main.py
```

Always tries to create and post content (respects quotas).

#### 3. REPLY Mode (Check Mentions)

```bash
export AI_MODE="reply"
python main.py
```

Checks mentions and replies to worthy ones.

### Cloud Scheduler Setup

**Recommended Schedule:**

```yaml
# Post during peak hours
- schedule: "0 9,12,15,18,21 * * *"  # 9am, 12pm, 3pm, 6pm, 9pm
  env: AI_MODE=post

# Check replies throughout day
- schedule: "*/30 * * * *"  # Every 30 minutes
  env: AI_MODE=reply
```

Or use AUTO mode and let AI decide:

```yaml
# AI decides what to do
- schedule: "0 * * * *"  # Every hour
  env: AI_MODE=auto
```

## How It Works

### POST Mode (Zero Waste)

1. **Check Quotas**: Can we post? Can we generate video/image?
2. **Research Stories**: Get 2 story options (cheap API calls)
3. **AI Picks Best**: Choose 1 story to create content for
4. **Budget Check**: Can we afford video/image? If no → text
5. **Create ONLY Chosen**: Generate 1 prompt → 1 video → 1 post
6. **Track Usage**: Record in Firestore

**Zero Waste Guarantee:**
- Research 2 options → Pick 1 → Create ONLY that 1
- For videos: 1 prompt → 1 video (never generate unused videos)
- Budget exceeded? Fall back to text automatically

### REPLY Mode (Selective Engagement)

1. **Check Quotas**: Can we check mentions? (1 per 15min limit)
2. **Fetch Mentions**: Get new mentions since last check
3. **AI Decides Each**: Is this worth replying to?
   - Spam/low-effort → Ignore
   - Genuine/valuable → Reply
4. **Generate Reply**: Only if AI approved
5. **Post & Track**: Send reply, store in memory

**AI Decision Criteria:**
- Is it genuine conversation?
- Does reply add value?
- Is the person worth engaging with?
- Avoids spam, arguments, low-effort mentions

## Budget Tracking

### View Daily Stats

```python
from ai_agent_controller import AIAgentController

controller = AIAgentController(project_id="your-project")
summary = controller.get_daily_summary()

print(summary)
# {
#   'posts': 7,
#   'replies': 2,
#   'videos_generated': 1,
#   'images_generated': 3,
#   'twitter_quota_used': '9/17',
#   'video_budget_used': '1/2'
# }
```

### Firestore Collections

**budget_tracking/daily_YYYY-MM-DD:**
```json
{
  "posts_created": 7,
  "replies_created": 2,
  "mentions_checked": 48,
  "vertex_ai_calls": 35,
  "videos_generated": 1,
  "images_generated": 3,
  "last_mention_check": "2025-12-09T14:30:00Z"
}
```

**ai_memory/{tweet_id}:**
```json
{
  "tweet_id": "123...",
  "author": "username",
  "content": "Their message",
  "interaction_type": "reply",
  "ai_response": "Our reply",
  "timestamp": "2025-12-09T14:35:00Z"
}
```

## Logs & Monitoring

### Startup Logs

```
🤖 Starting AI Agent (BIG BOSS)...
Mode: auto | Replies: enabled
📊 Today's activity: 7 posts, 2 replies
   Twitter quota: 9/17
   Video budget: 1/2
🧠 AI decided: POST mode
```

### POST Mode Logs

```
📝 POST MODE: Creating content...
✅ AI chose story 1: Bitcoin hits new high
   Reason: Strong visual potential, trending topic
⚠️ VIDEO budget limit (2/2) - falling back to text with URL
✅ Posted text with URL
📊 Daily stats: 8 posts, 0 videos, 3 images
```

### REPLY Mode Logs

```
💬 REPLY MODE: Checking mentions...
📬 Found 3 new mentions
🤔 AI decision for @user1: False
   Reason: Low-effort spam, not worth engaging
🤔 AI decision for @user2: True
   Reason: Genuine question about tech, valuable conversation
💬 Generated reply: "That's the cycle. Next year..."
✅ Sent 1 replies
```

## Cost Optimization

### Current Spend ($35.31, forecast $43.13/month)

**Costs Breakdown:**
- Firestore: ~$5/month (reads/writes)
- Vertex AI Gemini Flash: ~$15/month (text generation)
- Vertex AI Veo: ~$20/month (2 videos/day = ~60/month)
- Vertex AI Imagen: ~$3/month (4 images/day = ~120/month)

**Within Budget:** ✅ $43.13 < $60 AUD

### Optimization Tips

1. **Reduce Video**: Set `video_generations_per_day_max: 1`
2. **More Text Posts**: AI will choose text when budget tight
3. **Disable Replies**: `ENABLE_REPLIES=false` to save calls
4. **Less Frequent**: Reduce Cloud Scheduler triggers

## Safety Features

### Rate Limit Protection

- Tracks ALL API calls
- Enforces Twitter FREE tier limits
- Won't exceed daily quotas
- Returns friendly messages when limited

### Budget Protection

- Hard limits on expensive operations
- Automatic fallback to cheaper alternatives
- Daily tracking with Firestore
- Logs all generation costs

### AI Safety

- Won't reply to spam/abuse
- Won't engage in arguments
- Won't waste quota on low-value interactions
- Stays in character (BIG BOSS persona)

## Troubleshooting

### "Daily post limit reached"

```
❌ Cannot post: Daily post limit reached (17/17)
```

**Solution:** Wait until midnight (Australia/Perth timezone). Or reduce Cloud Scheduler frequency.

### "Daily video limit reached"

```
⚠️ VIDEO budget limit (2/2) - falling back to text with URL
```

**This is normal!** Budget protection working. Posts text instead.

### "Rate limit: wait 12 more minutes"

```
⏸️ Skipping mention check: Rate limit: wait 12 more minutes
```

**This is normal!** FREE tier allows 1 check per 15 minutes.

### No replies being sent

Check:
1. `ENABLE_REPLIES=true`
2. Run in `reply` or `auto` mode
3. Are there mentions? Check Twitter notifications
4. AI might be rejecting low-quality mentions (working as intended)

## Advanced Configuration

### Adjust Reply Aggressiveness

In `ai_agent_controller.py`:

```python
FREE_TIER_LIMITS = {
    "replies_per_day_target": 3,  # Change this (1-10)
}
```

### Adjust Video Budget

```python
BUDGET_LIMITS = {
    "video_generations_per_day_max": 2,  # Change this (0-5)
    "image_generations_per_day_max": 4,  # Change this (0-10)
}
```

### Adjust Peak Hours

In `ai_agent_controller.py`, `should_engage_mode()`:

```python
is_peak_hours = 9 <= current_hour <= 21  # 9am-9pm
```

## API Tier Upgrade Path

If you upgrade to **Basic ($200/month)**:

Update limits in `ai_agent_controller.py`:

```python
# From FREE:
"posts_per_day": 17
"mentions_check_interval_minutes": 15

# To BASIC:
"posts_per_day": 100  # Much higher!
"mentions_check_interval_minutes": 1.5  # 10 checks per 15min
"replies_per_day_target": 20  # More aggressive
```

Then set:
```bash
export ENABLE_REPLIES=true
export AI_MODE=auto
```

AI will automatically take advantage of higher limits!

---

## Summary

✅ **Production-Ready**: All systems operational
✅ **Budget-Conscious**: $43/month < $60 AUD limit
✅ **FREE Tier Optimized**: Respects all Twitter limits
✅ **Zero Waste**: Never generates unused content
✅ **AI Autonomous**: Decides what/when to post/reply
✅ **Tracked & Logged**: Full visibility into usage

**Status**: Ready to deploy! 🚀
