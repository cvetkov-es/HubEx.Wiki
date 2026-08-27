# Артефакты сжатого контекста на ветке-сироте — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Убрать `hubex-context.md` и `context/body.md` из рабочего дерева репозитория вики, сохранив их историю и читаемый ночной дифф.

**Architecture:** Артефакты переезжают на ветку-сироту `dist/context` того же репозитория, подключённую отдельным git-worktree в каталог `.context-dist/` внутри репозитория. Каталог — в `.gitignore`, существует только на машине пайплайна; свежий клон `main` содержит одну вики. Worktree лежит внутри корня репозитория намеренно: рабочий каталог агента остаётся прежним, второй корень пайплайну не нужен, меняются только две константы пути.

**Tech Stack:** Python 3.11+, pytest, git 2.34 (без `worktree add --orphan`), git-сабмодуль `tools/`.

**Spec:** `docs/superpowers/specs/2026-08-27-whole-file-context-design.md`, раздел «Поправка 2026-08-27: артефакты уходят из рабочего дерева вики»

## Global Constraints

- Каталог артефактов — `.context-dist/`, ветка — `dist/context`. Обе величины задаются константами в одном месте.
- Корень вики (`root`) остаётся единственным корнем пайплайна: проверки ссылок, покрытия и релиз-ноутов по-прежнему смотрят в `root/pages`. Артефакты адресуются относительными путями внутрь `.context-dist/`.
- Комментарии и docstrings — **по-русски**, объясняют «почему», а не «что».
- Строго TDD. Ничего сверх задачи.
- Сейчас 226 тестов зелёные, прогон обязан остаться зелёным.
- **Ничего не писать в существующие `/home/cvetkov_es/development/HubEx.Wiki/context/` и `hubex-context.md` до Задачи 3** — там действующий файл продукта, его переносит именно Задача 3.

---

### Task 1: Пути артефактов ведут в каталог worktree

**Files:**
- Create: `compact/artifacts.py`
- Modify: `compact/assemble.py`, `compact/wholegen.py`, `compact/pipeline.py`
- Test: `tests/test_compact_artifacts.py`, `tests/test_compact_pipeline.py`

**Interfaces:**
- Produces:
  - `artifacts.DIR = ".context-dist"`, `artifacts.BRANCH = "dist/context"`
  - `artifacts.BODY_REL = ".context-dist/body.md"`, `artifacts.OUT_REL = ".context-dist/hubex-context.md"`
  - `artifacts.missing_problem(root: Path) -> str | None` — текст ошибки, если каталога артефактов нет, иначе `None`
- Consumes: ничего нового

- [ ] **Step 1: Написать падающие тесты**

```python
from pathlib import Path

from compact import artifacts


def test_paths_point_inside_artifact_dir():
    assert artifacts.DIR == ".context-dist"
    assert artifacts.BRANCH == "dist/context"
    assert artifacts.BODY_REL == f"{artifacts.DIR}/body.md"
    assert artifacts.OUT_REL == f"{artifacts.DIR}/hubex-context.md"


def test_missing_problem_names_branch_and_setup(tmp_path):
    msg = artifacts.missing_problem(tmp_path)
    assert msg is not None
    assert artifacts.DIR in msg
    assert artifacts.BRANCH in msg
    assert "git worktree add" in msg


def test_missing_problem_silent_when_dir_exists(tmp_path):
    (tmp_path / artifacts.DIR).mkdir()
    assert artifacts.missing_problem(tmp_path) is None
```

И в `tests/test_compact_pipeline.py` — что оркестраторы пишут именно туда:

```python
def test_run_rebuild_writes_into_artifact_dir(tmp_path):
    _mkwiki(tmp_path, ["user/CreatingTicket"])
    (tmp_path / artifacts.DIR).mkdir()
    res = pipeline.run_rebuild(root=tmp_path, agent_fn=_agent_writing(BODY),
                               git_run=lambda *a, **k: "", built_on="2026-08-27")
    assert res["written"] is True
    assert (tmp_path / artifacts.OUT_REL).exists()
    assert not (tmp_path / "hubex-context.md").exists()


def test_run_rebuild_reports_missing_artifact_dir(tmp_path):
    _mkwiki(tmp_path, ["user/CreatingTicket"])
    res = pipeline.run_rebuild(root=tmp_path, agent_fn=lambda *a, **kw: None,
                               git_run=lambda *a, **k: "", built_on="2026-08-27")
    assert res["written"] is False
    assert any(artifacts.BRANCH in p for p in res["problems"])
```

Существующие тесты, создающие тело, надо поправить: они кладут его по `wholegen.BODY_REL`, значение которого меняется, — путь подтянется сам, но каталог `.context-dist` в `tmp_path` теперь нужно создавать. Правь только создание каталога, утверждения не трогай.

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `cd tools && python3 -m pytest tests/test_compact_artifacts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'compact.artifacts'`

- [ ] **Step 3: Реализовать модуль**

