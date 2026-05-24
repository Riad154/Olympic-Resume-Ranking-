"""
ollama_proxy.py — Reverse proxy for Ollama
Rewrites Host header to localhost so Ollama accepts tunneled requests.
Handles both regular and streaming responses (for /api/chat).

Usage:
    python ollama_proxy.py
    Then tunnel port 8080 instead of 11434.
"""
import http.server
import urllib.request
import urllib.error
import sys
import threading

OLLAMA = "http://localhost:11434"
PROXY_PORT = 8080


class OllamaProxy(http.server.BaseHTTPRequestHandler):
    """Forward every request to Ollama with Host: localhost."""

    def do_GET(self):
        self._proxy()

    def do_POST(self):
        self._proxy()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def _proxy(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        url = f"{OLLAMA}{self.path}"
        req = urllib.request.Request(url, data=body, method=self.command)
        req.add_header("Host", "localhost:11434")
        ct = self.headers.get("Content-Type")
        if ct:
            req.add_header("Content-Type", ct)

        try:
            resp = urllib.request.urlopen(req, timeout=300)
            self.send_response(resp.status)
            for key, val in resp.getheaders():
                if key.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(key, val)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            # Stream the response in chunks
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
            resp.close()
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"Proxy error: {e}".encode())

    def log_message(self, fmt, *args):
        sys.stdout.write(f"[proxy] {args[0]} {args[1]} {args[2]}\n")


def main():
    server = http.server.HTTPServer(("0.0.0.0", PROXY_PORT), OllamaProxy)
    print(f"=== Ollama Proxy running on http://0.0.0.0:{PROXY_PORT} ===")
    print(f"=== Forwarding to {OLLAMA} with Host: localhost ===")
    print(f"=== Tunnel THIS port ({PROXY_PORT}) instead of 11434 ===")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProxy stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
