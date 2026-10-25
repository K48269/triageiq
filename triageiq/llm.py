"""Minimal Ollama client (stdlib only). Inference stays on your own host."""
import json, urllib.request, urllib.error

class LLMError(RuntimeError):
    pass

def chat_json(url: str, model: str, system: str, user: str, timeout: int = 120) -> str:
    body = json.dumps({
        "model": model, "stream": False, "format": "json",
        "options": {"temperature": 0},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(url.rstrip("/") + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)["message"]["content"]
    except (urllib.error.URLError, KeyError, TimeoutError, json.JSONDecodeError) as e:
        raise LLMError(f"Ollama call failed ({url}, model {model}): {e}")
