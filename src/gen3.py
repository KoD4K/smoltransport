"""Build data/posts.json for the site.

python3 gen3.py wall-2026.json links-2026.jsonl archive-linked.json out/posts.json

wall-2026.json      2026 posts from the Mac archive (_служебное/posts.jsonl), photos with thumbs
links-2026.jsonl    the same posts re-read with links kept in the text as ⟦href|anchor⟧
archive-linked.json older posts that 2026 posts link to (shown as pages, not in the feed)
videos.jsonl        optional: the posts' videos
covers.json         optional: {post id: {"full", "thumb"}} feed pictures without text, made on the Mac from
                    a post folder's превью-сайта.jpg, so a carousel's headline cover doesn't repeat the title.
                    Older carousels have theirs in site/media/covers/<id>-<hash>.jpg (and -t.jpg); covers.json wins.
vcovers.json        optional: {video id: path under thumbs/} video covers saved on our server, so readers' browsers
                    don't fetch them from VK's CDN.
reposts.json        optional: {post id: [{"full", "thumb", "w", "h"}], "_slugs": {slug: post id}} slides without the counter and chevrons, made on the
                    Mac from a post folder's для-перепоста/ (thumbs/repost/), shown in the post's «Для перепоста» block
                    (Evgenii 26.10.2026, new posts only). "_slugs" names each such post by its Mac folder, so a post can
                    link to smoltransport.ru/#s/<slug> before it is published (Evgenii 26.10: a link to the news, not the site).
"""
import json, re, os, sys, html
from urllib.parse import unquote, urlparse, parse_qs

SRC, RICH, ARCH, OUT = sys.argv[1:5]
VIDS = sys.argv[5] if len(sys.argv) > 5 else ""
COVERS = {}
_cov = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "media", "covers")
if os.path.isdir(_cov):
    for f in sorted(os.listdir(_cov)):
        m = re.match(r"^(\d+)-[0-9a-f]{8}\.jpg$", f)
        if m and os.path.exists(os.path.join(_cov, f[:-4] + "-t.jpg")):
            COVERS[m.group(1)] = {"full": "media/covers/" + f, "thumb": "media/covers/" + f[:-4] + "-t.jpg"}
if len(sys.argv) > 6 and os.path.exists(sys.argv[6]):
    COVERS.update(json.load(open(sys.argv[6], encoding="utf-8")))
VCOVERS = json.load(open(sys.argv[7], encoding="utf-8")) if len(sys.argv) > 7 and os.path.exists(sys.argv[7]) else {}
REPOSTS = json.load(open(sys.argv[8], encoding="utf-8")) if len(sys.argv) > 8 and os.path.exists(sys.argv[8]) else {}
# "_slugs" {"<post folder slug>": "<id>"}: smoltransport.ru/#s/<slug> is written in a post before VK gives it an id
SLUGS = REPOSTS.pop("_slugs", {}) if isinstance(REPOSTS.get("_slugs"), dict) else {}
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
                {"id": x.get("id", ""), "cover": VCOVERS.get(x.get("id", "")) or html.unescape(x.get("cover") or ""), "duration": x.get("duration") or "",
                 "title": "" if DEFAULT_VTITLE.match(x.get("title") or "") else (x.get("title") or ""),
                 "embed": html.unescape(x.get("embed") or "")} for x in v.get("videos", [])]
HIDE = {}  # photos and videos kept off the 12+ site
_hide = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inputs", "hide-12plus.json")
if os.path.exists(_hide):
    HIDE = {k: v for k, v in json.load(open(_hide, encoding="utf-8")).items() if not k.startswith("_")}
# links that lead elsewhere on the site than on VK: {"<post id or Mac folder slug>": {"<href in the VK text>": "<site href>"}}
# (Evgenii 27.10: on VK a quote links to our post with it, on the site to the interview itself)
_sl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inputs", "site-links.json")
SITE_LINKS = {}
if os.path.exists(_sl):
    _slug_id = {k.lower(): str(v) for k, v in SLUGS.items()}
    SITE_LINKS = {_slug_id.get(k.lower(), k): v for k, v in json.load(open(_sl, encoding="utf-8")).items() if not k.startswith("_")}
rows = [r for r in rows if not HIDE.get(r["id"], {}).get("post")]  # whole posts not for 12+
arch = [a for a in arch if not HIDE.get(a["id"], {}).get("post")]
site_ids = {r["id"] for r in rows if r["text"].strip() or r["photos"] or rich.get(r["id"], "").strip() or videos.get(r["id"])} | {a["id"] for a in arch}

