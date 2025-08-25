import json
import queue
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:14b"
TEMP = 0.2


def stream_ollama(prompt: str, out_q: queue.Queue):
    try:
        with requests.post(
            OLLAMA_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "model": MODEL,
                "prompt": prompt,
                "options": {"temperature": TEMP},
                "stream": True
            }),
            stream=True, timeout=180,
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
