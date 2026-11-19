import http.server, os, sys, threading
D=sys.argv[1]; os.chdir(D)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        if self.path.startswith("/hold"):
            import time
            for _ in range(60):
                if os.path.exists("audio.wav") and os.path.getsize("audio.wav") > 1000: break
                time.sleep(0.5)
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok"); return
        return super().do_GET()
    def do_POST(self):
        n=int(self.headers["Content-Length"]); open("audio.wav","wb").write(self.rfile.read(n))
        self.send_response(200); self.end_headers(); print("got audio", n, self.path[:600], flush=True)
http.server.ThreadingHTTPServer(("127.0.0.1",8791),H).serve_forever()
