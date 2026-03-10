# app/services/lm_studio.py
import os
import requests
from typing import List, Optional

# LM Studio configuration (optional - doesn't require LM Studio to be running)
LM_STUDIO_BASE = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234")
CHAT_ENDPOINT = f"{LM_STUDIO_BASE}/v1/chat/completions"
DEFAULT_TIMEOUT = int(os.getenv("LM_STUDIO_TIMEOUT", "30"))

def _call(endpoint: str, payload: dict, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Low-level POST to LM Studio; raises on HTTP errors."""
    try:
        resp = requests.post(endpoint, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise Exception(f"LM Studio connection failed: {str(e)}")

def generate_chat(messages: list,
                  model: str = None,
                  temperature: float = 0.7,
                  max_new_tokens: int = 150) -> str:
    """
    Call LM Studio OpenAI-like chat endpoint.
    messages: list of {"role": "user"/"system"/"assistant", "content": "..."}
    """
    payload = {
        "model": model or "mistral-7b-instruct",
        "messages": messages,
        "temperature": temperature,
        "max_new_tokens": max_new_tokens
    }
    try:
        data = _call(CHAT_ENDPOINT, payload)
        # OpenAI-chat style response
        if isinstance(data, dict):
            choices = data.get("choices")
            if choices and isinstance(choices, list):
                m = choices[0].get("message") or {}
                content = m.get("content") or m.get("text")
                if content:
                    return content.strip()
        return str(data)
    except Exception as e:
        raise Exception(f"LM Studio generation failed: {str(e)}")

def generate_from_prompt(prompt: str,
                         system_prompt: Optional[str] = None,
                         temperature: float = 0.7,
                         max_new_tokens: int = 150) -> str:
    """Convenience wrapper that constructs messages list from system + user prompt."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return generate_chat(messages, temperature=temperature, max_new_tokens=max_new_tokens)

def generate_with_context(context_snippets: List[str], user_message: str,
                          max_new_tokens: int = 200,
                          temperature: float = 0.1) -> str:
    """
    RAG helper: supplies the model with context and instructs it to answer accurately.
    """
    ctx = "\n\n".join(context_snippets).strip()
    system = (
        "You are Ella, the Ellenki College assistant. Use the CONTEXT to answer the user's question "
        "briefly and accurately. Keep your answer conversational and friendly. "
        "If the information isn't in the context, say you don't know or recommend checking the official website. "
        "Do not make up facts."
    )
    prompt = f"CONTEXT:\n{ctx}\n\nUser question: {user_message}\n\nAnswer:"
    return generate_from_prompt(prompt, system_prompt=system, temperature=temperature, max_new_tokens=max_new_tokens)
