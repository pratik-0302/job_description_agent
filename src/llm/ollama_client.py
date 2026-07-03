# pyrefly: ignore [missing-import]
import httpx
import json
import logging
import time
from typing import List, Dict, Any, Generator, Optional

from src.config import AppConfig

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, cfg: AppConfig):
        self.base_url = cfg.llm.base_url  # e.g., "http://localhost:11434"
        self.model = cfg.llm.model  # e.g., "qwen3:8b"
        self.temperature = cfg.llm.temperature  # e.g., 0.0
        self.timeout = float(cfg.llm.timeout_seconds)  # e.g., 60.0

    def health_check(self) -> bool:
        """Check if local Ollama service is up and running."""
        try:
            # Check model availability or status endpoint
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                # Confirm target model is downloaded/available
                models_data = response.json()
                models = [m.get("name") for m in models_data.get("models", [])]
                # Allow partial match (e.g. qwen3:8b matches qwen3:8b-instruct-q4_K_M)
                target_short = self.model.split(":")[0]
                for m in models:
                    if target_short in m:
                        return True
                logger.warning(f"Ollama running but model '{self.model}' not found in: {models}")
                return True # Return true anyway if service is up
            return False
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    def generate(self, system_prompt: str, user_prompt: str, stream: bool = False) -> Any:
        """Send inference request to local Ollama chat API."""
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": stream,
            "options": {
                "temperature": self.temperature
            }
        }
        
        if stream:
            return self._generate_stream(url, payload)
        else:
            return self._generate_sync(url, payload)

    def _generate_sync(self, url: str, payload: dict) -> Dict[str, Any]:
        start_time = time.time()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
                
                if response.status_code != 200:
                    raise RuntimeError(f"Ollama API returned HTTP status {response.status_code}: {response.text}")
                    
                result = response.json()
                message = result.get("message", {})
                content = message.get("content", "")
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                return {
                    "response_text": content,
                    "model_used": self.model,
                    "generation_time_ms": duration_ms
                }
        except Exception as e:
            logger.error(f"Sync LLM generation failed: {e}")
            raise

    def _generate_stream(self, url: str, payload: dict) -> Generator[str, None, None]:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        raise RuntimeError(f"Ollama streaming API returned HTTP status {response.status_code}")
                        
                    for line in response.iter_lines():
                        if not line:
                            continue
                        try:
                            chunk_data = json.loads(line)
                            content = chunk_data.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Stream LLM generation failed: {e}")
            raise
