#!/usr/bin/env python3
"""Search over all posts of smoltransport.ru.

GET /api/search?q=<words>&tag=<rubric>&from=YYYY-MM-DD&to=YYYY-MM-DD returns {"hits": [[id, year], ...]}, newest
first: feed posts whose title, text or rubrics hold every word of q (case and ё/е ignored), with the rubric and
inside the dates when those are given. Posts come from data/m/<YYYY-MM>.json and are re-read when the site data
is updated. Nothing about readers is kept: no cookies, no addresses, no log.
"""
import glob, json, os, re, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

DATA = os.environ.get("DATA_DIR", "/var/www/smoltransport/data")
MARK = re.compile(r"⟦([^|⟧]+)\|([^⟧]*)⟧")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
lock = threading.Lock()
posts, stamp = [], None


def norm(s):
    return s.lower().replace("ё", "е")


def load():
    """(id, year, date, rubrics, text) of every feed post, newest month first; re-read when a month file changes."""
    global posts, stamp
    files = sorted(glob.glob(os.path.join(DATA, "m", "*.json")), reverse=True)
    try:
        now = tuple((f, os.path.getmtime(f)) for f in files)
    except OSError:
        return posts
    with lock:
        if now != stamp:
            fresh = []
            try:
                for f in files:
                    with open(f, encoding="utf-8") as fh:
                        for p in json.load(fh):
                            if p.get("archive") or p.get("nofeed"):
                                continue
                            tags = {norm(t.lstrip("#")) for t in p["tags"]}
                            text = norm(" ".join([p["title"], *(MARK.sub(r"\2", b) for b in p["body"]), *p["tags"]]))
                            fresh.append((p["id"], int(p["date"][:4]), p["date"], tags, text))
            except (OSError, ValueError, KeyError, TypeError):
                return posts  # a file is being replaced right now: answer from the previous copy
            posts, stamp = fresh, now
    return posts


def find(q, tag, start, end):
    words = norm(q).split()[:10]
    tag = norm(tag.lstrip("#"))
    return [[pid, year] for pid, year, date, tags, text in load()
            if (not tag or tag in tags) and (not start or date >= start) and (not end or date <= end)
            and all(w in text for w in words)]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlsplit(self.path)
        if url.path.rstrip("/") != "/api/search":
            return self.send(404, {"error": "not found"})
        args = {k: v[0] for k, v in parse_qs(url.query).items()}
        q, tag = args.get("q", "")[:200], args.get("tag", "")[:60]
        start, end = (args.get(k, "") for k in ("from", "to"))
        if any(d and not DAY.match(d) for d in (start, end)) or not (q.strip() or tag or start or end):
            return self.send(400, {"error": "bad query"})
        self.send(200, {"hits": find(q, tag, start, end)})

    def send(self, code, body):
        data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # no request log: it would hold readers' addresses and what they searched for
        pass


if __name__ == "__main__":
    load()
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("PORT", "8091"))), Handler).serve_forever()
