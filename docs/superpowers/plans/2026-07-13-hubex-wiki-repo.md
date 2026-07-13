# HubEx.Wiki — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Собрать автономный репозиторий HubEx.Wiki: вербатим-копии страниц вики HubEx (`pages/`), дистиллированные индексы (`index.md`, `releasenotes-index.md`) и самодостаточный пайплайн обновления `update` (sitemap → параллельный fetch → HTML→md с локальными кросс-ссылками → дифф против `pages/` → отчёт; `--recompress` пишет страницы и аннотации индексов), засеянный первым прогоном.

**Architecture:** Чистые модули (`manifest` — sitemap+курация; `fetch` — конвертер HTML→md с локализацией кросс-ссылок; `diff`; `report`; `guard`; `recompress` — аннотация индекса моделью) тестируются на фикстурах; сеть и модель (`claude -p`) мокаются. `pipeline.run_update` склеивает их: параллельный fetch/convert (ThreadPoolExecutor), дифф против `pages/<page_id>.md` (снапшотов нет — страницы и есть база сравнения), черновики в gitignored `drafts/`, `removed` только на полном прогоне. CLI — `tools/wiki_cli.py update`. Всё пишется unstaged, коммитит человек.

**Tech Stack:** Python 3.10+, stdlib (`re`, `difflib`, `hashlib`, `posixpath`, `urllib.parse`, `subprocess`, `concurrent.futures`, `pathlib`), `requests`, `beautifulsoup4` (парсер `html.parser`, без `lxml`), `markdownify`, `claude` CLI, `pytest`.

## Global Constraints

- Спека: `docs/superpowers/specs/2026-07-13-hubex-wiki-repo-design.md`. Монорепа `/root/projects/HubEx.AI-2.0` в этом цикле **не изменяется** (только читается при переносе индекса).
- Пакет — `tools/update/`, импорт в тестах и CLI — `from update import <module>` (через `tools/conftest.py` / `sys.path` в CLI).
- Прогон тестов из корня репо: `python3 -m pytest -v -m "not live"` — офлайн-набор всегда зелёный; живые тесты — маркер `live`.
- Зависимости только: `requests`, `beautifulsoup4`, `markdownify`, `pytest` (см. `tools/requirements.txt`).
- `page_id = "<section>/<slug>"`, секции `{admin, user, ReleaseNotes}`; денилист slug: суффиксы `Old`/`Copy`, префиксы `index`/`main`/`GettingStarted`.
- **Снапшотов нет**: база диффа — сами `pages/<page_id>.md`. Без `--recompress` пайплайн пишет только черновики `tools/update/drafts/**` (в `.gitignore`). `pages/**` и индексы пишутся **только** при `--recompress`, остаются unstaged.
- Аннотация: `changed` → модель вызывается всегда; `new` → только если строки в индексе ещё нет (иначе `skipped`). ReleaseNotes → `releasenotes-index.md`, admin/user → `index.md`.
- `removed` вычисляется только при полном прогоне (без `--page`); переименование = `removed`+`new`, спецлогики нет.
- Frontmatter страницы: `title`, `url`, `section`, `content_hash` — **без `crawled_at`**.
- Кросс-ссылки на курируемые страницы → локальные относительные пути; всё остальное (картинки, легаси, внешнее) → абсолютные URL `https://wiki.hubex.ru/...` (через `urljoin`).
- `claude -p` получает промпт через stdin, таймаут 180 с (`model_client.run_model`); модельные вызовы последовательные (параллелится только HTTP-забор).
- Корень репо из модулей `tools/update/*.py`: `Path(__file__).resolve().parents[2]`.
- Exit-коды CLI: `2` — `ManifestError`; `1` — ошибки страниц/модели или грязный guard; `0` — иначе.
- Язык кода/докстрингов/коммитов — как в монорепе: докстринги и сообщения по-русски, терсно.

---

### Task 1: Каркас репозитория и тестовой оснастки

**Files:**
- Create: `.gitignore`, `pytest.ini`, `tools/conftest.py`, `tools/requirements.txt`, `tools/update/__init__.py`

**Interfaces:**
- Consumes: —
- Produces: работающий `python3 -m pytest` (0 тестов), импортируемый пакет `update`, установленные зависимости. Все последующие задачи полагаются на эту оснастку.

- [ ] **Step 1: Создать `.gitignore`**

```gitignore
__pycache__/
*.pyc
.pytest_cache/
tools/update/drafts/
.superpowers/
```

- [ ] **Step 2: Создать `pytest.ini`** (в корне репо)

```ini
[pytest]
testpaths = tools/tests
markers =
    live: тесты с реальной сетью (офлайн-прогон: -m "not live")
```

- [ ] **Step 3: Создать `tools/conftest.py`**

```python
"""Делает пакет `update` и `wiki_cli` импортируемыми в тестах: tools/ в sys.path."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
```

- [ ] **Step 4: Создать `tools/requirements.txt` и установить**

```
requests>=2.31
beautifulsoup4>=4.12
markdownify>=0.11
pytest>=8
```

Run: `python3 -m pip install -r tools/requirements.txt`
Expected: зависимости установлены без ошибок.

- [ ] **Step 5: Создать пустой пакет и папку тестов**

Создать `tools/update/__init__.py` (пустой файл) и пустую папку `tools/tests/` (появится с первым тестом в Task 2; папку можно не коммитить отдельно).

Run: `python3 -m pytest -v -m "not live"`
Expected: `no tests ran` (exit 5) — оснастка работает, тестов пока нет.

- [ ] **Step 6: Commit**

```bash
git add .gitignore pytest.ini tools/conftest.py tools/requirements.txt tools/update/__init__.py
git commit -m "chore: каркас репозитория — pytest, пакет update, зависимости"
```

---

### Task 2: Манифест страниц из sitemap + фильтр курации (`manifest`)

**Files:**
- Create: `tools/update/manifest.py`
- Test: `tools/tests/test_manifest.py`
- Create фикстуру: `tools/tests/fixtures/sitemap.xml`

**Interfaces:**
- Consumes: —
- Produces:
  - `ManifestError(Exception)`
  - `parse_manifest(xml: str) -> list[tuple[str, str]]` — `[(page_id, url)]`, отфильтровано, отсортировано, без дублей.
  - `fetch_manifest(*, timeout=30) -> list` — сеть; пусто после фильтра → `ManifestError`.
  - `PAGE_RE` — публичный regex `/docs/FAQ/RU/(admin|user|ReleaseNotes)/([^/]+)\.html$` (переиспользуется в `fetch` для локализации ссылок).
  - `SITEMAP_URL: str`

- [ ] **Step 1: Создать фикстуру `tools/tests/fixtures/sitemap.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://wiki.hubex.ru/docs/FAQ/RU/admin/BusinessProcess.html</loc></url>
<url><loc>https://wiki.hubex.ru/docs/FAQ/RU/admin/PowersCopy.html</loc></url>
<url><loc>https://wiki.hubex.ru/docs/FAQ/RU/user/CreatingTicket.html</loc></url>
<url><loc>https://wiki.hubex.ru/docs/FAQ/RU/ReleaseNotes/v2_50_0.html</loc></url>
<url><loc>https://wiki.hubex.ru/index_admin.html</loc></url>
<url><loc>https://wiki.hubex.ru/docs/GettingStarted.html</loc></url>
<url><loc>https://wiki.hubex.ru/</loc></url>
</urlset>
```

- [ ] **Step 2: Написать падающие тесты `tools/tests/test_manifest.py`**

```python
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from update import manifest

FIXTURE = (Path(__file__).parent / "fixtures" / "sitemap.xml").read_text(encoding="utf-8")


def test_parse_keeps_tracked_sections():
    entries = dict(manifest.parse_manifest(FIXTURE))
    assert entries["admin/BusinessProcess"] == \
        "https://wiki.hubex.ru/docs/FAQ/RU/admin/BusinessProcess.html"
    assert "user/CreatingTicket" in entries
    assert "ReleaseNotes/v2_50_0" in entries


def test_parse_drops_legacy_copy():
    ids = [pid for pid, _ in manifest.parse_manifest(FIXTURE)]
    assert "admin/PowersCopy" not in ids


def test_parse_drops_root_navigation():
    ids = [pid for pid, _ in manifest.parse_manifest(FIXTURE)]
    assert not any("index_admin" in i or "GettingStarted" in i for i in ids)


def test_parse_sorted():
    ids = [pid for pid, _ in manifest.parse_manifest(FIXTURE)]
    assert ids == sorted(ids)


def test_fetch_raises_on_empty(monkeypatch):
    resp = MagicMock(text="<urlset></urlset>")
    resp.raise_for_status = MagicMock()
    monkeypatch.setattr(manifest, "requests", MagicMock(get=MagicMock(return_value=resp)))
    with pytest.raises(manifest.ManifestError):
        manifest.fetch_manifest()
```

