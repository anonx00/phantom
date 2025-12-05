# Phantom Tech Influencer - Terraform Variables
#
# Quick Start:
#   export TF_VAR_project_id="your-project-id"
#   terraform init && terraform apply

variable "project_id" {
  description = "GCP Project ID (required)"
  type        = string
}

variable "region" {
  description = "GCP Region for Cloud Run and Artifact Registry"
  type        = string
  default     = "us-central1"
}

variable "firestore_location" {
  description = "Firestore database location (must be valid Firestore region)"
  type        = string
  default     = "nam5"  # US multi-region, compatible with us-central1
  # Other options: "eur3" (Europe), "australia-southeast1", etc.
}

variable "timezone" {
  description = "Timezone for scheduling (AWST = Australia/Perth, UTC+8)"
  type        = string
  default     = "Australia/Perth"
}

variable "budget_mode" {
  description = "Enable strict budget mode: 1 post/day, max 1 video/day, no images/infographics"
  type        = bool
  default     = true
}

variable "image_name" {
  description = "Name for the container image"
  type        = string
  default     = "phantom-influencer"
}

variable "job_name" {
  description = "Name for the Cloud Run Job"
  type        = string
  default     = "phantom-influencer-job"
}

# Scheduler configuration - AWST times
# STRICT BUDGET MODE: 1 trigger per day to hit $30 AUD/month target
# Single daily post at peak engagement time (evening)
variable "scheduler_triggers" {
  description = "Cron expressions for Cloud Scheduler triggers (in configured timezone)"
  type        = list(string)
  default = [
    "0 18 * * *",   # 6:00 PM AWST - Peak evening engagement (1 post/day: video OR text)
  ]
}

# Resource limits
variable "cpu_limit" {
  description = "CPU limit for Cloud Run Job"
  type        = string
  default     = "1"
}

variable "memory_limit" {
  description = "Memory limit for Cloud Run Job"
  type        = string
  default     = "1Gi"
}

variable "timeout_seconds" {
  description = "Timeout for Cloud Run Job execution (seconds)"
  type        = number
  default     = 900  # 15 minutes
}

variable "max_retries" {
  description = "Maximum retries for failed job executions"
  type        = number
  default     = 1
}
