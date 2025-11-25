#!/bin/bash
set -e # Exit on error

# Configuration
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "Error: PROJECT_ID not set in gcloud config."
    exit 1
fi

REGION="us-central1"
REPO_NAME="tech-influencer-repo"
IMAGE_NAME="tech-influencer-agent"
JOB_NAME="tech-influencer-job"

echo "Deploying to Project: $PROJECT_ID in Region: $REGION"

# 1. Enable Services (idempotent)
gcloud services enable artifactregistry.googleapis.com run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com aiplatform.googleapis.com firestore.googleapis.com

# 2. Create Artifact Registry Repo if not exists
if ! gcloud artifacts repositories describe $REPO_NAME --location=$REGION > /dev/null 2>&1; then
    gcloud artifacts repositories create $REPO_NAME --repository-format=docker --location=$REGION --description="Docker repository for Tech Influencer Agent"
fi

# 3. Build and Push Container
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME .

# 4. Create/Update Cloud Run Job
# Check if job exists
if gcloud run jobs describe $JOB_NAME --region $REGION > /dev/null 2>&1; then
    echo "Updating existing job..."
    gcloud run jobs update $JOB_NAME \
        --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME \
        --region $REGION \
        --set-env-vars PROJECT_ID=$PROJECT_ID,REGION=$REGION,BUDGET_MODE=False \
        --max-retries 1 \
        --task-timeout 10m
else
    echo "Creating new job..."
    gcloud run jobs create $JOB_NAME \
        --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME \
        --region $REGION \
        --set-env-vars PROJECT_ID=$PROJECT_ID,REGION=$REGION,BUDGET_MODE=False \
        --max-retries 1 \
        --task-timeout 10m
fi

# 5. Create/Update Cloud Schedulers (Multiple triggers for human-like posting)
# Use the tech-influencer service account or default compute service account
SERVICE_ACCOUNT_EMAIL="tech-influencer-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Check if service account exists, fallback to default compute
if ! gcloud iam service-accounts describe $SERVICE_ACCOUNT_EMAIL > /dev/null 2>&1; then
    SERVICE_ACCOUNT_EMAIL="${PROJECT_ID//[^0-9]/}-compute@developer.gserviceaccount.com"
    # Try to get the actual compute SA
    COMPUTE_SA=$(gcloud iam service-accounts list --filter="email:compute@developer.gserviceaccount.com" --format="value(email)" --limit=1)
    if [ -n "$COMPUTE_SA" ]; then
        SERVICE_ACCOUNT_EMAIL=$COMPUTE_SA
    fi
fi

echo "Using Service Account: $SERVICE_ACCOUNT_EMAIL"

# Define multiple trigger schedules for human-like posting
# Times are in Australia/Sydney timezone (AEST/AEDT)
# The scheduler in the app will randomly decide whether to actually post

SCHEDULES=(
    "tech-influencer-morning:30 7 * * *"      # 7:30 AM - Morning coffee
    "tech-influencer-midmorning:15 10 * * *"  # 10:15 AM - Mid-morning
    "tech-influencer-lunch:45 12 * * *"       # 12:45 PM - Lunch break
    "tech-influencer-afternoon:30 15 * * *"   # 3:30 PM - Afternoon
    "tech-influencer-evening:0 18 * * *"      # 6:00 PM - Evening (peak)
    "tech-influencer-night:30 20 * * *"       # 8:30 PM - Night scroll
    "tech-influencer-late:45 22 * * *"        # 10:45 PM - Late night
)

echo "Creating/updating ${#SCHEDULES[@]} scheduler triggers..."

for schedule_entry in "${SCHEDULES[@]}"; do
    SCHEDULE_NAME="${schedule_entry%%:*}"
    CRON_EXPR="${schedule_entry##*:}"

    echo "  - $SCHEDULE_NAME: $CRON_EXPR (Australia/Sydney)"

    if gcloud scheduler jobs describe $SCHEDULE_NAME --location $REGION > /dev/null 2>&1; then
        gcloud scheduler jobs update http $SCHEDULE_NAME \
            --schedule "$CRON_EXPR" \
            --time-zone "Australia/Sydney" \
            --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$JOB_NAME:run" \
            --http-method POST \
            --oauth-service-account-email $SERVICE_ACCOUNT_EMAIL \
            --location $REGION \
            --quiet
    else
        gcloud scheduler jobs create http $SCHEDULE_NAME \
            --schedule "$CRON_EXPR" \
            --time-zone "Australia/Sydney" \
            --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$JOB_NAME:run" \
            --http-method POST \
            --oauth-service-account-email $SERVICE_ACCOUNT_EMAIL \
            --location $REGION \
            --quiet
    fi
done

# Clean up old single scheduler if it exists
if gcloud scheduler jobs describe tech-influencer-schedule --location $REGION > /dev/null 2>&1; then
    echo "Removing old single-trigger scheduler..."
    gcloud scheduler jobs delete tech-influencer-schedule --location $REGION --quiet
fi

echo ""
echo "Deployment Complete!"
echo ""
echo "Multiple scheduler triggers created. The app uses probabilistic posting"
echo "to simulate human-like behavior (not every trigger results in a post)."
echo ""
echo "Manual commands:"
echo "  Force a post now: gcloud run jobs execute $JOB_NAME --region $REGION --update-env-vars FORCE_POST=true"
echo "  Normal trigger:   gcloud run jobs execute $JOB_NAME --region $REGION"
echo ""
echo "View scheduler status: gcloud scheduler jobs list --location $REGION"
