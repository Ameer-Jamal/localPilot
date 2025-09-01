import json
import queue
import requests

from config import MODEL, OLLAMA_BASE_URL, TEMP

OLLAMA_URL = f"{OLLAMA_BASE_URL}/generate"

def stream_ollama(prompt: str, out_q: queue.Queue, model: str | None = None):
    model = model or MODEL
    try:
        with requests.post(
            OLLAMA_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "model": model,
                "prompt": prompt,
                "options": {"temperature": TEMP},
                "stream": True,
            }),
            stream=True,
            timeout=180,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    chunk = obj.get("response", "")
                except json.JSONDecodeError:
                    chunk = line
                if chunk:
                    out_q.put(chunk)
    except Exception as e:
        out_q.put(f"\n[Error] {e}\n")
    finally:
        out_q.put(None)