- [ ] **Step 3: Прогнать — падает**

Run: `python3 -m pytest tools/tests/test_manifest.py -v`
Expected: FAIL — модуль `manifest` не существует.

- [ ] **Step 4: Реализация `tools/update/manifest.py`**

```python
"""Обнаружение курированного списка страниц вики из sitemap.xml. Список НЕ хардкодится.

sitemap даёт «вселенную» страниц; трекаем подмножество: секции {admin,user,ReleaseNotes}
минус легаси (*Old/*Copy) и навигация (index*/main*/GettingStarted*).
"""
import re

import requests

SITEMAP_URL = "https://wiki.hubex.ru/sitemap.xml"

_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
PAGE_RE = re.compile(r"/docs/FAQ/RU/(admin|user|ReleaseNotes)/([^/]+)\.html$")
_DENY_RE = re.compile(r"(Old|Copy)$|^(index|main|GettingStarted)")


class ManifestError(Exception):
    """Источник перечня страниц недоступен или пуст после фильтра."""


def parse_manifest(xml: str) -> list:
    entries, seen = [], set()
    for loc in _LOC_RE.findall(xml):
        m = PAGE_RE.search(loc)
        if not m:
            continue
        section, slug = m.group(1), m.group(2)
        if _DENY_RE.search(slug):
            continue
        page_id = f"{section}/{slug}"
        if page_id in seen:
            continue
        seen.add(page_id)
        entries.append((page_id, loc))
    return sorted(entries)


def fetch_manifest(*, timeout: int = 30) -> list:
    resp = requests.get(SITEMAP_URL, timeout=timeout)
    resp.raise_for_status()
    entries = parse_manifest(resp.text)
    if not entries:
        raise ManifestError(
            f"sitemap {SITEMAP_URL} не дал ни одной трекаемой страницы — проверь фильтр/формат")
    return entries
```

- [ ] **Step 5: Прогнать — зелено**

Run: `python3 -m pytest tools/tests/test_manifest.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/update/manifest.py tools/tests/test_manifest.py tools/tests/fixtures/sitemap.xml
git commit -m "feat(update): manifest — sitemap + фильтр курации страниц"
```

---

### Task 3: Конвертер HTML→md с локальными кросс-ссылками (`fetch`)

**Files:**
- Create: `tools/update/fetch.py`
- Test: `tools/tests/test_fetch.py`
- Create фикстуру: `tools/tests/fixtures/page.html`

**Interfaces:**
- Consumes: `manifest.PAGE_RE`.
- Produces:
  - `fetch_html(url, *, timeout=30) -> str` — сеть.
  - `convert_page(html, *, page_id, url, known_pages=frozenset()) -> str` — **чистая**: нормализованный md с frontmatter (`title`,`url`,`section`,`content_hash`, без `crawled_at`). Ссылки на страницы из `known_pages` — локальные относительные; остальное абсолютизировано. Нет `#main_content_wrap` → `ValueError`.
  - `normalize(md) -> str`, `local_href(from_page_id, to_page_id) -> str`, `BASE = "https://wiki.hubex.ru"`.

- [ ] **Step 1: Создать фикстуру `tools/tests/fixtures/page.html`**

```html
<!DOCTYPE html>
<html>
  <head><title>Базовый бизнес-процесс для заявки</title></head>
  <body>
    <div id="header_wrap" class="outer"><nav>меню</nav></div>
    <div id="main_content_wrap" class="outer">
      <section class="inner">
        <h4>Базовый бизнес-процесс</h4>
        <p>Текст про <strong>Заявки</strong>. Подробнее: <a href="./TicketLifeCycle.html">ЖЦ</a>,
           <a href="../user/Filters.html">фильтры</a> и <a href="./PowersOld.html">легаси</a>.</p>
        <img style="max-width:100%" src="/attachments/images/FAQ/ADMIN/BusinessProcess/BasicStages.jpg" alt="Стадии" />
        <img src="https://mc.yandex.ru/watch/52269412" style="position:absolute" alt="" />
      </section>
    </div>
    <div id="footer_wrap" class="outer"><p>подвал</p></div>
    <script>var x = 1;</script>
  </body>
</html>
```

- [ ] **Step 2: Написать падающие тесты `tools/tests/test_fetch.py`**

```python
from pathlib import Path

import pytest

from update import fetch

HTML = (Path(__file__).parent / "fixtures" / "page.html").read_text(encoding="utf-8")
URL = "https://wiki.hubex.ru/docs/FAQ/RU/admin/BusinessProcess.html"
KNOWN = frozenset({"admin/BusinessProcess", "admin/TicketLifeCycle", "user/Filters"})


def _md():
    return fetch.convert_page(HTML, page_id="admin/BusinessProcess", url=URL, known_pages=KNOWN)


def test_frontmatter_fields():
    md = _md()
    assert md.startswith("---\n")
    assert 'section: "admin"' in md
    assert f'url: "{URL}"' in md
    assert "content_hash:" in md
    assert "crawled_at" not in md


def test_body_extracted_without_chrome():
    md = _md()
    assert "Базовый бизнес-процесс" in md
    assert "меню" not in md and "подвал" not in md


def test_image_absolutized_as_link():
    assert "![Стадии](https://wiki.hubex.ru/attachments/images/FAQ/ADMIN/BusinessProcess/BasicStages.jpg)" in _md()


def test_tracking_pixel_stripped():
    assert "mc.yandex.ru" not in _md()


def test_cross_link_same_section_localized():
    assert "](TicketLifeCycle.md)" in _md()


def test_cross_link_other_section_localized():
    assert "](../user/Filters.md)" in _md()


def test_non_curated_link_stays_absolute():
    assert "https://wiki.hubex.ru/docs/FAQ/RU/admin/PowersOld.html" in _md()


def test_local_href_paths():
    assert fetch.local_href("admin/A", "admin/B") == "B.md"
    assert fetch.local_href("admin/A", "user/C") == "../user/C.md"


def test_missing_content_container_raises():
    with pytest.raises(ValueError):
        fetch.convert_page("<html><body>нет</body></html>",
                           page_id="admin/X", url=URL)


def test_deterministic():
    assert _md() == _md()


def test_normalize_collapses_blanks_and_trailing_ws():
    assert fetch.normalize("a  \n\n\n\nb\n\n") == "a\n\nb\n"
```

- [ ] **Step 3: Прогнать — падает**

Run: `python3 -m pytest tools/tests/test_fetch.py -v`
Expected: FAIL — модуль `fetch` не существует.

- [ ] **Step 4: Реализация `tools/update/fetch.py`**

```python
"""Забор страницы вики и конвертация HTML→md: тело статьи, локальные кросс-ссылки,
картинки абсолютными URL, чистый frontmatter (без волатильных полей)."""
import hashlib
import posixpath
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

from update.manifest import PAGE_RE

BASE = "https://wiki.hubex.ru"
_CONTENT_ID = "main_content_wrap"
_TRACKING_HOSTS = ("mc.yandex.ru", "google-analytics.com", "googletagmanager.com")


def fetch_html(url: str, *, timeout: int = 30) -> str:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def normalize(md: str) -> str:
    md = md.replace("\r\n", "\n").replace("\r", "\n")
    out, blank = [], 0
    for line in md.split("\n"):
        line = line.rstrip()
        if line == "":
            blank += 1
            if blank <= 1:
                out.append(line)
        else:
            blank = 0
            out.append(line)
    return "\n".join(out).strip("\n") + "\n"


def local_href(from_page_id: str, to_page_id: str) -> str:
    """Относительный путь между страницами: admin/A → admin/B = "B.md", admin/A → user/C = "../user/C.md"."""
    return posixpath.relpath(f"{to_page_id}.md", posixpath.dirname(from_page_id))


def _title(soup: BeautifulSoup) -> str:
    t = soup.find("title")
    return (t.get_text(strip=True) if t else "").replace('"', "'")


def convert_page(html: str, *, page_id: str, url: str,
                 known_pages: frozenset = frozenset()) -> str:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.find(id=_CONTENT_ID)
    if body is None:
        raise ValueError(f"не найден #{_CONTENT_ID} — вёрстка страницы изменилась")
    for junk in body(["script", "style"]):
        junk.decompose()
    for img in body.find_all("img"):
        if any(h in (img.get("src") or "") for h in _TRACKING_HOSTS):
            img.decompose()
    for tag, attr in (("a", "href"), ("img", "src")):
        for el in body.find_all(tag):
            if el.get(attr):
                el[attr] = urljoin(url, el[attr])
    # ссылки с якорями/параметрами не матчатся PAGE_RE ($ после .html) и остаются URL-ами
    for a in body.find_all("a"):
        m = PAGE_RE.search(a.get("href") or "")
        if m and f"{m.group(1)}/{m.group(2)}" in known_pages:
            a["href"] = local_href(page_id, f"{m.group(1)}/{m.group(2)}")
    md = normalize(markdownify(str(body), heading_style="ATX"))
    section = page_id.split("/", 1)[0]
    content_hash = hashlib.sha256(md.encode("utf-8")).hexdigest()[:16]
    frontmatter = (
        "---\n"
        f'title: "{_title(soup)}"\n'
        f'url: "{url}"\n'
        f'section: "{section}"\n'
        f'content_hash: "{content_hash}"\n'
        "---\n\n"
    )
    return frontmatter + md
```

