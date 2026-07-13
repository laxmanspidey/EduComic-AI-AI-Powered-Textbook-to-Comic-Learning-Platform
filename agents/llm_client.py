"""
Shared Ollama LLM client for all agents.
"""
import json
import re
import requests
from django.conf import settings


def _strip_thinking(text: str) -> str:
    """
    qwen3 (and other reasoning models like deepseek-r1) wrap their reasoning
    in <think>...</think> before the real answer. If that block leaks into
    the response, JSON parsing breaks. Strip it out defensively regardless
    of whether we successfully disabled thinking mode via the API.
    """
    return re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE).strip()


def call_ollama(prompt: str, system: str = None, temperature: float = 0.7,
                 max_tokens: int = 2048, timeout: int = 180) -> str:
    """
    Call Ollama with the configured model.
    Returns the response text with any <think> reasoning block removed.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
        # Disables qwen3's chain-of-thought output (supported on Ollama 0.6.7+).
        # Older Ollama versions just ignore unknown fields, so this is safe
        # either way — _strip_thinking() below is the real safety net.
        "think": False,
    }

    try:
        response = requests.post(
            f"{settings.OLLAMA_URL}/api/chat",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content", "").strip()
        return _strip_thinking(content)
    except Exception as e:
        raise RuntimeError(f"Ollama call failed: {e}") from e


def extract_json(text: str) -> dict | list | None:
    """
    Extract JSON from a potentially markdown-wrapped LLM response.
    Tries code block first, then raw JSON, then outermost braces/brackets.

    Returns None (not {} or []) on total failure so callers can tell
    "LLM returned nothing usable" apart from "LLM legitimately returned
    an empty list", and so they don't silently treat malformed output as
    if it were valid.
    """
    text = _strip_thinking(text)

    # Try to extract from ```json ... ``` block
    match = re.search(r'```(?:json)?\s*([\s\S]+?)```', text, re.IGNORECASE)
    candidate = match.group(1).strip() if match else text

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Last resort: find the outermost JSON array first (most of our agents
    # return arrays), then object.
    for pattern in (r'(\[[\s\S]+\])', r'(\{[\s\S]+\})'):
        obj_match = re.search(pattern, text)
        if obj_match:
            try:
                return json.loads(obj_match.group(1))
            except json.JSONDecodeError:
                continue

    return None
