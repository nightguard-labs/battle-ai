#!/usr/bin/env python3
"""Small Ollama-compatible /api/chat server for any local MLX model (11/17: 4-bit 9B and Qwen3.8-27B races).

Usage: mlx-venv/bin/python plain_server.py <model_dir> <port> <name>
Listens on 127.0.0.1 only. One request at a time. Speaks just what TeTi's LocalChatClient sends:
POST /api/chat {model, stream:false, think, messages, options:{num_predict, temperature}} -> {message:{content}}
Also GET /api/tags. Logs one line per chat with tokens/s, like the MTP server.
"""
import json, os, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mlx_lm import load, stream_generate
from mlx_lm.sample_utils import make_sampler

MODEL_DIR, PORT, NAME = sys.argv[1], int(sys.argv[2]), sys.argv[3]
IDLE = int(sys.argv[4]) if len(sys.argv) > 4 else 0   # seconds idle before exiting to free RAM (0 = never)
last = [time.time()]
model, tok = load(MODEL_DIR)
lock = threading.Lock()
if IDLE:
    def reaper():
        while True:
            time.sleep(15)
            if not lock.locked() and time.time() - last[0] > IDLE:
                print(f"{time.strftime('%F %T')} idle {IDLE}s, exiting to free RAM", flush=True); os._exit(0)
    threading.Thread(target=reaper, daemon=True).start()
print(f"{time.strftime('%F %T')} ready: {NAME} on 127.0.0.1:{PORT}", flush=True)


def chat(body):
    msgs = body.get("messages", [])
    opts = body.get("options", {}) or {}
    think = bool(body.get("think", False))
    try:
        prompt = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, enable_thinking=think)
    except TypeError:
        prompt = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
    sampler = make_sampler(temp=float(opts.get("temperature", 0.3)))
    out, t0, n, ptoks = [], time.time(), 0, 0
    for r in stream_generate(model, tok, prompt, max_tokens=int(opts.get("num_predict", 2048)), sampler=sampler):
        out.append(r.text); n = r.generation_tokens; ptoks = r.prompt_tokens; gen_tps = r.generation_tps
    text = "".join(out)
    if "</think>" in text: text = text.split("</think>", 1)[1].lstrip()   # keep only the answer
    print(f"{time.strftime('%F %T')} chat: prompt {ptoks} tok, {n} out, {gen_tps if n else 0:.1f} tok/s, "
          f"{time.time()-t0:.1f} s total", flush=True)
    return text


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path == "/api/tags": self.send(200, {"models": [{"name": NAME, "model": NAME}]})
        else: self.send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/api/generate":   # Ollama-style unload: {"keep_alive": 0} -> exit and free the RAM
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if body.get("keep_alive") == 0 and not lock.locked():
                self.send(200, {"done": True}); os._exit(0)
            return self.send(200, {"done": True})
        if self.path != "/api/chat": return self.send(404, {"error": "not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            with lock: text = chat(body); last[0] = time.time()
            self.send(200, {"model": NAME, "message": {"role": "assistant", "content": text}, "done": True})
        except BrokenPipeError: pass
        except Exception as e: self.send(500, {"error": str(e)})


ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