- [ ] **Step 5: Прогнать — зелено**

Run: `python3 -m pytest tools/tests/test_fetch.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/update/fetch.py tools/tests/test_fetch.py tools/tests/fixtures/page.html
git commit -m "feat(update): fetch — HTML→md, локальные кросс-ссылки, картинки-URL (bs4+markdownify)"
```

---

### Task 4: Дифф страницы (`diff`)

**Files:**
- Create: `tools/update/diff.py`
- Test: `tools/tests/test_diff.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `page_status(old_md: str|None, new_md: str) -> str` — `"new"` / `"unchanged"` / `"changed"`.
  - `body_diff(old_md, new_md, *, context=3) -> str` — unified diff.

- [ ] **Step 1: Написать падающие тесты `tools/tests/test_diff.py`**

```python
from update import diff


def test_status_new():
    assert diff.page_status(None, "x") == "new"


def test_status_unchanged():
    assert diff.page_status("x\n", "x\n") == "unchanged"


def test_status_changed():
    assert diff.page_status("a\n", "b\n") == "changed"


def test_body_diff_shows_delta():
    d = diff.body_diff("line1\nold\n", "line1\nnew\n")
    assert "-old" in d and "+new" in d
```

- [ ] **Step 2: Прогнать — падает**

Run: `python3 -m pytest tools/tests/test_diff.py -v`
Expected: FAIL — модуль не существует.

- [ ] **Step 3: Реализация `tools/update/diff.py`**

```python
"""Дифф нормализованных страниц: статус + unified-diff тела. Чистый модуль."""
import difflib


def page_status(old_md, new_md: str) -> str:
    if old_md is None:
        return "new"
    return "unchanged" if old_md == new_md else "changed"


def body_diff(old_md, new_md: str, *, context: int = 3) -> str:
    d = difflib.unified_diff(
        (old_md or "").splitlines(), new_md.splitlines(),
        fromfile="old", tofile="new", n=context, lineterm="")
    return "\n".join(d)
```

- [ ] **Step 4: Прогнать — зелено**

Run: `python3 -m pytest tools/tests/test_diff.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/update/diff.py tools/tests/test_diff.py
git commit -m "feat(update): diff — статус страницы + unified-diff"
```

---

### Task 5: Отчёт (`report`)

**Files:**
- Create: `tools/update/report.py`
- Test: `tools/tests/test_report.py`

**Interfaces:**
- Consumes: результаты пайплайна — `[{"page","status","error"[, "diff"]}]`, `status ∈ {new, unchanged, changed, removed, error}`.
- Produces: `render(results: list) -> str` — markdown-отчёт.

- [ ] **Step 1: Написать падающие тесты `tools/tests/test_report.py`**

```python
from update import report


def test_render_groups_and_totals():
    results = [
        {"page": "admin/A", "status": "changed", "error": None, "diff": "-a\n+b"},
        {"page": "user/B", "status": "new", "error": None},
        {"page": "admin/Gone", "status": "removed", "error": None},
        {"page": "user/Err", "status": "error", "error": "таймаут"},
        {"page": "admin/Same", "status": "unchanged", "error": None},
    ]
    text = report.render(results)
    assert "admin/A" in text and "user/B" in text
    assert "-a" in text  # дифф changed-страницы попадает в отчёт
    assert "admin/Gone" in text and "таймаут" in text
    assert "изменилось 2" in text and "удалено 1" in text and "ошибок 1" in text


def test_render_no_changes():
    text = report.render([{"page": "a/b", "status": "unchanged", "error": None}])
    assert "Изменений нет." in text
```

- [ ] **Step 2: Прогнать — падает**

Run: `python3 -m pytest tools/tests/test_report.py -v`
Expected: FAIL — модуль не существует.

- [ ] **Step 3: Реализация `tools/update/report.py`**

```python
"""Рендер результатов update в markdown-отчёт. Чистый модуль."""


def render(results: list) -> str:
    changed = [r for r in results if r["status"] in ("new", "changed")]
    removed = [r for r in results if r["status"] == "removed"]
    errors = [r for r in results if r["status"] == "error"]
    unchanged = [r for r in results if r["status"] == "unchanged"]

    out = ["# Отчёт update"]
    for r in changed:
        out.append("")
        mark = "🆕" if r["status"] == "new" else "✏️"
        out.append(f"## {mark} {r['page']} — {r['status']}")
        out.append(f"→ проверь `pages/{r['page']}.md` и строку индекса")
        if r.get("diff"):
            out.append("```diff")
            out.append(r["diff"])
            out.append("```")
    for r in removed:
        out.append("")
        out.append(f"## ❌ {r['page']} — пропала на вики "
                   "(удалить копию и строку индекса вручную)")
    for r in errors:
        out.append("")
        out.append(f"## {r['page']} — не удалось забрать: {r['error']}")

    out.append("")
    out.append(f"Итого: изменилось {len(changed)}, удалено {len(removed)}, "
               f"ошибок {len(errors)}, без изменений {len(unchanged)}.")
    if not changed and not removed and not errors:
        out.append("Изменений нет.")
    return "\n".join(out) + "\n"
```

- [ ] **Step 4: Прогнать — зелено**

Run: `python3 -m pytest tools/tests/test_report.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/update/report.py tools/tests/test_report.py
git commit -m "feat(update): report — отчёт new/changed/removed/error с диффами"
```

---

### Task 6: Обёртка модели + guard аннотаций (`model_client`, `guard`)

**Files:**
- Create: `tools/update/model_client.py` (перенос из монорепы без изменений)
- Create: `tools/update/guard.py`
- Test: `tools/tests/test_guard.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `model_client.run_model(prompt: str, *, timeout=180) -> str`; `model_client.ModelError(Exception)`.
  - `guard.problems(annotation: str, root: Path) -> list[str]` — список проблем: битые относительные ссылки (`root / rel` не существует; `http(s)`-ссылки игнорируются, якоря отбрасываются) и превышение лимита длины `guard.MAX_LEN = 300`. Пустой список = guard чист.

- [ ] **Step 1: Создать `tools/update/model_client.py`** (проверенный код монорепы, verbatim)

```python
"""Тонкая обёртка вызова модели через `claude -p` (headless Claude Code). Промпт — в stdin."""
import subprocess


class ModelError(Exception):
    """Вызов модели не удался (ненулевой код, таймаут, пустой ответ)."""


def run_model(prompt: str, *, timeout: int = 180) -> str:
    try:
        proc = subprocess.run(["claude", "-p"], input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise ModelError(f"claude -p таймаут ({timeout}s)") from e
    if proc.returncode != 0:
        raise ModelError(f"claude -p код {proc.returncode}: {proc.stderr.strip()[:200]}")
    out = proc.stdout.strip()
    if not out:
        raise ModelError("claude -p вернул пустой ответ")
    return out
```

- [ ] **Step 2: Написать падающие тесты `tools/tests/test_guard.py`**

```python
from update import guard


def test_phantom_link_flagged(tmp_path):
    (tmp_path / "pages" / "admin").mkdir(parents=True)
    (tmp_path / "pages" / "admin" / "Real.md").write_text("x", encoding="utf-8")
    ann = "- [Real](pages/admin/Real.md) — ок. Ещё [Ghost](pages/admin/Ghost.md)."
    probs = guard.problems(ann, tmp_path)
    assert probs == ["битая ссылка: pages/admin/Ghost.md"]


def test_external_link_and_anchor_ignored(tmp_path):
    (tmp_path / "pages" / "user").mkdir(parents=True)
    (tmp_path / "pages" / "user" / "P.md").write_text("x", encoding="utf-8")
    ann = "- [P](pages/user/P.md#якорь) — с якорем и [внешней](https://wiki.hubex.ru/x.html)."
    assert guard.problems(ann, tmp_path) == []


def test_too_long_flagged(tmp_path):
    ann = "- [X](pages/user/P.md) — " + "оченьдлинно " * 40
    (tmp_path / "pages" / "user").mkdir(parents=True)
    (tmp_path / "pages" / "user" / "P.md").write_text("x", encoding="utf-8")
    probs = guard.problems(ann, tmp_path)
    assert len(probs) == 1 and probs[0].startswith("длина")


def test_clean_annotation(tmp_path):
    (tmp_path / "pages" / "user").mkdir(parents=True)
    (tmp_path / "pages" / "user" / "P.md").write_text("x", encoding="utf-8")
    assert guard.problems("- [P](pages/user/P.md) — чистая.", tmp_path) == []
```

