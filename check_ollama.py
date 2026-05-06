"""
check_ollama.py — Validate Ollama + GPU setup before ranking.

Run standalone:
    python check_ollama.py

Or import and call `run_checks(host, model)` from ranker.py.
Returns True if Ollama is reachable and the required model is available.
"""

from __future__ import annotations

import os
import sys
import time
import json
import requests


DEFAULT_HOST  = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b-q4_K_M")


def _check_env_vars() -> None:
    par = os.environ.get("OLLAMA_NUM_PARALLEL")
    if not par:
        print("[HINT] OLLAMA_NUM_PARALLEL is not set.")
        print("       Set it to allow concurrent request processing:")
        print("       Windows: setx OLLAMA_NUM_PARALLEL 5  (then restart Ollama)")
    else:
        print(f"[ENV]  OLLAMA_NUM_PARALLEL={par}")

    mlm = os.environ.get("OLLAMA_MAX_LOADED_MODELS")
    if not mlm:
        print("[HINT] OLLAMA_MAX_LOADED_MODELS is not set.")
        print("       Recommend setting it to 1 (we use a single model):")
        print("       Windows: setx OLLAMA_MAX_LOADED_MODELS 1  (then restart Ollama)")
    else:
        print(f"[ENV]  OLLAMA_MAX_LOADED_MODELS={mlm}")


def _tags(host: str) -> list[dict]:
    r = requests.get(f"{host}/api/tags", timeout=10)
    r.raise_for_status()
    return r.json().get("models", []) or []


def _ps(host: str) -> list[dict]:
    try:
        r = requests.get(f"{host}/api/ps", timeout=10)
        r.raise_for_status()
        return r.json().get("models", []) or []
    except Exception:
        return []


def _latency_probe(host: str, model: str) -> float:
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "user", "content": "/no_think\nSay OK"},
        ],
        "options": {"num_predict": 8},
    }
    t0 = time.time()
    r = requests.post(f"{host}/api/chat", json=payload, timeout=120)
    r.raise_for_status()
    _ = r.json()
    return time.time() - t0


def run_checks(host: str = DEFAULT_HOST, model: str = DEFAULT_MODEL) -> bool:
    print(f"[Ollama] Pre-flight check against {host} (model={model})")

    # 1. reachability / tags
    try:
        models = _tags(host)
    except Exception as e:
        print(f"[FAIL] Cannot reach Ollama at {host}: {e}")
        print("       Is `ollama serve` running? Windows tray icon should be visible.")
        return False
    names = [m.get("name") for m in models]
    print(f"[OK]   Ollama reachable. {len(names)} model(s) installed.")

    # 2. model available
    if model not in names:
        print(f"[FAIL] Model '{model}' not found. Available: {names}")
        print(f"       Run: ollama pull {model}")
        return False
    print(f"[OK]   Model '{model}' is installed.")

    # 3. latency probe
    try:
        secs = _latency_probe(host, model)
        print(f"[OK]   Ollama response time: {secs:.2f}s")
    except Exception as e:
        print(f"[WARN] Latency probe failed: {e}")

    # 4. GPU residency via /api/ps
    ps = _ps(host)
    if ps:
        for m in ps:
            name = m.get("name", "?")
            size_vram = m.get("size_vram", 0) or 0
            size_tot  = m.get("size", 0) or 0
            if size_tot and size_vram:
                vram_pct = 100.0 * size_vram / size_tot
                print(f"[PS]   {name}: VRAM {size_vram/1e9:.1f}/{size_tot/1e9:.1f} GB ({vram_pct:.0f}% on GPU)")
                if vram_pct < 95:
                    print(f"[WARN] {name} is partially offloaded to CPU — inference will be slow.")
                    print( "       Close other GPU apps or use a smaller quant.")
            else:
                print(f"[PS]   {name}: {json.dumps(m)[:200]}")
    else:
        print("[PS]   No running models reported by /api/ps (model may load lazily).")

    # 5. env var hints
    _check_env_vars()

    return True


def main():
    host  = os.environ.get("OLLAMA_HOST", DEFAULT_HOST)
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
    ok = run_checks(host, model)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
