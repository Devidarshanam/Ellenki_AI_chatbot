from typing import List
import requests


class LLMClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "tinyllama"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def chat(self, system_prompt: str, messages: List[dict]) -> str:
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": full_messages,
            "stream": False
        }

        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]