- [ ] **Step 3: Прогнать — падает**

Run: `python3 -m pytest tools/tests/test_guard.py -v`
Expected: FAIL — модуль `guard` не существует.

- [ ] **Step 4: Реализация `tools/update/guard.py`**

```python
"""Детерминированные fail-safe проверки модельной аннотации. Чистый модуль."""
import re

_LINK_RE = re.compile(r"\]\(([^)]+)\)")
MAX_LEN = 300


def problems(annotation: str, root) -> list:
    """Список проблем аннотации: битые относительные ссылки + превышение лимита длины."""
    out = []
    for target in _LINK_RE.findall(annotation):
        rel = target.split("#", 1)[0].strip()
        if not rel or rel.startswith(("http://", "https://")):
            continue
        if not (root / rel).exists():
            out.append(f"битая ссылка: {rel}")
    if len(annotation) > MAX_LEN:
        out.append(f"длина {len(annotation)} > {MAX_LEN}")
    return sorted(set(out))
```

- [ ] **Step 5: Прогнать — зелено**

Run: `python3 -m pytest tools/tests/test_guard.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/update/model_client.py tools/update/guard.py tools/tests/test_guard.py
git commit -m "feat(update): model_client (claude -p) + guard аннотаций (ссылки, длина)"
```

---

### Task 7: Промпт + аннотация индекса (`recompress`)

**Files:**
- Create: `tools/update/prompts/recompress.md`
- Create: `tools/update/recompress.py`
- Test: `tools/tests/test_recompress.py`

**Interfaces:**
- Consumes: `model_client.run_model`, `guard.problems`.
- Produces:
  - `update_annotation(page_id, page_md, status, *, model=model_client.run_model, root=None) -> dict` — `{"page","status","problems","error"}`, `status ∈ {ok, skipped, error}`. Правило: `changed` → модель всегда; `new` → модель только если строки в индексе нет, иначе `skipped`. Пишет строку в `index.md` (admin/user) или `releasenotes-index.md` (ReleaseNotes). Страницу НЕ пишет (это делает pipeline).
  - `render_summary(results: list) -> str` — сводка по ключам `recompress` результатов пайплайна.
  - Хелперы (для тестов и pipeline): `index_path(page_id, root) -> Path`, `link_target(page_id) -> str` (= `pages/<page_id>.md`), `splice(index_text, annotation, target) -> str`, `build_prompt(page_id, page_md, current_line, *, template_path=None) -> str`.

- [ ] **Step 1: Создать фикс-промпт `tools/update/prompts/recompress.md`**

```markdown
# Задача: строка-аннотация страницы вики для индекса

Ты обновляешь каталог страниц вики HubEx (`index.md` / `releasenotes-index.md`).
На вход — содержимое одной страницы (markdown) и текущая строка индекса (если была).

Верни **ровно одну строку** — markdown-элемент списка в доме-стиле:

`- [ЧитаемоеИмя](ССЫЛКА) — одно предложение о том, что внутри страницы.`

Правила:
- ССЫЛКА — строго та, что указана во входе как «Ссылка для аннотации». Не выдумывай другие пути.
- Одно предложение, по-русски, по фактическому содержимому страницы. Без воды.
- Если страница — сравнение/ограничение/грабли, начни предложение с `⚠`.
- Если текущая строка индекса дана и всё ещё точна — верни её без изменений.
- Никакого текста до или после строки. Только сама строка.
```

- [ ] **Step 2: Написать падающие тесты `tools/tests/test_recompress.py`**

```python
import pytest

from update import recompress


def _root(tmp_path):
    (tmp_path / "pages" / "admin").mkdir(parents=True)
    (tmp_path / "pages" / "admin" / "BusinessProcess.md").write_text("x", encoding="utf-8")
    (tmp_path / "index.md").write_text(
        "# Индекс\n\n## Заявки\n\n- [Old](pages/admin/BusinessProcess.md) — старьё.\n",
        encoding="utf-8")
    return tmp_path


def test_changed_replaces_line(tmp_path):
    root = _root(tmp_path)
    model = lambda p: "- [Бизнес-процесс](pages/admin/BusinessProcess.md) — ЖЦ заявки на ремонт."
    res = recompress.update_annotation(
        "admin/BusinessProcess", "тело\n", "changed", model=model, root=root)
    assert res["status"] == "ok" and res["problems"] == []
    index = (root / "index.md").read_text(encoding="utf-8")
    assert "ЖЦ заявки на ремонт" in index and "старьё" not in index


def test_new_with_existing_line_skips_model(tmp_path):
    root = _root(tmp_path)

    def boom(p):
        raise AssertionError("модель не должна вызываться")

    res = recompress.update_annotation(
        "admin/BusinessProcess", "тело\n", "new", model=boom, root=root)
    assert res["status"] == "skipped"
    assert "старьё" in (root / "index.md").read_text(encoding="utf-8")


def test_new_without_line_appended_to_new_section(tmp_path):
    root = _root(tmp_path)
    (root / "pages" / "user").mkdir(parents=True)
    (root / "pages" / "user" / "NewPage.md").write_text("x", encoding="utf-8")
    model = lambda p: "- [Новая](pages/user/NewPage.md) — про новое."
    res = recompress.update_annotation(
        "user/NewPage", "тело\n", "new", model=model, root=root)
    assert res["status"] == "ok"
    index = (root / "index.md").read_text(encoding="utf-8")
    assert "Новые страницы (разложить по темам)" in index and "про новое" in index


def test_releasenotes_use_own_index(tmp_path):
    root = _root(tmp_path)
    (root / "pages" / "ReleaseNotes").mkdir(parents=True)
    (root / "pages" / "ReleaseNotes" / "v2_50_0.md").write_text("x", encoding="utf-8")
    model = lambda p: "- [v2.50](pages/ReleaseNotes/v2_50_0.md) — что нового."
    recompress.update_annotation(
        "ReleaseNotes/v2_50_0", "тело\n", "new", model=model, root=root)
    assert "что нового" in (root / "releasenotes-index.md").read_text(encoding="utf-8")
    assert "что нового" not in (root / "index.md").read_text(encoding="utf-8")


def test_model_failure_leaves_index_untouched(tmp_path):
    root = _root(tmp_path)
    before = (root / "index.md").read_text(encoding="utf-8")

    def boom(p):
        raise RuntimeError("claude упал")

    res = recompress.update_annotation(
        "admin/BusinessProcess", "тело\n", "changed", model=boom, root=root)
    assert res["status"] == "error" and "claude упал" in res["error"]
    assert (root / "index.md").read_text(encoding="utf-8") == before


def test_guard_problems_reported_but_spliced(tmp_path):
    root = _root(tmp_path)
    model = lambda p: "- [X](pages/admin/Ghost.md) — не та ссылка."
    res = recompress.update_annotation(
        "admin/BusinessProcess", "тело\n", "changed", model=model, root=root)
    assert res["problems"] == ["битая ссылка: pages/admin/Ghost.md"]
    # строка всё равно вклеена — человек увидит её в git diff вместе с предупреждением
    assert "не та ссылка" in (root / "index.md").read_text(encoding="utf-8")


def test_render_summary():
    results = [
        {"page": "admin/A", "recompress": {"page": "admin/A", "status": "ok",
                                           "problems": [], "error": None}},
        {"page": "admin/B", "recompress": {"page": "admin/B", "status": "skipped",
                                           "problems": [], "error": None}},
        {"page": "admin/C", "recompress": {"page": "admin/C", "status": "ok",
                                           "problems": ["битая ссылка: x"], "error": None}},
        {"page": "admin/D", "recompress": {"page": "admin/D", "status": "error",
                                           "problems": [], "error": "упало"}},
        {"page": "admin/E"},
    ]
    text = recompress.render_summary(results)
    assert "admin/A" in text and "guard чист" in text
    assert "admin/B" in text and "модель не вызывалась" in text
    assert "битая ссылка: x" in text and "упало" in text
```

- [ ] **Step 3: Прогнать — падает**

Run: `python3 -m pytest tools/tests/test_recompress.py -v`
Expected: FAIL — модуль не существует.

- [ ] **Step 4: Реализация `tools/update/recompress.py`**

