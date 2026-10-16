# Смоленский транспорт — тестовый сайт

Лента постов со стены группы ВКонтакте «Смоленский транспорт» (https://vk.ru/smolensk_transport) за 2026 год.
Открыт на GitHub Pages: https://kod4k.github.io/smoltransport/

- `data/posts.json` — посты (текст как на стене, заголовок, теги, фото). Полноразмерные фото берутся с серверов ВК, превью лежат в `thumbs/`.
- `src/gen2.py` собирает `data/posts.json` из выгрузки стены (`wall-2026.json`, делается на Mac из архива `_служебное/posts.jsonl`).
- `src/base.css`, `src/extra.css`, `src/body.html` — части `index.html`.
- `server/views/` — счётчик просмотров постов для smoltransport.ru (`views.py`, служба systemd, настройка nginx). Ничего о читателе не хранит: ни cookie, ни адресов, ни журнала запросов. На github.io счётчика нет.