GREET = re.compile(r"^[\"«]?(доброе утро|доброго утра|добрый день|доброго дня|добрый вечер|доброго вечера|доброй ночи|спокойной ночи|"
                   r"здравствуйте|здравствуй|приветствую|привет|доброго времени суток)\b", re.I)
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


# old wall tags shown under one rubric: Evgenii asked for a purchases rubric on 23.10.2026, the group chose #закупка
# (the newest of the variants) and put the rest on the «Не ставим» list, but 2015–2025 posts still carry them
TAG_ALIAS = {"закупки": "закупка", "госзакупки": "закупка", "закупкимуттп": "закупка", "тендер": "закупка", "аукцион": "закупка",
             "платныепарковки": "платнаяПарковка", "платная_парковка": "платнаяПарковка"}  # old variants of #платнаяПарковка (Evgenii 28.10.2026)
LEAD_TAGS = ("нампишут", "слухи", "юмор", "ретро", "фото", "несмоленское", "официальныйответ", "обещание", "проверка", "платнаяпарковка")
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
    s = re.sub(r"^(?:upd|апд|обновлено)\b\s*[:.]?\s*", "", s, flags=re.I)  # «UPD: движение восстановлено» is still the news
    s = re.sub(r"\(?https?://\S+\)?", "", s.replace("\n", " "))
    s = re.sub(r"#([\wё]+)", untag, s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s[:1].upper() + s[1:]


HASHTAG = re.compile(r"(?<![\w&#/])#([A-Za-zА-Яа-яЁё][\wё]*)")
TAIL_TAGS = re.compile(r"(?:[ \t,]*(?<![\w&#/])#[A-Za-zА-Яа-яЁё][\wё]*)+[ \t,.]*$")


def detag(p):
    """The site shows rubrics under the post, so hashtags leave the text: a run of tags after the last
    sentence goes, a tag inside a sentence becomes a plain word («Автор #фото:» -> «Автор фото:»)."""
    p = MARK.sub(lambda m: m.group(2) if re.fullmatch(r"#[\wё]+", m.group(2).strip()) else m.group(0), p)
    p = re.sub(r"[ \t]*\n?[ \t]*Рубрик[аи]:[ \t]*(?:#[\wё]+[ \t,]*)+$", "", p, flags=re.I)
    tail = TAIL_TAGS.search(p)
    if tail and (len(HASHTAG.findall(tail.group(0))) > 1 or tail.start() == 0
                 or p[:tail.start()].rstrip()[-1:] in ".!?…»\")\n"):  # one tag right after a word is part of the sentence
        p = p[:tail.start()]
    out, last = "", 0
    for m in MARK.finditer(p):
        out += HASHTAG.sub(untag, p[last:m.start()]) + f"⟦{m.group(1)}|{HASHTAG.sub(untag, m.group(2))}⟧"
        last = m.end()
    out = (out + HASHTAG.sub(untag, p[last:])).strip()
    return out[:1].upper() + out[1:] if p.lstrip().startswith("#") else out


ABBR_DOT = re.compile(r"(?:\b(?:ул|пр|пер|мкр|пос|г|гг|д|им|мод|т\.е|т\.д|т\.п|др|см|стр|тыс|млн|млрд|руб|км|обл|наб|пл|ст|св|ок|напр|зам|нач|корп|кв|ед|рис|ср|вкл|совр)|(?<![\wё])[А-ЯЁA-Z])\.$", re.I)


def headline(s):
    """A sentence as a headline: no final period, unless it ends an abbreviation («2026 г.»)."""
    s = plain(s)
    s = s[:-1] if s.endswith(".") and not s.endswith("..") and not ABBR_DOT.search(s) else s
    if re.search(r'(?:^|[\s(])"[^"\s][^"]*$', s):  # «…троллейбуса "Горожанин»: the closing quote went with the rest
        s += '"'
    return s + "»" * (s.count("«") - s.count("»"))


def first_sentence(p):
    """(first sentence, rest) — never splits inside a link marker, after an abbreviation or an initial."""
    for m in re.finditer(r"(?<=[.!?…])\s+(?=[«\"(#]?[А-ЯЁA-Z0-9⟦#])|[ \t]*\n\s*(?=[«\"(]?[А-ЯЁA-Z0-9])", p):
        head = p[:m.start()]
        if head.count("⟦") != head.count("⟧") or ABBR_DOT.search(head) or head.rstrip().endswith(":"):
            continue
        return head, p[m.end():]
    return p, ""


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


# swear words are not for a 12+ site (436-ФЗ allows them from 16+): the word keeps its first letter, «г…»
SWEAR = re.compile(r"(?<![а-яё])(?:мудак|мудач|говн|жоп|рукожоп)[а-яё]*", re.I)
NUMBER_TAG = re.compile(r"(?<![\w&#/])#(\d+)")  # «трамвая #250» is a number, not a rubric
# «Картинки без надписей для перепоста: smoltransport.ru» sends VK readers here; the site shows the block itself
REPOST_LINE = re.compile(r"^\s*(?:картинки|изображения|слайды|фото)\b[^\n]{0,80}?\bдля\s+перепоста\b", re.I)


def build(r, text, archive):
    text = SWEAR.sub(lambda m: m.group(0)[0] + "…", text)
    text = NUMBER_TAG.sub("№\u00a0\\1", text)
    text = re.sub(r"(?<=[А-Яа-яЁё])#(\d+)", " №\u00a0\\1", text)  # «Маршрут#1»
    text = MENTION.sub(unmention, text.replace("\r", "").strip())
    over = {resolve(k): v for k, v in SITE_LINKS.get(r["id"], {}).items()}
    text = MARK.sub(lambda m: f"⟦{over.get(resolve(m.group(1)), resolve(m.group(1)))}|{m.group(2)}⟧", text)
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    paras = [q for q in ("\n".join(l for l in p.split("\n") if not REPOST_LINE.match(MARK.sub(lambda m: m.group(2), l))).strip()
                         for p in paras) if q]
    if paras:
        first, *rest = paras[0].split("\n", 1)
        if GREET.match(first) and len(first) < 60:
            paras = ([rest[0].strip()] if rest and rest[0].strip() else []) + paras[1:]
    paras = [p for p in paras if not TAGS_ONLY.match(MARK.sub(lambda m: m.group(2), p).strip())]
    tags = []
    for h in r.get("hashtags", []):
        k = h.lstrip("#").lower()
        if k in TAG_ALIAS:
            h = h[:len(h) - len(h.lstrip("#"))] + TAG_ALIAS[k]
        if h.lower() not in [t.lower() for t in tags]:
            tags.append(h)
    flat = MARK.sub(lambda m: m.group(2), " ".join(paras))
    vids = videos.get(r["id"], [])
    hide = HIDE.get(r["id"], {})
    if hide.get("videos") == "vk":
        vids = [dict(v, cover="", embed="", vk_only=True) for v in vids]
    nofeed, lede, dropped = False, None, ""
    if not paras and vids and not r["photos"]:  # a photo with a bare video is still a photo of the day
        title, body = vids[0]["title"] or "Видео", paras
        nofeed = not vids[0]["title"]  # a bare video with no words reads as noise in the feed
    elif not paras or (len(flat) < 70 and re.search(r"#фото", flat, re.I)):  # «Автор #фото: …» is a photo of the day
        title, body = "Фото дня", paras
    else:
        p0 = paras[0]
        sent, rest = first_sentence(p0)
        if rest.strip() and len(plain(sent)) < 40 and GREET.match(plain(sent)):  # «"Здравствуйте! Пишу вам…» — the letter starts after it
            p0 = rest.strip()
            paras = [p0] + paras[1:]
            sent, rest = first_sentence(p0)
        if len(plain(p0)) <= 110 and ("\n" not in p0 or not rest.strip()):
            title, body, dropped = headline(p0), paras[1:], p0  # a short first paragraph is the headline itself
        elif len(plain(sent)) <= 110:
            title, body, dropped = headline(sent), ([rest.strip()] if rest.strip() else []) + paras[1:], sent
        else:
            title, body = short(plain(sent)).rstrip("."), paras
            if title.endswith("…"):  # the feed shows the shortened headline, so its teaser starts after that sentence
                lede = detag(MARK.sub(lambda m: m.group(2), rest)).strip()
    body = [q for q in (detag(x) for x in body) if q.strip()]  # rubrics are shown under the post, not in the text
    links = [{"href": h, "label": a or h} for h, a in MARK.findall(dropped)]  # links of the sentence that became the headline
    if r["id"] not in rich:  # no inline links known: keep the archive's list
        for h in r.get("links", []):
            href = resolve(h)
            if href != "#p" + r["id"] and href not in [x["href"] for x in links]:
                links.append({"href": href, "label": re.sub(r"^https?://(www\.)?", "", href).rstrip("/")})
    o = {"id": r["id"], "date": r["date"][:10], "time": r["date"][11:16],
         "url": "https://vk.ru/wall-102293762_" + r["id"], "title": title, "body": body, "tags": tags, "links": links,
         "photos": [{"full": ph["full"], "thumb": ph.get("thumb") and "thumbs/" + os.path.basename(ph["thumb"]).lstrip("-")}
                    for k, ph in enumerate(r["photos"], 1) if k not in hide.get("photos", [])]}
    if vids:
        o["videos"] = vids
    if archive:
        o["archive"] = True
    if nofeed:
        o["nofeed"] = True
    if lede is not None:
        o["lede"] = lede
    if REPOSTS.get(r["id"]) and not archive:
        o["repost"] = REPOSTS[r["id"]]
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

# the same posts split for a site with all years (posts.json stays for old pages):
# data/index/meta.json (years, months with their id ranges, rubric counts), data/index/<year>.json (feed cards),
# data/m/<YYYY-MM>.json (full posts of a month, loaded when one of them opens; the search service reads these too)
DATA = os.path.dirname(os.path.abspath(OUT))


def card(o):
    lede = o["lede"] if "lede" in o else (MARK.sub(lambda m: m.group(2), o["body"][0]) if o["body"] else "")
    c = {"id": o["id"], "date": o["date"], "title": o["title"], "lede": short(lede, 240) if lede else "", "tags": o["tags"],
         "np": len(o["photos"])}
    cov = COVERS.get(o["id"])
    if cov and cov.get("full"):
        c["ph"] = {"full": cov["full"], "thumb": cov.get("thumb") or cov["full"]}
    elif o["photos"]:
        c["ph"] = o["photos"][0]
    if o.get("videos"):
        v = o["videos"][0]
        c["nv"], c["v"] = len(o["videos"]), {"cover": v.get("cover", ""), "duration": v.get("duration", "")}
    for k in ("nofeed", "archive"):
        if o.get(k):
            c[k] = True
    return c


def write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def bucket(key):
    groups = {}
    for o in out:
        groups.setdefault(key(o), []).append(o)
    return groups


feedable = lambda o: not o.get("archive") and not o.get("nofeed")
years, months = bucket(lambda o: o["date"][:4]), bucket(lambda o: o["date"][:7])
for sub, groups, fn in (("index", years, lambda ps: [card(o) for o in ps]), ("m", months, lambda ps: ps)):
    folder = os.path.join(DATA, sub)
    os.makedirs(folder, exist_ok=True)
    for name in os.listdir(folder):  # a year or month that has no posts any more
        if name.endswith(".json") and name != "meta.json" and name[:-5] not in groups:
            os.remove(os.path.join(folder, name))
    for k, ps in groups.items():
        write(os.path.join(folder, k + ".json"), fn(ps))
rubrics = {}
for o in filter(feedable, out):
    for t in {t.lstrip("#").lower() for t in o["tags"]}:
        rubrics[t] = rubrics.get(t, 0) + 1
ids = lambda ps: [min(int(o["id"]) for o in ps), max(int(o["id"]) for o in ps)]
write(os.path.join(DATA, "index", "meta.json"), {
    "years": [{"year": int(y), "feed": sum(map(feedable, ps)), "first": min(o["date"] for o in ps if feedable(o)) if any(map(feedable, ps)) else "",
               "last": max(o["date"] for o in ps if feedable(o)) if any(map(feedable, ps)) else "", "ids": ids(ps)}
              for y, ps in sorted(years.items(), reverse=True)],
    "months": [[m] + ids(ps) for m, ps in sorted(months.items(), reverse=True)],
    "rubrics": rubrics,
    "slugs": {k.lower(): str(v) for k, v in SLUGS.items() if str(v) in {o["id"] for o in out if not o.get("archive")}}})
inline = sum(len(MARK.findall(" ".join(o["body"]))) for o in out)
internal = sum(1 for o in out for m in MARK.findall(" ".join(o["body"])) if m[0].startswith("#p"))
print(f"{len(out)} posts ({len(arch)} from the archive); {len(skipped)} skipped; inline links {inline}, to site pages {internal}; "
      f"{os.path.getsize(OUT) // 1024} KB")
