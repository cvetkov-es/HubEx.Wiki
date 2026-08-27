# Цельный файл сжатого контекста — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить поразделную сборку `hubex-context.md` цельным проходом модели по всей вике с ночным обновлением через патч по диффу изменившихся страниц.

**Architecture:** Полная сборка — агентный headless-прогон `claude -p` с доступом к файлам: модель читает `pages/**`, дописывает тело файла по частям и мерит себя. Пайплайн детерминированно оборачивает тело шапкой и блоком релизов. Ночью тот же агентный механизм правит готовый файл по диффу, а не пересобирает его. Все проверки — файлового уровня, карта разделов не нужна.

**Tech Stack:** Python 3.11+, pytest, git-сабмодуль `tools/` (репо HubEx.Wiki.Pipeline), headless Claude Code CLI.

**Spec:** `docs/superpowers/specs/2026-08-27-whole-file-context-design.md` (отменяет архитектурную часть `2026-08-25-compact-context-design.md`, цели и требования к содержанию берутся оттуда)

## Global Constraints

- Модель для сборки и патча — **`opus`, передаётся явным флагом `--model`**. Дефолт `claude -p` для этой задачи не годится.
- Целевой размер файла — **150 000 символов**; жёсткий потолок — **165 000** (1.10); ориентир снизу — **127 500** (0.85), предупреждение.
- Новые проверки (покрытие страниц, градиент сжатия) вводятся **предупреждениями, не блокерами**.
- Жёсткие проверки — только две: потолок размера и битые ссылки `[section/slug]`.
- Комментарии и docstrings — по-русски, в тон существующему коду: объясняют «почему», а не «что».
- Работа идёт в сабмодуле `tools/` (отдельный репозиторий); коммиты там и в контент-репо раздельные.
- Ночной крон в 00:00 МСК отменяется любой незакоммиченной правкой в дереве контент-репо.
- `pages/**` руками не правим ни в тестах, ни в коде — только через `update`.

---

### Task 1: Агентный запуск модели

Существующий `run_model` собирает stdout от `claude -p`. Для файла в 150 тыс. символов это не работает: столько не выходит одним ответом. Нужен запуск с инструментами, где результат — записанный моделью файл, а stdout лишь отчёт.

**Files:**
- Modify: `update/model_client.py`
- Test: `tests/test_model_client.py`

**Interfaces:**
- Consumes: `model_client.ModelError` (существует)
- Produces: `model_client.run_agent(prompt: str, *, cwd: Path, timeout: int = 5400, model: str | None = None, tools: str = AGENT_TOOLS) -> str` — возвращает stdout прогона; побочный эффект (записанный файл) проверяет вызывающий. `model_client.AGENT_TOOLS: str` — список инструментов через запятую.

- [ ] **Step 1: Написать падающие тесты**

```python
def test_run_agent_builds_headless_command_with_tools_and_model(monkeypatch):
    seen = {}

    class R:
        returncode = 0
        stdout = "готово"
        stderr = ""

    def fake_run(args, **kw):
        seen["args"] = args
        seen["cwd"] = kw.get("cwd")
        seen["input"] = kw.get("input")
        return R()

    monkeypatch.setattr(model_client.subprocess, "run", fake_run)
    out = model_client.run_agent("промпт", cwd="/repo", model="opus")

    assert out == "готово"
    assert seen["cwd"] == "/repo"
    assert seen["input"] == "промпт"
    assert seen["args"][:2] == ["claude", "-p"]
    assert "--permission-mode" in seen["args"]
    assert seen["args"][seen["args"].index("--permission-mode") + 1] == "acceptEdits"
    assert seen["args"][seen["args"].index("--allowedTools") + 1] == model_client.AGENT_TOOLS
    assert seen["args"][seen["args"].index("--model") + 1] == "opus"


def test_run_agent_allows_reading_writing_and_measuring():
    # Прогон обязан уметь прочитать страницы, записать файл и измерить его длину.
    for tool in ("Read", "Write", "Edit", "Glob", "Grep", "Bash(wc"):
        assert tool in model_client.AGENT_TOOLS


def test_run_agent_raises_on_timeout(monkeypatch):
    def boom(args, **kw):
        raise model_client.subprocess.TimeoutExpired(cmd=args, timeout=1)

    monkeypatch.setattr(model_client.subprocess, "run", boom)
    with pytest.raises(model_client.ModelError, match="таймаут"):
        model_client.run_agent("промпт", cwd="/repo", timeout=1)


def test_run_agent_raises_on_nonzero_code(monkeypatch):
    class R:
        returncode = 2
        stdout = ""
        stderr = "нет доступа"

    monkeypatch.setattr(model_client.subprocess, "run", lambda args, **kw: R())
    with pytest.raises(model_client.ModelError, match="код 2"):
        model_client.run_agent("промпт", cwd="/repo")


def test_run_agent_empty_stdout_is_not_an_error(monkeypatch):
    # В отличие от run_model, результат прогона — записанный файл, а не текст ответа.
    class R:
        returncode = 0
        stdout = "   "
        stderr = ""

    monkeypatch.setattr(model_client.subprocess, "run", lambda args, **kw: R())
    assert model_client.run_agent("промпт", cwd="/repo") == ""
```

Импорт `pytest` в начале файла добавить, если его там нет.

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `cd tools && python3 -m pytest tests/test_model_client.py -v`
Expected: FAIL — `AttributeError: module 'update.model_client' has no attribute 'run_agent'`

- [ ] **Step 3: Реализовать**

```python
# Прогон, где результат — записанный моделью файл, а не текст ответа. Инструменты
# перечислены поимённо: агент обязан уметь прочитать страницы, дописать файл и измерить
# его длину, и не обязан уметь ничего больше. `Bash(wc *)` даёт ровно измерение —
# без него модель не может проверить, попала ли в целевой объём.
AGENT_TOOLS = "Read,Write,Edit,Glob,Grep,Bash(wc *)"
# Полная сборка на живых данных заняла 64 минуты. Полтора часа — запас, а не ожидание.
AGENT_TIMEOUT = 5400


def run_agent(prompt: str, *, cwd, timeout: int = AGENT_TIMEOUT,
              model: str | None = None, tools: str = AGENT_TOOLS) -> str:
    """Агентный headless-прогон: модель работает инструментами в `cwd`, результат — на диске.

    Пустой stdout ошибкой не считается, в отличие от `run_model`: содержательный результат
    здесь — файл, а не ответ модели.
    """
    cmd = (["claude", "-p", "--permission-mode", "acceptEdits", "--allowedTools", tools]
           + (["--model", model] if model else []))
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired as e:
        raise ModelError(f"claude -p таймаут ({timeout}s)") from e
    if proc.returncode != 0:
        raise ModelError(f"claude -p код {proc.returncode}: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()
```

- [ ] **Step 4: Запустить тесты**

Run: `cd tools && python3 -m pytest tests/test_model_client.py -v`
Expected: PASS, все тесты файла

- [ ] **Step 5: Коммит**

```bash
cd tools && git add update/model_client.py tests/test_model_client.py
git commit -m "feat: агентный headless-прогон модели для файла, который не выходит одним ответом"
```

---

### Task 2: Промпт и сборка тела цельного файла

**Files:**
- Create: `compact/prompts/whole.md`
- Create: `compact/wholegen.py`
- Test: `tests/test_compact_wholegen.py`

**Interfaces:**
- Consumes: `model_client.run_agent`, `model_client.ModelError`
- Produces:
  - `wholegen.MODEL = "opus"`, `wholegen.TARGET_CHARS = 150_000`, `wholegen.BODY_REL = "context/body.md"`
  - `wholegen.build_prompt(*, target_chars: int, body_rel: str) -> str`
  - `wholegen.rebuild(root: Path, *, target_chars: int = TARGET_CHARS, agent_fn=None) -> dict` → `{"body": str, "problems": list, "chars": int}`

- [ ] **Step 1: Написать промпт**

Создать `compact/prompts/whole.md`:

