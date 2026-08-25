# Сжатый однофайловый контекст HubEx — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Собирать из вики один файл ~110 тыс. символов, который прикрепляется в чат или проект любого облачного ИИ-агента и обновляется ночью вместе с `sync`.

**Architecture:** Разделы в два яруса. Ярус 1 генерируется моделью из страниц вики по карте `context/map.tsv`; ярус 2 — из текстов яруса 1. Разделы лежат в git как `context/sections/*.md` и перегенерируются целиком (не патчатся), когда изменился их источник. Итоговый файл собирается детерминированно, без модели.

**Tech Stack:** Python 3, stdlib + `requests` (уже в зависимостях), `claude -p` для вызова модели, pytest.

**Spec:** [docs/superpowers/specs/2026-08-25-compact-context-design.md](../specs/2026-08-25-compact-context-design.md)

## Global Constraints

- Код — в репозитории пайплайна `HubEx.Wiki.Pipeline`, подключённом сабмодулем в `tools/`. Пути ниже даны от корня контент-репозитория.
- Новый пакет — `tools/compact/`. Трогать `tools/update/` только там, где сказано явно.
- Данные и артефакты — в контент-репозитории: карта `context/map.tsv`, разделы `context/sections/*.md`, готовый файл `hubex-context.md` в корне. Всё коммитится.
- Целевой размер файла — **110 000 символов**, коридор **99 000–121 000** (±10%). Бюджет раздела — жёсткий потолок.
- Модель вызывается **явно на Opus**, а не на дефолте `claude -p`.
- Стиль кода — как в `tools/update/`: чистые модули, докстринг на русском первой строкой, инъекция зависимостей через именованные аргументы со значением `None`, guard-ы возвращают `list[str]` отсортированных сообщений, тесты на `tmp_path` без моков.
- Тесты не ходят в сеть и не зовут модель. Модель инъектируется параметром `model=`.
- Прогон офлайн-набора: `python3 -m pytest -v -m "not live"` из каталога `tools/`.

---

### Task 1: Карта разделов — формат, чтение, валидация

**Files:**
- Create: `tools/compact/__init__.py`
- Create: `tools/compact/sectionmap.py`
- Create: `context/map.tsv`
- Test: `tools/tests/test_compact_map.py`

**Interfaces:**
- Consumes: ничего.
- Produces:
  - `sectionmap.parse(text: str) -> list[dict]` — каждый раздел `{"id": str, "title": str, "budget": int, "sources": list[str], "tier": 1|2}`.
  - `sectionmap.load(root: Path | None = None) -> list[dict]` — читает `context/map.tsv`.
  - `sectionmap.problems(sections: list[dict], root: Path) -> list[str]`.
  - `sectionmap.affected(sections: list[dict], changed_pages: set[str]) -> list[str]` — id разделов к перегенерации, ярус 1 раньше яруса 2.

- [ ] **Step 1: Написать падающий тест на разбор и ярусы**

Создать `tools/tests/test_compact_map.py`:

