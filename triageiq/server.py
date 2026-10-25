"""Event receiver: point your CI's failure webhook at POST /events."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .pipeline import triage

FAILED = {"failed", "failure", "error", "errored", "cancelled_by_error"}

def make_handler(cfg):
    class H(BaseHTTPRequestHandler):
        def _reply(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            self._reply(200, {"status": "ok"}) if self.path == "/health" else self._reply(404, {})

        def do_POST(self):
            if self.path != "/events":
                return self._reply(404, {})
            if cfg.shared_secret and self.headers.get("X-TriageIQ-Token") != cfg.shared_secret:
                return self._reply(401, {"error": "bad token"})
            try:
                ev = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            except json.JSONDecodeError:
                return self._reply(400, {"error": "invalid JSON"})
            if str(ev.get("status", "failed")).lower() not in FAILED:
                return self._reply(200, {"skipped": f"status={ev.get('status')}"})
            if not ev.get("run_id") and not ev.get("logs"):
                return self._reply(400, {"error": "need run_id (or inline logs)"})
            ctx = {k: ev.get(k, "") for k in ("run_id", "pipeline", "environment", "stage")}
            try:
                res = triage(cfg, ctx, log_text=ev.get("logs"), quiet=True)
            except Exception as e:
                return self._reply(502, {"error": str(e)})
            self._reply(200, res)

        def log_message(self, *a):
            pass
    return H

def serve(cfg):
    print(f"TriageIQ listening on http://{cfg.listen_host}:{cfg.listen_port}/events")
    ThreadingHTTPServer((cfg.listen_host, cfg.listen_port), make_handler(cfg)).serve_forever()