```markdown
Ты собираешь ЕДИНСТВЕННЫЙ файл-контекст продукта HubEx для облачного ИИ-агента —
за один проход, держа всю вику в контексте одновременно.

Читатель — машина, не человек. Оптимизируй под точность поиска факта и невозможность
выдумать, не под приятность чтения. Телеграфный стиль, без вводных оборотов и маркетинга.

Реальные потребители — продавцы HubEx: грузят файл в Project и спрашивают не только
«где это настраивается», но и «как посадить процесс клиента на сущности HubEx», «какие
есть степени свободы», «во что упрёмся», «можно ли обещать это клиенту».

## Что читать

Все страницы в `pages/admin/` и `pages/user/` — целиком, без выборочности. Пропущенная
страница означает дыру в файле. Каталог `pages/ReleaseNotes/` НЕ читать: блок релизов
пайплайн добавляет сам.

## Что включать

Сущности и связи между ними; ограничения и числа; условия доступности; контринтуитивное
и типовые ошибки; пути настройки в форме `Путь: Раздел → Подраздел`; точные названия
полей, вкладок, флагов в кавычках-ёлочках.

## Что не включать

Пошаговые инструкции («нажмите кнопку +»); описания скриншотов; ссылки на картинки;
факты, которых нет на страницах. Страница-заглушка без содержания — так и написать.

## Три запрета на выдумывание

Их не ловит ни одна автоматическая проверка, а цена ошибки в этом файле выше, чем
пропуск факта: агент уверенно скажет клиенту неправду.

1. **Факт действует ровно там, где он сказан.** Не переноси утверждение с одного объекта
   на семейство. Сказано «логотип компании отображается в Сервисном акте» — значит в
   Сервисном акте, а не «во всех печатных формах».
2. **Молчание источника — не факт.** Формулировки «только у X», «в отличие от Y»,
   «Z недоступно» пиши лишь тогда, когда противопоставление прямо стоит в тексте.
3. **Квалификаторы сохраняй дословно.** «По умолчанию», «может быть», «обычно»,
   «рекомендуется» несут смысл. Выброшенное «по умолчанию» превращает настраиваемое
   поведение в неизменяемое — это уже неверный факт, а не сокращение.

## Твоё преимущество перед поразделным сжатием

Ты видишь всю вику разом. Поэтому:

- распредели объём **глобально**: важное для продажи получает место за счёт
  второстепенного, где бы они ни лежали;
- **сшивай факты между темами** — то, что на разных страницах и порознь бессмысленно;
- если две страницы **противоречат друг другу**, не выбирай молча: назови обе версии и
  укажи страницы.

Про противоречия — точность обязательна. Противоречие это когда две страницы утверждают
несовместимое об одном и том же. Разные числа о разных вещах (60 запросов в минуту для
API и 10 запросов в секунду для облака; 12.0 для телефонов и 6.0 для терминалов)
противоречием НЕ являются. Если не уверен, что предмет один и тот же, — не называй это
расхождением.

## Объём

Цель — {target_chars} символов. Это одновременно потолок и цель: недобор так же плох,
как перебор.

Пиши файл по частям и **периодически измеряй написанное** командой
`wc -m {body_rel}`, распределяя остаток осознанно. Не растрать объём на первой трети:
темы, оставшиеся на конец, обязаны получить не меньше места, чем начальные.

## Формат

Разделы уровня `## `. Деление на темы придумываешь сам, исходя из того, что нужно
читателю-агенту. Заголовков глубже `##` не вводить. Внутри раздела структура свободная;
блоки «Модель / Настройка / Ограничения / ⚠ Грабли» — хороший каркас, но не обязательный.

Ссылки на страницы — только короткие id в квадратных скобках вида `[admin/SLA]`,
`[user/CreatingTicket]`. Полные URL не приводить. **Каждая страница `pages/admin/**` и
`pages/user/**` должна быть упомянута хотя бы раз** — это проверяется автоматически.

Шапку файла не пиши: её добавляет пайплайн. Начинай сразу с первого `## `.

## Куда писать

`{body_rel}` — создай файл и дописывай его по частям. Больше ничего в дереве не трогай.

## Что вернуть в ответе

Одну строку: итоговый размер в символах и число разделов. Больше ничего.
```

- [ ] **Step 2: Написать падающие тесты**

```python
from pathlib import Path

import pytest

from compact import wholegen
from update import model_client

BODY = ("## Заявки\n\nВводная. [user/CreatingTicket]\n\n"
        "## Объекты\n\nВводная. [user/CreatingObjects]\n")


def test_prompt_carries_target_and_path_and_prohibitions():
    p = wholegen.build_prompt(target_chars=150_000, body_rel="context/body.md")
    assert "150000" in p or "150 000" in p
    assert "context/body.md" in p
    assert "Молчание источника" in p
    assert "wc -m" in p
    assert "ReleaseNotes" in p


def test_rebuild_returns_body_written_by_agent(tmp_path):
    def fake_agent(prompt, *, cwd, timeout=None, model=None, tools=None):
        assert model == "opus"
        body = Path(cwd) / wholegen.BODY_REL
        body.parent.mkdir(parents=True, exist_ok=True)
        body.write_text(BODY, encoding="utf-8")
        return "готово"

    res = wholegen.rebuild(tmp_path, agent_fn=fake_agent)
    assert res["problems"] == []
    assert res["body"] == BODY
    assert res["chars"] == len(BODY)


def test_rebuild_reports_problem_when_agent_wrote_nothing(tmp_path):
    res = wholegen.rebuild(
        tmp_path, agent_fn=lambda prompt, **kw: "ничего не сделал")
    assert res["body"] == ""
    assert any("не создан" in p for p in res["problems"])


def test_rebuild_reports_model_error_as_problem(tmp_path):
    def boom(prompt, **kw):
        raise model_client.ModelError("claude -p таймаут (5400s)")

    res = wholegen.rebuild(tmp_path, agent_fn=boom)
    assert any("таймаут" in p for p in res["problems"])


def test_rebuild_reports_problem_when_body_has_no_sections(tmp_path):
    def fake_agent(prompt, *, cwd, **kw):
        body = Path(cwd) / wholegen.BODY_REL
        body.parent.mkdir(parents=True, exist_ok=True)
        body.write_text("просто текст без заголовков\n", encoding="utf-8")
        return ""

    res = wholegen.rebuild(tmp_path, agent_fn=fake_agent)
    assert any("нет ни одного раздела" in p for p in res["problems"])
```

- [ ] **Step 3: Запустить, убедиться что падает**

Run: `cd tools && python3 -m pytest tests/test_compact_wholegen.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'compact.wholegen'`

- [ ] **Step 4: Реализовать**

```python
"""Полная сборка тела сжатого контекста одним агентным проходом модели по всей вике."""
from functools import partial
from pathlib import Path

from update import model_client

PROMPTS = Path(__file__).resolve().parent / "prompts"
MODEL = "opus"
# Цель и потолок одновременно: недобор так же плох, как перебор (спек 2026-08-27).
TARGET_CHARS = 150_000
# Тело без шапки и блока релизов — их добавляет `assemble.build_whole`. Держим отдельным
# файлом, а не только в памяти: прогон длинный, и промежуточный результат должен
# переживать падение пайплайна, чтобы его можно было посмотреть глазами.
BODY_REL = "context/body.md"


def build_prompt(*, target_chars: int, body_rel: str) -> str:
    template = (PROMPTS / "whole.md").read_text(encoding="utf-8")
    return template.replace("{target_chars}", str(target_chars)).replace(
        "{body_rel}", body_rel)


def rebuild(root: Path, *, target_chars: int = TARGET_CHARS, agent_fn=None) -> dict:
    """Зовёт агента и забирает написанное им тело файла.

    Ретрая нет намеренно: прогон стоит около часа, а причины провала (таймаут, пустой
    файл) вторая попытка не лечит. Провал возвращается проблемой, файл не переписывается.
    """
    agent_fn = agent_fn or partial(model_client.run_agent,
                                   timeout=model_client.AGENT_TIMEOUT)
    prompt = build_prompt(target_chars=target_chars, body_rel=BODY_REL)
    body_path = root / BODY_REL
    try:
        agent_fn(prompt, cwd=root, model=MODEL)
    except model_client.ModelError as e:
        return {"body": "", "problems": [str(e)], "chars": 0}
    if not body_path.exists():
        return {"body": "", "problems": [f"файл тела не создан: {BODY_REL}"], "chars": 0}
    body = body_path.read_text(encoding="utf-8")
    problems = []
    if "\n## " not in "\n" + body:
        problems.append("в теле нет ни одного раздела `## `")
    return {"body": body, "problems": problems, "chars": len(body)}
