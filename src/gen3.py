"""Build data/posts.json for the site.

python3 gen3.py wall-2026.json links-2026.jsonl archive-linked.json out/posts.json

wall-2026.json      2026 posts from the Mac archive (_служебное/posts.jsonl), photos with thumbs
links-2026.jsonl    the same posts re-read with links kept in the text as ⟦href|anchor⟧
archive-linked.json older posts that 2026 posts link to (shown as pages, not in the feed)
"""
import json, re, os, sys, html
from urllib.parse import unquote, urlparse, parse_qs

SRC, RICH, ARCH, OUT = sys.argv[1:5]
VIDS = sys.argv[5] if len(sys.argv) > 5 else ""
rows = json.load(open(SRC, encoding="utf-8"))
DEFAULT_VTITLE = re.compile(r"^\s*((clip|video) by\b|.*\.(mp4|mov|avi|mkv|3gp|webm)\s*$|(vid|img|mov|video)[_-]?\d|\S{30,}\s*$)", re.I)  # VK defaults and file names, not real headings
rich = {}
if os.path.exists(RICH):
    for l in open(RICH, encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            rich[r["post_id"].split("_")[1]] = r["rich"]
arch = json.load(open(ARCH, encoding="utf-8")) if os.path.exists(ARCH) else []
videos = {}
if VIDS and os.path.exists(VIDS):
    for l in open(VIDS, encoding="utf-8"):
        if l.strip():
            v = json.loads(l)
            videos[v["post_id"].split("_")[1]] = [
                {"id": x.get("id", ""), "cover": html.unescape(x.get("cover") or ""), "duration": x.get("duration") or "",
                 "title": "" if DEFAULT_VTITLE.match(x.get("title") or "") else (x.get("title") or ""),
                 "embed": html.unescape(x.get("embed") or "")} for x in v.get("videos", [])]
site_ids = {r["id"] for r in rows if r["text"].strip() or r["photos"] or rich.get(r["id"], "").strip() or videos.get(r["id"])} | {a["id"] for a in arch}

GREET = re.compile(r"^(доброе утро|доброго утра|добрый день|доброго дня|добрый вечер|доброго вечера|доброй ночи|спокойной ночи)\b", re.I)
TAGS_ONLY = re.compile(r"^(рубрик[аи]:\s*)?(#\S+[\s,]*)+$", re.I)
MARK = re.compile(r"⟦([^|⟧]+)\|([^⟧]*)⟧")
# VK mentions «@id837561370 (Patron-67 )» and «[id1|Имя]» read as noise on the site: keep the name, linked like VK does
MENTION = re.compile(r"(?<![\w.@])@((?:id|club|public)\d+|[A-Za-z][\w.]{2,})\s*\(([^)\n]+)\)|\[((?:id|club|public)\d+)\|([^\]\n]+)\]")
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


LEAD_TAGS = ("нампишут", "слухи", "ретро", "фото", "несмоленское", "официальныйответ", "обещание", "проверка")
LEAD = re.compile(r"^\s*#([\wё]+)[\s:.—–-]*", re.I)


def strip_lead(s):
    """Drop rubric-only hashtags at the start of a title: «#намПишут Таганрогский трамвай» -> «Таганрогский трамвай»."""
    while True:
        m = LEAD.match(s)
        if not m or m.group(1).lower() not in LEAD_TAGS:
            return s
        rest = s[m.end():]
        if not rest or not rest[0].isupper():  # «#намПишут смоляне, что…» reads as a sentence: keep it
            return s
        s = rest


def plain(s):
    s = MARK.sub(lambda m: m.group(2), s)
    s = strip_lead(s.strip())
    s = re.sub(r"\(?https?://\S+\)?", "", s.replace("\n", " "))
    s = re.sub(r"#([\wё]+)", untag, s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s[:1].upper() + s[1:]


def short(s, n=110):
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0].rstrip(",;:—-")
    return cut + "…"


def resolve(href):
    """Turn a VK href into a site link (#pN) or an absolute external URL."""
    if href.startswith("/away.php"):
        q = parse_qs(urlparse(href).query)
        href = unquote(q.get("to", [href])[0])
    m = re.search(r"wall-102293762_(\d+)", href)
    if m and m.group(1) in site_ids and not re.search(r"[?&](reply|thread)=", href):  # a link to a comment stays on VK
        return "#p" + m.group(1)
    if href.startswith("/"):
        href = "https://vk.ru" + href
    return re.sub(r"^https?://(m\.)?vk\.com", "https://vk.ru", href)


def unmention(m):
    ref, name = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
    return f"⟦https://vk.ru/{ref}|{name.strip()}⟧"


def build(r, text, archive):
    text = MENTION.sub(unmention, text.replace("\r", "").strip())
    text = MARK.sub(lambda m: f"⟦{resolve(m.group(1))}|{m.group(2)}⟧", text)
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if paras:
        first, *rest = paras[0].split("\n", 1)
        if GREET.match(first) and len(first) < 60:
            paras = ([rest[0].strip()] if rest and rest[0].strip() else []) + paras[1:]
    paras = [p for p in paras if not TAGS_ONLY.match(MARK.sub(lambda m: m.group(2), p).strip())]
    tags = []
    for h in r.get("hashtags", []):
        if h.lower() not in [t.lower() for t in tags]:
            tags.append(h)
    flat = MARK.sub(lambda m: m.group(2), " ".join(paras))
    vids = videos.get(r["id"], [])
    nofeed = False
    if not paras and vids:
        title, body = vids[0]["title"] or "Видео", paras
        nofeed = not vids[0]["title"]  # a bare video with no words reads as noise in the feed
    elif not paras or (len(flat) < 70 and re.search(r"#фото", flat, re.I)):
        title, body = "Фото дня", paras
    else:
        p0 = paras[0]
        if len(plain(p0)) <= 110 and "\n" not in p0 and len(paras) > 1:
            title, body = plain(p0).rstrip("."), paras[1:]
        else:
            sent = re.split(r"(?<=[.!?…])\s+", p0)[0]
            title, body = short(plain(sent)).rstrip("."), paras
    links = []
    if r["id"] not in rich:  # no inline links known: keep the archive's list
        for h in r.get("links", []):
            href = resolve(h)
            if href != "#p" + r["id"] and href not in [x["href"] for x in links]:
                links.append({"href": href, "label": re.sub(r"^https?://(www\.)?", "", href).rstrip("/")})
    o = {"id": r["id"], "date": r["date"][:10], "time": r["date"][11:16],
         "url": "https://vk.ru/wall-102293762_" + r["id"], "title": title, "body": body, "tags": tags, "links": links,
         "photos": [{"full": ph["full"], "thumb": ph.get("thumb") and "thumbs/" + os.path.basename(ph["thumb"]).lstrip("-")}
                    for ph in r["photos"]]}
    if vids:
        o["videos"] = vids
    if archive:
        o["archive"] = True
    if nofeed:
        o["nofeed"] = True
    return o


out, skipped = [], []
for r in sorted(rows, key=lambda x: x["date"], reverse=True):
    if not r["text"].strip() and not r["photos"] and not rich.get(r["id"], "").strip() and not videos.get(r["id"]):
        skipped.append(r["id"]); continue
    out.append(build(r, rich.get(r["id"], r["text"]), False))
for a in sorted(arch, key=lambda x: x["date"], reverse=True):
    out.append(build(a, a["text"], True))

# label internal links in the fallback lists with the post date
dates = {o["id"]: o["date"] for o in out}
for o in out:
    for l in o["links"]:
        if l["href"].startswith("#p"):
            d = dates[l["href"][2:]]
            l["label"] = "Наш пост от " + ".".join(reversed(d.split("-")))
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
inline = sum(len(MARK.findall(" ".join(o["body"]))) for o in out)
internal = sum(1 for o in out for m in MARK.findall(" ".join(o["body"])) if m[0].startswith("#p"))
print(f"{len(out)} posts ({len(arch)} from the archive); {len(skipped)} skipped; inline links {inline}, to site pages {internal}; "
      f"{os.path.getsize(OUT) // 1024} KB")