```python
"""Где живут артефакты сжатого контекста: каталог worktree ветки-сироты.

Артефакты не лежат в рабочем дереве вики намеренно. Репозиторий существует ради
достоверности: агент, которому дали папку, идёт `index.md` → `pages/` и читает
первоисточник. Сжатый файл рядом с оглавлением выглядит готовым ответом — агент возьмёт
его и остановится, имея под рукой полную версию. Хуже того, индексатор над папкой получит
куски и из страницы, и из её лоссового пересказа, и вернёт на запрос оба. Инструкцией это
не лечится: её прочитает Claude Code, а сторонний индексатор — нет.

Каталог лежит внутри корня репозитория и добавлен в `.gitignore`: так рабочий каталог
агента остаётся прежним, а свежий клон `main` содержит одну вики.
"""
from pathlib import Path

DIR = ".context-dist"
BRANCH = "dist/context"
BODY_REL = f"{DIR}/body.md"
OUT_REL = f"{DIR}/hubex-context.md"


def missing_problem(root: Path) -> str | None:
    """Текст ошибки, если worktree артефактов не подключён. Иначе None.

    Git 2.34 не умеет `worktree add --orphan`, поэтому ветка создаётся плюмбингом —
    пустым коммитом поверх пустого дерева, без касания рабочего дерева вики.
    """
    if (root / DIR).is_dir():
        return None
    return (
        f"каталог артефактов {DIR} не подключён. Артефакты живут на ветке-сироте "
        f"{BRANCH} отдельным worktree — создать так:\n"
        f"  EMPTY=$(git hash-object -t tree /dev/null)\n"
        f"  COMMIT=$(git commit-tree \"$EMPTY\" -m 'chore: ветка артефактов')\n"
        f"  git branch {BRANCH} \"$COMMIT\"\n"
        f"  git push -u origin {BRANCH}\n"
        f"  git worktree add {DIR} {BRANCH}")
```

- [ ] **Step 4: Перевести константы путей**

В `compact/assemble.py` заменить `OUT_REL = "hubex-context.md"` на реэкспорт из нового модуля:

```python
from compact.artifacts import OUT_REL  # noqa: F401 — путь артефакта задан в одном месте
```

В `compact/wholegen.py` — то же с `BODY_REL`:

```python
from compact.artifacts import BODY_REL  # noqa: F401 — путь артефакта задан в одном месте
```

Оба модуля продолжают отдавать эти имена наружу: их читают `pipeline` и `patch`, менять их обращения не нужно.

- [ ] **Step 5: Проверка наличия каталога в оркестраторах**

В `compact/pipeline.py`, в начале `run_rebuild` и `run_patch`, сразу после `root = _root(root)`:

```python
    missing = artifacts.missing_problem(root)
    if missing:
        return {"mode": "rebuild", "written": False, "problems": [missing],
                "warnings": [], "undated": [], "date_problems": [], "chars": 0,
                "body_mtime": None, "out": root / assemble.OUT_REL}
```

Для `run_patch` — та же форма с `"mode": "patch"` и `"pages": []`, без `body_mtime`.

Импорт `artifacts` добавить в шапку модуля.

- [ ] **Step 6: Прогнать все тесты**

Run: `cd tools && python3 -m pytest -q`
Expected: PASS

- [ ] **Step 7: Коммит**

```bash
cd tools && git add -A
git commit -m "feat: артефакты сжатого контекста адресуются в каталог worktree"
```

---

### Task 2: Ночной прогон коммитит артефакты в ветку-сироту

**Files:**
- Modify: `update/sync.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- Consumes: `artifacts.DIR`, `artifacts.BRANCH`
- Produces: `sync.commit_artifacts(root: Path, *, today: date, git_run=None) -> dict` → `{"status": str, "report": str}`; статусы `committed`, `no-changes`, `failed`

- [ ] **Step 1: Написать падающие тесты**

```python
def test_commit_paths_no_longer_carry_artifacts():
    # Артефакты уходят отдельным коммитом в ветку-сироту, в main их больше нет.
    assert "hubex-context.md" not in sync.COMMIT_PATHS
    assert "context" not in sync.COMMIT_PATHS
    assert "pages" in sync.COMMIT_PATHS


def test_artifacts_committed_to_orphan_branch(repo):
    """Артефакты коммитятся в своём worktree, а не в основном дереве."""
    art = repo / artifacts.DIR
    art.mkdir()
    (art / "hubex-context.md").write_text("контекст\n", encoding="utf-8")
    calls = []

    def fake_git(cwd, *args):
        calls.append((str(cwd), args))
        return ""

    res = sync.commit_artifacts(repo, today=TODAY, git_run=fake_git)
    assert res["status"] in ("committed", "no-changes")
    assert all(str(art) in c[0] for c in calls), "все git-команды идут в worktree артефактов"
    assert any(a[0] == "push" for _, a in calls) or res["status"] == "no-changes"