```python
"""Аннотация индекса для одной страницы: модель пишет строку, guard проверяет, сплайс в индекс.

Правило вызова модели: changed — всегда (тело менялось, аннотация могла устареть);
new — только если строки в индексе ещё нет (кейс засева с перенесёнными аннотациями → skipped).
Страницу пишет pipeline; здесь — только индекс. При падении модели индекс не трогаем.
"""
from pathlib import Path

from update import guard, model_client

REPO_ROOT = Path(__file__).resolve().parents[2]
_PROMPT = Path(__file__).resolve().parent / "prompts" / "recompress.md"
_NEW_SECTION = "## Новые страницы (разложить по темам)"


def index_path(page_id: str, root: Path) -> Path:
    if page_id.startswith("ReleaseNotes/"):
        return root / "releasenotes-index.md"
    return root / "index.md"


def link_target(page_id: str) -> str:
    return f"pages/{page_id}.md"


def build_prompt(page_id: str, page_md: str, current_line, *, template_path=None) -> str:
    template = (template_path or _PROMPT).read_text(encoding="utf-8")
    cur = current_line if current_line else "(строки нет — страница новая)"
    return (
        f"{template}\n\n"
        f"## Страница\n{page_id}\nСсылка для аннотации: {link_target(page_id)}\n\n"
        f"## Текущая строка индекса\n{cur}\n\n"
        f"## Содержимое страницы (markdown)\n{page_md}\n"
    )


def _current_line(index_text: str, target: str):
    for line in index_text.splitlines():
        if f"]({target})" in line:
            return line
    return None


def splice(index_text: str, annotation: str, target: str) -> str:
    lines = index_text.splitlines()
    for i, line in enumerate(lines):
        if f"]({target})" in line:
            lines[i] = annotation
            return "\n".join(lines) + "\n"
    if _NEW_SECTION not in lines:
        lines += ["", _NEW_SECTION, ""]
    idx = lines.index(_NEW_SECTION)
    lines.insert(idx + 1, annotation)
    return "\n".join(lines) + "\n"


def update_annotation(page_id: str, page_md: str, status: str, *,
                      model=model_client.run_model, root: Path | None = None) -> dict:
    base = root if root is not None else REPO_ROOT
    idx = index_path(page_id, base)
    index_text = idx.read_text(encoding="utf-8") if idx.exists() else "# Индекс\n"
    target = link_target(page_id)
    current = _current_line(index_text, target)
    if status == "new" and current is not None:
        return {"page": page_id, "status": "skipped", "problems": [], "error": None}
    prompt = build_prompt(page_id, page_md, current)
    try:
        annotation = model(prompt).strip().splitlines()[0].strip()
    except Exception as e:  # noqa: BLE001 — падение модели одной страницы не роняет прогон
        return {"page": page_id, "status": "error", "problems": [], "error": str(e)}
    probs = guard.problems(annotation, base)
    idx.write_text(splice(index_text, annotation, target), encoding="utf-8")
    return {"page": page_id, "status": "ok", "problems": probs, "error": None}


def render_summary(results: list) -> str:
    out = ["# Пересжатие"]
    for r in results:
        rc = r.get("recompress")
        if not rc:
            continue
        if rc["status"] == "error":
            out.append(f"- {rc['page']}: ошибка — {rc['error']}")
        elif rc["status"] == "skipped":
            out.append(f"- {rc['page']}: аннотация уже есть, модель не вызывалась")
        elif rc["problems"]:
            out.append(f"- {rc['page']}: ⚠ guard: {', '.join(rc['problems'])}")
        else:
            out.append(f"- {rc['page']}: аннотация обновлена, guard чист")
    if len(out) == 1:
        out.append("(нечего пересжимать)")
    return "\n".join(out) + "\n"
```

- [ ] **Step 5: Прогнать — зелено**

Run: `python3 -m pytest tools/tests/test_recompress.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/update/recompress.py tools/update/prompts/recompress.md tools/tests/test_recompress.py
git commit -m "feat(update): recompress — аннотация индекса моделью, правило changed/new, guard"
```

---

### Task 8: Оркестратор (`pipeline`)

**Files:**
- Create: `tools/update/pipeline.py`
- Test: `tools/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `manifest.fetch_manifest`, `fetch.fetch_html`/`convert_page`, `diff.page_status`/`body_diff`, `recompress.update_annotation`.
- Produces:
  - `run_update(pages=None, *, fetch_html=None, manifest_fn=None, root=None, recompress=False, recompress_impl=None, jobs=8) -> list` — результаты `[{"page","status","error"[, "diff"][, "recompress"]}]`. Fetch/convert — параллельно (`ThreadPoolExecutor`), диффы/записи/модель — последовательно. Без `recompress` пишет только черновики; с `recompress` — сначала `pages/<page_id>.md`, затем аннотацию.
  - `page_path(page_id, *, root=None) -> Path`, `drafts_dir(root=None) -> Path`.
  - `REPO_ROOT: Path`.

- [ ] **Step 1: Написать падающие тесты `tools/tests/test_pipeline.py`**

```python
from update import pipeline


def _manifest():
    return [("admin/A", "https://wiki.hubex.ru/docs/FAQ/RU/admin/A.html"),
            ("user/B", "https://wiki.hubex.ru/docs/FAQ/RU/user/B.html")]


def _fetch(url):
    return "<html/>"  # convert_page замокан, html не важен


def _mock_convert(monkeypatch, text="md-{}"):
    monkeypatch.setattr(pipeline.fetch, "convert_page",
                        lambda html, *, page_id, url, known_pages=frozenset():
                        text.format(page_id) + "\n")


def _fake_rc(page_id, page_md, status, *, root=None):
    return {"page": page_id, "status": "ok", "problems": [], "error": None}


def test_report_only_writes_drafts_not_pages(tmp_path, monkeypatch):
    _mock_convert(monkeypatch)
    res = pipeline.run_update(manifest_fn=_manifest, fetch_html=_fetch, root=tmp_path)
    assert {r["page"]: r["status"] for r in res} == {"admin/A": "new", "user/B": "new"}
    assert not (tmp_path / "pages").exists()
    assert (pipeline.drafts_dir(tmp_path) / "admin" / "A.md").read_text(
        encoding="utf-8") == "md-admin/A\n"


def test_recompress_writes_pages_then_unchanged(tmp_path, monkeypatch):
    _mock_convert(monkeypatch)
    pipeline.run_update(manifest_fn=_manifest, fetch_html=_fetch, root=tmp_path,
                        recompress=True, recompress_impl=_fake_rc)
    assert (tmp_path / "pages" / "admin" / "A.md").exists()
    res = pipeline.run_update(manifest_fn=_manifest, fetch_html=_fetch, root=tmp_path)
    assert all(r["status"] == "unchanged" for r in res)


def test_changed_detected_with_diff(tmp_path, monkeypatch):
    _mock_convert(monkeypatch)
    pipeline.run_update(manifest_fn=_manifest, fetch_html=_fetch, root=tmp_path,
                        recompress=True, recompress_impl=_fake_rc)
    _mock_convert(monkeypatch, text="NEW-{}")
    res = {r["page"]: r for r in pipeline.run_update(
        manifest_fn=_manifest, fetch_html=_fetch, root=tmp_path)}
    assert res["admin/A"]["status"] == "changed" and "diff" in res["admin/A"]


def test_removed_flagged_only_on_full_run(tmp_path, monkeypatch):
    _mock_convert(monkeypatch)
    (tmp_path / "pages" / "user").mkdir(parents=True)
    (tmp_path / "pages" / "user" / "Gone.md").write_text("x", encoding="utf-8")
    full = pipeline.run_update(manifest_fn=_manifest, fetch_html=_fetch, root=tmp_path)
    assert any(r["page"] == "user/Gone" and r["status"] == "removed" for r in full)
    partial = pipeline.run_update(manifest_fn=_manifest, fetch_html=_fetch,
                                  root=tmp_path, pages=["admin/A"])
    assert not any(r["status"] == "removed" for r in partial)
    assert [r["page"] for r in partial if r["status"] != "removed"] == ["admin/A"]


def test_fetch_error_isolated(tmp_path, monkeypatch):
    _mock_convert(monkeypatch)

    def boom(url):
        if "admin/A" in url:
            raise RuntimeError("нет сети")
        return "<html/>"

    res = {r["page"]: r for r in pipeline.run_update(
        manifest_fn=_manifest, fetch_html=boom, root=tmp_path)}
    assert res["admin/A"]["status"] == "error" and "нет сети" in res["admin/A"]["error"]
    assert res["user/B"]["status"] == "new"


def test_recompress_receives_status(tmp_path, monkeypatch):
    _mock_convert(monkeypatch)
    calls = []

    def rc(page_id, page_md, status, *, root=None):
        calls.append((page_id, status))
        return {"page": page_id, "status": "ok", "problems": [], "error": None}

    res = pipeline.run_update(manifest_fn=lambda: [_manifest()[0]], fetch_html=_fetch,
                              root=tmp_path, recompress=True, recompress_impl=rc)
    assert calls == [("admin/A", "new")]
    assert res[0]["recompress"]["status"] == "ok"


