# GCP Tech Influencer Agent

A serverless, autonomous agent that posts trending tech content to X (Twitter). Built with Google Cloud Run Jobs, Vertex AI (Gemini + Veo), and Firestore.

## Architecture

- **Orchestrator**: Cloud Run Jobs (Python container)
- **Brain**: Vertex AI Gemini 1.5 Flash (Strategy & Scripting)
- **Video**: Vertex AI Veo (Video Generation)
- **Database**: Firestore (History & Deduplication)
- **Secrets**: Secret Manager (API Keys)
- **CI/CD**: Cloud Build

## Setup

1. **Prerequisites**
   - Google Cloud Project with Billing enabled.
   - X (Twitter) Developer Account with v2 API access.
   - `gcloud` CLI installed and authenticated.

2. **Environment Variables**
   - `PROJECT_ID`: Your GCP Project ID.
   - `REGION`: Region for resources (default: `us-central1`).
   - `BUDGET_MODE`: `True` to disable video generation (save costs), `False` otherwise.

3. **Secrets (Secret Manager)**
   Create the following secrets in GCP Secret Manager:
   - `TWITTER_CONSUMER_KEY`
   - `TWITTER_CONSUMER_SECRET`
   - `TWITTER_ACCESS_TOKEN`
   - `TWITTER_ACCESS_TOKEN_SECRET`

4. **Deployment**
   
   **Manual:**
   ```bash
   ./deploy.sh
   ```

   **CI/CD:**
   Connect your repo to Cloud Build and use the included `cloudbuild.yaml`.

## Development

- **Install Dependencies**: `pip install -r requirements.txt`
- **Run Locally**: `python main.py` (Ensure you have local credentials or set env vars).

## License
MIT