def test_sync_stops_before_main_commit_when_artifacts_fail(repo):
    """Провал артефактов останавливает прогон до коммита вики: лучше ничего, чем половина."""
    before = head(repo)
    res = sync.run_sync(root=repo, today=TODAY, run_compact_fn=compact_ok,
                        run_update_fn=writes(repo, {"pages/admin/A.md": "свежее\n"}),
                        commit_artifacts_fn=lambda *a, **kw: {
                            "status": "failed", "report": "push не прошёл"})
    assert res["code"] == 4
    assert head(repo) == before
```

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `cd tools && python3 -m pytest tests/test_sync.py -v -k "artifact or commit_paths"`
Expected: FAIL — `AttributeError: module 'update.sync' has no attribute 'commit_artifacts'`

- [ ] **Step 3: Реализовать**

В `update/sync.py`:

```python
COMMIT_PATHS = ("pages", "index.md", "releasenotes-index.md")


def commit_artifacts(root: Path, *, today: date, git_run=None) -> dict:
    """Коммит и пуш артефактов в их собственном worktree на ветке-сироте.

    Отдельный коммит, а не часть основного: артефакты не лежат в рабочем дереве вики,
    и `main` о них ничего не знает. История и читаемый дифф при этом сохраняются —
    ради них артефакты и держатся в git.
    """
    art = root / artifacts.DIR
    run = git_run or (lambda cwd, *a: _git(cwd, *a))
    ...
```

Реализация: `add -A`, проверка `diff --cached --name-only`, при пустом — `no-changes`; иначе `commit -m` с датой и `push origin <BRANCH>`; ненулевой код любой команды — `failed` с текстом в `report`.

В `run_sync` вызвать `commit_artifacts` **до** коммита основного дерева, параметром `commit_artifacts_fn` (для тестов), и при `failed` вернуть код 4, не трогая `main`.

- [ ] **Step 4: Прогнать все тесты**

Run: `cd tools && python3 -m pytest -q`
Expected: PASS

- [ ] **Step 5: Коммит**

```bash
cd tools && git add -A
git commit -m "feat: артефакты коммитятся отдельно, в ветку-сироту"
```

---

### Task 3: Перенос артефактов и документация

**Files:**
- Контент-репо: `.gitignore`, `README.md`, `CLAUDE.md`, `AGENTS.md`, удаление `hubex-context.md` и `context/`
- Пайплайн: `tools/README.md`

- [ ] **Step 1: Создать ветку-сироту и worktree**

```bash
cd /home/cvetkov_es/development/HubEx.Wiki
EMPTY=$(git hash-object -t tree /dev/null)
COMMIT=$(git commit-tree "$EMPTY" -m "chore: ветка артефактов сжатого контекста")
git branch dist/context "$COMMIT"
git push -u origin dist/context
git worktree add .context-dist dist/context
```

- [ ] **Step 2: Перенести файлы**

```bash
cd /home/cvetkov_es/development/HubEx.Wiki
git mv hubex-context.md .context-dist/hubex-context.md 2>/dev/null || \
  { cp hubex-context.md .context-dist/ && git rm --cached hubex-context.md && rm hubex-context.md; }
cp context/body.md .context-dist/body.md
git rm -r --cached context && rm -rf context
```

Проверить: `.context-dist/` содержит оба файла, в корне их нет.

- [ ] **Step 3: `.gitignore`**

Добавить строку `.context-dist/` рядом с `dist/`.

- [ ] **Step 4: Коммит артефактов в их ветке**

```bash
cd /home/cvetkov_es/development/HubEx.Wiki/.context-dist
git add -A && git commit -m "chore: сжатый контекст и его тело переехали из дерева вики"
git push origin dist/context
```

- [ ] **Step 5: Документация**

В `CLAUDE.md` и `AGENTS.md` строку про `context/body.md` и `hubex-context.md` **заменить** на объяснение, а не на новый запрет: артефакты сжатого контекста живут на ветке `dist/context` отдельным worktree и в рабочем дереве отсутствуют; вопрос о продукте — всегда `index.md` → `pages/`.

В `README.md` и `tools/README.md` описать: где лежат артефакты, как подключить worktree на новой машине, что ночной прогон коммитит вики в `main`, а артефакты — в `dist/context`.

- [ ] **Step 6: Прогон и коммит**

```bash
cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest -q
cd /home/cvetkov_es/development/HubEx.Wiki
git add -A && git commit -m "chore: артефакты сжатого контекста вне рабочего дерева вики"
```

---

## Self-Review

**Покрытие спека.** Ветка-сирота и worktree — Задачи 1 и 3. Отсутствие артефактов в рабочем дереве `main` — Задача 3, шаг 2. Отдельный коммит артефактов ночью — Задача 2. Внятная ошибка при отсутствующем worktree — Задача 1, шаг 3. Корень вики остаётся единственным корнем пайплайна — Задача 1, шаг 4: меняются только константы путей, сигнатуры функций нет.

**Типы.** `artifacts.missing_problem` возвращает `str | None`; оркестраторы кладут строку в `problems`. `sync.commit_artifacts` возвращает `dict` с ключами `status`/`report`, как остальные ветки `run_sync`.