def test_known_pages_passed_to_converter(tmp_path, monkeypatch):
    seen = {}

    def conv(html, *, page_id, url, known_pages=frozenset()):
        seen[page_id] = known_pages
        return "x\n"

    monkeypatch.setattr(pipeline.fetch, "convert_page", conv)
    pipeline.run_update(manifest_fn=_manifest, fetch_html=_fetch, root=tmp_path)
    assert seen["admin/A"] == frozenset({"admin/A", "user/B"})
```

- [ ] **Step 2: Прогнать — падает**

Run: `python3 -m pytest tools/tests/test_pipeline.py -v`
Expected: FAIL — модуль не существует.

- [ ] **Step 3: Реализация `tools/update/pipeline.py`**

```python
"""Оркестратор update: manifest → параллельный fetch/convert → дифф против pages/ →
черновики → (--recompress: страница + аннотация) → removed на полном прогоне.

Снапшотов нет: pages/<page_id>.md — и контент репозитория, и база сравнения.
Без --recompress прогон пишет только gitignored-черновики (detect-and-report чист по построению).
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from update import diff, fetch
from update.manifest import fetch_manifest as _fetch_manifest
from update.recompress import update_annotation as _update_annotation

REPO_ROOT = Path(__file__).resolve().parents[2]


def page_path(page_id: str, *, root: Path | None = None) -> Path:
    return (root if root is not None else REPO_ROOT) / "pages" / f"{page_id}.md"


def drafts_dir(root: Path | None = None) -> Path:
    return (root if root is not None else REPO_ROOT) / "tools" / "update" / "drafts"


def _write_draft(page_id: str, text: str, root: Path | None) -> None:
    p = drafts_dir(root) / f"{page_id}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def run_update(pages=None, *, fetch_html=None, manifest_fn=None, root: Path | None = None,
               recompress: bool = False, recompress_impl=None, jobs: int = 8) -> list:
    fetch_html = fetch_html or fetch.fetch_html
    manifest_fn = manifest_fn or _fetch_manifest
    impl = recompress_impl or _update_annotation

    entries = manifest_fn()
    known = frozenset(pid for pid, _ in entries)
    wanted = set(pages) if pages else None
    if wanted is not None:
        entries = [(pid, u) for pid, u in entries if pid in wanted]

    def _convert_one(entry):
        page_id, url = entry
        try:
            md = fetch.convert_page(fetch_html(url), page_id=page_id, url=url,
                                    known_pages=known)
            return page_id, md, None
        except Exception as e:  # noqa: BLE001 — сбой одной страницы не роняет прогон
            return page_id, None, str(e)

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        converted = list(ex.map(_convert_one, entries))

    results = []
    for page_id, new_md, err in converted:
        if err is not None:
            results.append({"page": page_id, "status": "error", "error": err})
            continue
        p = page_path(page_id, root=root)
        old_md = p.read_text(encoding="utf-8") if p.exists() else None
        status = diff.page_status(old_md, new_md)
        r = {"page": page_id, "status": status, "error": None}
        if status == "changed":
            r["diff"] = diff.body_diff(old_md, new_md)
        results.append(r)
        if status in ("new", "changed"):
            _write_draft(page_id, new_md, root)
            if recompress:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(new_md, encoding="utf-8")
                r["recompress"] = impl(page_id, new_md, status, root=root)

    if wanted is None:  # removed корректен только при полном наборе
        pages_root = (root if root is not None else REPO_ROOT) / "pages"
        if pages_root.exists():
            for f in sorted(pages_root.rglob("*.md")):
                pid = str(f.relative_to(pages_root)).replace("\\", "/")[:-3]
                if pid not in known:
                    results.append({"page": pid, "status": "removed", "error": None})
    return results
```

- [ ] **Step 4: Прогнать — зелено, весь офлайн-набор**

Run: `python3 -m pytest -v -m "not live"`
Expected: PASS — все тесты Tasks 2–8.

- [ ] **Step 5: Commit**

```bash
git add tools/update/pipeline.py tools/tests/test_pipeline.py
git commit -m "feat(update): pipeline — параллельный fetch, дифф против pages/, removed, recompress"
```

---

### Task 9: CLI (`wiki_cli`)

**Files:**
- Create: `tools/wiki_cli.py`
- Test: `tools/tests/test_cli.py`

**Interfaces:**
- Consumes: `pipeline.run_update`, `report.render`, `recompress.render_summary`, `manifest.ManifestError`.
- Produces: `python3 tools/wiki_cli.py update [--page P ...] [--recompress] [--report-file PATH] [--jobs N]`; `main(argv) -> int`; exit-коды `2` (ManifestError), `1` (ошибки страниц/модели или guard-проблемы), `0` (иначе).

- [ ] **Step 1: Написать падающие тесты `tools/tests/test_cli.py`**

```python
import wiki_cli
from update import manifest


def test_update_prints_report(monkeypatch, capsys):
    monkeypatch.setattr(wiki_cli.pipeline, "run_update",
                        lambda **kw: [{"page": "admin/A", "status": "new", "error": None}])
    assert wiki_cli.main(["update"]) == 0
    assert "Отчёт update" in capsys.readouterr().out


def test_manifest_error_exit_2(monkeypatch, capsys):
    def boom(**kw):
        raise manifest.ManifestError("sitemap пуст")
    monkeypatch.setattr(wiki_cli.pipeline, "run_update", boom)
    assert wiki_cli.main(["update"]) == 2
    assert "sitemap пуст" in capsys.readouterr().err


def test_fetch_error_exit_1(monkeypatch):
    monkeypatch.setattr(wiki_cli.pipeline, "run_update",
                        lambda **kw: [{"page": "a/b", "status": "error", "error": "x"}])
    assert wiki_cli.main(["update"]) == 1


def test_guard_problem_exit_1(monkeypatch):
    monkeypatch.setattr(wiki_cli.pipeline, "run_update", lambda **kw: [
        {"page": "admin/A", "status": "changed", "error": None,
         "recompress": {"page": "admin/A", "status": "ok",
                        "problems": ["битая ссылка: x"], "error": None}}])
    assert wiki_cli.main(["update", "--recompress"]) == 1


def test_clean_recompress_exit_0_with_summary(monkeypatch, capsys):
    monkeypatch.setattr(wiki_cli.pipeline, "run_update", lambda **kw: [
        {"page": "admin/A", "status": "changed", "error": None,
         "recompress": {"page": "admin/A", "status": "ok", "problems": [], "error": None}}])
    assert wiki_cli.main(["update", "--recompress"]) == 0
    assert "Пересжатие" in capsys.readouterr().out


def test_report_file_written(monkeypatch, tmp_path):
    monkeypatch.setattr(wiki_cli.pipeline, "run_update",
                        lambda **kw: [{"page": "a/b", "status": "unchanged", "error": None}])
    out = tmp_path / "r.md"
    assert wiki_cli.main(["update", "--report-file", str(out)]) == 0
    assert "Изменений нет." in out.read_text(encoding="utf-8")


def test_flags_passed_to_pipeline(monkeypatch):
    seen = {}

    def spy(**kw):
        seen.update(kw)
        return []

    monkeypatch.setattr(wiki_cli.pipeline, "run_update", spy)
    wiki_cli.main(["update", "--page", "admin/A", "--page", "user/B",
                   "--recompress", "--jobs", "4"])
    assert seen["pages"] == ["admin/A", "user/B"]
    assert seen["recompress"] is True and seen["jobs"] == 4
```

- [ ] **Step 2: Прогнать — падает**

Run: `python3 -m pytest tools/tests/test_cli.py -v`
Expected: FAIL — модуль `wiki_cli` не существует.

- [ ] **Step 3: Реализация `tools/wiki_cli.py`**

```python
"""CLI HubEx.Wiki. Использование: python3 tools/wiki_cli.py update [флаги]."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from update import manifest, pipeline, recompress, report  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wiki_cli", description="Пайплайн обновления HubEx.Wiki")
    sub = p.add_subparsers(dest="command", required=True)
    up = sub.add_parser("update",
                        help="дифф страниц вики против pages/ → отчёт; "
                             "--recompress пишет pages/ и аннотации индексов (unstaged)")
    up.add_argument("--page", action="append", default=None,
                    help="ограничить страницей <section>/<slug> (можно повторять; "
                         "removed при этом не вычисляется)")
    up.add_argument("--recompress", action="store_true",
                    help="перезаписать затронутые pages/** и обновить аннотации моделью (claude -p)")
    up.add_argument("--report-file", type=Path, default=None,
                    help="продублировать отчёт в файл")
    up.add_argument("--jobs", type=int, default=8,
                    help="параллельность HTTP-забора страниц (по умолчанию 8)")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "update":
        try:
            results = pipeline.run_update(pages=args.page, recompress=args.recompress,
                                          jobs=args.jobs)
        except manifest.ManifestError as e:
            print(f"ОШИБКА: {e}", file=sys.stderr)
            return 2
        text = report.render(results)
        print(text, end="")
        if args.recompress:
            print(recompress.render_summary(results), end="")
        if args.report_file:
            args.report_file.write_text(text, encoding="utf-8")
        has_err = any(r["status"] == "error" for r in results)
        rcs = [r.get("recompress") or {} for r in results]
        has_rc_err = any(rc.get("status") == "error" for rc in rcs)
        has_problems = any(rc.get("problems") for rc in rcs)
        return 1 if (has_err or has_rc_err or has_problems) else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Прогнать — зелено**

