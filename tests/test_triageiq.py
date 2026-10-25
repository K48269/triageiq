"""Offline tests: a fake Ollama server returns different answers depending on the log content,
so we verify the pipeline wiring (redaction, parsing, store, rendering, server) end to end."""
import json, os, tempfile, threading, unittest, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from triageiq import classify, config, redact, server
from triageiq.pipeline import triage

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")
SEEN_PROMPTS = []

class FakeOllama(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        user = body["messages"][1]["content"]
        SEEN_PROMPTS.append(user)
        if "INSUFFICIENT_ACCESS" in user:
            ans = {"category": "missing_permission", "reason": "svc-deploy lacks a permission set.",
                   "evidence": "INSUFFICIENT_ACCESS_OR_READONLY: insufficient access rights on object id", "confidence": 0.9}
            raw = json.dumps(ans)
        elif "AssertException" in user:
            raw = 'Sure! {"category": "test_failure", "reason": "A discount test failed.", "evidence": "System.AssertException: Assertion Failed", "confidence": 0.95}'
        else:
            raw = "not json at all"
        out = json.dumps({"message": {"content": raw}}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)
    def log_message(self, *a): pass

class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls): cls.srv.shutdown()
    def cfg(self):
        c = config.Config(); c.ollama_url = f"http://127.0.0.1:{self.srv.server_port}"
        c.db_path = os.path.join(tempfile.mkdtemp(), "t.db"); return c

    def read(self, n): return open(os.path.join(SAMPLES, n)).read()

    def test_two_different_failures_classified_differently(self):
        c = self.cfg()
        a = triage(c, {"run_id": "r1", "pipeline": "p"}, self.read("01_failing_test.log"), quiet=True)
        b = triage(c, {"run_id": "r2", "pipeline": "p"}, self.read("02_permission_issue.log"), quiet=True)
        self.assertEqual(a["diagnosis"]["category"], "test_failure")
        self.assertEqual(b["diagnosis"]["category"], "missing_permission")
        self.assertIn("agentia cicd run retry --run r1", a["commands"]["retry"])

    def test_repeat_detection(self):
        c = self.cfg(); log = self.read("02_permission_issue.log")
        triage(c, {"run_id": "r1", "pipeline": "p"}, log, quiet=True)
        r = triage(c, {"run_id": "r2", "pipeline": "p"}, log, quiet=True)
        self.assertEqual(r["history"]["seen_before"], 1)
        self.assertIn("Seen 1 time(s) before", r["message"])

    def test_garbage_model_output_degrades_safely(self):
        d = classify.parse("not json at all")
        self.assertEqual(d.category, "other"); self.assertLess(d.confidence, 0.5)
        self.assertEqual(classify.parse('{"category":"rm -rf /"}').category, "other")

    def test_redaction_before_llm(self):
        SEEN_PROMPTS.clear()
        triage(self.cfg(), {"run_id": "r"}, "ERROR token=abc123SECRET and mail bob@corp.com INSUFFICIENT_ACCESS", quiet=True)
        self.assertNotIn("abc123SECRET", SEEN_PROMPTS[0]); self.assertNotIn("bob@corp.com", SEEN_PROMPTS[0])

    def test_condense_keeps_errors(self):
        log = "\n".join(["info line"] * 2000 + ["FATAL error: boom"] + ["info line"] * 2000)
        self.assertIn("boom", classify.condense(log, 500))

    def test_webhook_server(self):
        c = self.cfg(); c.shared_secret = "s"
        from http.server import ThreadingHTTPServer
        s = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(c))
        threading.Thread(target=s.serve_forever, daemon=True).start()
        def post(payload, tok):
            req = urllib.request.Request(f"http://127.0.0.1:{s.server_port}/events", json.dumps(payload).encode(),
                                         {"Content-Type": "application/json", "X-TriageIQ-Token": tok})
            try: return json.load(urllib.request.urlopen(req))
            except urllib.error.HTTPError as e: return {"http": e.code}
        self.assertEqual(post({"status": "failed", "run_id": "x"}, "bad"), {"http": 401})
        self.assertIn("skipped", post({"status": "succeeded", "run_id": "x"}, "s"))
        r = post({"status": "failed", "run_id": "x", "pipeline": "p", "logs": self.read("01_failing_test.log")}, "s")
        self.assertEqual(r["diagnosis"]["category"], "test_failure")
        s.shutdown()

if __name__ == "__main__":
    unittest.main()
