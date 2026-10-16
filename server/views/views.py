#!/usr/bin/env python3
"""Post view counter for smoltransport.ru.

POST /api/views/<id> adds a view and returns {"id", "views"}; GET returns the count without adding.
Only ids of posts on the site are counted (data/index/<year>.json, or data/posts.json in the old layout). Nothing about the reader is stored: no cookies, no
addresses, no log. The page itself skips the POST when this browser already opened the post today.
"""
import glob, json, os, re, sqlite3, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB = os.path.join(os.environ.get("STATE_DIRECTORY", "/var/lib/smoltransport-views"), "views.sqlite")
DATA = os.environ.get("DATA_DIR", "/var/www/smoltransport/data")
PATH = re.compile(r"^/api/views/(\d{1,12})/?$")
BOTS = re.compile(r"bot|crawl|spider|slurp|preview|fetch|curl|wget|python|java/|go-http|headless|lighthouse", re.I)

db = sqlite3.connect(DB, check_same_thread=False, isolation_level=None)
db.execute("CREATE TABLE IF NOT EXISTS views (post_id TEXT PRIMARY KEY, n INTEGER NOT NULL DEFAULT 0)")
lock = threading.Lock()
known, known_mtime = set(), None


def known_ids():
    """Post ids of the site, re-read whenever the site data is updated."""
    global known, known_mtime
    files = [f for f in glob.glob(os.path.join(DATA, "index", "*.json")) if not f.endswith("meta.json")]
    try:
        if not files:  # old layout: one posts.json
            files = [os.path.join(DATA, "posts.json")]
        m = tuple(os.path.getmtime(f) for f in files)
        if m != known_mtime:
            ids = set()
            for f in files:
                with open(f, encoding="utf-8") as fh:
                    ids |= {str(p["id"]) for p in json.load(fh)}
            known, known_mtime = ids, m
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return known


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def answer(self, add):
        m = PATH.match(self.path.split("?", 1)[0])
        if not m or m.group(1) not in known_ids():
            return self.send(404, {"error": "unknown post"})
        pid = m.group(1)
        with lock:
            if add and not BOTS.search(self.headers.get("User-Agent", "")):
                db.execute("INSERT INTO views (post_id, n) VALUES (?, 1) ON CONFLICT(post_id) DO UPDATE SET n = n + 1", (pid,))
            row = db.execute("SELECT n FROM views WHERE post_id = ?", (pid,)).fetchone()
        self.send(200, {"id": pid, "views": row[0] if row else 0})

    def do_GET(self):
        self.answer(False)

    def do_POST(self):
        self.answer(True)

    def log_message(self, *args):  # no request log: it would hold readers' addresses
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("PORT", "8090"))), Handler).serve_forever()
