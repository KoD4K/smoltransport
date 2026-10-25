#!/usr/bin/env python3
"""Search over all posts of smoltransport.ru.

GET /api/search?q=<words>&tag=<rubric>&from=YYYY-MM-DD&to=YYYY-MM-DD returns {"hits": [[id, year], ...]}, newest
first: feed posts whose title, text or rubrics hold every word of q (case and ё/е ignored), with the rubric and
inside the dates when those are given. Posts come from data/m/<YYYY-MM>.json and are re-read when the site data
is updated. Nothing about readers is kept: no cookies, no addresses, no log.
"""
import glob, json, os, re, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

DATA = os.environ.get("DATA_DIR", "/var/www/smoltransport/data")
MARK = re.compile(r"⟦([^|⟧]+)\|([^⟧]*)⟧")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
lock = threading.Lock()
posts, stamp, cache, warned = [], None, {}, set()


def norm(s):
    return s.lower().replace("ё", "е")


def read_month(f):
    """(id, year, date, rubrics, text) of the feed posts in one month file."""
    out = []
    with open(f, encoding="utf-8") as fh:
        for p in json.load(fh):
            if p.get("archive") or p.get("nofeed"):
                continue
            tags = {norm(t.lstrip("#")) for t in p.get("tags") or []}
            text = norm(" ".join([p.get("title") or "", *(MARK.sub(r"\2", b) for b in p.get("body") or []),
                                  *(p.get("tags") or [])]))
            out.append((p["id"], int(p["date"][:4]), p["date"], tags, text))
    return out


def load():
    """Feed posts of all months, newest month first; a month is re-read when its file changes. A month that can't be
    read right now (being replaced, or broken) keeps its previous copy, is named in the journal and is tried again on
    the next search; the other months still answer, so one bad file no longer empties the whole search."""
    global posts, stamp
    files = sorted(glob.glob(os.path.join(DATA, "m", "*.json")), reverse=True)
    now = []
    for f in files:
        try:
            now.append((f, os.path.getmtime(f)))
        except OSError:
            pass
    now = tuple(now)
    with lock:
        if now != stamp:
            fresh, failed = [], False
            for f, mtime in now:
                old = cache.get(f)
                if not old or old[0] != mtime:
                    try:
                        cache[f] = (mtime, read_month(f))
                    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
                        if (f, mtime) not in warned:  # once per file version, not on every search
                            warned.add((f, mtime))
                            print(f"search: {os.path.basename(f)} not read: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
                        failed = True
                        if not old:
                            continue
                fresh.extend(cache[f][1])
            for f in set(cache) - {f for f, _ in now}:
                del cache[f]
            if not failed or len(fresh) != len(posts):
                print(f"search: {len(fresh)} posts from {len(now)} month files", file=sys.stderr, flush=True)
            posts, stamp = fresh, (None if failed else now)
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
