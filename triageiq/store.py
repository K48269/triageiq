"""SQLite failure history + repeat-failure detection."""
import hashlib, re, sqlite3, time

SCHEMA = """CREATE TABLE IF NOT EXISTS failures(
 id INTEGER PRIMARY KEY, ts REAL, run_id TEXT, pipeline TEXT, category TEXT,
 reason TEXT, evidence TEXT, confidence REAL, signature TEXT)"""

def signature(category: str, evidence: str) -> str:
    norm = re.sub(r"\d+", "#", evidence.lower())
    norm = re.sub(r"\s+", " ", norm).strip()
    return hashlib.sha1(f"{category}|{norm}".encode()).hexdigest()[:12]

class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.execute(SCHEMA)

    def record(self, ctx: dict, d) -> dict:
        sig = signature(d.category, d.evidence)
        prior = self.db.execute("SELECT COUNT(*), MAX(ts) FROM failures WHERE signature=? AND pipeline=?",
                                (sig, ctx.get("pipeline", ""))).fetchone()
        self.db.execute("INSERT INTO failures(ts,run_id,pipeline,category,reason,evidence,confidence,signature) VALUES(?,?,?,?,?,?,?,?)",
                        (time.time(), ctx.get("run_id", ""), ctx.get("pipeline", ""), d.category,
                         d.reason, d.evidence, d.confidence, sig))
        self.db.commit()
        return {"seen_before": prior[0], "last_seen": prior[1], "signature": sig}

    def recent(self, n=20):
        return self.db.execute("SELECT datetime(ts,'unixepoch'),run_id,pipeline,category,reason FROM failures ORDER BY id DESC LIMIT ?", (n,)).fetchall()
