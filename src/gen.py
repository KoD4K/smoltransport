import json, re, html, os
S = os.path.dirname(os.path.abspath(__file__))
posts = json.load(open(os.path.join(S, "posts.json"), encoding="utf-8"))

TITLES = {
    "138482": "Маршрут 20 проверили: нарушений не нашли",
    "138583": "Новый участок трамвайных путей на ул. Кашена",
    "138805": "Деньги на транспорт из дорожных фондов",
}
RUBRICS = {
    "138482": ["автобус", "официальныйОтвет"],
    "138507": ["трамвай"],
    "138543": ["трамвай", "остановка", "официальныйОтвет"],
    "138580": ["трамвай", "слухи"],
    "138583": ["трамвай", "ремонтРельсов"],
    "138764": ["автобус", "троллейбус", "расписание"],
    "138805": ["транспортнаяРеформа", "обещание"],
    "138712": ["транспортнаяРеформа", "обещание"],
    "138750": ["трамвай", "обновление", "обещание"],
    "138759": ["трамвай", "обновление"],
}
INLINE = {
    "#маршрут20": "маршрут 20", "#МУТТП": "МУТТП", "#улицаБагратиона": "ул. Багратиона",
    "#улицаКашена": "ул. Кашена", "#улицаЖелябова": "ул. Желябова",
    "#улицаДзержинского": "ул. Дзержинского",
}
NOTE_PREFIXES = ("Отличие от файлов", "Теги на стене", "Пост на стене", "Картинки instagram", "15.10.2026")

out = []
for p in posts:
    lines = p["body"].split("\n")
    if lines[0].startswith("Добрый вечер"):
        lines = lines[1:]
    paras, cur = [], []
    for ln in lines + [""]:
        s = ln.strip()
        if not s:
            if cur:
                paras.append(" ".join(cur)); cur = []
            continue
        cur.append(s)
    clean, source = [], None
    for para in paras:
        if para.startswith(NOTE_PREFIXES) or para.startswith("Рубрики:"):
            continue
        if re.fullmatch(r"(#\S+\s*)+", para):
            continue
        if para.startswith("Источник новости"):
            continue
        m = re.match(r"Источник\s*-\s*(https?://\S+)", para)
        if m:
            source = m.group(1); continue
        for k, v in INLINE.items():
            para = para.replace(k, v)
        para = re.sub(r"\s{2,}", " ", para).replace(" «", " «")
        clean.append(para)
    title = TITLES.get(p["id"]) or clean[0]
    if not TITLES.get(p["id"]):
        clean = clean[1:]
    out.append(dict(id=p["id"], date=p["date"], time=p["time"], link=p["link"].replace("vk.com", "vk.ru"),
                    title=title.strip(), paras=clean, source=source, rubrics=RUBRICS[p["id"]],
                    images=["media/" + i for i in p["images"]]))
out.sort(key=lambda x: (x["date"], x["time"]), reverse=True)
data = json.dumps(out, ensure_ascii=False)
tpl = open(os.path.join(S, "template.html"), encoding="utf-8").read()
open(os.path.join(S, "site", "index.html"), "w", encoding="utf-8").write(tpl.replace("/*POSTS*/[]", data))
for o in out:
    print(o["date"], o["title"], len(o["paras"]), o["source"])