```

- [ ] **Step 5: Запустить тесты**

Run: `cd tools && python3 -m pytest tests/test_compact_wholegen.py -v`
Expected: PASS

- [ ] **Step 6: Коммит**

```bash
cd tools && git add compact/prompts/whole.md compact/wholegen.py tests/test_compact_wholegen.py
git commit -m "feat: промпт и агентная сборка тела цельного файла контекста"
```

---

### Task 3: Файловые проверки без карты

Все нынешние проверки завязаны на карту: коридор выводится из суммы бюджетов, наличие раздела — из списка карты. Нужны проверки, которым карта не нужна.

**Files:**
- Modify: `compact/guard.py`
- Test: `tests/test_compact_guard.py`

**Interfaces:**
- Consumes: `guard._page_refs` (существует), `guard._REF_RE` (существует)
- Produces:
  - `guard.WHOLE_TARGET = 150_000`, `guard.WHOLE_MAX_RATIO = 1.10`, `guard.WHOLE_MIN_RATIO = 0.85`, `guard.GRADIENT_FLOOR = 0.6`
  - `guard.wiki_pages(root: Path) -> set[str]` — id страниц `pages/**` вне `ReleaseNotes`
  - `guard.page_coverage(text: str, root: Path) -> list[str]` — неупомянутые страницы, отсортированы
  - `guard.gradient(text: str, root: Path) -> tuple[float, float]` — (медиана сжатия первой половины, второй); `(0.0, 0.0)` если считать не по чему
  - `guard.whole_file_problems(text: str, root: Path) -> list[str]` — жёсткое: потолок размера, битые ссылки
  - `guard.whole_file_warnings(text: str, root: Path) -> list[str]` — мягкое: тонкий файл, непокрытые страницы, просевший хвост

- [ ] **Step 1: Написать падающие тесты**

```python
def _mkwiki(tmp_path, sizes: dict):
    """sizes: {'user/A': 1000, ...} — создаёт страницы указанной длины."""
    for pid, n in sizes.items():
        p = tmp_path / "pages" / f"{pid}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("я" * n, encoding="utf-8")


def test_wiki_pages_ignores_releasenotes(tmp_path):
    _mkwiki(tmp_path, {"user/A": 10, "admin/B": 10})
    rn = tmp_path / "pages" / "ReleaseNotes" / "R1.md"
    rn.parent.mkdir(parents=True, exist_ok=True)
    rn.write_text("релиз", encoding="utf-8")
    assert guard.wiki_pages(tmp_path) == {"user/A", "admin/B"}


def test_page_coverage_lists_unmentioned_pages(tmp_path):
    _mkwiki(tmp_path, {"user/A": 10, "user/B": 10, "admin/C": 10})
    text = "## Раздел\n\nТекст [user/A] и [admin/C].\n"
    assert guard.page_coverage(text, tmp_path) == ["user/B"]


def test_whole_file_problems_flags_size_over_ceiling(tmp_path):
    _mkwiki(tmp_path, {"user/A": 10})
    text = "## Раздел\n\n[user/A]\n" + "я" * 200_000
    problems = guard.whole_file_problems(text, tmp_path)
    assert any("выше потолка" in p for p in problems)


def test_whole_file_problems_flags_broken_ref(tmp_path):
    _mkwiki(tmp_path, {"user/A": 10})
    text = "## Раздел\n\n[user/A] и [user/Missing]\n"
    problems = guard.whole_file_problems(text, tmp_path)
    assert any("битая ссылка на страницу: user/Missing" in p for p in problems)


def test_whole_file_problems_clean_on_good_file(tmp_path):
    _mkwiki(tmp_path, {"user/A": 10})
    assert guard.whole_file_problems("## Раздел\n\n[user/A]\n", tmp_path) == []


def test_thin_file_is_a_warning_not_a_problem(tmp_path):
    _mkwiki(tmp_path, {"user/A": 10})
    text = "## Раздел\n\n[user/A]\n"
    assert guard.whole_file_problems(text, tmp_path) == []
    assert any("ниже ориентира" in w for w in guard.whole_file_warnings(text, tmp_path))


def test_uncovered_page_is_a_warning_not_a_problem(tmp_path):
    _mkwiki(tmp_path, {"user/A": 10, "user/B": 10})
    text = "## Раздел\n\n[user/A]\n"
    assert not any("не упомянут" in p for p in guard.whole_file_problems(text, tmp_path))
    assert any("user/B" in w for w in guard.whole_file_warnings(text, tmp_path))


def test_gradient_warns_when_tail_is_starved(tmp_path):
    # Четыре раздела над источниками одного размера: первые два щедрые, последние два
    # сжаты вшестеро. Это и есть «разогнался на первой трети».
    _mkwiki(tmp_path, {"user/A": 6000, "user/B": 6000, "user/C": 6000, "user/D": 6000})
    text = ("## Один\n\n" + "я" * 3000 + " [user/A]\n\n"
            "## Два\n\n" + "я" * 3000 + " [user/B]\n\n"
            "## Три\n\n" + "я" * 500 + " [user/C]\n\n"
            "## Четыре\n\n" + "я" * 500 + " [user/D]\n")
    assert any("хвост" in w for w in guard.whole_file_warnings(text, tmp_path))


def test_gradient_quiet_when_tail_is_not_starved(tmp_path):
    _mkwiki(tmp_path, {"user/A": 6000, "user/B": 6000, "user/C": 6000, "user/D": 6000})
    text = ("## Один\n\n" + "я" * 1000 + " [user/A]\n\n"
            "## Два\n\n" + "я" * 1000 + " [user/B]\n\n"
            "## Три\n\n" + "я" * 1200 + " [user/C]\n\n"
            "## Четыре\n\n" + "я" * 1100 + " [user/D]\n")
    assert not any("хвост" in w for w in guard.whole_file_warnings(text, tmp_path))
```

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `cd tools && python3 -m pytest tests/test_compact_guard.py -v -k "whole or gradient or coverage or wiki_pages or thin or uncovered"`
Expected: FAIL — `AttributeError: module 'compact.guard' has no attribute 'wiki_pages'`

- [ ] **Step 3: Реализовать**

Добавить в `compact/guard.py`:

```python
import statistics

# Цель размера цельного файла. В отличие от прежнего коридора она задана числом, а не
# выведена из карты: карты больше нет, а требование «файл влезает в контекст целиком»
# от неё никогда и не зависело.
WHOLE_TARGET = 150_000
WHOLE_MAX_RATIO = 1.10
WHOLE_MIN_RATIO = 0.85
# Медиана сжатия второй половины файла к первой. Ниже — хвост обокраден в пользу начала.
# Замер 2026-08-27 на живом файле дал 1.30 (15,1% против 19,7%), то есть порог 0.6
# от реального поведения далеко и ложно срабатывать не должен.
GRADIENT_FLOOR = 0.6


def wiki_pages(root: Path) -> set:
    """Id страниц вики: всё в `pages/**` кроме релиз-ноутов — их несёт отдельный блок."""
    base = root / "pages"
    return {str(p.relative_to(base))[:-3] for p in base.rglob("*.md")
            if "ReleaseNotes" not in p.relative_to(base).parts}


def page_coverage(text: str, root: Path) -> list:
    """Страницы вики, не упомянутые в файле ни разу. Неупомянутая выпадает из файла целиком."""
    return sorted(wiki_pages(root) - _page_refs(text))


def _section_ratios(text: str, root: Path) -> list:
    """Сжатие каждого раздела: его объём к объёму процитированных в нём страниц.

    Страницу, упомянутую в нескольких разделах, делим между ними — иначе сквозная сводка
    со ссылками на пол-вики выглядела бы катастрофически пересжатой.
    """
    chunks = [c for c in re.split(r"\n(?=## )", text) if c.startswith("## ")]
    refs_by_chunk = [_page_refs(c) for c in chunks]
    times = Counter(pid for refs in refs_by_chunk for pid in refs)
    sizes = {}
    for pid in times:
        p = root / "pages" / f"{pid}.md"
        sizes[pid] = len(p.read_text(encoding="utf-8")) if p.exists() else 0
    out = []
    for chunk, refs in zip(chunks, refs_by_chunk):
        src = sum(sizes[pid] / times[pid] for pid in refs)
        if src:
            out.append(len(chunk) / src)
    return out


def gradient(text: str, root: Path) -> tuple:
    """(медиана сжатия первой половины разделов, второй). (0.0, 0.0) — считать не по чему."""
    ratios = _section_ratios(text, root)
    if len(ratios) < 4:
        return 0.0, 0.0
    half = len(ratios) // 2
    return statistics.median(ratios[:half]), statistics.median(ratios[half:])


def whole_file_problems(text: str, root: Path) -> list:
    """Жёсткое: файл влезает в контекст и не ссылается на несуществующие страницы."""
    out = []
    ceiling = int(WHOLE_TARGET * WHOLE_MAX_RATIO)
    if len(text) > ceiling:
        out.append(f"размер файла {len(text)} выше потолка {ceiling} "
                   f"= {WHOLE_TARGET} (цель) × {WHOLE_MAX_RATIO}. Файл обязан влезать "
                   f"в контекст целиком, поэтому это жёсткий отказ.")
    for pid in sorted(_page_refs(text)):
        if not (root / "pages" / f"{pid}.md").exists():
            out.append(f"битая ссылка на страницу: {pid}")
    return sorted(set(out))


def whole_file_warnings(text: str, root: Path) -> list:
    """Мягкое: тонкий файл, непокрытые страницы, просевший хвост. Записи не блокирует.

    Все три проверки на живых прогонах ещё не работали. Прежний спек уже наступал на эти
    грабли: проверку покрытия сделали блокером, не увидев её на реальных данных, и
    решение пришлось отменять. Поднимать в блокеры — по результатам эксплуатации.
    """
    out = []
    floor = int(WHOLE_TARGET * WHOLE_MIN_RATIO)
    if len(text) < floor:
        out.append(f"размер файла {len(text)} ниже ориентира {floor} "
                   f"({WHOLE_TARGET} — цель — × {WHOLE_MIN_RATIO}). Файл записан, но "
                   f"недобирает: смотреть, не выпала ли тема целиком.")
    missing = page_coverage(text, root)
    if missing:
        out.append("страницы не упомянуты в файле (выпадают из него целиком): "
                   + ", ".join(missing))
    first, second = gradient(text, root)
    if first and second / first < GRADIENT_FLOOR:
        out.append(f"хвост файла сжат сильнее начала: медиана сжатия второй половины "
                   f"{second:.1%} против {first:.1%} у первой. Похоже, объём растрачен "
                   f"на первых темах, а поздние получили остаток.")
    return out
```

В начало файла добавить `from collections import Counter`.

- [ ] **Step 4: Запустить тесты**

Run: `cd tools && python3 -m pytest tests/test_compact_guard.py -v`
Expected: PASS, включая существующие тесты посекционного guard (их пока не трогаем)

- [ ] **Step 5: Коммит**

```bash
cd tools && git add compact/guard.py tests/test_compact_guard.py
git commit -m "feat: файловые проверки цельного контекста без карты разделов"
```

---

### Task 4: Сборка файла и оркестрация полной пересборки

**Files:**
- Modify: `compact/assemble.py`
- Modify: `compact/pipeline.py`
- Modify: `compact/report.py`
- Modify: `wiki_cli.py`
- Test: `tests/test_compact_assemble.py`, `tests/test_compact_pipeline.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `assemble.build_header`, `assemble.build_releases_block`, `releases.latest`, `wholegen.rebuild`, `guard.whole_file_problems`, `guard.whole_file_warnings`
- Produces:
  - `assemble.build_whole(body: str, *, releases_block: str, built_on: str) -> str`
  - `pipeline.run_rebuild(*, root: Path | None = None, agent_fn=None, git_run=None, releases_n: int = 5, built_on: str | None = None) -> dict` → `{"mode": "rebuild", "written": bool, "problems": list, "warnings": list, "undated": list, "date_problems": list, "chars": int, "out": Path}`
  - `report.render_whole(res: dict) -> str`, `report.exit_code_whole(res: dict) -> int` (0 чисто, 1 проблема)

- [ ] **Step 1: Написать падающие тесты сборки**

```python
def test_build_whole_puts_header_first_and_releases_last():
    out = assemble.build_whole("## Заявки\n\nТело.\n",
                               releases_block="## Последние релизы\n\n- **2026-08-01** — Р\n",
                               built_on="2026-08-27")
    assert out.startswith("# HubEx — сжатый контекст продукта")
    assert "2026-08-27" in out
    assert out.index("## Заявки") < out.index("## Последние релизы")


def test_build_whole_without_releases_block():
    out = assemble.build_whole("## Заявки\n\nТело.\n", releases_block="",
                               built_on="2026-08-27")
    assert "Последние релизы" not in out
    assert out.rstrip().endswith("Тело.")
```

- [ ] **Step 2: Написать падающие тесты оркестрации**

```python
BODY = "## Заявки\n\nТело. [user/CreatingTicket]\n"


def _mkwiki(tmp_path, ids):
    for pid in ids:
        p = tmp_path / "pages" / f"{pid}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("я" * 500, encoding="utf-8")


def _agent_writing(body):
    def fake(prompt, *, cwd, **kw):
        p = Path(cwd) / wholegen.BODY_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        return ""
    return fake


def test_run_rebuild_writes_file(tmp_path):
    _mkwiki(tmp_path, ["user/CreatingTicket"])
    res = pipeline.run_rebuild(root=tmp_path, agent_fn=_agent_writing(BODY),
                               git_run=lambda *a, **k: "", built_on="2026-08-27")
    assert res["written"] is True
    assert res["problems"] == []
    out = (tmp_path / assemble.OUT_REL).read_text(encoding="utf-8")
    assert out.startswith("# HubEx — сжатый контекст продукта")
    assert "## Заявки" in out


def test_run_rebuild_does_not_write_when_guard_fails(tmp_path):
    _mkwiki(tmp_path, ["user/CreatingTicket"])
    bad = "## Заявки\n\nТело. [user/Missing]\n"
    res = pipeline.run_rebuild(root=tmp_path, agent_fn=_agent_writing(bad),
                               git_run=lambda *a, **k: "", built_on="2026-08-27")
    assert res["written"] is False
    assert any("битая ссылка" in p for p in res["problems"])
    assert not (tmp_path / assemble.OUT_REL).exists()


def test_run_rebuild_keeps_previous_file_when_guard_fails(tmp_path):
    _mkwiki(tmp_path, ["user/CreatingTicket"])
    prev = tmp_path / assemble.OUT_REL
    prev.write_text("прежний файл\n", encoding="utf-8")
    bad = "## Заявки\n\nТело. [user/Missing]\n"
    pipeline.run_rebuild(root=tmp_path, agent_fn=_agent_writing(bad),
                         git_run=lambda *a, **k: "", built_on="2026-08-27")
    assert prev.read_text(encoding="utf-8") == "прежний файл\n"


def test_run_rebuild_propagates_agent_failure(tmp_path):
    _mkwiki(tmp_path, ["user/CreatingTicket"])
    res = pipeline.run_rebuild(root=tmp_path, agent_fn=lambda p, **kw: "",
                               git_run=lambda *a, **k: "", built_on="2026-08-27")
    assert res["written"] is False
    assert any("не создан" in p for p in res["problems"])


def test_run_rebuild_reports_uncovered_page_as_warning(tmp_path):
    _mkwiki(tmp_path, ["user/CreatingTicket", "user/Forgotten"])
    res = pipeline.run_rebuild(root=tmp_path, agent_fn=_agent_writing(BODY),
                               git_run=lambda *a, **k: "", built_on="2026-08-27")
    assert res["written"] is True
    assert any("user/Forgotten" in w for w in res["warnings"])
```

- [ ] **Step 3: Запустить, убедиться что падает**

Run: `cd tools && python3 -m pytest tests/test_compact_assemble.py tests/test_compact_pipeline.py -v -k "whole or rebuild"`
Expected: FAIL — `AttributeError: module 'compact.assemble' has no attribute 'build_whole'`

- [ ] **Step 4: Реализовать сборку**

В `compact/assemble.py`:

```python
def build_whole(body: str, *, releases_block: str, built_on: str) -> str:
    """Шапка + тело от модели + блок релизов. Подмены id нет: карты разделов больше нет."""
    parts = [build_header(built_on), "", body.strip("\n")]
    if releases_block:
        parts.append("")
        parts.append(releases_block.rstrip("\n"))
    return "\n".join(parts).rstrip("\n") + "\n"
```

- [ ] **Step 5: Реализовать оркестрацию**

В `compact/pipeline.py` добавить (существующий `run_compact` пока не трогаем — он уйдёт в Задаче 8):

```python
def run_rebuild(*, root: Path | None = None, agent_fn=None, git_run=None,
                releases_n: int = 5, built_on: str | None = None) -> dict:
    """Полная пересборка: агент пишет тело, пайплайн оборачивает его и проверяет.

    Прежний файл переживает провал: пишем только после того, как guard дал добро.
    Устаревший цельный файл честен, свежий файл с дырой врёт умолчанием.
    """
    root = _root(root)
    built_on = built_on or date.today().isoformat()
    gen = wholegen.rebuild(root, **({} if agent_fn is None else {"agent_fn": agent_fn}))
    out = root / assemble.OUT_REL
    if gen["problems"]:
        return {"mode": "rebuild", "written": False, "problems": gen["problems"],
                "warnings": [], "undated": [], "date_problems": [], "chars": 0, "out": out}
    picked, undated = releases.latest(releases_n, root, run=git_run)
    text = assemble.build_whole(
        gen["body"], releases_block=assemble.build_releases_block(picked, root),
        built_on=built_on)
    problems = guard.whole_file_problems(text, root)
    written = not problems
    if written:
        out.write_text(text, encoding="utf-8")
    return {"mode": "rebuild", "written": written, "problems": problems,
            "warnings": guard.whole_file_warnings(text, root), "undated": undated,
            "date_problems": releases.override_problems(root),
            "chars": len(text), "out": out}
```

Импорт `wholegen` добавить в шапку модуля.

- [ ] **Step 6: Реализовать отчёт**

В `compact/report.py`:

```python
def exit_code_whole(res: dict) -> int:
    """0 — чисто; 1 — файл не прошёл проверку и не записан."""
    return 1 if res["problems"] else 0


def render_whole(res: dict) -> str:
    """Отчёт цельной сборки: размер, что записано, проблемы и предупреждения."""
    head = "полная пересборка" if res["mode"] == "rebuild" else "правка по диффу"
    lines = [f"## Сжатый контекст ({head})", ""]
    lines.append(f"- размер файла: {res['chars']} символов")
    lines.append(f"- записан: {'да' if res['written'] else 'НЕТ'}")
    for p in res["problems"]:
        lines.append(f"- ПРОБЛЕМА: {p}")
    for w in res["warnings"]:
        lines.append(f"- предупреждение: {w}")
    for d in res.get("undated", []):
        lines.append(f"- релиз без даты: {d}")
    for d in res.get("date_problems", []):
        lines.append(f"- ПРОБЛЕМА с датой релиза: {d}")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 7: Подключить к CLI**

В `wiki_cli.py` добавить к парсеру `compact` флаг и ветку в `main`:

```python
    cp.add_argument("--rebuild", action="store_true",
                    help="полная пересборка файла одним проходом модели по всей вике "
                         "(около часа; обычный режим — правка по диффу)")
```

```python
    if args.command == "compact" and args.rebuild:
        res = compact_pipeline.run_rebuild()
        text = compact_report.render_whole(res)
        print(text, end="")
        if args.report_file:
            args.report_file.write_text(text, encoding="utf-8")
        return compact_report.exit_code_whole(res)
```

Тест в `tests/test_cli.py`:

```python
def test_compact_rebuild_calls_run_rebuild(monkeypatch, capsys):
    seen = {}

    def fake(**kw):
        seen["called"] = True
        return {"mode": "rebuild", "written": True, "problems": [], "warnings": [],
                "undated": [], "date_problems": [], "chars": 150000,
                "out": Path("hubex-context.md")}

    monkeypatch.setattr(wiki_cli.compact_pipeline, "run_rebuild", fake)
    assert wiki_cli.main(["compact", "--rebuild"]) == 0
    assert seen["called"]
    assert "150000" in capsys.readouterr().out
```

- [ ] **Step 8: Запустить все тесты**

Run: `cd tools && python3 -m pytest -v`
Expected: PASS, ни один существующий тест не сломан

- [ ] **Step 9: Коммит**

```bash
cd tools && git add compact/assemble.py compact/pipeline.py compact/report.py wiki_cli.py tests/
git commit -m "feat: полная пересборка цельного файла контекста и её отчёт"
```

---

### Task 5: Живая полная пересборка

Первый настоящий прогон. Не автоматизируется и требует человека рядом: около часа работы модели и решение о том, годится ли результат.

**Files:**
- Modify: `context/body.md` (создаётся прогоном), `hubex-context.md` (в контент-репо)

**Interfaces:**
- Consumes: `wiki_cli.py compact --rebuild`
- Produces: собранный `hubex-context.md`, воспроизводимый пайплайном

- [ ] **Step 1: Убедиться, что дерево контент-репо чисто или его состояние осознано**

```bash
cd /home/cvetkov_es/development/HubEx.Wiki && git status --short
```

Незакоммиченные изменения отменяют ночной крон — это нормально на время работы, но должно быть решением, а не случайностью.

- [ ] **Step 2: Запустить пересборку**

```bash
cd /home/cvetkov_es/development/HubEx.Wiki && time python3 tools/wiki_cli.py compact --rebuild --report-file /tmp/rebuild-report.md
```

Expected: код возврата 0, файл `hubex-context.md` записан, размер в отчёте 135 000–165 000 символов. Ожидаемое время — около часа.

- [ ] **Step 3: Проверить результат независимо от отчёта**

```bash
cd /home/cvetkov_es/development/HubEx.Wiki && python3 - <<'EOF'
import re, pathlib
t = open('hubex-context.md', encoding='utf-8').read()
ids = {f'{a}/{b}' for a, b in re.findall(r'\[(admin|user)/([A-Za-z0-9_]+)\]', t)}
disk = {str(p)[6:-3] for p in pathlib.Path('pages').rglob('*.md') if 'ReleaseNotes' not in str(p)}
print('символов:', len(t))
print('разделов:', len(re.findall(r'^## ', t, flags=re.M)))
print('страниц упомянуто:', len(ids & disk), 'из', len(disk))
print('битых ссылок:', sorted(ids - disk) or 'нет')
print('блок релизов:', 'Последние релизы' in t)
EOF
```

- [ ] **Step 4: Прогнать замер полноты**

Набор из 40 вопросов и эталоны лежат в скретчпаде сессии, где проводился замер 2026-08-27 (`scratchpad/recall/facts-A.md`, `facts-B.md`, `questions.md`). Если скретчпад уже стёрт — этот шаг пропускается с явной отметкой в отчёте, а не выполняется наспех заново: набор вопросов дороже одного прогона.

- [ ] **Step 5: Коммит контент-репо**

```bash
cd /home/cvetkov_es/development/HubEx.Wiki && git add hubex-context.md context/body.md
git commit -m "feat: сжатый контекст собран цельным проходом"
```

---

### Task 6: Промпт и механизм правки по диффу

**Files:**
- Create: `compact/prompts/patch.md`
- Create: `compact/patch.py`
- Test: `tests/test_compact_patch.py`

**Interfaces:**
- Consumes: `model_client.run_agent`, `pipeline.significant` (существует)
- Produces:
  - `patch.MODEL = "opus"`, `patch.TIMEOUT = 1800`
  - `patch.page_diff(pid: str, old: str, new: str) -> str` — unified diff содержательных частей
  - `patch.build_prompt(*, diffs: str, body_rel: str, target_chars: int) -> str`
  - `patch.apply(root: Path, *, changed: dict, previous: dict, agent_fn=None) -> dict` → `{"body": str, "problems": list, "chars": int, "pages": list}`; `changed` — `{pid: новый текст}`, `previous` — `{pid: прежний текст}`

- [ ] **Step 1: Написать промпт**

Создать `compact/prompts/patch.md`:

```markdown
Ты правишь готовый файл-контекст продукта HubEx по изменениям в вики.

Файл: `{body_rel}` — тело сжатого контекста для облачного ИИ-агента. Читатель — машина.
Телеграфный стиль, без вводных оборотов и маркетинга.

## Задача

Ниже дан дифф изменившихся страниц вики. Внеси в файл **точечные правки**, отражающие
эти изменения. Не переписывай файл заново и не трогай то, чего изменения не касаются.

Порядок работы:

1. Прочитай файл целиком.
2. По каждому изменению найди в файле место, где этот факт живёт, — он может лежать не
   в одном месте и не в том разделе, где ты его ждёшь. Ищи по названиям сущностей и
   полей, а не по названиям разделов.
3. Правь на месте. Факта в файле не было и он существенный — добавь в подходящий раздел.
   Факт из вики пропал — убери его и из файла.
4. Если изменение косметическое (переформулировка без нового смысла) — не трогай файл.

## Три запрета на выдумывание

1. **Факт действует ровно там, где он сказан.** Не переноси утверждение с одного объекта
   на семейство.
2. **Молчание источника — не факт.** «Только у X», «в отличие от Y», «Z недоступно» —
   лишь когда противопоставление прямо стоит в тексте.
3. **Квалификаторы сохраняй дословно.** «По умолчанию», «может быть», «обычно»,
   «рекомендуется» несут смысл.

## Ограничения

- Ссылки на страницы — только короткие id вида `[admin/SLA]`. Полные URL не приводить.
- Заголовков глубже `##` не вводить.
- Целевой размер файла — около {target_chars} символов. Правка не повод его раздувать:
  добавил абзац — посмотри, нет ли рядом того, что этот абзац делает лишним.
- Шапку файла и блок «Последние релизы» не трогай: их ведёт пайплайн, а в этом файле
  их нет вовсе.

## Изменения в вики

{diffs}

## Что вернуть в ответе

Перечисли одной строкой на изменение: что поменял и в каком разделе. Если по какому-то
изменению ничего не правил — так и напиши, с причиной.
```

- [ ] **Step 2: Написать падающие тесты**

```python
def test_page_diff_shows_added_line():
    d = patch.page_diff("user/A", "строка один\n", "строка один\nстрока два\n")
    assert "user/A" in d
    assert "+строка два" in d


def test_page_diff_ignores_frontmatter_and_nav_tail():
    old = "---\ncontent_hash: aaa\n---\nтело\n\n[Перейти в меню](http://x)\n"
    new = "---\ncontent_hash: bbb\n---\nтело\n\n[Перейти в меню](https://x/)\n"
    assert patch.page_diff("user/A", old, new).strip() == ""


def test_prompt_carries_diffs_and_path():
    p = patch.build_prompt(diffs="ДИФФ", body_rel="context/body.md", target_chars=150_000)
    assert "ДИФФ" in p
    assert "context/body.md" in p
    assert "Молчание источника" in p


def test_apply_returns_body_edited_by_agent(tmp_path):
    body = tmp_path / wholegen.BODY_REL
    body.parent.mkdir(parents=True, exist_ok=True)
    body.write_text("## Заявки\n\nСтарый факт.\n", encoding="utf-8")

    def fake_agent(prompt, *, cwd, **kw):
        assert "ДИФФ" not in prompt  # промпт несёт настоящий дифф, а не заглушку
        (Path(cwd) / wholegen.BODY_REL).write_text(
            "## Заявки\n\nНовый факт.\n", encoding="utf-8")
        return "поправил раздел Заявки"

    res = patch.apply(tmp_path, changed={"user/A": "новое\n"},
                      previous={"user/A": "старое\n"}, agent_fn=fake_agent)
    assert res["problems"] == []
    assert "Новый факт" in res["body"]
    assert res["pages"] == ["user/A"]


def test_apply_is_a_noop_when_all_changes_are_cosmetic(tmp_path):
    body = tmp_path / wholegen.BODY_REL
    body.parent.mkdir(parents=True, exist_ok=True)
    body.write_text("## Заявки\n\nФакт.\n", encoding="utf-8")
    old = "---\ncontent_hash: aaa\n---\nтело\n"
    new = "---\ncontent_hash: bbb\n---\nтело\n"

    called = []
    res = patch.apply(tmp_path, changed={"user/A": new}, previous={"user/A": old},
                      agent_fn=lambda *a, **kw: called.append(1))
    assert called == []
    assert res["pages"] == []
    assert res["body"] == "## Заявки\n\nФакт.\n"


def test_apply_reports_missing_body(tmp_path):
    res = patch.apply(tmp_path, changed={"user/A": "новое\n"},
                      previous={"user/A": "старое\n"}, agent_fn=lambda *a, **kw: "")
    assert any("не найден" in p for p in res["problems"])


def test_apply_reports_model_error(tmp_path):
    body = tmp_path / wholegen.BODY_REL
    body.parent.mkdir(parents=True, exist_ok=True)
    body.write_text("## Заявки\n\nФакт.\n", encoding="utf-8")

    def boom(prompt, **kw):
        raise model_client.ModelError("claude -p код 1: нет доступа")

    res = patch.apply(tmp_path, changed={"user/A": "новое\n"},
                      previous={"user/A": "старое\n"}, agent_fn=boom)
    assert any("нет доступа" in p for p in res["problems"])
```

- [ ] **Step 3: Запустить, убедиться что падает**

Run: `cd tools && python3 -m pytest tests/test_compact_patch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'compact.patch'`

- [ ] **Step 4: Реализовать**

```python
"""Ночная правка сжатого контекста по диффу изменившихся страниц вики."""
import difflib
from functools import partial
from pathlib import Path

from compact import pipeline as compact_pipeline, wholegen
from update import model_client

PROMPTS = Path(__file__).resolve().parent / "prompts"
MODEL = "opus"
# Правка на порядок дешевле полной сборки: в контексте один файл и небольшой дифф,
# а не вся вика. Полчаса — запас на десяток изменившихся страниц.
TIMEOUT = 1800


def page_diff(pid: str, old: str, new: str) -> str:
    """Unified diff содержательных частей страницы.

    Сравниваем через `significant`, а не сырые тексты: frontmatter несёт `content_hash`,
    хвост — навигационный шаблон вики, и ни то, ни другое в файл контекста не попадает.
    Косметическая правка шаблона обязана давать пустой дифф, иначе модель полезет
    править файл без причины.
    """
    a = compact_pipeline.significant(old).splitlines(keepends=True)
    b = compact_pipeline.significant(new).splitlines(keepends=True)
    body = "".join(difflib.unified_diff(a, b, fromfile=f"{pid} было",
                                        tofile=f"{pid} стало", n=3))
    return f"### {pid}\n\n```diff\n{body}```\n" if body else ""


def build_prompt(*, diffs: str, body_rel: str, target_chars: int) -> str:
    template = (PROMPTS / "patch.md").read_text(encoding="utf-8")
    return (template.replace("{diffs}", diffs)
            .replace("{body_rel}", body_rel)
            .replace("{target_chars}", str(target_chars)))


def apply(root: Path, *, changed: dict, previous: dict, agent_fn=None) -> dict:
    """Правит тело файла по диффу изменившихся страниц. Пустой дифф — прогон не зовём."""
    body_path = root / wholegen.BODY_REL
    if not body_path.exists():
        return {"body": "", "problems": [f"файл тела не найден: {wholegen.BODY_REL}. "
                                         f"Сначала полная сборка: `compact --rebuild`."],
                "chars": 0, "pages": []}
    parts, pages = [], []
    for pid in sorted(changed):
        d = page_diff(pid, previous.get(pid, ""), changed[pid])
        if d:
            parts.append(d)
            pages.append(pid)
    body = body_path.read_text(encoding="utf-8")
    if not parts:
        return {"body": body, "problems": [], "chars": len(body), "pages": []}
    agent_fn = agent_fn or partial(model_client.run_agent, timeout=TIMEOUT)
    prompt = build_prompt(diffs="\n".join(parts), body_rel=wholegen.BODY_REL,
                          target_chars=wholegen.TARGET_CHARS)
    try:
        agent_fn(prompt, cwd=root, model=MODEL)
    except model_client.ModelError as e:
        return {"body": body, "problems": [str(e)], "chars": len(body), "pages": pages}
    new_body = body_path.read_text(encoding="utf-8")
    return {"body": new_body, "problems": [], "chars": len(new_body), "pages": pages}
```

- [ ] **Step 5: Запустить тесты**

Run: `cd tools && python3 -m pytest tests/test_compact_patch.py -v`
Expected: PASS

- [ ] **Step 6: Коммит**

```bash
cd tools && git add compact/prompts/patch.md compact/patch.py tests/test_compact_patch.py
git commit -m "feat: правка сжатого контекста по диффу изменившихся страниц"
```

---

### Task 7: Ночная оркестрация правки и встройка в sync

**Files:**
- Modify: `compact/pipeline.py`
- Modify: `update/sync.py`
- Test: `tests/test_compact_pipeline.py`, `tests/test_sync.py`

**Interfaces:**
- Consumes: `patch.apply`, `assemble.build_whole`, `guard.whole_file_problems`, `guard.whole_file_warnings`, `releases.latest`
- Produces: `pipeline.run_patch(*, changed: dict, previous: dict, root: Path | None = None, agent_fn=None, git_run=None, releases_n: int = 5, built_on: str | None = None) -> dict` — та же форма результата, что у `run_rebuild`, с `"mode": "patch"` и дополнительным ключом `"pages": list`

- [ ] **Step 1: Написать падающие тесты**

```python
def test_run_patch_writes_file_and_reports_pages(tmp_path):
    _mkwiki(tmp_path, ["user/CreatingTicket"])
    (tmp_path / wholegen.BODY_REL).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / wholegen.BODY_REL).write_text(BODY, encoding="utf-8")

    def fake_agent(prompt, *, cwd, **kw):
        (Path(cwd) / wholegen.BODY_REL).write_text(
            "## Заявки\n\nПоправлено. [user/CreatingTicket]\n", encoding="utf-8")
        return ""

    res = pipeline.run_patch(changed={"user/CreatingTicket": "новое тело\n"},
                             previous={"user/CreatingTicket": "старое тело\n"},
                             root=tmp_path, agent_fn=fake_agent,
                             git_run=lambda *a, **k: "", built_on="2026-08-27")
    assert res["mode"] == "patch"
    assert res["written"] is True
    assert res["pages"] == ["user/CreatingTicket"]
    assert "Поправлено" in (tmp_path / assemble.OUT_REL).read_text(encoding="utf-8")


def test_run_patch_restores_body_when_guard_fails(tmp_path):
    # Агент правит тело на месте. Если после правки файл не проходит guard, тело обязано
    # вернуться к прежнему: иначе следующая ночь начнёт с испорченного файла.
    _mkwiki(tmp_path, ["user/CreatingTicket"])
    body_path = tmp_path / wholegen.BODY_REL
    body_path.parent.mkdir(parents=True, exist_ok=True)
    body_path.write_text(BODY, encoding="utf-8")

    def bad_agent(prompt, *, cwd, **kw):
        (Path(cwd) / wholegen.BODY_REL).write_text(
            "## Заявки\n\nСломано. [user/Missing]\n", encoding="utf-8")
        return ""

    res = pipeline.run_patch(changed={"user/CreatingTicket": "новое\n"},
                             previous={"user/CreatingTicket": "старое\n"},
                             root=tmp_path, agent_fn=bad_agent,
                             git_run=lambda *a, **k: "", built_on="2026-08-27")
    assert res["written"] is False
    assert any("битая ссылка" in p for p in res["problems"])
    assert body_path.read_text(encoding="utf-8") == BODY


def test_run_patch_without_significant_changes_still_rebuilds_releases(tmp_path):
    # Релиз-ноуты меняются отдельно от страниц: даже без правок тела файл пересобирается,
    # иначе блок «Последние релизы» застынет.
    _mkwiki(tmp_path, ["user/CreatingTicket"])
    (tmp_path / wholegen.BODY_REL).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / wholegen.BODY_REL).write_text(BODY, encoding="utf-8")
    res = pipeline.run_patch(changed={}, previous={}, root=tmp_path,
                             agent_fn=lambda *a, **kw: pytest.fail("модель не нужна"),
                             git_run=lambda *a, **k: "", built_on="2026-08-27")
    assert res["written"] is True
    assert res["pages"] == []
```

Тест в `tests/test_sync.py`: `run_sync` зовёт `run_patch`, а не `run_compact`, и передаёт ему изменившиеся страницы вместе с прежними текстами.

```python
def test_sync_hands_changed_and_previous_texts_to_patch(repo):
    """Ночная стадия зовёт `run_patch` и получает и новый текст страницы, и прежний:
    дифф без прежнего текста не построить."""
    seen = {}

    def fake_update(**kw):
        (repo / "pages" / "admin" / "A.md").write_text("стало\n", encoding="utf-8")
        return [{"page": "admin/A", "status": "changed", "error": None,
                 "old_md": "было\n"}]

    def spy_patch(**kw):
        seen.update(kw)
        return {"mode": "patch", "written": True, "problems": [], "warnings": [],
                "undated": [], "date_problems": [], "chars": 150000,
                "pages": ["admin/A"], "out": repo / "hubex-context.md"}

    sync.run_sync(root=repo, today=TODAY, run_update_fn=fake_update,
                  run_compact_fn=spy_patch)

    assert seen["previous"] == {"admin/A": "было\n"}
    assert seen["changed"] == {"admin/A": "стало\n"}
```

Фикстура `repo` и константа `TODAY` уже есть в `tests/test_sync.py`.

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `cd tools && python3 -m pytest tests/test_compact_pipeline.py -v -k patch`
Expected: FAIL — `AttributeError: module 'compact.pipeline' has no attribute 'run_patch'`

- [ ] **Step 3: Реализовать оркестрацию**

```python
def run_patch(*, changed: dict, previous: dict, root: Path | None = None, agent_fn=None,
              git_run=None, releases_n: int = 5, built_on: str | None = None) -> dict:
    """Ночной режим: правка тела по диффу, затем та же сборка и те же проверки.

    Тело правится на месте, поэтому прежнее держим в руках: не прошёл guard — возвращаем
    файл к состоянию до правки. Иначе следующая ночь начнёт с испорченного тела, и
    испортит его дальше.
    """
    root = _root(root)
    built_on = built_on or date.today().isoformat()
    body_path = root / wholegen.BODY_REL
    before = body_path.read_text(encoding="utf-8") if body_path.exists() else ""
    res = patch.apply(root, changed=changed, previous=previous,
                      **({"agent_fn": agent_fn} if agent_fn is not None else {}))
    out = root / assemble.OUT_REL
    if res["problems"]:
        if before:
            body_path.write_text(before, encoding="utf-8")
        return {"mode": "patch", "written": False, "problems": res["problems"],
                "warnings": [], "undated": [], "date_problems": [], "chars": 0,
                "pages": res["pages"], "out": out}
    picked, undated = releases.latest(releases_n, root, run=git_run)
    text = assemble.build_whole(
        res["body"], releases_block=assemble.build_releases_block(picked, root),
        built_on=built_on)
    problems = guard.whole_file_problems(text, root)
    if problems:
        body_path.write_text(before, encoding="utf-8")
        return {"mode": "patch", "written": False, "problems": problems, "warnings": [],
                "undated": undated, "date_problems": [], "chars": len(text),
                "pages": res["pages"], "out": out}
    out.write_text(text, encoding="utf-8")
    return {"mode": "patch", "written": True, "problems": [],
            "warnings": guard.whole_file_warnings(text, root), "undated": undated,
            "date_problems": releases.override_problems(root),
            "chars": len(text), "pages": res["pages"], "out": out}
```

Импорт `patch` добавить в шапку модуля.

- [ ] **Step 4: Переключить sync**

В `update/sync.py` заменить вызов стадии compact:

```python
    run_compact_fn = run_compact_fn or compact_pipeline.run_patch
    changed = {r["page"]: r["new_md"] for r in results
               if r["status"] in ("new", "changed") and r.get("new_md")}
    previous = {r["page"]: r["old_md"] for r in results if r.get("old_md")}
    compact_res = run_compact_fn(changed=changed, previous=previous, root=root)
    text += "\n" + compact_report.render_whole(compact_res)
    if compact_report.exit_code_whole(compact_res) != 0:
```

Если `update` не кладёт в результат `new_md`, взять новый текст со страницы:
`changed = {r["page"]: (root / "pages" / f"{r['page']}.md").read_text(encoding="utf-8") for r in results if r["status"] in ("new", "changed")}`. Проверить, что именно возвращает `update.pipeline.run_update`, и использовать существующий ключ, не изобретая новый.

`COMMIT_PATHS` оставить как есть: `context` теперь содержит `body.md` вместо `sections/`, путь тот же.

- [ ] **Step 5: Запустить все тесты**

Run: `cd tools && python3 -m pytest -v`
Expected: PASS

- [ ] **Step 6: Коммит**

```bash
cd tools && git add compact/pipeline.py update/sync.py tests/
git commit -m "feat: ночная правка контекста по диффу вместо перегенерации разделов"
```

---

### Task 8: Убрать машинерию разделов

Делается последней: до живого прогона Задачи 5 старый путь остаётся рабочим запасным.

**Files:**
- Delete: `compact/sectionmap.py`, `compact/generate.py`, `compact/prompts/tier1.md`, `compact/prompts/tier2.md`
- Delete: `tests/test_compact_map.py`, `tests/test_compact_generate.py`
- Modify: `compact/guard.py`, `compact/pipeline.py`, `compact/assemble.py`, `compact/report.py`, `wiki_cli.py`
- Delete в контент-репо: `context/map.tsv`, `context/sections/`
- Test: `tests/test_compact_guard.py`, `tests/test_compact_pipeline.py`, `tests/test_compact_assemble.py`, `tests/test_cli.py`

- [ ] **Step 1: Удалить модули и их тесты**

```bash
cd tools && git rm compact/sectionmap.py compact/generate.py \
  compact/prompts/tier1.md compact/prompts/tier2.md \
  tests/test_compact_map.py tests/test_compact_generate.py
```

- [ ] **Step 2: Вычистить посекционное из guard**

Удалить из `compact/guard.py`: `MIN_RATIO`, `MAX_RATIO`, `OVERHEAD_CHARS`, `SECTION_BUDGET_TOLERANCE`, `REQUIRED_BLOCKS`, `corridor`, `budget_limit`, `section_problems`, `section_warnings`, `file_problems`, `file_warnings`, импорт `SECTION_ID_RE`. Остаются `_REF_RE`, `_page_refs` и всё, добавленное в Задаче 3.

- [ ] **Step 3: Вычистить посекционное из pipeline и assemble**

Удалить из `compact/pipeline.py`: `_sources_text`, `_todo`, `_blocked`, `run_compact`, `MASS_REBUILD_SHARE`, `MASS_REBUILD_MIN`, импорты `generate`, `sectionmap`. Оставить `significant`, `drop_cosmetic` (их использует `patch.page_diff`), `run_rebuild`, `run_patch`.

Удалить из `compact/assemble.py`: `section_path`, `SECTIONS_DIR_REL`, `substitute_ids`, `build_unplaced_block`, `build`, `_INDEX_BULLET_RE`, импорт `SECTION_ID_RE`. Оставить `build_header`, `build_whole`, `release_summary`, `build_releases_block`, `OUT_REL`.

- [ ] **Step 4: Вычистить report и CLI**

Удалить из `compact/report.py`: `render`, `exit_code`, `_fill`, `_tolerance_note`, `_cosmetic_line` и прочее посекционное. Остаются `render_whole`, `exit_code_whole`.

В `wiki_cli.py` у команды `compact` убрать `--all`, `--section`, `--page`; оставить `--rebuild` и `--report-file`. Без `--rebuild` команда зовёт `run_patch` по страницам, изменившимся с прошлого коммита — либо, если это неудобно определить вне `sync`, требует явного `--rebuild` и печатает подсказку, что ночная правка живёт в `sync`. Выбрать первое, если `update` даёт список изменённых страниц; иначе второе, и написать это в help.

- [ ] **Step 5: Удалить артефакты карты в контент-репо**

```bash
cd /home/cvetkov_es/development/HubEx.Wiki && git rm -r context/map.tsv context/sections
```

- [ ] **Step 6: Запустить все тесты**

Run: `cd tools && python3 -m pytest -v`
Expected: PASS. Число тестов уменьшится — это ожидаемо; проверить, что ни один оставшийся не был про удалённый код.

- [ ] **Step 7: Коммит**

```bash
cd tools && git add -A && git commit -m "refactor: убрана машинерия разделов — файл собирается цельным проходом"
cd /home/cvetkov_es/development/HubEx.Wiki && git add -A && git commit -m "chore: карта разделов и посекционные тексты больше не нужны"
```

---

### Task 9: Документация

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `AGENTS.md` (контент-репо), `tools/README.md` (если есть)

- [ ] **Step 1: Обновить правила «руками не править»**

В `CLAUDE.md` и `AGENTS.md` заменить строку про `context/sections/**` на `context/body.md`, а команду `compact` — на `compact --rebuild`. Формулировка: «`context/body.md` и `hubex-context.md` руками не правь — их ведёт пайплайн».

- [ ] **Step 2: Обновить README**

Описать два режима: ночная правка по диффу (внутри `sync`) и полная пересборка `compact --rebuild` (около часа, раз в квартал либо после крупных изменений вики). Убрать описание карты разделов, бюджетов и яруса 2. Добавить, что набор из 40 вопросов — способ проверить полноту после пересборки.

- [ ] **Step 3: Проставить ссылку в старом спеке**

В начало `docs/superpowers/specs/2026-08-25-compact-context-design.md` добавить строку: «Архитектурная часть отменена [2026-08-27-whole-file-context-design.md](2026-08-27-whole-file-context-design.md) по итогам замера. Документ сохранён ради обоснований, переживших смену метода».

- [ ] **Step 4: Коммит**

```bash
cd /home/cvetkov_es/development/HubEx.Wiki && git add README.md CLAUDE.md AGENTS.md docs/
git commit -m "docs: цельный файл контекста и правка по диффу"
```

---

## Self-Review

**Покрытие спека.** Полная сборка агентным прогоном — Задачи 1, 2, 4, 5. Патч-обновление — Задачи 6, 7. Файловые проверки без карты, включая градиент и покрытие как предупреждения — Задача 3. Явная модель `opus` — Задачи 2 и 6 (константа `MODEL`), проверяется тестом в Задаче 2. Удаление карты и яруса 2 — Задача 8. Сохранение шапки, блока релизов и фильтра косметики — Задачи 4, 6, 8. Квартальная пересборка и замер на 40 вопросах — Задача 5, шаг 4, и Задача 9, шаг 2.

**Незакрытое спеком.** Требование промпта различать «страницы противоречат» и «страницы говорят о разном» — в промпте Задачи 2, раздел про противоречия.

**Типы.** `run_agent` возвращает `str` и принимает `cwd`, `timeout`, `model`, `tools` — так его зовут `wholegen.rebuild` и `patch.apply`. `wholegen.rebuild` и `patch.apply` возвращают `dict` с ключами `body`/`problems`/`chars`, у `patch.apply` добавлен `pages` — так их читают `run_rebuild` и `run_patch`. `run_rebuild` и `run_patch` возвращают одинаковую форму с `mode`, что и позволяет одному `render_whole` печатать обе.
