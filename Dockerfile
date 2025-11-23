FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (ffmpeg)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user
RUN useradd -m appuser
USER appuser

# Set entrypoint
CMD ["python", "main.py"]
