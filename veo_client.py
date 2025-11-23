import time
import requests
import google.auth
import google.auth.transport.requests
from config import Config

class VeoClient:
    def __init__(self, project_id: str, region: str):
        self.project_id = project_id
        self.region = region
        self.base_url = f"https://{region}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{region}/publishers/google/models/veo-3.1-generate-001:predict"
        self.credentials, _ = google.auth.default()

    def _get_headers(self):
        """Refreshes credentials and returns headers."""
        auth_req = google.auth.transport.requests.Request()
        self.credentials.refresh(auth_req)
        return {
            "Authorization": f"Bearer {self.credentials.token}",
            "Content-Type": "application/json"
        }

    def generate_video(self, prompt: str) -> str:
        """
        Generates a video using Veo, polls for completion, and saves to a temporary file.
        Returns the path to the saved video.
        """
        print(f"Generating video for prompt: {prompt}")
        
        payload = {
            "instances": [
                {
                    "prompt": prompt
                }
            ],
            "parameters": {
                "sampleCount": 1,
                "videoLength": "6s",
                "aspectRatio": "16:9"
            }
        }

        try:
            response = requests.post(
                self.base_url,
                headers=self._get_headers(),
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            predictions = result.get("predictions", [])
            if not predictions:
                raise ValueError(f"No predictions returned: {result}")
            
            # Create a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
                output_path = tmp_file.name

            # Check for video content
            video_bytes = None
            
            if "bytesBase64Encoded" in predictions[0]:
                import base64
                video_bytes = base64.b64decode(predictions[0]["bytesBase64Encoded"])
                with open(output_path, "wb") as f:
                    f.write(video_bytes)
            elif "videoUri" in predictions[0]:
                # Download from GCS
                video_uri = predictions[0]["videoUri"]
                print(f"Downloading video from {video_uri}...")
                
                # Use GCS client to download
                from google.cloud import storage
                storage_client = storage.Client(project=self.project_id)
                
                # Parse GCS URI (gs://bucket/path)
                if video_uri.startswith("gs://"):
                    parts = video_uri[5:].split("/", 1)
                    bucket_name = parts[0]
                    blob_name = parts[1]
                    
                    bucket = storage_client.bucket(bucket_name)
                    blob = bucket.blob(blob_name)
                    blob.download_to_filename(output_path)
                else:
                    raise ValueError(f"Unsupported video URI format: {video_uri}")
            else:
                raise ValueError(f"Could not find video data in response: {predictions[0]}")
            
            print(f"Video saved to {output_path}")
            return output_path

        except Exception as e:
            print(f"Veo generation failed: {e}")
            raise
