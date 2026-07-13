# tools — пайплайн обновления HubEx.Wiki

## Установка

```
python3 -m pip install -r tools/requirements.txt
```

Для `--recompress` нужен `claude` CLI в PATH (аннотации пишутся через `claude -p`).

## Команды

```
python3 tools/wiki_cli.py update [--page <section>/<slug>] [--recompress] [--report-file PATH] [--jobs N]
```

- Без флагов: sitemap → фильтр курации → параллельный забор → HTML→md → дифф против `pages/` → отчёт new/changed/removed/error. Пишутся только черновики `tools/update/drafts/**` (gitignored).
- `--recompress`: дополнительно перезаписывает затронутые `pages/**` (механически) и обновляет строку-аннотацию индекса моделью (changed — всегда; new — только если строки ещё нет). Всё unstaged, коммитит человек.
- `--page` (повторяемый): только указанные страницы; `removed` при этом не вычисляется.
- Exit-коды: 0 — ок; 1 — ошибки страниц/модели или guard-проблемы (битая ссылка/длина аннотации); 2 — sitemap недоступен/пуст.

## Тесты и линт

```
python3 -m pytest -v -m "not live"   # офлайн-набор
python3 -m pytest -v -m live         # живой смоук (сеть)
python3 tools/lint/check_links.py    # битые относительные md-ссылки
```
