import json, re, os, sys
from urllib.parse import unquote, urlparse, parse_qs

SRC = sys.argv[1]          # wall-2026.json from the Mac archive
OUT = sys.argv[2]          # data/posts.json for the site
rows = json.load(open(SRC, encoding="utf-8"))
ids = {r["id"] for r in rows}

GREET = re.compile(r"^(доброе утро|доброго утра|добрый день|доброго дня|добрый вечер|доброго вечера|доброй ночи|спокойной ночи)\b", re.I)
TAGS_ONLY = re.compile(r"^(рубрик[аи]:\s*)?(#\S+[\s,]*)+$", re.I)
KEEP_CASE = ("улица", "проспект", "площадь", "переулок", "шоссе")


ABBR = {"улица": "ул.", "проспект": "пр."}


def untag(m):
    w = m.group(1)
    w = re.sub(r"(?<=[^\d\s])(?=\d)", " ", w)
    parts = re.split(r"(?<=[а-яёa-z])(?=[А-ЯЁA-Z])", w)
    head = parts[0].lower()
    if len(parts) > 1 and head not in KEEP_CASE:
        parts = [parts[0]] + [p if p.isupper() else p.lower() for p in parts[1:]]
    if head in ABBR and len(parts) > 1:
        parts[0] = ABBR[head]
    elif m.start() > 0 and not parts[0].isupper():
        parts[0] = parts[0].lower()
    return " ".join(parts)


def plain(s):
    s = re.sub(r"\(?https?://\S+\)?", "", s.replace("\n", " "))
    s = re.sub(r"#([\wё]+)", untag, s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s[:1].upper() + s[1:]


def short(s, n=110):
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0].rstrip(",;:—-")
    return cut + "…"


def link(href):
    if href.startswith("/away.php"):
        q = parse_qs(urlparse(href).query)
        href = unquote(q.get("to", [href])[0])
    m = re.search(r"wall-102293762_(\d+)", href)
    if m and m.group(1) in ids:
        return {"href": "#p" + m.group(1), "label": "Наш пост от " + "{d}", "pid": m.group(1)}
    if href.startswith("/"):
        href = "https://vk.ru" + href
    return {"href": href, "label": re.sub(r"^https?://(www\.)?", "", href).rstrip("/")}


out, skipped = [], []
for r in sorted(rows, key=lambda x: x["date"], reverse=True):
    text = r["text"].replace("\r", "").strip()
    if not text and not r["photos"]:
        skipped.append(r["id"]); continue
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if paras:
        first, *rest = paras[0].split("\n", 1)
        if GREET.match(first) and len(first) < 60:
            paras = ([rest[0].strip()] if rest and rest[0].strip() else []) + paras[1:]
    paras = [p for p in paras if not TAGS_ONLY.match(p.strip())]
    tags = []
    for h in r["hashtags"]:
        if h.lower() not in [t.lower() for t in tags]:
            tags.append(h)
    if not paras or (len(" ".join(paras)) < 70 and re.search(r"#фото", " ".join(paras), re.I)):
        title, body = "Фото дня", paras
    else:
        p0 = paras[0]
        if len(p0) <= 110 and "\n" not in p0 and len(paras) > 1:
            title, body = plain(p0).rstrip("."), paras[1:]
        else:
            sent = re.split(r"(?<=[.!?…])\s+", p0)[0]
            title, body = short(plain(sent)).rstrip("."), paras
    links = []
    for h in r.get("links", []):
        l = link(h)
        if l["href"] not in [x["href"] for x in links] and l.get("pid") != r["id"]:
            links.append(l)
    out.append({
        "id": r["id"], "date": r["date"][:10], "time": r["date"][11:16], "url": r["url"].replace("vk.com", "vk.ru"),
        "title": title, "body": body, "tags": tags, "links": links,
        "photos": [{"full": ph["full"], "thumb": ph["thumb"] and "thumbs/" + os.path.basename(ph["thumb"]).lstrip("-")} for ph in r["photos"]],
    })

dates = {o["id"]: o["date"] for o in out}
for o in out:
    for l in o["links"]:
        if l.get("pid"):
            d = dates.get(l["pid"], "")
            l["label"] = "Наш пост от " + ".".join(reversed(d.split("-"))) if d else "Наш пост"
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(len(out), "posts;", len(skipped), "skipped without text and photos;", os.path.getsize(OUT) // 1024, "KB")
for o in out[:12]:
    print(o["date"], "|", o["title"])