```python
from pathlib import Path

from compact import sectionmap

MAP = (
    "s01\tЖизненный цикл\t4400\tadmin/BusinessProcess admin/StageType\n"
    "s02\tТипы заявок\t4000\tadmin/TicketType\n"
    "t01\tКарта сущностей\t6000\t@s01 @s02\n"
    "t03\tОграничения-стоперы\t3000\t@все\n"
)


def test_parse_splits_tiers():
    secs = sectionmap.parse(MAP)
    assert [s["id"] for s in secs] == ["s01", "s02", "t01", "t03"]
    assert [s["tier"] for s in secs] == [1, 1, 2, 2]
    assert secs[0]["budget"] == 4400
    assert secs[0]["sources"] == ["admin/BusinessProcess", "admin/StageType"]
    assert secs[2]["sources"] == ["@s01", "@s02"]


def test_parse_skips_blank_and_comment_lines():
    text = "# комментарий\n\n" + MAP
    assert len(sectionmap.parse(text)) == 4
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `cd tools && python3 -m pytest tests/test_compact_map.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'compact'`

- [ ] **Step 3: Минимальная реализация разбора**

Создать `tools/compact/__init__.py` пустым файлом.

Создать `tools/compact/sectionmap.py`:

```python
"""Карта разделов сжатого контекста: разбор, валидация, вычисление затронутого. Чистый модуль."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAP_REL = "context/map.tsv"
ALL_TIER1 = "@все"


def _root(root):
    return root if root is not None else REPO_ROOT


def parse(text: str) -> list:
    """Строки `id \\t название \\t бюджет \\t источники`. Источник с '@' — ссылка на раздел (ярус 2)."""
    out = []
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            raise ValueError(f"строка карты не из 4 полей: {line!r}")
        sid, title, budget, sources = (p.strip() for p in parts)
        src = sources.split()
        out.append({"id": sid, "title": title, "budget": int(budget),
                    "sources": src, "tier": 2 if any(s.startswith("@") for s in src) else 1})
    return out


def load(root: Path | None = None) -> list:
    return parse((_root(root) / MAP_REL).read_text(encoding="utf-8"))
```

- [ ] **Step 4: Убедиться, что тест проходит**

Run: `cd tools && python3 -m pytest tests/test_compact_map.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Написать падающий тест на валидацию**

Дописать в `tools/tests/test_compact_map.py`:

```python
def _mkpages(tmp_path, ids):
    for pid in ids:
        p = tmp_path / "pages" / f"{pid}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("тело", encoding="utf-8")


def test_problems_clean(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess", "admin/StageType", "admin/TicketType"])
    assert sectionmap.problems(sectionmap.parse(MAP), tmp_path) == []


def test_uncovered_lists_pages_outside_map(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess", "admin/StageType",
                        "admin/TicketType", "user/Забытая"])
    secs = sectionmap.parse(MAP)
    assert sectionmap.uncovered(secs, tmp_path) == ["user/Забытая"]
    assert sectionmap.problems(secs, tmp_path) == []


def test_problems_missing_page_and_duplicate_and_bad_ref(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess", "admin/StageType", "admin/TicketType"])
    bad = MAP + "s03\tДубль\t1500\tadmin/TicketType\n" \
                "t02\tБитая\t1500\t@s99\n"
    probs = sectionmap.problems(sectionmap.parse(bad), tmp_path)
    assert "страница в карте дважды: admin/TicketType (s02, s03)" in probs
    assert "раздел t02 ссылается на несуществующий раздел s99" in probs


def test_problems_tier2_cannot_depend_on_tier2(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess", "admin/StageType", "admin/TicketType"])
    bad = MAP + "t02\tВложенный\t1500\t@t01\n"
    probs = sectionmap.problems(sectionmap.parse(bad), tmp_path)
    assert "раздел t02 зависит от раздела яруса 2: t01" in probs
```

- [ ] **Step 6: Убедиться, что тесты падают**

Run: `cd tools && python3 -m pytest tests/test_compact_map.py -v`
Expected: FAIL, `AttributeError: module 'compact.sectionmap' has no attribute 'problems'`

- [ ] **Step 7: Реализовать валидацию**

Дописать в `tools/compact/sectionmap.py`:

```python
def _wiki_pages(root: Path) -> set:
    base = _root(root) / "pages"
    return {f"{d.name}/{p.stem}" for d in base.iterdir() if d.is_dir() and d.name != "ReleaseNotes"
            for p in d.glob("*.md")}


def problems(sections: list, root: Path) -> list:
    """Потери, дубли, битые ссылки между разделами, недопустимая вложенность ярусов."""
    out = []
    ids = {s["id"] for s in sections}
    tier_of = {s["id"]: s["tier"] for s in sections}
    seen = {}
    for s in sections:
        if s["tier"] == 1:
            for pid in s["sources"]:
                if pid in seen:
                    out.append(f"страница в карте дважды: {pid} ({seen[pid]}, {s['id']})")
                else:
                    seen[pid] = s["id"]
        else:
            for ref in s["sources"]:
                if ref == ALL_TIER1:
                    continue
                target = ref[1:]
                if target not in ids:
                    out.append(f"раздел {s['id']} ссылается на несуществующий раздел {target}")
                elif tier_of.get(target) == 2:
                    out.append(f"раздел {s['id']} зависит от раздела яруса 2: {target}")
    for pid in sorted(set(seen) - _wiki_pages(root)):
        out.append(f"раздел {seen[pid]} ссылается на несуществующую страницу {pid}")
    return sorted(set(out))


def uncovered(sections: list, root: Path) -> list:
    """Страницы вики, не попавшие ни в один раздел. Не ошибка: уходят в «Ещё не разложено»."""
    placed = {pid for s in sections if s["tier"] == 1 for pid in s["sources"]}
    return sorted(_wiki_pages(root) - placed)
```

- [ ] **Step 8: Убедиться, что тесты проходят**

Run: `cd tools && python3 -m pytest tests/test_compact_map.py -v`
Expected: PASS (6 passed)

- [ ] **Step 9: Написать падающий тест на вычисление затронутого**

Дописать в `tools/tests/test_compact_map.py`:

```python
def test_affected_tier1_then_tier2():
    secs = sectionmap.parse(MAP)
    assert sectionmap.affected(secs, {"admin/StageType"}) == ["s01", "t01", "t03"]


def test_affected_all_tier1_marker_fires_on_any_change():
    secs = sectionmap.parse(MAP)
    assert "t03" in sectionmap.affected(secs, {"admin/TicketType"})


def test_affected_empty_when_nothing_changed():
    assert sectionmap.affected(sectionmap.parse(MAP), set()) == []
```

- [ ] **Step 10: Убедиться, что тесты падают**

Run: `cd tools && python3 -m pytest tests/test_compact_map.py -v`
Expected: FAIL, `AttributeError: ... has no attribute 'affected'`

- [ ] **Step 11: Реализовать вычисление затронутого**

Дописать в `tools/compact/sectionmap.py`:

```python
def affected(sections: list, changed_pages: set) -> list:
    """Id разделов к перегенерации: сперва ярус 1, затем зависящий от него ярус 2."""
    if not changed_pages:
        return []
    t1 = [s["id"] for s in sections
          if s["tier"] == 1 and set(s["sources"]) & set(changed_pages)]
    if not t1:
        return []
    hit = set(t1)
    t2 = [s["id"] for s in sections if s["tier"] == 2
          and (ALL_TIER1 in s["sources"]
               or any(r[1:] in hit for r in s["sources"] if r != ALL_TIER1))]
    return t1 + t2
```

- [ ] **Step 12: Убедиться, что тесты проходят**

Run: `cd tools && python3 -m pytest tests/test_compact_map.py -v`
Expected: PASS (9 passed)

- [ ] **Step 13: Создать реальную карту**

Создать `context/map.tsv` в контент-репозитории. Разделители — табуляции. Ярус 1 — 24 раздела, покрывающие все 137 страниц `pages/admin` и `pages/user`; ярус 2 — 4 раздела. Бюджеты распределены по значимости, не пропорционально числу страниц: сумма яруса 1 — 88 000, яруса 2 — 21 000.

Взять состав разделов и распределение страниц из эксперимента: `s01`–`s24` в том же виде, что и в `MAP.tsv` скретчпада сессии (24 раздела, 137 страниц, ноль дублей). Бюджеты пересчитать по значимости:

- поднять: `s01` 4400→6000, `s09` 5400→6500, `s12` 3200→5000, `s21` 4000→5500 (ЖЦ, роли и участки, SLA и автоназначение, платформа и деплой — самые запрашиваемые продажами);
- срезать: `s17` 5100→3000, `s22` 3400→2200, `s15` 2300→1800 (уведомления, геонастройки устройств, печатные формы — детализация продажам не нужна);
- остальные подогнать так, чтобы сумма яруса 1 дала 88 000.

Ярус 2 добавить строками:

```
t01	Карта сущностей и связей	6000	@s01 @s02 @s06 @s07 @s09 @s12
t02	Паттерны посадки процессов клиента	9000	@s01 @s04 @s05 @s09 @s11 @s12 @s16 @s23
t03	Ограничения-стоперы	3000	@все
t04	Позиционирование против смежных классов	3000	@s21
```

- [ ] **Step 14: Написать тест на реальную карту**

Дописать в `tools/tests/test_compact_map.py`:

```python
def test_real_map_is_valid():
    secs = sectionmap.load()
    assert sectionmap.problems(secs, sectionmap.REPO_ROOT) == []


def test_real_map_covers_every_page():
    secs = sectionmap.load()
    assert sectionmap.uncovered(secs, sectionmap.REPO_ROOT) == []


def test_real_map_budget_within_target():
    secs = sectionmap.load()
    t1 = sum(s["budget"] for s in secs if s["tier"] == 1)
    t2 = sum(s["budget"] for s in secs if s["tier"] == 2)
    assert 85_000 <= t1 <= 91_000, t1
    assert 19_000 <= t2 <= 23_000, t2
```

- [ ] **Step 15: Убедиться, что все тесты проходят**

Run: `cd tools && python3 -m pytest tests/test_compact_map.py -v`
Expected: PASS (12 passed). Если `test_real_map_covers_every_page` падает — дописать страницу в подходящий раздел карты; это штатная реакция на новую страницу вики.

- [ ] **Step 16: Коммит**

```bash
cd tools && git add compact/__init__.py compact/sectionmap.py tests/test_compact_map.py
git commit -m "feat(compact): карта разделов — разбор, валидация, вычисление затронутого"
cd .. && git add context/map.tsv
git commit -m "feat(compact): карта разделов сжатого контекста (24 + 4 раздела, 137 страниц)"
```

---

### Task 2: Guard раздела и собранного файла

**Files:**
- Create: `tools/compact/guard.py`
- Test: `tools/tests/test_compact_guard.py`

**Interfaces:**
- Consumes: `sectionmap.parse` (Task 1).
- Produces:
  - `guard.section_problems(text: str, section: dict, root: Path) -> list[str]`
  - `guard.file_problems(text: str, sections: list[dict], root: Path) -> list[str]`
  - `guard.MIN_CHARS = 99_000`, `guard.MAX_CHARS = 121_000`

- [ ] **Step 1: Написать падающий тест на проверки раздела**

Создать `tools/tests/test_compact_guard.py`:

```python
from compact import guard, sectionmap

SEC = {"id": "s01", "title": "Жизненный цикл", "budget": 300,
       "sources": ["admin/BusinessProcess"], "tier": 1}

GOOD = (
    "## Жизненный цикл\n\nВводная фраза.\n\n"
    "**Модель.** Стадия и Статус. [admin/BusinessProcess]\n\n"
    "**Настройка.** Путь: Настройки заявки → Стадии.\n\n"
    "**Ограничения.** Один цикл на тип.\n\n"
    "Источники: [admin/BusinessProcess]\n"
)


def _mkpages(tmp_path, ids):
    for pid in ids:
        p = tmp_path / "pages" / f"{pid}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("тело", encoding="utf-8")


def test_clean_section(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess"])
    assert guard.section_problems(GOOD, SEC, tmp_path) == []


def test_budget_exceeded(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess"])
    text = GOOD.replace("Вводная фраза.", "Вводная фраза. " + "длинно " * 100)
    probs = guard.section_problems(text, SEC, tmp_path)
    assert any(p.startswith("бюджет") for p in probs)


def test_missing_required_block(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess"])
    text = GOOD.replace("**Ограничения.** Один цикл на тип.\n\n", "")
    assert "нет обязательного блока «Ограничения»" in guard.section_problems(text, SEC, tmp_path)


def test_broken_page_ref(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess"])
    text = GOOD.replace("Источники: [admin/BusinessProcess]",
                        "Источники: [admin/BusinessProcess] [user/Призрак]")
    assert "битая ссылка на страницу: user/Призрак" in guard.section_problems(text, SEC, tmp_path)


def test_wrong_heading(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess"])
    text = GOOD.replace("## Жизненный цикл", "## Что-то другое")
    probs = guard.section_problems(text, SEC, tmp_path)
    assert any(p.startswith("заголовок") for p in probs)
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd tools && python3 -m pytest tests/test_compact_guard.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'compact.guard'`

- [ ] **Step 3: Реализовать guard раздела**

Создать `tools/compact/guard.py`:

```python
"""Детерминированные проверки разделов и собранного файла сжатого контекста. Чистый модуль."""
import re
from pathlib import Path

MIN_CHARS = 99_000
MAX_CHARS = 121_000
REQUIRED_BLOCKS = ("Модель", "Настройка", "Ограничения")

_REF_RE = re.compile(r"\[(admin|user)/([^\]\s]+)\]")
_SECTION_ID_RE = re.compile(r"(?<![\w@])([st]\d{2})(?![\w])")


def _page_refs(text: str) -> set:
    return {f"{a}/{b}" for a, b in _REF_RE.findall(text)}


def section_problems(text: str, section: dict, root: Path) -> list:
    out = []
    lines = text.lstrip().splitlines()
    head = lines[0] if lines else ""
    if head.strip() != f"## {section['title']}":
        out.append(f"заголовок {head.strip()!r} не совпадает с названием из карты "
                   f"{'## ' + section['title']!r}")
    if len(text) > section["budget"]:
        out.append(f"бюджет превышен: {len(text)} > {section['budget']}")
    for block in REQUIRED_BLOCKS:
        if f"**{block}.**" not in text:
            out.append(f"нет обязательного блока «{block}»")
    if not re.search(r"^Источники:", text, flags=re.M):
        out.append("нет строки «Источники:»")
    for pid in sorted(_page_refs(text)):
        if not (root / "pages" / f"{pid}.md").exists():
            out.append(f"битая ссылка на страницу: {pid}")
    return sorted(set(out))
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd tools && python3 -m pytest tests/test_compact_guard.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Написать падающий тест на проверки файла**

Дописать в `tools/tests/test_compact_guard.py`:

```python
MAP = ("s01\tЖизненный цикл\t300\tadmin/BusinessProcess\n"
       "t01\tКарта сущностей\t300\t@s01\n")


def test_file_flags_unsubstituted_section_id(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess"])
    secs = sectionmap.parse(MAP)
    text = "## Жизненный цикл\n\nПодробности — s04.\n" + "x" * MIN_CHARS
    assert "в тексте остался внутренний id раздела: s04" in guard.file_problems(text, secs, tmp_path)


def test_file_flags_size_below_corridor(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess"])
    secs = sectionmap.parse(MAP)
    probs = guard.file_problems("## Жизненный цикл\n\nкоротко\n", secs, tmp_path)
    assert any(p.startswith("размер файла") for p in probs)


def test_file_flags_missing_section(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess"])
    secs = sectionmap.parse(MAP)
    text = "## Жизненный цикл\n\n" + "x" * MIN_CHARS
    assert "раздела нет в файле: t01 (Карта сущностей)" in guard.file_problems(text, secs, tmp_path)
```

- [ ] **Step 6: Убедиться, что тесты падают**

Run: `cd tools && python3 -m pytest tests/test_compact_guard.py -v`
Expected: FAIL, `AttributeError: module 'compact.guard' has no attribute 'file_problems'`

- [ ] **Step 7: Реализовать guard файла**

Дописать в `tools/compact/guard.py`:

```python
def file_problems(text: str, sections: list, root: Path) -> list:
    """Собранный файл: размер в коридоре, все разделы на месте, id разделов подменены."""
    out = []
    if not (MIN_CHARS <= len(text) <= MAX_CHARS):
        out.append(f"размер файла {len(text)} вне коридора {MIN_CHARS}–{MAX_CHARS}")
    titles = set(re.findall(r"^## (.+)$", text, flags=re.M))
    for s in sections:
        if s["title"] not in titles:
            out.append(f"раздела нет в файле: {s['id']} ({s['title']})")
    for sid in sorted(set(_SECTION_ID_RE.findall(text))):
        out.append(f"в тексте остался внутренний id раздела: {sid}")
    for pid in sorted(_page_refs(text)):
        if not (root / "pages" / f"{pid}.md").exists():
            out.append(f"битая ссылка на страницу: {pid}")
    return sorted(set(out))
```

- [ ] **Step 8: Убедиться, что тесты проходят**

Run: `cd tools && python3 -m pytest tests/test_compact_guard.py -v`
Expected: PASS (8 passed)

- [ ] **Step 9: Коммит**

```bash
cd tools && git add compact/guard.py tests/test_compact_guard.py
git commit -m "feat(compact): guard раздела и собранного файла"
```

---

### Task 3: Даты релиз-ноутов и отбор последних N

**Files:**
- Create: `tools/compact/releases.py`
- Test: `tools/tests/test_compact_releases.py`

**Interfaces:**
- Consumes: ничего.
- Produces:
  - `releases.date_from_slug(slug: str) -> str | None` — ISO-дата или `None`.
  - `releases.date_from_title(title: str) -> str | None`
  - `releases.git_first_seen(page_id: str, root: Path, *, run=None) -> str | None`
  - `releases.resolve(page_id: str, root: Path, *, run=None) -> str | None`
  - `releases.latest(n: int, root: Path, *, run=None) -> tuple[list[tuple[str, str]], list[str]]` — `(отобранные [(page_id, iso_date)], без даты [page_id])`
  - `releases.OVERRIDES_REL = "context/release-dates.tsv"`

- [ ] **Step 1: Написать падающий тест на разбор дат**

Создать `tools/tests/test_compact_releases.py`:

```python
from compact import releases


def test_date_from_slug_ddmmyyyy():
    assert releases.date_from_slug("ListOfChanges24082026") == "2026-08-24"
    assert releases.date_from_slug("SLA25062021") == "2021-06-25"


def test_date_from_slug_dotted_short_year():
    assert releases.date_from_slug("TaskTypeInCalendarFilter22.05.25") == "2025-05-22"


def test_date_from_slug_rejects_nonsense():
    assert releases.date_from_slug("CustomerApp") is None
    assert releases.date_from_slug("Video99999999") is None


def test_date_from_title():
    assert releases.date_from_title("SLA в HubEx: обновление от 25.06.2021") == "2021-06-25"
    assert releases.date_from_title("Обновления мобильного приложения") is None
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd tools && python3 -m pytest tests/test_compact_releases.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'compact.releases'`

- [ ] **Step 3: Реализовать разбор дат**

Создать `tools/compact/releases.py`:

```python
"""Дата релиз-ноута и отбор последних N. Дата из git (первое появление) с фолбэком на slug/заголовок."""
import re
import subprocess
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OVERRIDES_REL = "context/release-dates.tsv"
_SECTION = "ReleaseNotes"

_DDMMYYYY_RE = re.compile(r"(\d{2})(\d{2})(20\d{2})")
_DOTTED_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{2}(?:\d{2})?)")


def _root(root):
    return root if root is not None else REPO_ROOT


def _mk(d, m, y) -> str | None:
    y = int(y)
    if y < 100:
        y += 2000
    try:
        return date(y, int(m), int(d)).isoformat()
    except ValueError:
        return None


def date_from_slug(slug: str) -> str | None:
    m = _DOTTED_RE.search(slug)
    if m:
        return _mk(m.group(1), m.group(2), m.group(3))
    m = _DDMMYYYY_RE.search(slug)
    if m:
        return _mk(m.group(1), m.group(2), m.group(3))
    return None


def date_from_title(title: str) -> str | None:
    m = re.search(r"(\d{2})\.(\d{2})\.(20\d{2})", title)
    return _mk(m.group(1), m.group(2), m.group(3)) if m else None
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd tools && python3 -m pytest tests/test_compact_releases.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Написать падающий тест на приоритет источников и отбор**

Дописать в `tools/tests/test_compact_releases.py`:

```python
def _mkrn(tmp_path, slug, title="Без даты", body="тело"):
    p = tmp_path / "pages" / "ReleaseNotes" / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'---\ntitle: "{title}"\n---\n\n{body}\n', encoding="utf-8")


def test_resolve_prefers_git_over_slug(tmp_path):
    _mkrn(tmp_path, "SLA25062021")
    run = lambda args, cwd: "2026-03-01"
    assert releases.resolve("ReleaseNotes/SLA25062021", tmp_path, run=run) == "2026-03-01"


def test_resolve_falls_back_to_slug_then_title(tmp_path):
    _mkrn(tmp_path, "SLA25062021")
    _mkrn(tmp_path, "CustomerApp", title="Релиз от 03.02.2024")
    run = lambda args, cwd: ""
    assert releases.resolve("ReleaseNotes/SLA25062021", tmp_path, run=run) == "2021-06-25"
    assert releases.resolve("ReleaseNotes/CustomerApp", tmp_path, run=run) == "2024-02-03"


def test_resolve_none_when_nothing_works(tmp_path):
    _mkrn(tmp_path, "CustomerApp")
    assert releases.resolve("ReleaseNotes/CustomerApp", tmp_path, run=lambda a, c: "") is None


def test_latest_sorts_desc_and_reports_undated(tmp_path):
    _mkrn(tmp_path, "SLA25062021")
    _mkrn(tmp_path, "ListOfChanges24082026")
    _mkrn(tmp_path, "CustomerApp")
    picked, undated = releases.latest(2, tmp_path, run=lambda a, c: "")
    assert [p for p, _ in picked] == ["ReleaseNotes/ListOfChanges24082026",
                                      "ReleaseNotes/SLA25062021"]
    assert undated == ["ReleaseNotes/CustomerApp"]


def test_override_wins_over_everything(tmp_path):
    _mkrn(tmp_path, "CustomerApp")
    ov = tmp_path / releases.OVERRIDES_REL
    ov.parent.mkdir(parents=True, exist_ok=True)
    ov.write_text("ReleaseNotes/CustomerApp\t2025-12-31\n", encoding="utf-8")
    assert releases.resolve("ReleaseNotes/CustomerApp", tmp_path, run=lambda a, c: "2020-01-01") \
        == "2025-12-31"
```

- [ ] **Step 6: Убедиться, что тесты падают**

Run: `cd tools && python3 -m pytest tests/test_compact_releases.py -v`
Expected: FAIL, `AttributeError: module 'compact.releases' has no attribute 'resolve'`

- [ ] **Step 7: Реализовать git-дату, оверрайды и отбор**

Дописать в `tools/compact/releases.py`:

```python
def _git(args: list, cwd: Path) -> str:
    try:
        p = subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True,
                           text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return p.stdout.strip() if p.returncode == 0 else ""


def git_first_seen(page_id: str, root: Path, *, run=None) -> str | None:
    run = run or _git
    out = run(["log", "--diff-filter=A", "--format=%as", "--", f"pages/{page_id}.md"],
              _root(root))
    lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
    return lines[-1] if lines else None


def _overrides(root: Path) -> dict:
    p = _root(root) / OVERRIDES_REL
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        pid, _, iso = line.partition("\t")
        out[pid.strip()] = iso.strip()
    return out


def _title(page_id: str, root: Path) -> str:
    text = (_root(root) / "pages" / f"{page_id}.md").read_text(encoding="utf-8")
    m = re.search(r'^title:\s*"(.*)"\s*$', text, flags=re.M)
    return m.group(1) if m else ""


def resolve(page_id: str, root: Path, *, run=None) -> str | None:
    """Приоритет: ручной оверрайд → git (первое появление) → дата в slug → дата в заголовке."""
    ov = _overrides(root).get(page_id)
    if ov:
        return ov
    return (git_first_seen(page_id, root, run=run)
            or date_from_slug(page_id.split("/", 1)[1])
            or date_from_title(_title(page_id, root)))


def latest(n: int, root: Path, *, run=None) -> tuple:
    """(последние n релизов [(page_id, iso)], страницы без определённой даты)."""
    base = _root(root) / "pages" / _SECTION
    if not base.exists():
        return [], []
    dated, undated = [], []
    for p in sorted(base.glob("*.md")):
        pid = f"{_SECTION}/{p.stem}"
        iso = resolve(pid, root, run=run)
        (dated.append((pid, iso)) if iso else undated.append(pid))
    dated.sort(key=lambda t: t[1], reverse=True)
    return dated[:n], undated
```

- [ ] **Step 8: Убедиться, что тесты проходят**

Run: `cd tools && python3 -m pytest tests/test_compact_releases.py -v`
Expected: PASS (9 passed)

- [ ] **Step 9: Коммит**

```bash
cd tools && git add compact/releases.py tests/test_compact_releases.py
git commit -m "feat(compact): дата релиз-ноута из git с фолбэком на slug/заголовок, отбор последних N"
```

---

### Task 4: Детерминированная сборка файла

**Files:**
- Create: `tools/compact/assemble.py`
- Test: `tools/tests/test_compact_assemble.py`

**Interfaces:**
- Consumes: `sectionmap.parse` (Task 1), `releases.latest` (Task 3).
- Produces:
  - `assemble.build_header(built_on: str) -> str`
  - `assemble.substitute_ids(text: str, id_to_title: dict) -> str`
  - `assemble.build_releases_block(picked: list, root: Path) -> str`
  - `assemble.build(sections: list, texts: dict, *, releases_block: str, built_on: str) -> str`
  - `assemble.OUT_REL = "hubex-context.md"`, `assemble.SECTIONS_DIR_REL = "context/sections"`
  - `assemble.section_path(sid: str, root: Path) -> Path`

- [ ] **Step 1: Написать падающий тест на подмену id и порядок**

Создать `tools/tests/test_compact_assemble.py`:

```python
from compact import assemble, sectionmap

MAP = ("s01\tЖизненный цикл\t300\tadmin/BusinessProcess\n"
       "s02\tТипы заявок\t300\tadmin/TicketType\n"
       "t01\tКарта сущностей\t300\t@s01 @s02\n")


def test_substitute_ids_replaces_known_only():
    m = {"s01": "Жизненный цикл", "s02": "Типы заявок"}
    src = "Механика — s01. Также s02 и s99 и слово rs01."
    got = assemble.substitute_ids(src, m)
    assert got == ("Механика — «Жизненный цикл». Также «Типы заявок» и s99 и слово rs01.")


def test_build_orders_sections_by_map_and_puts_releases_last():
    secs = sectionmap.parse(MAP)
    texts = {"s01": "## Жизненный цикл\n\nА\n",
             "s02": "## Типы заявок\n\nБ\n",
             "t01": "## Карта сущностей\n\nВ\n"}
    out = assemble.build(secs, texts, releases_block="## Последние релизы\n\nР\n",
                         built_on="2026-08-25")
    assert out.index("## Жизненный цикл") < out.index("## Типы заявок")
    assert out.index("## Типы заявок") < out.index("## Карта сущностей")
    assert out.index("## Карта сущностей") < out.index("## Последние релизы")


def test_header_carries_link_rule_and_date():
    h = assemble.build_header("2026-08-25")
    assert "https://wiki.hubex.ru/docs/FAQ/RU/{section}/{slug}.html" in h
    assert "2026-08-25" in h
    assert "в вике этого нет" in h
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd tools && python3 -m pytest tests/test_compact_assemble.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'compact.assemble'`

- [ ] **Step 3: Реализовать сборку**

Создать `tools/compact/assemble.py`:

```python
"""Детерминированная сборка сжатого контекста: шапка, разделы по карте, релизы. Модель не нужна."""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_REL = "hubex-context.md"
SECTIONS_DIR_REL = "context/sections"

_SECTION_ID_RE = re.compile(r"(?<![\w@])([st]\d{2})(?![\w])")


def _root(root):
    return root if root is not None else REPO_ROOT


def section_path(sid: str, root: Path | None = None) -> Path:
    return _root(root) / SECTIONS_DIR_REL / f"{sid}.md"


def build_header(built_on: str) -> str:
    return (
        "# HubEx — сжатый контекст продукта\n\n"
        "**Что это.** Единственный источник знаний о продукте HubEx (вендор HubEx, hubex.ru) "
        "для ИИ-агента. Собрано из публичной вики wiki.hubex.ru, разделы `admin` и `user`. "
        f"Дата сборки: {built_on}.\n\n"
        "**Ссылки.** В тексте — короткие id вида `[admin/SLA]`, `[user/CreatingTicket]`. "
        "Разворачивать в URL по правилу "
        "`https://wiki.hubex.ru/docs/FAQ/RU/{section}/{slug}.html`. "
        "Полные URL в теле не приводятся.\n\n"
        "**Правило ответа.** Отвечать только фактами из этого файла. Если факта нет — сказать "
        "«в вике этого нет» и предложить проверить первоисточник по ссылке раздела. "
        "Не додумывать, не обобщать, не переносить на HubEx логику других FSM- и "
        "Help Desk-систем.\n\n"
        "**Актуальность.** Блок «Последние релизы» опережает основные разделы: фича может быть "
        "уже выпущена и описана в релизе, а страница вики ещё не обновлена. При расхождении "
        "«вика молчит, а клиент говорит, что фича есть» — не отрицать, а предложить сверку.\n\n"
        "---\n"
    )


def substitute_ids(text: str, id_to_title: dict) -> str:
    """Заменяет внутренние id разделов на их названия: читающему агенту `s04` ничего не говорит."""
    return _SECTION_ID_RE.sub(
        lambda m: f"«{id_to_title[m.group(1)]}»" if m.group(1) in id_to_title else m.group(0),
        text)


def build_releases_block(picked: list, root: Path | None = None) -> str:
    if not picked:
        return ""
    out = ["## Последние релизы", "",
           "Опережающий слой: описанное здесь может ещё не попасть в разделы выше.", ""]
    for pid, iso in picked:
        title = ""
        p = _root(root) / "pages" / f"{pid}.md"
        if p.exists():
            m = re.search(r'^title:\s*"(.*)"\s*$', p.read_text(encoding="utf-8"), flags=re.M)
            title = m.group(1) if m else ""
        out.append(f"- **{iso}** — {title} [{pid}]")
    return "\n".join(out) + "\n"


_INDEX_BULLET_RE = re.compile(r"^- \[([^\]]*)\]\(pages/([^)]+)\.md\)\s+—\s+(.*)$")


def build_unplaced_block(uncovered: list, root: Path | None = None) -> str:
    """Страницы вне карты не выпадают из файла: указатель лучше, чем дыра."""
    if not uncovered:
        return ""
    ann = {}
    for name in ("index.md", "releasenotes-index.md"):
        f = _root(root) / name
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            m = _INDEX_BULLET_RE.match(line.strip())
            if m:
                ann[m.group(2)] = m.group(3)
    out = ["## Ещё не разложено", "",
           "Страницы вики, не попавшие в тематические разделы. Факты по ним есть на "
           "первоисточнике; здесь — только указатели.", ""]
    for pid in uncovered:
        out.append(f"- [{pid}] — {ann.get(pid, 'аннотации нет')}")
    return "\n".join(out) + "\n"


def build(sections: list, texts: dict, *, releases_block: str, built_on: str,
          unplaced_block: str = "") -> str:
    id_to_title = {s["id"]: s["title"] for s in sections}
    parts = [build_header(built_on)]
    for s in sections:
        body = texts.get(s["id"])
        if body is None:
            continue
        parts.append("")
        parts.append(substitute_ids(body.rstrip("\n"), id_to_title))
    for extra in (unplaced_block, releases_block):
        if extra:
            parts.append("")
            parts.append(substitute_ids(extra.rstrip("\n"), id_to_title))
    return "\n".join(parts).rstrip("\n") + "\n"
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd tools && python3 -m pytest tests/test_compact_assemble.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Написать тест на блок релизов**

Дописать в `tools/tests/test_compact_assemble.py`:

```python
def test_releases_block_lists_date_title_and_ref(tmp_path):
    p = tmp_path / "pages" / "ReleaseNotes" / "ListOfChanges24082026.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('---\ntitle: "Офлайн-режим починен"\n---\n\nтело\n', encoding="utf-8")
    block = assemble.build_releases_block(
        [("ReleaseNotes/ListOfChanges24082026", "2026-08-24")], tmp_path)
    assert "**2026-08-24** — Офлайн-режим починен" in block
    assert "[ReleaseNotes/ListOfChanges24082026]" in block


def test_releases_block_empty_when_nothing_picked():
    assert assemble.build_releases_block([], None) == ""


def test_unplaced_block_takes_annotation_from_index(tmp_path):
    (tmp_path / "index.md").write_text(
        "- [Новая](pages/user/Новая.md) — про новое.\n", encoding="utf-8")
    assert "- [user/Новая] — про новое." in assemble.build_unplaced_block(
        ["user/Новая"], tmp_path)


def test_unplaced_block_survives_missing_annotation(tmp_path):
    (tmp_path / "index.md").write_text("", encoding="utf-8")
    assert "аннотации нет" in assemble.build_unplaced_block(["user/Сирота"], tmp_path)


def test_unplaced_block_empty_when_all_covered():
    assert assemble.build_unplaced_block([], None) == ""
```

- [ ] **Step 6: Убедиться, что тесты проходят**

Run: `cd tools && python3 -m pytest tests/test_compact_assemble.py -v`
Expected: PASS (8 passed)

- [ ] **Step 7: Коммит**

```bash
cd tools && git add compact/assemble.py tests/test_compact_assemble.py
git commit -m "feat(compact): детерминированная сборка файла с шапкой и подменой id разделов"
```

---

### Task 5: Явный выбор модели в model_client

**Files:**
- Modify: `tools/update/model_client.py`
- Test: `tools/tests/test_model_client.py`

**Interfaces:**
- Consumes: ничего.
- Produces: `model_client.run_model(prompt: str, *, timeout: int = 180, model: str | None = None) -> str` — при заданном `model` добавляет `--model <model>` в командную строку.

- [ ] **Step 1: Написать падающий тест**

Создать `tools/tests/test_model_client.py`:

```python
from update import model_client


def test_model_flag_added_when_model_given(monkeypatch):
    seen = {}

    class R:
        returncode = 0
        stdout = "ответ"
        stderr = ""

    def fake_run(args, **kw):
        seen["args"] = args
        return R()

    monkeypatch.setattr(model_client.subprocess, "run", fake_run)
    assert model_client.run_model("промпт", model="opus") == "ответ"
    assert seen["args"] == ["claude", "-p", "--model", "opus"]


def test_no_model_flag_by_default(monkeypatch):
    seen = {}

    class R:
        returncode = 0
        stdout = "ответ"
        stderr = ""

    monkeypatch.setattr(model_client.subprocess, "run",
                        lambda args, **kw: (seen.__setitem__("args", args), R())[1])
    model_client.run_model("промпт")
    assert seen["args"] == ["claude", "-p"]
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd tools && python3 -m pytest tests/test_model_client.py -v`
Expected: FAIL, `TypeError: run_model() got an unexpected keyword argument 'model'`

- [ ] **Step 3: Добавить параметр модели**

В `tools/update/model_client.py` заменить сигнатуру и вызов:

```python
def run_model(prompt: str, *, timeout: int = 180, model: str | None = None) -> str:
    cmd = ["claude", "-p"] + (["--model", model] if model else [])
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
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

- [ ] **Step 4: Убедиться, что тесты проходят и старые не сломались**

Run: `cd tools && python3 -m pytest tests/test_model_client.py tests/test_recompress.py -v`
Expected: PASS

- [ ] **Step 5: Коммит**

```bash
cd tools && git add update/model_client.py tests/test_model_client.py
git commit -m "feat: явный выбор модели в run_model (--model)"
```

---

### Task 6: Генерация раздела моделью

**Files:**
- Create: `tools/compact/prompts/tier1.md`
- Create: `tools/compact/prompts/tier2.md`
- Create: `tools/compact/generate.py`
- Test: `tools/tests/test_compact_generate.py`

**Interfaces:**
- Consumes: `guard.section_problems` (Task 2), `sectionmap` (Task 1), `model_client.run_model` (Task 5).
- Produces:
  - `generate.build_prompt(section: dict, sources_text: str, neighbours: list[dict]) -> str`
  - `generate.generate(section: dict, sources_text: str, neighbours: list[dict], root: Path, *, model_fn=None) -> dict` — `{"id", "text", "problems", "attempts"}`
  - `generate.MODEL = "opus"`, `generate.MAX_ATTEMPTS = 2`

- [ ] **Step 1: Написать промпты**

Создать `tools/compact/prompts/tier1.md`:

```markdown
Ты сжимаешь страницы вики HubEx в ОДИН раздел файла-контекста для облачного ИИ-агента.

Читатель — машина, не человек. Оптимизируй под точность поиска факта и невозможность
выдумать, не под приятность чтения. Телеграфный стиль, без вводных оборотов и маркетинга.

Включать: сущности и связи между ними; ограничения и числа; условия доступности;
контринтуитивное и типовые ошибки; пути настройки в форме `Путь: Раздел → Подраздел`;
точные названия полей, вкладок, флагов в кавычках-ёлочках.

НЕ включать: пошаговые инструкции («нажмите кнопку +»); описания скриншотов; ссылки на
картинки; пересказ соседних разделов; факты, которых нет на данных тебе страницах.
Страница-заглушка без содержания — так и написать.

Формат ответа — строго:

## <название раздела, дословно из задания>

<1–3 фразы: что это и место в системе>

**Модель.** <сущности и связи; что от чего зависит>

**Настройка.** <пути, названия полей и флагов>

**Ограничения.** <числа, пределы, условия>

**⚠ Грабли.** <контринтуитивное; чем X отличается от Y> (блок опустить, если грабель нет)

Источники: [section/slug] [section/slug] ...

Ссылки на страницы — только короткие id в квадратных скобках вида [admin/SLA].
Полные URL не приводить. Блоки Модель/Настройка/Ограничения обязательны, порядок фиксирован.
Заголовков глубже `##` не вводить.

Соседние разделы файла перечислены в задании. Их содержимое не пересказывай: если тема
принадлежит соседу, дай одну связку-упоминание с его id и иди дальше.

Бюджет в символах — жёсткий потолок. Лучше сказать меньше, но точно, чем разлить воду.
Ответ — только текст раздела, без пояснений до и после.
```

Создать `tools/compact/prompts/tier2.md`:

```markdown
Ты пишешь СИНТЕТИЧЕСКИЙ раздел файла-контекста HubEx для облачного ИИ-агента.

Твой источник — не страницы вики, а уже готовые разделы этого же файла, данные ниже.
Твоя задача — то, чего нет ни в одном отдельном разделе: связи поверх них.

Основной потребитель — отдел продаж: разбор discovery-встреч, концепция «как процессы
заказчика лягут на HubEx», квалификация лидов. Поэтому пиши так, чтобы по разделу можно
было ОТВЕТИТЬ НА ВОПРОС МОДЕЛИРОВАНИЯ: чем в HubEx выразить процесс клиента, какие есть
степени свободы, обо что процесс упрётся.

Читатель — машина. Телеграфный стиль, без воды и маркетинга.

Формат ответа — строго:

## <название раздела, дословно из задания>

<1–3 фразы: что даёт этот раздел>

**Модель.** <суть: граф сущностей, либо перечень паттернов, либо перечень ограничений>

**Настройка.** <чем это настраивается; пути и названия, если применимо>

**Ограничения.** <границы применимости; что выразить нельзя>

**⚠ Грабли.** <ошибки моделирования; что путают> (блок опустить, если грабель нет)

Источники: [section/slug] ...

Ссылки — короткие id страниц, взятые из блоков «Источники:» тех разделов, на которые
ты опираешься. Новых фактов не изобретать: всё, что пишешь, должно следовать из данных
тебе разделов. Бюджет в символах — жёсткий потолок.
Ответ — только текст раздела, без пояснений до и после.
```

- [ ] **Step 2: Написать падающий тест на сборку промпта**

Создать `tools/tests/test_compact_generate.py`:

```python
from compact import generate

SEC1 = {"id": "s01", "title": "Жизненный цикл", "budget": 4400,
        "sources": ["admin/BusinessProcess"], "tier": 1}
SEC2 = {"id": "t01", "title": "Карта сущностей", "budget": 6000,
        "sources": ["@s01"], "tier": 2}
NEIGH = [{"id": "s02", "title": "Типы заявок"}, {"id": "s09", "title": "Роли"}]


def test_tier1_prompt_carries_title_budget_and_neighbours():
    p = generate.build_prompt(SEC1, "ТЕКСТ СТРАНИЦ", NEIGH)
    assert "Жизненный цикл" in p
    assert "4400" in p
    assert "s02 — Типы заявок" in p
    assert "ТЕКСТ СТРАНИЦ" in p
    assert "Формат ответа — строго" in p


def test_tier2_prompt_uses_tier2_template():
    p = generate.build_prompt(SEC2, "ТЕКСТЫ РАЗДЕЛОВ", NEIGH)
    assert "СИНТЕТИЧЕСКИЙ раздел" in p
    assert "ТЕКСТЫ РАЗДЕЛОВ" in p
```

- [ ] **Step 3: Убедиться, что тесты падают**

Run: `cd tools && python3 -m pytest tests/test_compact_generate.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'compact.generate'`

- [ ] **Step 4: Реализовать сборку промпта**

Создать `tools/compact/generate.py`:

```python
"""Генерация одного раздела сжатого контекста моделью, с ретраем по guard-проблемам."""
from pathlib import Path

from compact import guard
from update import model_client

PROMPTS = Path(__file__).resolve().parent / "prompts"
MODEL = "opus"
MAX_ATTEMPTS = 2


def build_prompt(section: dict, sources_text: str, neighbours: list) -> str:
    template = (PROMPTS / ("tier1.md" if section["tier"] == 1 else "tier2.md")
                ).read_text(encoding="utf-8")
    neigh = "\n".join(f"- {n['id']} — {n['title']}" for n in neighbours) or "(соседей нет)"
    what = "Содержимое страниц" if section["tier"] == 1 else "Тексты разделов-источников"
    return (
        f"{template}\n\n"
        f"## Задание\n"
        f"Название раздела: {section['title']}\n"
        f"Бюджет: {section['budget']} символов (жёсткий потолок)\n\n"
        f"## Соседние разделы файла\n{neigh}\n\n"
        f"## {what}\n{sources_text}\n"
    )
```

- [ ] **Step 5: Убедиться, что тесты проходят**

Run: `cd tools && python3 -m pytest tests/test_compact_generate.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Написать падающий тест на генерацию с ретраем**

Дописать в `tools/tests/test_compact_generate.py`:

```python
GOOD = ("## Жизненный цикл\n\nВводная.\n\n"
        "**Модель.** Стадия. [admin/BusinessProcess]\n\n"
        "**Настройка.** Путь: Настройки заявки → Стадии.\n\n"
        "**Ограничения.** Один цикл на тип.\n\n"
        "Источники: [admin/BusinessProcess]\n")


def _mkpages(tmp_path, ids):
    for pid in ids:
        p = tmp_path / "pages" / f"{pid}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("тело", encoding="utf-8")


def test_generate_returns_clean_text(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess"])
    res = generate.generate(SEC1, "страницы", NEIGH, tmp_path,
                            model_fn=lambda prompt, model=None: GOOD)
    assert res["problems"] == []
    assert res["attempts"] == 1
    assert res["text"] == GOOD


def test_generate_retries_once_on_guard_problem(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess"])
    calls = []

    def fake(prompt, model=None):
        calls.append(prompt)
        return "## Не тот заголовок\n\nпусто\n" if len(calls) == 1 else GOOD

    res = generate.generate(SEC1, "страницы", NEIGH, tmp_path, model_fn=fake)
    assert res["attempts"] == 2
    assert res["problems"] == []
    assert "Предыдущий ответ не прошёл проверку" in calls[1]


def test_generate_gives_up_after_max_attempts(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess"])
    res = generate.generate(SEC1, "страницы", NEIGH, tmp_path,
                            model_fn=lambda prompt, model=None: "## Мусор\n")
    assert res["attempts"] == generate.MAX_ATTEMPTS
    assert res["problems"]


def test_generate_passes_opus_model(tmp_path):
    _mkpages(tmp_path, ["admin/BusinessProcess"])
    seen = {}

    def fake(prompt, model=None):
        seen["model"] = model
        return GOOD

    generate.generate(SEC1, "страницы", NEIGH, tmp_path, model_fn=fake)
    assert seen["model"] == "opus"
```

- [ ] **Step 7: Убедиться, что тесты падают**

Run: `cd tools && python3 -m pytest tests/test_compact_generate.py -v`
Expected: FAIL, `AttributeError: module 'compact.generate' has no attribute 'generate'`

- [ ] **Step 8: Реализовать генерацию с ретраем**

Дописать в `tools/compact/generate.py`:

```python
def _retry_prompt(prompt: str, text: str, problems: list) -> str:
    return (f"{prompt}\n\n## Предыдущий ответ не прошёл проверку\n"
            f"Проблемы: {'; '.join(problems)}.\n"
            f"Верни СТРОГО текст раздела в требуемом формате, начиная со строки '## '. "
            f"Уложись в бюджет.\n")


def generate(section: dict, sources_text: str, neighbours: list, root: Path,
             *, model_fn=None) -> dict:
    """Зовёт модель, проверяет guard-ом, при проблемах даёт один ретрай с их перечнем."""
    model_fn = model_fn or model_client.run_model
    prompt = build_prompt(section, sources_text, neighbours)
    text, problems = "", ["модель не вызывалась"]
    for attempt in range(1, MAX_ATTEMPTS + 1):
        text = model_fn(prompt, model=MODEL).strip() + "\n"
        problems = guard.section_problems(text, section, root)
        if not problems:
            return {"id": section["id"], "text": text, "problems": [], "attempts": attempt}
        prompt = _retry_prompt(prompt, text, problems)
    return {"id": section["id"], "text": text, "problems": problems,
            "attempts": MAX_ATTEMPTS}
```

- [ ] **Step 9: Убедиться, что тесты проходят**

Run: `cd tools && python3 -m pytest tests/test_compact_generate.py -v`
Expected: PASS (6 passed)

- [ ] **Step 10: Коммит**

```bash
cd tools && git add compact/generate.py compact/prompts/tier1.md compact/prompts/tier2.md tests/test_compact_generate.py
git commit -m "feat(compact): генерация раздела моделью на Opus с ретраем по guard"
```

---

### Task 7: Оркестратор и отчёт

**Files:**
- Create: `tools/compact/pipeline.py`
- Create: `tools/compact/report.py`
- Test: `tools/tests/test_compact_pipeline.py`

**Interfaces:**
- Consumes: всё из Task 1–6.
- Produces:
  - `pipeline.run_compact(*, changed_pages=None, rebuild_all=False, root=None, model_fn=None, git_run=None, releases_n=5) -> dict` — `{"sections": [результаты generate], "written": bool, "file_problems": [...], "map_problems": [...], "undated": [...], "chars": int, "out": Path}`
  - `report.render(res: dict) -> str`
  - `report.exit_code(res: dict) -> int` — 0 чисто, 1 guard-проблемы или ошибка модели, 2 карта невалидна.

- [ ] **Step 1: Написать падающий тест на выборочную перегенерацию**

Создать `tools/tests/test_compact_pipeline.py`:

```python
from compact import assemble, pipeline, report

MAP = ("s01\tЖизненный цикл\t400\tadmin/BusinessProcess\n"
       "s02\tТипы заявок\t400\tadmin/TicketType\n"
       "t01\tКарта сущностей\t400\t@s01 @s02\n")


def _sec_text(title):
    return (f"## {title}\n\nВводная.\n\n**Модель.** М.\n\n**Настройка.** Н.\n\n"
            f"**Ограничения.** О.\n\nИсточники: [admin/BusinessProcess]\n")


def _fixture(tmp_path):
    (tmp_path / "context").mkdir(parents=True, exist_ok=True)
    (tmp_path / "context" / "map.tsv").write_text(MAP, encoding="utf-8")
    for pid in ("admin/BusinessProcess", "admin/TicketType"):
        p = tmp_path / "pages" / f"{pid}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('---\ntitle: "T"\n---\n\nтело\n', encoding="utf-8")
    d = tmp_path / assemble.SECTIONS_DIR_REL
    d.mkdir(parents=True, exist_ok=True)
    for sid, title in (("s01", "Жизненный цикл"), ("s02", "Типы заявок"),
                       ("t01", "Карта сущностей")):
        (d / f"{sid}.md").write_text(_sec_text(title), encoding="utf-8")
    return tmp_path


def test_only_affected_sections_regenerated(tmp_path, monkeypatch):
    root = _fixture(tmp_path)
    monkeypatch.setattr(pipeline.guard, "MIN_CHARS", 0)
    called = []

    def fake(prompt, model=None):
        called.append(prompt)
        return _sec_text("Жизненный цикл") if "Жизненный цикл" in prompt \
            else _sec_text("Карта сущностей")

    res = pipeline.run_compact(changed_pages={"admin/BusinessProcess"}, root=root,
                               model_fn=fake, git_run=lambda a, c: "")
    assert [r["id"] for r in res["sections"]] == ["s01", "t01"]
    assert len(called) == 2


def test_nothing_changed_means_no_model_calls(tmp_path, monkeypatch):
    root = _fixture(tmp_path)
    monkeypatch.setattr(pipeline.guard, "MIN_CHARS", 0)

    def boom(prompt, model=None):
        raise AssertionError("модель не должна вызываться")

    res = pipeline.run_compact(changed_pages=set(), root=root, model_fn=boom,
                               git_run=lambda a, c: "")
    assert res["sections"] == []
    assert res["written"] is True
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd tools && python3 -m pytest tests/test_compact_pipeline.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'compact.pipeline'`

- [ ] **Step 3: Реализовать оркестратор**

Создать `tools/compact/pipeline.py`:

```python
"""Оркестратор сжатого контекста: карта → перегенерация затронутых разделов → сборка → guard."""
from datetime import date
from pathlib import Path

from compact import assemble, generate, guard, releases, sectionmap

REPO_ROOT = Path(__file__).resolve().parents[2]


def _root(root):
    return root if root is not None else REPO_ROOT


def _sources_text(section: dict, root: Path, texts: dict) -> str:
    if section["tier"] == 1:
        parts = []
        for pid in section["sources"]:
            p = root / "pages" / f"{pid}.md"
            parts.append(f"### Страница {pid}\n\n" + p.read_text(encoding="utf-8"))
        return "\n\n".join(parts)
    refs = ([s for s in texts] if sectionmap.ALL_TIER1 in section["sources"]
            else [r[1:] for r in section["sources"] if r != sectionmap.ALL_TIER1])
    return "\n\n".join(texts[r] for r in refs if r in texts)


def run_compact(*, changed_pages=None, rebuild_all: bool = False, root: Path | None = None,
                model_fn=None, git_run=None, releases_n: int = 5, built_on: str | None = None
                ) -> dict:
    root = _root(root)
    built_on = built_on or date.today().isoformat()
    sections = sectionmap.load(root)
    map_problems = sectionmap.problems(sections, root)
    if map_problems:
        return {"sections": [], "written": False, "file_problems": [],
                "map_problems": map_problems, "uncovered": [], "undated": [],
                "chars": 0, "out": root / assemble.OUT_REL}

    texts = {}
    for s in sections:
        p = assemble.section_path(s["id"], root)
        if p.exists():
            texts[s["id"]] = p.read_text(encoding="utf-8")

    todo = ([s["id"] for s in sections] if rebuild_all
            else sectionmap.affected(sections, set(changed_pages or ())))
    by_id = {s["id"]: s for s in sections}
    results = []
    for sid in todo:
        s = by_id[sid]
        neighbours = [{"id": o["id"], "title": o["title"]} for o in sections if o["id"] != sid]
        res = generate.generate(s, _sources_text(s, root, texts), neighbours, root,
                                model_fn=model_fn)
        results.append(res)
        if not res["problems"]:
            texts[sid] = res["text"]
            p = assemble.section_path(sid, root)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(res["text"], encoding="utf-8")

    picked, undated = releases.latest(releases_n, root, run=git_run)
    uncov = sectionmap.uncovered(sections, root)
    text = assemble.build(sections, texts,
                          releases_block=assemble.build_releases_block(picked, root),
                          unplaced_block=assemble.build_unplaced_block(uncov, root),
                          built_on=built_on)
    file_problems = guard.file_problems(text, sections, root)
    out = root / assemble.OUT_REL
    written = not file_problems
    if written:
        out.write_text(text, encoding="utf-8")
    return {"sections": results, "written": written, "file_problems": file_problems,
            "map_problems": [], "uncovered": uncov, "undated": undated,
            "chars": len(text), "out": out}
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd tools && python3 -m pytest tests/test_compact_pipeline.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Написать падающий тест на отчёт и коды возврата**

Дописать в `tools/tests/test_compact_pipeline.py`:

```python
def test_report_and_exit_code_clean():
    res = {"sections": [{"id": "s01", "problems": [], "attempts": 1}],
           "written": True, "file_problems": [], "map_problems": [],
           "uncovered": [], "undated": [], "chars": 110_000, "out": "hubex-context.md"}
    text = report.render(res)
    assert "Перегенерировано разделов: 1" in text
    assert "110000" in text
    assert report.exit_code(res) == 0


def test_exit_code_2_on_bad_map():
    res = {"sections": [], "written": False, "file_problems": [],
           "map_problems": ["раздел t02 ссылается на несуществующий раздел s99"],
           "uncovered": [], "undated": [], "chars": 0, "out": "hubex-context.md"}
    assert report.exit_code(res) == 2
    assert "несуществующий раздел s99" in report.render(res)


def test_exit_code_1_on_guard_problem():
    res = {"sections": [{"id": "s01", "problems": ["бюджет превышен: 5000 > 4400"],
                         "attempts": 2}],
           "written": False, "file_problems": [], "map_problems": [],
           "uncovered": [], "undated": [], "chars": 0, "out": "hubex-context.md"}
    assert report.exit_code(res) == 1


def test_undated_releases_are_reported():
    res = {"sections": [], "written": True, "file_problems": [], "map_problems": [],
           "uncovered": [], "undated": ["ReleaseNotes/CustomerApp"], "chars": 110_000,
           "out": "hubex-context.md"}
    assert "ReleaseNotes/CustomerApp" in report.render(res)
    assert report.exit_code(res) == 0


def test_uncovered_pages_warn_but_do_not_fail():
    res = {"sections": [], "written": True, "file_problems": [], "map_problems": [],
           "uncovered": ["user/Новая"], "undated": [], "chars": 110_000,
           "out": "hubex-context.md"}
    text = report.render(res)
    assert "user/Новая" in text
    assert "Ещё не разложено" in text
    assert report.exit_code(res) == 0
```

- [ ] **Step 6: Убедиться, что тесты падают**

Run: `cd tools && python3 -m pytest tests/test_compact_pipeline.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'compact.report'`

- [ ] **Step 7: Реализовать отчёт**

Создать `tools/compact/report.py`:

```python
"""Рендер результатов compact в markdown-отчёт. Чистый модуль."""


def exit_code(res: dict) -> int:
    """0 — чисто; 1 — guard-проблемы раздела или файла; 2 — карта невалидна."""
    if res["map_problems"]:
        return 2
    if res["file_problems"] or any(r["problems"] for r in res["sections"]):
        return 1
    return 0


def render(res: dict) -> str:
    out = ["# Отчёт compact"]
    if res["map_problems"]:
        out.append("")
        out.append("## ❌ Карта разделов невалидна — сборка не запускалась")
        out.extend(f"- {p}" for p in res["map_problems"])
        return "\n".join(out) + "\n"

    out.append("")
    out.append(f"Перегенерировано разделов: {len(res['sections'])}")
    for r in res["sections"]:
        mark = "⚠️" if r["problems"] else "✅"
        retry = " (со второй попытки)" if r["attempts"] > 1 else ""
        out.append(f"- {mark} {r['id']}{retry}")
        out.extend(f"    - {p}" for p in r["problems"])

    if res["file_problems"]:
        out.append("")
        out.append("## ❌ Собранный файл не прошёл проверку — не записан")
        out.extend(f"- {p}" for p in res["file_problems"])
    else:
        out.append("")
        out.append(f"Файл: {res['out']}, {res['chars']} символов.")

    if res["uncovered"]:
        out.append("")
        out.append("## ⚠ Страницы вне карты — ушли в «Ещё не разложено»")
        out.extend(f"- {p}" for p in res["uncovered"])
        out.append("Разложить по темам в `context/map.tsv`. Прогон не блокируется: "
                   "указатель в файле лучше, чем дыра.")

    if res["undated"]:
        out.append("")
        out.append("## Релиз-ноуты без определённой даты (в блок не попали)")
        out.extend(f"- {p}" for p in res["undated"])
        out.append("Проставить вручную в `context/release-dates.tsv`.")
    return "\n".join(out) + "\n"
```

- [ ] **Step 8: Убедиться, что тесты проходят**

Run: `cd tools && python3 -m pytest tests/test_compact_pipeline.py -v`
Expected: PASS (7 passed)

- [ ] **Step 9: Коммит**

```bash
cd tools && git add compact/pipeline.py compact/report.py tests/test_compact_pipeline.py
git commit -m "feat(compact): оркестратор перегенерации и отчёт"
```

---

### Task 8: Подкоманда CLI, встройка в sync, документация

**Files:**
- Modify: `tools/wiki_cli.py`
- Modify: `tools/update/sync.py`
- Modify: `tools/README.md`
- Modify: `README.md` (контент-репозиторий)
- Modify: `CLAUDE.md` (контент-репозиторий)
- Test: `tools/tests/test_cli.py`

**Interfaces:**
- Consumes: `pipeline.run_compact`, `report.render`, `report.exit_code` (Task 7).
- Produces: подкоманда `python3 tools/wiki_cli.py compact [--all] [--page <section>/<slug>] [--report-file PATH]`.

- [ ] **Step 1: Написать падающий тест на CLI**

Дописать в `tools/tests/test_cli.py`:

```python
def test_compact_subcommand_parses_all_and_page():
    import wiki_cli
    args = wiki_cli.build_parser().parse_args(
        ["compact", "--all", "--page", "admin/SLA", "--page", "user/Filters"])
    assert args.command == "compact"
    assert args.all is True
    assert args.page == ["admin/SLA", "user/Filters"]


def test_compact_subcommand_defaults():
    import wiki_cli
    args = wiki_cli.build_parser().parse_args(["compact"])
    assert args.all is False
    assert args.page is None
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd tools && python3 -m pytest tests/test_cli.py -v`
Expected: FAIL, `SystemExit: 2` — подкоманда `compact` не зарегистрирована

- [ ] **Step 3: Добавить подкоманду**

В `tools/wiki_cli.py` в импорты добавить:

```python
from compact import pipeline as compact_pipeline, report as compact_report  # noqa: E402
```

В `build_parser()` перед `return p` добавить:

```python
    cp = sub.add_parser("compact",
                        help="собрать hubex-context.md — однофайловый сжатый контекст "
                             "для облачных ИИ-агентов (нужна модель)")
    cp.add_argument("--all", action="store_true",
                    help="перегенерировать все разделы, а не только затронутые")
    cp.add_argument("--page", action="append", default=None,
                    help="считать изменившейся страницу <section>/<slug> (можно повторять)")
    cp.add_argument("--report-file", type=Path, default=None,
                    help="продублировать отчёт в файл")
```

В `main()` перед `return 2` добавить:

```python
    if args.command == "compact":
        res = compact_pipeline.run_compact(changed_pages=set(args.page or ()),
                                           rebuild_all=args.all)
        text = compact_report.render(res)
        print(text, end="")
        if args.report_file:
            args.report_file.write_text(text, encoding="utf-8")
        return compact_report.exit_code(res)
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd tools && python3 -m pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Написать падающий тест на встройку в sync**

Дописать в `tools/tests/test_sync.py`:

```python
def test_sync_commits_compact_artifacts():
    from update import sync
    assert "hubex-context.md" in sync.COMMIT_PATHS
    assert "context" in sync.COMMIT_PATHS
```

- [ ] **Step 6: Убедиться, что тест падает**

Run: `cd tools && python3 -m pytest tests/test_sync.py -v`
Expected: FAIL — `COMMIT_PATHS` не содержит новых путей (либо константы нет; тогда сперва вынести список путей `git add` в модульную константу `COMMIT_PATHS`, не меняя поведения)

- [ ] **Step 7: Встроить в sync**

В `tools/update/sync.py`:

1. Вынести пути коммита в модульную константу рядом с остальными:

```python
COMMIT_PATHS = ("pages", "index.md", "releasenotes-index.md", "context", "hubex-context.md")
```

и использовать её в вызове `git add` вместо литерального списка.

2. После успешного `update --recompress` и до проверки «есть ли изменения» вызвать пересборку контекста по фактически изменившимся страницам:

```python
from compact import pipeline as compact_pipeline, report as compact_report

changed = {r["page"] for r in results if r["status"] in ("new", "changed")}
compact_res = compact_pipeline.run_compact(changed_pages=changed)
compact_text = compact_report.render(compact_res)
compact_code = compact_report.exit_code(compact_res)
```

Отчёт `compact_text` дописать в общий отчёт прогона. Ненулевой `compact_code` трактовать как guard-проблему: коммита нет, выход **1** — так же, как для guard-проблем аннотаций. Логика гейтов git не меняется.

- [ ] **Step 8: Убедиться, что тесты проходят**

Run: `cd tools && python3 -m pytest -v -m "not live"`
Expected: PASS, весь офлайн-набор зелёный

- [ ] **Step 9: Обновить документацию пайплайна**

В `tools/README.md` в раздел «Команды» добавить после `export-llms`:

```markdown
```
python3 tools/wiki_cli.py compact [--all] [--page <section>/<slug>] [--report-file PATH]
```

Собирает `hubex-context.md` — однофайловый сжатый контекст для облачных ИИ-агентов
(Perplexity, ChatGPT, DeepSeek), которым репозиторий вики недоступен.

Разделы описаны картой `context/map.tsv` и лежат в `context/sections/**`. Без флагов
перегенерируются только разделы, затронутые указанными `--page`; `--all` — все.
Ярус 1 собирается из страниц вики, ярус 2 — из текстов яруса 1. Модель зовётся явно
на Opus. Итоговый файл собирается детерминированно и записывается, только если прошёл
guard: размер в коридоре 99 000–121 000, все разделы на месте, ссылки резолвятся,
внутренние id разделов подменены на названия.

Exit-коды: 0 — ок; 1 — guard-проблема раздела или файла; 2 — карта разделов невалидна
(дубль страницы, ссылка на несуществующий раздел, вложенность ярусов).

Новая страница вики, не попавшая ни в один раздел, прогон **не** валит: она уходит в
раздел «Ещё не разложено» с аннотацией из `index.md` и в отчёт. Разложить по темам
в `context/map.tsv` — за человеком.
```

- [ ] **Step 10: Обновить документацию контент-репозитория**

В `README.md` в таблицу «Слои» добавить строку:

```markdown
| [hubex-context.md](hubex-context.md) | весь продукт одним файлом ~110 тыс. символов | прикрепить в чат облачного агента без доступа к репозиторию |
```

Там же после раздела «Экспорт для сайта (llms.txt)» добавить раздел про `compact` — назначение файла, команду сборки, что карта `context/map.tsv` ведётся человеком.

В `CLAUDE.md` в список критичного добавить строку:

```markdown
- `context/sections/**` и `hubex-context.md` руками не правь — их ведёт пайплайн (`python3 tools/wiki_cli.py compact`). Правится только карта `context/map.tsv`.
```

- [ ] **Step 11: Первичная генерация всех разделов**

Run: `python3 tools/wiki_cli.py compact --all --report-file /tmp/compact-first.txt`
Expected: exit 0; создано 28 файлов в `context/sections/`, записан `hubex-context.md` размером в коридоре.

Прочитать отчёт. Разделы с ⚠ разобрать вручную: обычно это превышение бюджета — либо поднять бюджет в карте, либо перегенерировать раздел точечно через `--page` с его страницами.

- [ ] **Step 12: Сверить полноту с эталоном**

Сравнить `hubex-context.md` с эталонным файлом варианта A из эксперимента (сохранён в скретчпаде сессии; результаты сверки — в спеке). Проверить наличие фактуры, которой в эксперименте не хватило варианту C: трудоёмкость доработок в часах, частота геотрекинга (3 мин / 10 м), таблица переходов базового бизнес-процесса.

Отсутствует — поднять бюджет соответствующего раздела в `context/map.tsv` и перегенерировать его.

- [ ] **Step 13: Коммит**

```bash
cd tools && git add wiki_cli.py update/sync.py README.md tests/test_cli.py tests/test_sync.py
git commit -m "feat(compact): подкоманда CLI, встройка в ночной sync, документация"
cd .. && git add context hubex-context.md README.md CLAUDE.md
git commit -m "feat: hubex-context.md — сжатый контекст HubEx для облачных ИИ-агентов"
```

---

## Что осталось за рамками плана

Эти пункты спека реализуются отдельно, после того как основной поток заработает:

- **Дельта графа ссылок** как сигнал о новых сквозных связях (спек, «Ревизия карты», пункт 1).
- **Самоотчёт модели** о нехватке фактов из соседних разделов (пункт 2). В эксперименте механизм работал, но выдавал 6–12 связей на раздел — прежде чем встраивать, нужен фильтр, иначе отчёт превратится в шум.
- **Квартальная ревизия карты** моделью (пункт 3).

Каждый — отдельный небольшой план поверх готовой команды `compact`.
