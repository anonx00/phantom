# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Phantom is an autonomous AI agent that posts trending tech content to X (Twitter). It runs as a serverless Cloud Run Job on GCP, triggered by Cloud Scheduler 5 times daily (AWST timezone: 10:30 AM, 2:45 PM, 6:00 PM, 8:30 PM, 10:15 PM).

## Architecture

```
┌─────────────────────────────────────────────┐
│ ENTRY POINT (main.py)                       │
├─────────────────────────────────────────────┤
│ ORCHESTRATION LAYER                         │
│ - agent_graph.py (LangGraph Workflow)       │
│ - ai_agent_controller.py (Quota Management) │
├─────────────────────────────────────────────┤
│ AI/INTELLIGENCE LAYER                       │
│ - brain.py (Content Generation + Gemini)    │
│ - memory_system.py (Vector Memory)          │
│ - toon_helper.py (Token-efficient encoding) │
├─────────────────────────────────────────────┤
│ DATA GATHERING LAYER                        │
│ - trend_scraper.py (8 free sources)         │
│ - news_fetcher.py (RSS feeds)               │
│ - meme_fetcher.py (Reddit, Giphy, Imgflip)  │
│ - civitai_downloader.py (FREE videos)       │
├─────────────────────────────────────────────┤
│ CONTENT TRANSFORMATION                      │
│ - content_mixer.py (Format selection)       │
│ - infographic_generator.py (Imagen)         │
│ - cinematic_director.py (Video prompts)     │
├─────────────────────────────────────────────┤
│ CONFIGURATION                               │
│ - config.py (Secrets, env vars)             │
│ - terraform/ (Infrastructure as Code)       │
└─────────────────────────────────────────────┘
```

## LangGraph Agent Workflow

```
gather_context() → decide_content() → generate_strategy()
                                            ↓
                                    [conditional_edge]
                                    /              \
                            quality_check      finalize (skip)
                                    ↓
                                finalize → END
```

**AgentState** carries: `trends`, `memory`, `daily_stats`, `content_type`, `topic`, `strategy`

## Content Pipeline

1. **TrendScraper** gathers from 8 free sources (HN, Reddit, CoinGecko, GitHub, Lobsters, Dev.to, TechCrunch RSS, HuggingFace) with 30-min caching
2. **LangGraph agent** decides content type based on trends, time of day, variety, and budget
3. **Brain** generates content with Gemini, validates quality
4. **AIAgentController** enforces Twitter quotas (17 posts/day) and GCP budget
5. **Post execution** with automatic fallback to text on media failures

## Content Types

| Type | Source | Generation |
|------|--------|------------|
| video | CivitAI (FREE) | Download community videos |
| meme | Reddit/Giphy/Imgflip | AI-validated for quality |
| infographic | Imagen 3/4 | AI extracts key points |
| image | Imagen 3/4 | News-based prompts |
| text | Gemini | Tweet or thread |
| thought | Gemini | Rare AI reflections (1 per 10 posts) |

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires GCP credentials)
export PROJECT_ID="phantom-479109"
export REGION="us-central1"
python main.py

# Run tests
python -m unittest tests/test_brain.py

# Build and deploy to GCP
gcloud builds submit --tag us-central1-docker.pkg.dev/phantom-479109/phantom-influencer/phantom-influencer:latest .
gcloud run jobs update phantom-influencer-job --image us-central1-docker.pkg.dev/phantom-479109/phantom-influencer/phantom-influencer:latest --region us-central1

# Force a post (testing)
gcloud run jobs execute phantom-influencer-job --region us-central1 --update-env-vars FORCE_POST=true

# View logs
gcloud logging read 'resource.type=cloud_run_job AND resource.labels.job_name=phantom-influencer-job' --limit=50

# Terraform commands
cd terraform
terraform init
terraform plan
terraform apply
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PROJECT_ID` | GCP project ID | Required |
| `REGION` | GCP region | `us-central1` |
| `BUDGET_MODE` | Disable expensive video gen | `False` |
| `FORCE_POST` | Bypass scheduler checks | `false` |
| `USE_LANGGRAPH` | Use agent workflow | `true` |
| `TIMEZONE` | Scheduler timezone | `Australia/Perth` |

## GCP Services & IAM

**Services Used:**
- Cloud Run Jobs (container execution)
- Vertex AI (Gemini 2.5/2.0/1.5 Flash, Imagen 3/4, text-embedding-004)
- Firestore (post_history, ai_memory, budget_tracking collections)
- Secret Manager (Twitter API credentials)
- Cloud Scheduler (5 daily triggers)
- Artifact Registry (Docker images)

**Service Account:** `phantom-influencer-sa` with roles:
- `secretmanager.secretAccessor`
- `datastore.user`
- `aiplatform.user`
- `storage.objectViewer`
- `logging.logWriter`
- `run.invoker`

## Firestore Collections

| Collection | Purpose | Retention |
|------------|---------|-----------|
| `post_history` | Posted content, deduplication | 30 days |
| `ai_memory` | Vector embeddings, context | 14 days |
| `budget_tracking` | Daily usage stats | 90 days |

## Key Design Patterns

### Graceful Degradation
Every component has fallbacks:
- Model: Gemini 2.5 → 2.0 → 1.5
- Video: CivitAI → text fallback
- Image: Imagen → text fallback
- Trends: 8 sources, any can fail

### Zero-Waste Strategy
- Research 2 story options (cheap)
- AI picks 1 best story
- Generate content only for chosen story
- No wasted API calls

### TOON Format (toon_helper.py)
Token-efficient encoding saves ~40% tokens vs JSON. Use `toon()` or `encode_for_llm()` when passing structured data to Gemini.

### Budget Controls
- Twitter: 17 posts/day limit enforced
- Videos: 10/day max (FREE via CivitAI)
- Images: 4/day max (Imagen costs)
- Daily stats tracked in Firestore

## Testing

```bash
# Run unit tests (mocks GCP services)
python -m unittest tests/test_brain.py

# Test patterns used:
# - unittest + unittest.mock
# - @patch decorators for GCP mocks
# - sys.modules mocking for missing credentials
```

## Secrets (Secret Manager)

Must be created manually before deployment:
- `TWITTER_CONSUMER_KEY`
- `TWITTER_CONSUMER_SECRET`
- `TWITTER_ACCESS_TOKEN`
- `TWITTER_ACCESS_TOKEN_SECRET`
- `TWITTER_BEARER_TOKEN` (optional)

## Cost Estimates (AUD/month)

| Service | Cost |
|---------|------|
| Cloud Run | $5-15 |
| Vertex AI (Gemini) | $5-20 |
| Vertex AI (Imagen) | $10-30 |
| Other | $1-5 |
| **Total** | **$21-70** |

Enable `BUDGET_MODE=true` to reduce costs by disabling image generation.
