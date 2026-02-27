import json
import os

import requests
import yaml
from hasher import compute_hash


def load_config():
    with open("docgen/config.yaml") as f:
        return yaml.safe_load(f)


_cache = None
_cache_dirty = False


def load_cache(cfg):
    global _cache
    if _cache is not None:
        return _cache
    path = cfg["cache"]["path"]
    if not os.path.exists(path):
        _cache = {}
    else:
        with open(path) as f:
            _cache = json.load(f)
    return _cache


def save_cache(cfg, cache):
    path = cfg["cache"]["path"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(cache, f, indent=2)


def call_model(prompt, cfg=None):
    if cfg is None:
        cfg = load_config()
    url = cfg["model"]["base_url"] + "/chat/completions"

    payload = {
        "model": cfg["model"]["model_name"],
        "temperature": cfg["model"]["temperature"],
        "messages": [
            {"role": "system", "content": "You are a senior backend architect."},
            {"role": "user", "content": prompt},
        ],
    }

    headers = {"Authorization": f"Bearer {cfg['model']['api_key']}"}

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=1000000)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Model request failed: {e}")
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected model response format: {r.text[:200]}")


def summarize_chunk(path, content, cfg=None):
    if cfg is None:
        cfg = load_config()

    file_hash = compute_hash(content)
    cache_key = f"{path}:{file_hash}"

    if cfg["cache"]["enabled"]:
        cache = load_cache(cfg)
        if cache_key in cache:
            print(f"[CACHE HIT] {path}")
            return cache[cache_key]

    print(f"[PROCESSING] {path}")

    prompt = f"""You are documenting a software project for other developers.
Analyze the following source file chunk and produce a concise technical summary.

Write in clear, professional English. Use plain prose — avoid filler phrases like "this file contains" or "it is responsible for".
Go straight to the point. Be specific: name the actual classes, functions, and modules involved.

Cover these aspects in order:
1. **Purpose** — What problem does this file solve? What is its role in the system?
2. **Key components** — List the main classes and functions with a one-line description of each.
3. **Dependencies** — What does this file import or rely on (internal modules, external libraries)?
4. **Interactions** — How does this file connect to the rest of the codebase (called by, calls into, data it produces or consumes)?

Keep the summary under 200 words. Do not repeat the file path in your answer.

--- FILE: {path} ---

{content}
"""

    summary = call_model(prompt, cfg)

    if cfg["cache"]["enabled"]:
        cache = load_cache(cfg)
        cache[cache_key] = summary
        save_cache(cfg, cache)

    return summary