Run: `python3 -m pytest tools/tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/wiki_cli.py tools/tests/test_cli.py
git commit -m "feat(cli): update — подкоманда, флаги --page/--recompress/--report-file/--jobs"
```

---

### Task 10: Живой смоук-тест (`live`)

**Files:**
- Create: `tools/tests/test_live.py`

**Interfaces:**
- Consumes: `manifest.fetch_manifest`, `fetch` (реальная сеть).

- [ ] **Step 1: Написать живой тест `tools/tests/test_live.py`**

```python
import pytest

from update import fetch, manifest

pytestmark = pytest.mark.live


def test_sitemap_has_tracked_pages():
    entries = dict(manifest.fetch_manifest())
    assert "admin/BusinessProcess" in entries
    sections = {pid.split("/", 1)[0] for pid in entries}
    assert sections == {"admin", "user", "ReleaseNotes"}


def test_fetch_and_convert_business_process():
    entries = manifest.fetch_manifest()
    known = frozenset(pid for pid, _ in entries)
    url = dict(entries)["admin/BusinessProcess"]
    md = fetch.convert_page(fetch.fetch_html(url),
                            page_id="admin/BusinessProcess", url=url, known_pages=known)
    assert md.strip()
    assert 'section: "admin"' in md
    assert "crawled_at" not in md
    # картинка — абсолютная ссылка на вики
    assert "![" in md and "https://wiki.hubex.ru/attachments/" in md
    # тело статьи на месте
    assert "стади" in md.lower()
```

- [ ] **Step 2: Прогнать офлайн-набор — живой пропускается**

Run: `python3 -m pytest -v -m "not live"`
Expected: PASS; тесты из `test_live.py` — deselected.

- [ ] **Step 3: Прогнать живой смоук (если есть сеть)**

Run: `python3 -m pytest -v -m live`
Expected: PASS — sitemap отдаёт все три секции, BusinessProcess конвертируется, картинка абсолютная. Если сети нет — зафиксировать и пропустить (не блокирует).

- [ ] **Step 4: Commit**

```bash
git add tools/tests/test_live.py
git commit -m "test: живой смоук — sitemap + конвертация BusinessProcess"
```

---

### Task 11: Индексы — перенос аннотаций из монорепы

**Files:**
- Create: `index.md` (шапка + тематические секции из `wiki-index.md` монорепы, пути `wiki/` → `pages/`)
- Create: `releasenotes-index.md` (заготовка)

**Interfaces:**
- Consumes: `/root/projects/HubEx.AI-2.0/knowledge/product/wiki-index.md` (только чтение; монорепа не изменяется).
- Produces: `index.md` с ~136 строками-аннотациями, целями которых будут файлы `pages/**` (появятся при засеве в Task 13); `releasenotes-index.md` с секцией `## Новые страницы (разложить по темам)`, куда сплайсится Task 7. **Линтер ссылок в этой задаче не гоняем** — цели ссылок появятся при засеве.

- [ ] **Step 1: Сгенерировать `index.md` скриптом-однократкой**

Из корня репо (`/root/projects/HubEx.Wiki`):

```bash
python3 - <<'EOF'
from pathlib import Path

src = Path("/root/projects/HubEx.AI-2.0/knowledge/product/wiki-index.md").read_text(encoding="utf-8")
body = src[src.index("\n## "):]                 # тематические секции без старой шапки
body = body.replace("](wiki/", "](pages/")      # пути к страницам в новом репо

header = """# Индекс вики HubEx

> **Что здесь:** аннотированный каталог страниц вики HubEx (секции admin и user), по темам.
> **Когда сюда идти:** любой вопрос про поведение/настройку продукта HubEx.
> **Источник:** wiki.hubex.ru · Обновляется: `python3 tools/wiki_cli.py update --recompress`

Копии страниц — в [pages/](pages/). Страницы-«грабли» помечены ⚠.
Релиз-ноуты — в отдельном [releasenotes-index.md](releasenotes-index.md).
"""

Path("index.md").write_text(header + body, encoding="utf-8")
print("строк-аннотаций:", sum(1 for l in body.splitlines() if l.startswith("- [")))
EOF
```

Expected: `строк-аннотаций: 136` (число может отличаться на ±пару строк, если монорепа обновлялась — сверить с `grep -c '^- \[' /root/projects/HubEx.AI-2.0/knowledge/product/wiki-index.md`).

- [ ] **Step 2: Проверить, что старых путей не осталось**

Run: `grep -c "](wiki/" index.md || true`
Expected: `0`.

- [ ] **Step 3: Создать `releasenotes-index.md`**

```markdown
# Индекс релиз-ноутов HubEx

> **Что здесь:** каталог страниц раздела ReleaseNotes вики HubEx (по строке на релиз).
> **Когда сюда идти:** нужен факт про конкретный релиз или изменение версии.
> **Источник:** wiki.hubex.ru · Обновляется: `python3 tools/wiki_cli.py update --recompress`

Копии страниц — в [pages/ReleaseNotes/](pages/ReleaseNotes/).

## Новые страницы (разложить по темам)
```

- [ ] **Step 4: Commit**

```bash
git add index.md releasenotes-index.md
git commit -m "docs: индексы — перенос аннотаций admin/user из монорепы, заготовка релиз-ноутов"
```

---

### Task 12: Роутер-доки и линтер ссылок

**Files:**
- Create: `README.md`, `CLAUDE.md`, `AGENTS.md`, `tools/README.md`, `tools/lint/check_links.py`

**Interfaces:**
- Consumes: —
- Produces: роутер для агентов (три слоя: README → индексы → pages) и `python3 tools/lint/check_links.py` (exit 1 при битых относительных ссылках). **Линтер запускается в Task 13 после засева** — до него ссылки индексов на `pages/**` заведомо битые.

- [ ] **Step 1: Создать `README.md`**

