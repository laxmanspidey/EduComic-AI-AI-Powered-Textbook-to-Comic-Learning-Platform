"""
ComfyUI API client.
Sends workflow prompts, polls for completion, and retrieves generated images.
"""
import time
import uuid
import urllib.parse
import requests
from django.conf import settings


class ComfyUIClient:
    """Client for interacting with the ComfyUI API."""

    def __init__(self):
        self.base_url = settings.COMFYUI_URL
        self.client_id = str(uuid.uuid4())

    def _post_prompt(self, workflow: dict) -> str:
        """
        Submit a workflow to ComfyUI.
        Returns the prompt_id.
        """
        payload = {
            "prompt": workflow,
            "client_id": self.client_id,
        }
        response = requests.post(
            f"{self.base_url}/prompt",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI did not return a prompt_id: {data}")
        return prompt_id

    def _poll_history(self, prompt_id: str, timeout: int = 300) -> dict:
        """
        Poll the /history endpoint until the prompt is completed.
        Returns the history entry for the prompt.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                response = requests.get(
                    f"{self.base_url}/history/{prompt_id}",
                    timeout=10,
                )
                if response.status_code == 200:
                    history = response.json()
                    if prompt_id in history:
                        return history[prompt_id]
            except requests.RequestException:
                pass
            time.sleep(3)

        raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out after {timeout}s")

    def _get_output_images(self, history_entry: dict) -> list[str]:
        """
        Extract output image filenames from a history entry.
        Returns list of (filename, subfolder, type) tuples.
        """
        images = []
        outputs = history_entry.get("outputs", {})
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for img in node_output["images"]:
                    images.append({
                        "filename": img["filename"],
                        "subfolder": img.get("subfolder", ""),
                        "type": img.get("type", "output"),
                    })
        return images

    def download_image(self, filename: str, subfolder: str = "", img_type: str = "output") -> bytes:
        """Download an image from ComfyUI and return raw bytes."""
        params = urllib.parse.urlencode({
            "filename": filename,
            "subfolder": subfolder,
            "type": img_type,
        })
        response = requests.get(
            f"{self.base_url}/view?{params}",
            timeout=30,
        )
        response.raise_for_status()
        return response.content

    def is_available(self) -> bool:
        """Check if ComfyUI is running."""
        try:
            r = requests.get(f"{self.base_url}/system_stats", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def generate_image(self, workflow: dict, timeout: int = 300) -> list[bytes]:
        """
        Submit a workflow, wait for completion, return list of image bytes.
        """
        prompt_id = self._post_prompt(workflow)
        history = self._poll_history(prompt_id, timeout=timeout)
        image_infos = self._get_output_images(history)

        images = []
        for info in image_infos:
            img_bytes = self.download_image(
                filename=info['filename'],
                subfolder=info['subfolder'],
                img_type=info['type'],
            )
            images.append(img_bytes)

        return images