```markdown
# HubEx.Wiki — вики HubEx для ИИ-агентов

> **Что здесь:** автономная копия вики HubEx (wiki.hubex.ru): вербатим-страницы, дистиллированные индексы и пайплайн обновления.
> **Когда сюда идти:** нужен факт о поведении или настройке продукта HubEx — начни с [index.md](index.md).

**HubEx** — облачная мультитенантная FSM-платформа (Field Service Management) для выездного обслуживания: заявки с жизненным циклом, объекты/оборудование, исполнители, SLA, чек-листы, акты, склад, аналитика.

## Слои

| Куда | Что там | Когда идти |
|---|---|---|
| [index.md](index.md) | аннотированный каталог страниц (admin+user) по темам | старт любого вопроса о продукте |
| [releasenotes-index.md](releasenotes-index.md) | каталог релиз-ноутов | «что нового/что изменилось в релизе X» |
| [pages/](pages/) | вербатим-копии страниц вики | полный текст по ссылке из индекса |

## Правила

- Страницы `pages/**` руками не правятся — их перезаписывает пайплайн. Правятся только индексы (точечно), README и tools.
- Не выдумывай факты о продукте: нет в страницах — так и скажи.
- URL страницы на вики: поле `url` во frontmatter; общее правило `pages/<section>/<slug>.md` ↔ `https://wiki.hubex.ru/docs/FAQ/RU/<section>/<slug>.html`.
- Кросс-ссылки между курируемыми страницами — локальные относительные; картинки и прочие ссылки — абсолютные URL вики.
- Страница пропала с вики → пайплайн помечает `removed` в отчёте; копию и строку индекса удаляет человек.

## Обновление

```
python3 tools/wiki_cli.py update [--page <section>/<slug>] [--recompress] [--report-file PATH] [--jobs N]
```

Без флагов — отчёт new/changed/removed (ничего не пишет). `--recompress` перезаписывает затронутые страницы и обновляет строки-аннотации индексов моделью; всё остаётся unstaged — ревью и коммит за человеком. Детали — [tools/README.md](tools/README.md).

## Комбинирование с другими доменами

Репозиторий автономен (лист): ссылок наружу нет, подключается сабмодулем в комбо-репозитории (вики+API и т.д.).

Мейнтейнер и единственный коммитер — Евгений Цветков.
```

- [ ] **Step 2: Создать `CLAUDE.md`**

```markdown
# Вход для Claude Code

Это автономная копия вики HubEx для ИИ-агентов. **Перед задачей прочитай [README.md](README.md).**

Критичное, дублируется намеренно:
- Вопрос о продукте → [index.md](index.md) (релиз-ноуты → [releasenotes-index.md](releasenotes-index.md)) → страница в `pages/`.
- `pages/**` руками не правь — их ведёт пайплайн (`python3 tools/wiki_cli.py update --recompress`).
- Не выдумывай факты о продукте: нет в страницах — так и скажи.
```

- [ ] **Step 3: Создать `AGENTS.md`**

```markdown
# Вход для агентов

Это автономная копия вики HubEx для ИИ-агентов. **Перед задачей прочитай [README.md](README.md).**

Критичное, дублируется намеренно:
- Вопрос о продукте → [index.md](index.md) (релиз-ноуты → [releasenotes-index.md](releasenotes-index.md)) → страница в `pages/`.
- `pages/**` руками не правь — их ведёт пайплайн (`python3 tools/wiki_cli.py update --recompress`).
- Не выдумывай факты о продукте: нет в страницах — так и скажи.
```

- [ ] **Step 4: Создать `tools/README.md`**

```markdown
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
```

- [ ] **Step 5: Создать `tools/lint/check_links.py`** (адаптация монорепного: `pages/` проверяются — кросс-ссылки в них локальные)

```python
"""Проверка относительных markdown-ссылок в репозитории. Выход 1, если есть битые."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)]*)?\)")
FENCE_RE = re.compile(r"^\s*`{3,}")
SKIP_PARTS = {".git", ".superpowers", "drafts"}


def strip_code_fences(text: str) -> str:
    """Убирает fenced code blocks — примеры в доках содержат ссылки будущих/чужих файлов."""
    out_lines, in_fence = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out_lines.append(line)
    return "\n".join(out_lines)


def main() -> int:
    broken = []
    for md in ROOT.rglob("*.md"):
        if SKIP_PARTS & set(md.parts):
            continue
        text = strip_code_fences(md.read_text(encoding="utf-8"))
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (md.parent / target).resolve().exists():
                broken.append(f"{md.relative_to(ROOT)} -> {target}")
    for b in broken:
        print(f"БИТАЯ ССЫЛКА: {b}")
    print(f"Проверено файлов: {len(list(ROOT.rglob('*.md')))}, битых ссылок: {len(broken)}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Commit**

```bash
git add README.md CLAUDE.md AGENTS.md tools/README.md tools/lint/check_links.py
git commit -m "docs: роутер (README/CLAUDE/AGENTS), tools/README, линтер ссылок"
```

---

### Task 13: Засев контента первым прогоном + проверки

**Files:**
- Create (прогоном): `pages/{admin,user,ReleaseNotes}/**` (~251 файл), аннотации ReleaseNotes в `releasenotes-index.md`
- Возможные точечные правки: `index.md` (новые admin/user-страницы, появившиеся на вики после 2026-07-02, попадут в секцию «Новые страницы»)

**Interfaces:**
- Consumes: весь пайплайн (Tasks 2–9), индексы (Task 11).
- Produces: наполненный репозиторий; идемпотентный `update`; чистый линтер.

- [ ] **Step 1: Засев**

Run: `python3 tools/wiki_cli.py update --recompress --report-file /tmp/claude-0/-root-projects-HubEx-Wiki/897c36b7-f795-48c1-9933-ce3636c07287/scratchpad/seed-report.md`
Expected: exit 0; в отчёте все страницы `new`; появились `pages/{admin,user,ReleaseNotes}/**`. Сводка пересжатия: admin/user из индекса — `skipped` (аннотации перенесены), ReleaseNotes и новые страницы — `ok`. **Замечание по времени:** ~113 вызовов `claude -p` последовательно — закладывать 30–90 минут; при падениях отдельных страниц (exit 1) — добрать точечно `--page <section>/<slug> --recompress`.

- [ ] **Step 2: Идемпотентность**

Run: `python3 tools/wiki_cli.py update`
Expected: «Изменений нет.», все `unchanged`, `git status` не показывает новых изменений после засева.

- [ ] **Step 3: Линтер ссылок**

Run: `python3 tools/lint/check_links.py`
Expected: `битых ссылок: 0`. Если есть битые в `pages/**` — это локализованные кросс-ссылки на страницы, не попавшие в курацию; разобраться (обычно — правка `_DENY_RE` или признание ссылки внешней) до коммита.

- [ ] **Step 4: Выборочная сверка с монорепой**

Run: `diff <(tail -n +8 /root/projects/HubEx.AI-2.0/knowledge/product/wiki/admin/TicketLifeCycle.md) <(tail -n +8 pages/admin/TicketLifeCycle.md) | head -40`
Expected: расхождения только форматные (разметка markdownify, локализованные ссылки) — тело статьи смыслово идентично. Повторить для 2–3 страниц из user/ (например `Filters`, `Checklists`).

- [ ] **Step 5: Полный офлайн-набор тестов**

Run: `python3 -m pytest -v -m "not live"`
Expected: PASS.

- [ ] **Step 6: Commit (человек ревьюит перед этим `git diff --stat`)**

```bash
git add pages index.md releasenotes-index.md
git commit -m "feat(content): засев вики первым прогоном update --recompress (~251 страница)"
```

---

## Self-Review

**Spec coverage (спека `2026-07-13-hubex-wiki-repo-design.md`):**
- §2 границы: контент+пайплайн (Tasks 2–9, 13); автономность/лист (Task 12 README, ссылок наружу нет); ReleaseNotes с отдельным индексом (Tasks 7, 11, 13); засев пайплайном (Task 13); монорепа только читается (Task 11); без снапшотов — дифф против `pages/` (Task 8); без `crawled_at` (Task 3); локальные кросс-ссылки + правило восстановления URL (Tasks 3, 12 README); группировка pages как в источнике (Tasks 2, 8); обзор не делаем (нет задачи — намеренно, §14 спеки).
- §3 структура: все файлы созданы Tasks 1 (каркас), 11 (индексы), 12 (доки, линт), 2–9 (tools).
- §4 поток данных: Task 8 (+ Task 9 CLI). Detect-and-report чист: без `--recompress` пишутся только gitignored-черновики.
- §5 компоненты: manifest(2), fetch(3), diff(4), report(5), model_client+guard(6), recompress+prompt(7), pipeline(8), CLI(9). Отклонение как в монорепе: отдельного `draft.py` нет — черновик пишет `pipeline._write_draft` (no-op-модуль, YAGNI). Улучшения сверх спеки: параллельный fetch (`--jobs`), guard проверяет и длину (спека §9 требовала лимит — реализован в `guard.problems`).
- §6 фильтр курации: Task 2 (секции, денилист, `page_id`).
- §7 конвертация: Task 3 (контейнер, чистка, абсолютизация, локализация, frontmatter, нормализация; ошибка при отсутствии контейнера).
- §8 дифф: Tasks 4, 8 (new/unchanged/changed + diff 3 строки контекста; removed только на полном прогоне; переименование = removed+new — спецкода нет, что и требуется).
- §9 пересжатие: Task 7 (механика страницы в pipeline Task 8; правило changed/new; сплайс; guard; всё unstaged; авто-коммита нет — YAGNI по спеке).
- §10 ошибки: ManifestError (Task 2, CLI exit 2 — Task 9); ошибка страницы изолирована, exit 1 (Tasks 8, 9); падение модели не трогает индекс (Task 7).
- §11 засев: Tasks 11 (перенос аннотаций, правка путей), 13 (засев, проверки, идемпотентность, сверка 3–5 страниц). Каркас — Tasks 1, 12.
- §12 CLI: Task 9 (все флаги; `--jobs` добавлен сверх спеки как улучшение).
- §13 тестирование: фикстуры sitemap/HTML (Tasks 2, 3), diff/report/guard/recompress/pipeline юниты (4–8), CLI (9), живой смоук (10), моки сети и модели везде, офлайн-набор зелёный.
- §14 «что дальше» — вне плана, как и в спеке.

**Placeholder scan:** плейсхолдеров нет — весь код, фикстуры, содержимое доков и команды приведены полностью.

**Type consistency:** результат страницы `{"page","status","error"[, "diff"][, "recompress"]}` — един в Tasks 8→5(render)→9(CLI). Результат аннотации `{"page","status"∈{ok,skipped,error},"problems","error"}` — Tasks 7→8(attach)→9(exit-логика)→7(render_summary). `convert_page(html, *, page_id, url, known_pages)` — Tasks 3→8→10. `update_annotation(page_id, page_md, status, *, model, root)` — Tasks 7→8 (fake с той же сигнатурой). `guard.problems(annotation, root)` — Tasks 6→7. `page_status`/`body_diff` — Tasks 4→8. `ManifestError` — Tasks 2→9. `link_target` = `pages/<page_id>.md` согласован с фикстурами тестов Task 7 и путями Task 11 (`](pages/...`).
