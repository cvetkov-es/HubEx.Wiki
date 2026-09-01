# Автоматическая выкладка на wiki.hubex.ru — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ночной прогон сам публикует llms-слой и сжатый контекст на боевой `wiki.hubex.ru`, не имея физической возможности задеть остальной сайт.

**Architecture:** новый пакет `tools/publish/` по образцу `tools/compact/`: `site.py` (где живёт клон репозитория сайта и проверка, что это он), `guard.py` (белый список путей и контентные проверки), `pipeline.py` (генерация → проверки → коммит → пуш), `report.py` (рендер стадии). `update/sync.py` получает гейты клона и ветки до `update` и стадию выкладки в хвосте. Чужие файлы сайта в рабочее дерево не выгружаются — клон разреженный.

**Tech Stack:** Python 3.10+, stdlib (`subprocess`, `pathlib`, `shutil`, `re`), pytest. Сети и модели в новом коде нет.

**Spec:** [2026-09-01-site-publish-design.md](../specs/2026-09-01-site-publish-design.md)

## Global Constraints

- **Код пайплайна живёт в сабмодуле.** Все файлы под `tools/` принадлежат отдельному репозиторию `HubEx.Wiki.Pipeline`. Коммитить их надо изнутри: `git -C tools add ... && git -C tools commit ...`. Команды из корня вики попадут не в тот репозиторий. Указатель сабмодуля в контент-репозитории бампится **одним коммитом в самом конце**, после того как ветка пайплайна влита.
- **Все пути в командах — абсолютные.** `cd` в предыдущем вызове сохраняется между командами и уводит запись не туда; на этом уже обжигались дважды.
- **Тестовый фейк git обязан возвращать `subprocess.CompletedProcess`, а не строку.** Фейк, не умеющий воспроизвести провал, делает тест провала тавтологичным — это уже случалось в этом проекте. Образец: `tools/tests/test_compact_artifacts.py`.
- **Имя публикуемого файла сжатого контекста: `hubex-context-compact.txt`.** Именно `.txt`: Jekyll рендерит любой `.md` в страницу.
- **Ни один публикуемый файл не начинается с `---`.** Jekyll читает такой файл как YAML front matter на любом расширении, а битый YAML роняет сборку всего сайта.
- **`git add` — только точечными путями, никогда `-A`.** `-A` в клоне сайта — это ровно тот способ задеть чужие файлы, которого мы избегаем.
- **Прогон тестов:** `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest -q -m "not live"`.
- **Дерево обязано быть чистым к 21:00 UTC**, иначе ночной прогон отменяется. Коммитить по ходу, не копить.

---

### Task 1: `publish/site.py` — где живёт клон и проверка, что это он

**Files:**
- Create: `tools/publish/__init__.py`
- Create: `tools/publish/site.py`
- Test: `tools/tests/test_publish_site.py`

**Interfaces:**
- Consumes: ничего.
- Produces: `site.REMOTE: str`, `site.BRANCH: str`, `site.DEFAULT_DIR: Path`, `site.ROOT_FILES: tuple[str, ...]`, `site.MIRROR_DIR: str`, `site.CONTEXT_FILE: str`, `site.SETUP_HINT: str`, `site.normalize_remote(url: str) -> str`, `site.clone_problem(site_dir: Path, *, git_run=None) -> str | None`.

- [ ] **Step 1: Write the failing test**

Создать `tools/tests/test_publish_site.py`:

```python
"""Проверка клона репозитория сайта: это должен быть именно он, на master.

Наличия каталога недостаточно. Чужой или не тот клон на этом месте означает пуш
в чужой репозиторий либо в чужую ветку — то есть передеплой не того сайта.
"""
import subprocess
from pathlib import Path

from publish import site


def ok(stdout=""):
    return subprocess.CompletedProcess((), 0, stdout, "")


def fail(stderr="fatal: not a git repository"):
    return subprocess.CompletedProcess((), 128, "", stderr)


def fake_git(*, toplevel=None, remote=None, head=None):
    def _run(cwd, *args):
        if args[:2] == ("rev-parse", "--show-toplevel"):
            return ok(f"{toplevel}\n") if toplevel is not None else fail()
        if args[:2] == ("remote", "get-url"):
            return ok(f"{remote}\n") if remote is not None else fail()
        if args[:1] == ("symbolic-ref",):
            return ok(f"{head}\n") if head is not None else fail()
        raise AssertionError(f"лишняя git-команда в проверке: {args}")
    return _run


def test_publishable_paths_are_the_whole_allowlist():
    assert site.CONTEXT_FILE == "hubex-context-compact.txt"
    assert site.MIRROR_DIR == "llms"
    assert set(site.ROOT_FILES) == {
        "llms.txt", "llms-releasenotes.txt", "llms-full.txt", site.CONTEXT_FILE}


def test_normalize_remote_strips_userinfo_and_suffix():
    a = site.normalize_remote("https://melston@dev.azure.com/melston/X/_git/Y.git")
    b = site.normalize_remote("https://dev.azure.com/melston/X/_git/Y/")
    assert a == b


def test_missing_directory_reports_clone_command(tmp_path):
    problem = site.clone_problem(tmp_path / "нет", git_run=fake_git())
    assert problem is not None
    assert "git clone" in problem


def test_right_clone_on_master_is_fine(tmp_path):
    run = fake_git(toplevel=str(tmp_path), remote=site.REMOTE, head="master")
    assert site.clone_problem(tmp_path, git_run=run) is None


def test_foreign_remote_is_a_problem(tmp_path):
    run = fake_git(toplevel=str(tmp_path),
                   remote="https://github.com/cvetkov-es/HubEx.Wiki.git", head="master")
    problem = site.clone_problem(tmp_path, git_run=run)
    assert problem is not None
    assert "github.com" in problem


def test_wrong_branch_is_a_problem(tmp_path):
    run = fake_git(toplevel=str(tmp_path), remote=site.REMOTE, head="azure-migration")
    problem = site.clone_problem(tmp_path, git_run=run)
    assert problem is not None
    assert "azure-migration" in problem


def test_plain_directory_is_a_problem(tmp_path):
    """Каталог есть, но git его не знает — самый опасный случай: команды уходят вверх."""
    problem = site.clone_problem(tmp_path, git_run=fake_git())
    assert problem is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_publish_site.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'publish'`

- [ ] **Step 3: Write minimal implementation**

Создать `tools/publish/__init__.py` пустым файлом.

Создать `tools/publish/site.py`:

```python
"""Где живёт клон репозитория сайта wiki.hubex.ru и как убедиться, что это он.

Клон разреженный: `--filter=blob:none --sparse` плюс `sparse-checkout set llms`
(cone-режим отдаёт файлы корня и каталог llms/). `docs/`, `attachments/`, `assets/`,
конфиги Jekyll и `deploy/` в рабочее дерево не выгружаются вовсе — испортить нельзя то,
чего нет на диске. Это и есть гарантия «остальное не должно сломаться»: не правило,
которому надо следовать, а отсутствие файлов. Заодно снимается размер — репозиторий
сайта 405 МБ, из них наши 5 МБ.

Клон лежит снаружи обоих деревьев вики. Чужой клон внутри нашего репозитория повторил бы
ошибку `.context-dist` в худшем варианте: там хотя бы тот же репозиторий, здесь — совсем
другой, и git-команда, запущенная не в том каталоге, ушла бы в чужую историю.
"""
import re
import subprocess
from pathlib import Path

REMOTE = "https://dev.azure.com/melston/HubEx%20Plugins/_git/HubEx.Wiki"
BRANCH = "master"
DEFAULT_DIR = Path.home() / ".local" / "state" / "hubex-wiki" / "site"

CONTEXT_FILE = "hubex-context-compact.txt"
MIRROR_DIR = "llms"
ROOT_FILES = ("llms.txt", "llms-releasenotes.txt", "llms-full.txt", CONTEXT_FILE)

SETUP_HINT = (
    f"Подключить клон (разреженный — чужие файлы сайта на диск не попадут):\n"
    f"  git clone --filter=blob:none --sparse {REMOTE} {DEFAULT_DIR}\n"
    f"  git -C {DEFAULT_DIR} sparse-checkout set {MIRROR_DIR}")

# Azure DevOps отдаёт remote и с userinfo (`https://melston@dev.azure.com/...`), и без;
# git может хранить его с хвостовым слэшем или `.git`. Сравниваем нормализованное.
_USERINFO_RE = re.compile(r"^(https://)[^/@]+@")


def normalize_remote(url: str) -> str:
    url = _USERINFO_RE.sub(r"\1", url.strip()).rstrip("/")
    return url[:-4] if url.endswith(".git") else url


def _git(cwd, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _out(res) -> str:
    return (res.stdout if res.returncode == 0 else (res.stderr or res.stdout)).strip()


def clone_problem(site_dir: Path, *, git_run=None) -> str | None:
    """Текст ошибки, если site_dir — не клон репозитория сайта на master. Иначе None.

    Проверяем три вещи, и каждая закрывает свой способ выстрелить в ногу: корень
    рабочего дерева (обычный каталог молча разрешает git-команды в родительский
    репозиторий), remote (пуш в чужой репозиторий) и ветку (пуш в ветку, которая не
    деплоится, — выкладка молча уходит в никуда).
    """
    if not site_dir.is_dir():
        return (f"клон репозитория сайта не подключён ({site_dir}).\n" + SETUP_HINT)
    run = git_run or _git
    top = run(site_dir, "rev-parse", "--show-toplevel")
    remote = run(site_dir, "remote", "get-url", "origin")
    head = run(site_dir, "symbolic-ref", "--short", "HEAD")
    top_ok = top.returncode == 0 and top.stdout.strip() and \
        Path(top.stdout.strip()).resolve() == site_dir.resolve()
    remote_ok = remote.returncode == 0 and \
        normalize_remote(remote.stdout) == normalize_remote(REMOTE)
    head_ok = head.returncode == 0 and head.stdout.strip() == BRANCH
    if top_ok and remote_ok and head_ok:
        return None
    return (
        f"каталог {site_dir} существует, но это не клон репозитория сайта на {BRANCH}: "
        f"git видит корень «{_out(top)}», remote «{_out(remote)}», HEAD «{_out(head)}». "
        f"Выкладка отсюда ушла бы в чужой репозиторий или в недеплоящуюся ветку. "
        f"Убрать каталог и подключить заново:\n"
        f"  rm -rf {site_dir}\n" + SETUP_HINT)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_publish_site.py -q`
Expected: PASS, 7 тестов.

- [ ] **Step 5: Commit**

```bash
git -C /home/cvetkov_es/development/HubEx.Wiki/tools add publish/__init__.py publish/site.py tests/test_publish_site.py
git -C /home/cvetkov_es/development/HubEx.Wiki/tools commit -m "feat: клон репозитория сайта и проверка, что это он"
```

---

### Task 2: `publish/guard.py` — белый список и контентные проверки

**Files:**
- Create: `tools/publish/guard.py`
- Test: `tools/tests/test_publish_guard.py`

**Interfaces:**
- Consumes: `publish.site.ROOT_FILES`, `publish.site.MIRROR_DIR`, `publish.site.CONTEXT_FILE`; `compact.guard.WHOLE_TARGET`, `WHOLE_MIN_RATIO`, `WHOLE_MAX_RATIO`.
- Produces: `guard.MIN_CONTEXT_CHARS: int`, `guard.MAX_CONTEXT_CHARS: int`, `guard.outside_allowlist(paths) -> list[str]`, `guard.content_problems(files: dict[str, str], *, expected_mirrors: int) -> list[str]`.

- [ ] **Step 1: Write the failing test**

Создать `tools/tests/test_publish_guard.py`:

```python
"""Два рубежа выкладки: что трогаем и что публикуем.

Первый — белый список путей: всё, чего в нём нет, коммититься не должно, даже если
разреженный клон почему-то отдал больше файлов. Второй — содержимое: файл, начинающийся
с `---`, роняет сборку ВСЕГО сайта (Jekyll читает его как YAML front matter на любом
расширении), а `.md` Jekyll рендерит в страницу и та коллизирует с настоящей.
"""
from publish import guard, site


def full_set(*, mirrors=2, context_chars=None):
    """Корректный набор публикуемых файлов — отправная точка для порчи в тестах."""
    chars = context_chars if context_chars is not None else guard.MIN_CONTEXT_CHARS + 10
    files = {
        "llms.txt": "# llms\n",
        "llms-releasenotes.txt": "# rn\n",
        "llms-full.txt": "# full\n",
        site.CONTEXT_FILE: "# HubEx\n" + "х" * chars,
    }
    for i in range(mirrors):
        files[f"{site.MIRROR_DIR}/docs/FAQ/RU/admin/P{i}.html.txt"] = "текст\n"
    return files


def test_clean_set_has_no_problems():
    assert guard.content_problems(full_set(), expected_mirrors=2) == []


def test_leading_dashes_are_rejected():
    files = full_set()
    files["llms.txt"] = "---\nтитул\n"
    problems = guard.content_problems(files, expected_mirrors=2)
    assert any("llms.txt" in p for p in problems)


def test_markdown_extension_is_rejected():
    files = full_set()
    files[f"{site.MIRROR_DIR}/docs/FAQ/RU/admin/P0.html.md"] = "текст\n"
    problems = guard.content_problems(files, expected_mirrors=3)
    assert any(".md" in p for p in problems)


def test_zero_mirrors_is_rejected():
    problems = guard.content_problems(full_set(mirrors=0), expected_mirrors=0)
    assert problems != []


def test_mirror_count_mismatch_is_rejected():
    problems = guard.content_problems(full_set(mirrors=2), expected_mirrors=253)
    assert any("253" in p for p in problems)


def test_truncated_context_is_rejected():
    files = full_set(context_chars=100)
    problems = guard.content_problems(files, expected_mirrors=2)
    assert any(site.CONTEXT_FILE in p for p in problems)


def test_oversized_context_is_rejected():
    files = full_set(context_chars=guard.MAX_CONTEXT_CHARS + 1)
    problems = guard.content_problems(files, expected_mirrors=2)
    assert any(site.CONTEXT_FILE in p for p in problems)


def test_context_must_not_be_listed_in_the_catalogue():
    """Решение спеки, защищённое механически, а не комментарием.

    `llms.txt` — каталог для краулеров, а сжатый контекст лоссовый. Индексатор не должен
    получать и страницу, и её пересказ: это ровно та причина, по которой файла нет и в
    корне нашего репозитория. Проверка ловит будущую доброжелательную правку экспортёра.
    """
    files = full_set()
    files["llms.txt"] = f"# llms\n- [сжатый контекст](/{site.CONTEXT_FILE})\n"
    problems = guard.content_problems(files, expected_mirrors=2)
    assert any("llms.txt" in p for p in problems)


def test_missing_root_file_is_rejected():
    files = full_set()
    del files["llms-full.txt"]
    problems = guard.content_problems(files, expected_mirrors=2)
    assert any("llms-full.txt" in p for p in problems)


def test_allowlist_passes_our_paths():
    assert guard.outside_allowlist([
        "llms.txt", site.CONTEXT_FILE,
        f"{site.MIRROR_DIR}/docs/FAQ/RU/user/X.html.txt"]) == []


def test_allowlist_catches_foreign_paths():
    foreign = ["docs/FAQ/RU/admin/Actuality.md", "_config.yml", "deploy/deploy.sh"]
    assert sorted(guard.outside_allowlist(foreign + ["llms.txt"])) == sorted(foreign)


def test_allowlist_catches_lookalike_prefix():
    """`llmsX/` не входит в поддерево `llms/` — префиксное сравнение обязано это видеть."""
    assert guard.outside_allowlist(["llmsX/y.txt"]) == ["llmsX/y.txt"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_publish_guard.py -q`
Expected: FAIL — `ImportError: cannot import name 'guard' from 'publish'`

- [ ] **Step 3: Write minimal implementation**

Создать `tools/publish/guard.py`:

```python
"""Два рубежа перед пушем на боевой сайт: какие пути трогаем и что в них лежит.

Разреженный клон уже не даёт чужим файлам оказаться на диске. Белый список — второй
рубеж поверх него: один отказал, держит другой. Контентные проверки закрывают то, чем
наш собственный корректно расположенный файл может уронить чужую сборку.
"""
from compact import guard as compact_guard
from publish import site

MIN_CONTEXT_CHARS = int(compact_guard.WHOLE_TARGET * compact_guard.WHOLE_MIN_RATIO)
MAX_CONTEXT_CHARS = int(compact_guard.WHOLE_TARGET * compact_guard.WHOLE_MAX_RATIO)

_MIRROR_PREFIX = site.MIRROR_DIR + "/"


def _allowed(path: str) -> bool:
    return path in site.ROOT_FILES or path.startswith(_MIRROR_PREFIX)


def outside_allowlist(paths) -> list[str]:
    """Пути, которых нет в белом списке. Пустой список — можно коммитить."""
    return [p for p in paths if not _allowed(p)]


def content_problems(files: dict, *, expected_mirrors: int) -> list[str]:
    """Что не так с набором публикуемых файлов. Пустой список — можно коммитить."""
    problems = []

    for name in site.ROOT_FILES:
        if name not in files:
            problems.append(f"{name}: файла нет в наборе — публиковать нечего")

    for path, text in sorted(files.items()):
        if path.endswith(".md"):
            problems.append(
                f"{path}: расширение .md — Jekyll отрендерит файл в страницу, и она "
                f"коллизирует с настоящей. Публикуем только .txt")
        if text.startswith("---"):
            problems.append(
                f"{path}: файл начинается с `---` — Jekyll прочитает его как YAML "
                f"front matter (на любом расширении) и уронит сборку ВСЕГО сайта")

    mirrors = sum(1 for p in files if p.startswith(_MIRROR_PREFIX))
    if mirrors == 0:
        problems.append("постраничных зеркал ноль — выкладывать пустой llms-слой нельзя")
    elif mirrors != expected_mirrors:
        problems.append(
            f"постраничных зеркал {mirrors}, а страниц в pages/** {expected_mirrors} — "
            f"набор неполный")

    catalogue = files.get("llms.txt", "")
    if site.CONTEXT_FILE in catalogue:
        problems.append(
            f"llms.txt: в каталоге упомянут {site.CONTEXT_FILE} — сжатый контекст лоссовый "
            f"и в каталог для краулеров не входит: индексатор не должен получать и "
            f"страницу, и её пересказ")

    context = files.get(site.CONTEXT_FILE)
    if context is not None and not MIN_CONTEXT_CHARS <= len(context) <= MAX_CONTEXT_CHARS:
        problems.append(
            f"{site.CONTEXT_FILE}: {len(context)} символов вне коридора "
            f"{MIN_CONTEXT_CHARS}–{MAX_CONTEXT_CHARS} — публиковать обрубок или "
            f"разбухший файл нельзя")

    return problems
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_publish_guard.py -q`
Expected: PASS, 12 тестов.

- [ ] **Step 5: Commit**

```bash
git -C /home/cvetkov_es/development/HubEx.Wiki/tools add publish/guard.py tests/test_publish_guard.py
git -C /home/cvetkov_es/development/HubEx.Wiki/tools commit -m "feat: белый список путей и контентные проверки выкладки"
```

---

### Task 3: `publish/pipeline.py` — генерация, проверки, коммит, пуш

**Files:**
- Create: `tools/publish/pipeline.py`
- Test: `tools/tests/test_publish_pipeline.py`

**Interfaces:**
- Consumes: `publish.site.clone_problem`, `site.DEFAULT_DIR`, `site.ROOT_FILES`, `site.MIRROR_DIR`, `site.CONTEXT_FILE`, `site.BRANCH`; `publish.guard.outside_allowlist`, `guard.content_problems`; `compact.artifacts.OUT_REL`; `export_llms.write_export`.
- Produces: `pipeline.run_publish(*, root=None, site_dir=None, today=None, dry_run=False, export_fn=None, git_run=None) -> dict` с ключами `status` (`committed` | `no-changes` | `dry-run` | `clone-missing` | `guard-failed` | `outside-allowlist` | `failed`), `code` (0 | 2 | 5), `report` (str), `commit` (str | None).

- [ ] **Step 1: Write the failing test**

Создать `tools/tests/test_publish_pipeline.py`:

```python
"""Выкладка целиком: что попадает в коммит и когда коммита не происходит.

Главное, что здесь проверяется, — отрицательные исходы. Пуш идёт на боевой сайт, и
цена ошибки не «тест покраснел», а «клиентская вика перестала обновляться».
"""
import subprocess
from pathlib import Path

from publish import pipeline, site


def ok(stdout=""):
    return subprocess.CompletedProcess((), 0, stdout, "")


def fail(stderr="fatal"):
    return subprocess.CompletedProcess((), 1, "", stderr)


class FakeGit:
    """Раннер, который помнит вызовы и умеет проваливать заданную команду."""

    def __init__(self, *, staged="llms.txt\n", fail_on=None, site_dir=None):
        self.calls = []
        self.staged = staged
        self.fail_on = fail_on
        self.site_dir = site_dir

    def __call__(self, cwd, *args):
        self.calls.append(args)
        if self.fail_on and args[:len(self.fail_on)] == self.fail_on:
            return fail()
        if args[:2] == ("rev-parse", "--show-toplevel"):
            return ok(f"{self.site_dir}\n")
        if args[:2] == ("remote", "get-url"):
            return ok(site.REMOTE + "\n")
        if args[:1] == ("symbolic-ref",):
            return ok(site.BRANCH + "\n")
        if args[:3] == ("diff", "--cached", "--name-only"):
            return ok(self.staged)
        if args[:1] == ("commit",):
            return ok("[master abc1234] chore: выкладка\n")
        return ok()

    def ran(self, *prefix):
        return any(c[:len(prefix)] == prefix for c in self.calls)


def build_tree(tmp_path, *, mirrors=2, context_chars=None):
    """Каталог-клон сайта плюс исходный артефакт сжатого контекста в дереве вики."""
    from publish import guard
    root = tmp_path / "wiki"
    site_dir = tmp_path / "site"
    (root / ".context-dist").mkdir(parents=True)
    chars = context_chars if context_chars is not None else guard.MIN_CONTEXT_CHARS + 10
    (root / ".context-dist" / "hubex-context.md").write_text(
        "# HubEx\n" + "х" * chars, encoding="utf-8")
    site_dir.mkdir()

    def export_fn(root=None, out_dir=None):
        out = Path(out_dir)
        for name in ("llms.txt", "llms-releasenotes.txt", "llms-full.txt"):
            (out / name).write_text(f"# {name}\n", encoding="utf-8")
        d = out / site.MIRROR_DIR / "docs" / "FAQ" / "RU" / "admin"
        d.mkdir(parents=True, exist_ok=True)
        for i in range(mirrors):
            (d / f"P{i}.html.txt").write_text("текст\n", encoding="utf-8")
        return {"exported": mirrors, "warnings": [], "out": str(out)}

    return root, site_dir, export_fn


def test_happy_path_commits_and_pushes(tmp_path):
    root, site_dir, export_fn = build_tree(tmp_path)
    git = FakeGit(site_dir=site_dir)
    res = pipeline.run_publish(root=root, site_dir=site_dir, export_fn=export_fn,
                               git_run=git)
    assert res["status"] == "committed", res["report"]
    assert res["code"] == 0
    assert res["commit"] == "abc1234"
    assert git.ran("push", "origin", site.BRANCH)


def test_context_file_lands_under_published_name(tmp_path):
    root, site_dir, export_fn = build_tree(tmp_path)
    pipeline.run_publish(root=root, site_dir=site_dir, export_fn=export_fn,
                         git_run=FakeGit(site_dir=site_dir))
    assert (site_dir / site.CONTEXT_FILE).exists()
    assert not (site_dir / "hubex-context.md").exists()


def test_add_is_pathspec_never_dash_a(tmp_path):
    """`git add -A` в чужом клоне — ровно тот способ задеть чужие файлы."""
    root, site_dir, export_fn = build_tree(tmp_path)
    git = FakeGit(site_dir=site_dir)
    pipeline.run_publish(root=root, site_dir=site_dir, export_fn=export_fn, git_run=git)
    assert not git.ran("add", "-A")
    assert git.ran("add", "--")


def test_nothing_staged_means_no_commit(tmp_path):
    root, site_dir, export_fn = build_tree(tmp_path)
    git = FakeGit(site_dir=site_dir, staged="")
    res = pipeline.run_publish(root=root, site_dir=site_dir, export_fn=export_fn,
                               git_run=git)
    assert res["status"] == "no-changes"
    assert res["code"] == 0
    assert not git.ran("commit")
    assert not git.ran("push", "origin", site.BRANCH)


def test_foreign_staged_path_aborts_before_commit(tmp_path):
    root, site_dir, export_fn = build_tree(tmp_path)
    git = FakeGit(site_dir=site_dir, staged="llms.txt\n_config.yml\n")
    res = pipeline.run_publish(root=root, site_dir=site_dir, export_fn=export_fn,
                               git_run=git)
    assert res["status"] == "outside-allowlist"
    assert res["code"] == 5
    assert "_config.yml" in res["report"]
    assert not git.ran("commit")
    assert git.ran("reset", "--quiet")


def test_guard_problem_aborts_before_commit(tmp_path):
    root, site_dir, export_fn = build_tree(tmp_path, context_chars=100)
    git = FakeGit(site_dir=site_dir)
    res = pipeline.run_publish(root=root, site_dir=site_dir, export_fn=export_fn,
                               git_run=git)
    assert res["status"] == "guard-failed"
    assert res["code"] == 5
    assert not git.ran("commit")


def test_missing_clone_refuses_without_touching_anything(tmp_path):
    root, site_dir, export_fn = build_tree(tmp_path)
    absent = tmp_path / "нет"
    res = pipeline.run_publish(root=root, site_dir=absent, export_fn=export_fn,
                               git_run=FakeGit(site_dir=absent))
    assert res["status"] == "clone-missing"
    assert res["code"] == 2
    assert "git clone" in res["report"]


def test_push_failure_is_reported(tmp_path):
    root, site_dir, export_fn = build_tree(tmp_path)
    git = FakeGit(site_dir=site_dir, fail_on=("push",))
    res = pipeline.run_publish(root=root, site_dir=site_dir, export_fn=export_fn,
                               git_run=git)
    assert res["status"] == "failed"
    assert res["code"] == 5


def test_commit_failure_is_reported(tmp_path):
    root, site_dir, export_fn = build_tree(tmp_path)
    git = FakeGit(site_dir=site_dir, fail_on=("commit",))
    res = pipeline.run_publish(root=root, site_dir=site_dir, export_fn=export_fn,
                               git_run=git)
    assert res["status"] == "failed"
    assert res["code"] == 5


def test_dry_run_stages_but_never_commits(tmp_path):
    root, site_dir, export_fn = build_tree(tmp_path)
    git = FakeGit(site_dir=site_dir)
    res = pipeline.run_publish(root=root, site_dir=site_dir, export_fn=export_fn,
                               git_run=git, dry_run=True)
    assert res["status"] == "dry-run"
    assert res["code"] == 0
    assert not git.ran("commit")
    assert not git.ran("push", "origin", site.BRANCH)
    assert git.ran("reset", "--quiet")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_publish_pipeline.py -q`
Expected: FAIL — `ImportError: cannot import name 'pipeline' from 'publish'`

- [ ] **Step 3: Write minimal implementation**

Создать `tools/publish/pipeline.py`:

```python
"""Выкладка: генерация в клон сайта → проверки → коммит → пуш.

Порядок не случаен. Генерируем в рабочее дерево клона, читаем получившееся обратно с
диска (а не доверяем тому, что собирались записать), проверяем и только потом стейджим.
Проверка staged-путей идёт после `git add`, потому что именно она видит правду: что
реально попало в индекс, включая удаления и то, что дописал кто-то другой.
"""
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

import export_llms
from compact import artifacts
from publish import guard, site

REPO_ROOT = Path(__file__).resolve().parents[2]

_COMMIT_HASH_RE = re.compile(r"^\[\S+(?:\s+\(root-commit\))?\s+([0-9a-f]+)\]")


def _git(cwd, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _collect(site_dir: Path) -> dict:
    """Публикуемые файлы, прочитанные с диска: путь относительно клона → текст."""
    files = {}
    for name in site.ROOT_FILES:
        f = site_dir / name
        if f.exists():
            files[name] = f.read_text(encoding="utf-8")
    mirrors = site_dir / site.MIRROR_DIR
    if mirrors.is_dir():
        for f in sorted(mirrors.rglob("*")):
            if f.is_file():
                rel = f.relative_to(site_dir).as_posix()
                files[rel] = f.read_text(encoding="utf-8")
    return files


def run_publish(*, root: Path | None = None, site_dir: Path | None = None,
                today: date | None = None, dry_run: bool = False,
                export_fn=None, git_run=None) -> dict:
    root = root if root is not None else REPO_ROOT
    site_dir = site_dir if site_dir is not None else site.DEFAULT_DIR
    run = git_run or _git

    problem = site.clone_problem(site_dir, git_run=run)
    if problem:
        return {"status": "clone-missing", "code": 2, "commit": None,
                "report": "ОШИБКА: " + problem + "\n"}

    export_fn = export_fn or export_llms.write_export
    rep = export_fn(root=root, out_dir=site_dir)

    src = root / artifacts.OUT_REL
    if not src.exists():
        return {"status": "guard-failed", "code": 5, "commit": None,
                "report": f"ОШИБКА: нет {artifacts.OUT_REL} — сжатый контекст не собран, "
                          f"публиковать нечего\n"}
    shutil.copyfile(src, site_dir / site.CONTEXT_FILE)

    files = _collect(site_dir)
    problems = guard.content_problems(files, expected_mirrors=rep["exported"])
    if problems:
        return {"status": "guard-failed", "code": 5, "commit": None,
                "report": "ОШИБКА: набор не прошёл проверку, коммита нет:\n" +
                          "".join(f"- {p}\n" for p in problems)}

    def call(*args: str):
        res = run(site_dir, *args)
        text = res.stdout if res.returncode == 0 else (res.stderr or res.stdout)
        return res.returncode == 0, (text or "")

    # Точечные пути, никогда `-A`: в чужом клоне `-A` — это и есть способ задеть чужое.
    ok, out = call("add", "--", *site.ROOT_FILES, site.MIRROR_DIR)
    if not ok:
        return {"status": "failed", "code": 5, "commit": None, "report": out}

    ok, out = call("diff", "--cached", "--name-only")
    if not ok:
        return {"status": "failed", "code": 5, "commit": None, "report": out}
    staged = [p for p in out.split("\n") if p.strip()]

    foreign = guard.outside_allowlist(staged)
    if foreign:
        call("reset", "--quiet")
        return {"status": "outside-allowlist", "code": 5, "commit": None,
                "report": "ОШИБКА: в индекс попали чужие пути, коммита нет:\n" +
                          "".join(f"- {p}\n" for p in foreign)}

    if not staged:
        return {"status": "no-changes", "code": 0, "commit": None, "report": ""}

    if dry_run:
        _, diff = call("diff", "--cached", "--stat")
        call("reset", "--quiet")
        return {"status": "dry-run", "code": 0, "commit": None,
                "report": "--dry-run: коммита и пуша нет. Готово к выкладке:\n" + diff}

    today = today if today is not None else date.today()
    ok, out = call("commit", "-m", f"chore: llms-слой и сжатый контекст {today.isoformat()}")
    if not ok:
        return {"status": "failed", "code": 5, "commit": None, "report": out}
    m = _COMMIT_HASH_RE.match(out)

    ok, push_out = call("push", "origin", site.BRANCH)
    if not ok:
        return {"status": "failed", "code": 5, "commit": None,
                "report": "Коммит создан, но push не прошёл — выкладка не доехала:\n" +
                          push_out}

    return {"status": "committed", "code": 0, "commit": m.group(1) if m else None,
            "report": ""}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_publish_pipeline.py -q`
Expected: PASS, 10 тестов.

- [ ] **Step 5: Commit**

```bash
git -C /home/cvetkov_es/development/HubEx.Wiki/tools add publish/pipeline.py tests/test_publish_pipeline.py
git -C /home/cvetkov_es/development/HubEx.Wiki/tools commit -m "feat: выкладка llms-слоя и сжатого контекста в клон сайта"
```

---

### Task 4: отчёт стадии и команда `wiki_cli.py publish`

**Files:**
- Create: `tools/publish/report.py`
- Modify: `tools/wiki_cli.py`
- Test: `tools/tests/test_publish_report.py`
- Test: `tools/tests/test_cli.py`

**Interfaces:**
- Consumes: результат `pipeline.run_publish`.
- Produces: `report.render_stage(res: dict | None) -> str`.

- [ ] **Step 1: Write the failing test**

Создать `tools/tests/test_publish_report.py`:

```python
"""Стадия обязана печататься и при успехе тоже.

В необслуживаемом ночном прогоне тихий успех неотличим от того, что стадия не
отработала вовсе: по логу нельзя понять, доехала выкладка до сайта или нет. Ровно эта
неразличимость и держала llms-слой протухшим месяц.
"""
from publish import report


def test_committed_names_the_hash():
    out = report.render_stage({"status": "committed", "code": 0, "commit": "abc1234",
                               "report": ""})
    assert "abc1234" in out


def test_no_changes_says_so_explicitly():
    out = report.render_stage({"status": "no-changes", "code": 0, "commit": None,
                               "report": ""})
    assert "не менялось" in out


def test_dry_run_stage_is_marked_skipped():
    assert "--dry-run" in report.render_stage(None)


def test_failure_carries_the_reason():
    out = report.render_stage({"status": "guard-failed", "code": 5, "commit": None,
                               "report": "ОШИБКА: обрубок\n"})
    assert "обрубок" in out
```

Дописать в `tools/tests/test_cli.py`:

```python
def test_publish_command_passes_dry_run(monkeypatch, capsys):
    import wiki_cli
    seen = {}

    def fake_run_publish(**kwargs):
        seen.update(kwargs)
        return {"status": "dry-run", "code": 0, "commit": None, "report": "готово\n"}

    monkeypatch.setattr(wiki_cli.publish_pipeline, "run_publish", fake_run_publish)
    code = wiki_cli.main(["publish", "--dry-run"])
    assert code == 0
    assert seen["dry_run"] is True
    assert "готово" in capsys.readouterr().out


def test_publish_command_returns_failure_code(monkeypatch):
    import wiki_cli

    monkeypatch.setattr(wiki_cli.publish_pipeline, "run_publish",
                        lambda **kw: {"status": "guard-failed", "code": 5,
                                      "commit": None, "report": "плохо\n"})
    assert wiki_cli.main(["publish"]) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_publish_report.py tests/test_cli.py -q`
Expected: FAIL — нет модуля `publish.report` и нет команды `publish`.

- [ ] **Step 3: Write minimal implementation**

Создать `tools/publish/report.py`:

```python
"""Рендер стадии выкладки. Непустая строка и при успехе тоже.

`res=None` — стадию пропустили из-за `--dry-run` на уровне sync, а не она смолчала.
"""
from publish import site


def render_stage(res: dict | None) -> str:
    lines = ["## Выкладка на wiki.hubex.ru", ""]
    if res is None:
        lines.append("- --dry-run: стадия пропущена, коммита и пуша не было")
    elif res["status"] == "committed":
        commit = res.get("commit") or "хеш не распознан"
        lines.append(f"- запушено в {site.BRANCH}, сайт пересоберётся: {commit}")
    elif res["status"] == "no-changes":
        lines.append("- содержимое не менялось — коммита нет, деплой не дёргали")
    elif res["status"] == "dry-run":
        lines.append("- --dry-run: коммита и пуша нет")
        lines.append(res["report"])
    else:
        lines.append(f"- НЕ ВЫЛОЖЕНО ({res['status']}):")
        lines.append(res["report"])
    return "\n".join(lines) + "\n"
```

В `tools/wiki_cli.py` добавить импорт рядом с остальными (строка 9–11):

```python
from publish import pipeline as publish_pipeline, report as publish_report  # noqa: E402
```

В `build_parser()` после блока `compact` добавить:

```python
    pb = sub.add_parser("publish",
                        help="выложить llms-слой и сжатый контекст на wiki.hubex.ru")
    pb.add_argument("--dry-run", action="store_true",
                    help="пройти гейты и генерацию, показать дифф, не коммитить и не пушить")
    pb.add_argument("--report-file", help="дополнительно записать отчёт в файл")
```

В `main()` перед обработкой `compact` добавить:

```python
    if args.command == "publish":
        res = publish_pipeline.run_publish(dry_run=args.dry_run)
        text = publish_report.render_stage(res)
        print(text)
        if args.report_file:
            Path(args.report_file).write_text(text, encoding="utf-8")
        return res["code"]
```

(Если `Path` в `wiki_cli.py` ещё не импортирован — добавить `from pathlib import Path`; проверить перед правкой.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_publish_report.py tests/test_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/cvetkov_es/development/HubEx.Wiki/tools add publish/report.py wiki_cli.py tests/test_publish_report.py tests/test_cli.py
git -C /home/cvetkov_es/development/HubEx.Wiki/tools commit -m "feat: команда publish и отчёт стадии выкладки"
```

---

### Task 5: гейты `sync` — клон сайта и ветка основного дерева

**Files:**
- Modify: `tools/update/sync.py`
- Test: `tools/tests/test_sync.py`

**Interfaces:**
- Consumes: `publish.site.clone_problem`, `site.DEFAULT_DIR`, `site.BRANCH`.
- Produces: `sync.MAIN_BRANCH: str`, `sync.branch_gate(root, *, git_run=None) -> dict | None`, `sync.site_gate(root, *, site_dir=None, git_run=None) -> dict | None`.

- [ ] **Step 1: Write the failing test**

Дописать в `tools/tests/test_sync.py`:

```python
def test_branch_gate_passes_on_main(tmp_path):
    from update import sync

    def run(cwd, *args):
        return subprocess.CompletedProcess((), 0, "main\n", "")

    assert sync.branch_gate(tmp_path, git_run=run) is None


def test_branch_gate_blocks_on_feature_branch(tmp_path):
    """Не на main работают руками — робот в это время работать не должен.

    Без этого гейта ночной `git push origin HEAD` уносит перезабор вики на фиче-ветку,
    main тихо отстаёт, а ff-пул следующей ночью идёт по той же ветке и ничего не замечает.
    """
    from update import sync

    def run(cwd, *args):
        return subprocess.CompletedProcess((), 0, "feat/site-publish\n", "")

    gate = sync.branch_gate(tmp_path, git_run=run)
    assert gate is not None
    assert gate["code"] == 3
    assert "feat/site-publish" in gate["report"]


def test_branch_gate_blocks_on_detached_head(tmp_path):
    from update import sync

    def run(cwd, *args):
        return subprocess.CompletedProcess((), 128, "", "fatal: ref HEAD is not a symbolic ref")

    gate = sync.branch_gate(tmp_path, git_run=run)
    assert gate is not None
    assert gate["code"] == 3


def test_site_gate_missing_clone_is_code_2(tmp_path):
    from update import sync

    def run(cwd, *args):
        return subprocess.CompletedProcess((), 128, "", "fatal")

    gate = sync.site_gate(tmp_path, site_dir=tmp_path / "нет", git_run=run)
    assert gate is not None
    assert gate["code"] == 2


def test_site_gate_dirty_clone_is_code_3(tmp_path):
    from publish import site
    from update import sync
    site_dir = tmp_path / "site"
    site_dir.mkdir()

    def run(cwd, *args):
        if args[:2] == ("rev-parse", "--show-toplevel"):
            return subprocess.CompletedProcess((), 0, f"{site_dir}\n", "")
        if args[:2] == ("remote", "get-url"):
            return subprocess.CompletedProcess((), 0, site.REMOTE + "\n", "")
        if args[:1] == ("symbolic-ref",):
            return subprocess.CompletedProcess((), 0, site.BRANCH + "\n", "")
        if args[:1] == ("status",):
            return subprocess.CompletedProcess((), 0, " M llms.txt\n", "")
        raise AssertionError(args)

    gate = sync.site_gate(tmp_path, site_dir=site_dir, git_run=run)
    assert gate is not None
    assert gate["code"] == 3


def test_site_gate_not_ff_is_code_3(tmp_path):
    from publish import site
    from update import sync
    site_dir = tmp_path / "site"
    site_dir.mkdir()

    def run(cwd, *args):
        if args[:2] == ("rev-parse", "--show-toplevel"):
            return subprocess.CompletedProcess((), 0, f"{site_dir}\n", "")
        if args[:2] == ("remote", "get-url"):
            return subprocess.CompletedProcess((), 0, site.REMOTE + "\n", "")
        if args[:1] == ("symbolic-ref",):
            return subprocess.CompletedProcess((), 0, site.BRANCH + "\n", "")
        if args[:1] == ("status",):
            return subprocess.CompletedProcess((), 0, "", "")
        if args[:1] == ("pull",):
            return subprocess.CompletedProcess((), 1, "", "diverged")
        raise AssertionError(args)

    gate = sync.site_gate(tmp_path, site_dir=site_dir, git_run=run)
    assert gate is not None
    assert gate["code"] == 3


def test_site_gate_clean_clone_passes(tmp_path):
    from publish import site
    from update import sync
    site_dir = tmp_path / "site"
    site_dir.mkdir()

    def run(cwd, *args):
        if args[:2] == ("rev-parse", "--show-toplevel"):
            return subprocess.CompletedProcess((), 0, f"{site_dir}\n", "")
        if args[:2] == ("remote", "get-url"):
            return subprocess.CompletedProcess((), 0, site.REMOTE + "\n", "")
        if args[:1] == ("symbolic-ref",):
            return subprocess.CompletedProcess((), 0, site.BRANCH + "\n", "")
        if args[:1] == ("status",):
            return subprocess.CompletedProcess((), 0, "", "")
        if args[:1] == ("pull",):
            return subprocess.CompletedProcess((), 0, "Already up to date.\n", "")
        raise AssertionError(args)

    assert sync.site_gate(tmp_path, site_dir=site_dir, git_run=run) is None
```

(Если `import subprocess` в `test_sync.py` ещё нет — добавить в шапку.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_sync.py -q`
Expected: FAIL — `AttributeError: module 'update.sync' has no attribute 'branch_gate'`

- [ ] **Step 3: Write minimal implementation**

В `tools/update/sync.py` добавить импорт:

```python
from publish import site as publish_site
```

Добавить константу рядом с `COMMIT_PATHS`:

```python
MAIN_BRANCH = "main"
```

Добавить две функции рядом с `artifacts_gate`:

```python
def branch_gate(root: Path, *, git_run=None) -> dict | None:
    """Основное дерево обязано быть на main. None — путь чист.

    `run_sync` коммитит и делает `git push origin HEAD`. Репозиторий, оставленный
    человеком на фиче-ветке, получил бы ночной перезабор вики туда же: `main` тихо
    отстаёт, а `pull --ff-only` следующей ночью идёт по той же ветке и расхождения не
    замечает — сбой не проявляется, пока кто-то не посмотрит. Для worktree артефактов
    такая проверка есть с самого начала; здесь её просто не было.
    """
    run = git_run or _git
    head = run(root, "symbolic-ref", "--short", "HEAD")
    if head.returncode == 0 and head.stdout.strip() == MAIN_BRANCH:
        return None
    where = head.stdout.strip() if head.returncode == 0 else (head.stderr or "").strip()
    return {"status": "wrong-branch", "code": 3,
            "report": f"Основное дерево не на {MAIN_BRANCH} (HEAD: «{where}») — ночной "
                      f"прогон пропущен. Не на {MAIN_BRANCH} работают руками, и робот в "
                      f"это время работать не должен: иначе перезабор вики уедет "
                      f"коммитом на чужую ветку, а {MAIN_BRANCH} тихо отстанет.\n"}


def site_gate(root: Path, *, site_dir=None, git_run=None) -> dict | None:
    """Гейты клона репозитория сайта — те же три, что у артефактов. None — путь чист.

    Стоят до `update` и стоят секунду. Сломанный канал выкладки останавливает прогон
    целиком, а не деградирует в «стадия пропущена»: молчаливо пропускаемый шаг — это
    ровно тот механизм, из-за которого опубликованный llms-слой отстал на месяц.
    """
    site_dir = site_dir if site_dir is not None else publish_site.DEFAULT_DIR
    run = git_run or _git
    problem = publish_site.clone_problem(site_dir, git_run=run)
    if problem:
        return {"status": "site-missing", "code": 2, "report": "ОШИБКА: " + problem + "\n"}

    dirty = run(site_dir, "status", "--porcelain").stdout.strip()
    if dirty:
        return {"status": "site-dirty", "code": 3,
                "report": f"Клон сайта ({site_dir}) не чист — ночной прогон пропущен, "
                          "чтобы не выложить наружу чью-то незакоммиченную правку:\n"
                          + dirty + "\n"}

    pull = run(site_dir, "pull", "--ff-only")
    if pull.returncode != 0:
        return {"status": "site-not-ff", "code": 3,
                "report": f"git pull --ff-only в клоне сайта не прошёл — ветка "
                          f"{publish_site.BRANCH} разошлась с origin, нужен человек. "
                          f"Иначе push выкладки будет отвергнут:\n" +
                          (pull.stderr or pull.stdout)}
    return None
```

В `run_sync` вставить оба гейта: `branch_gate` — сразу после проверки чистого дерева и до `pull --ff-only` (на чужой ветке пулить тоже нечего), `site_gate` — сразу после `artifacts_gate`:

```python
    dirty = _git(root, "status", "--porcelain").stdout.strip()
    if dirty:
        return {...}

    gate = branch_gate(root)
    if gate:
        return gate

    pull = _git(root, "pull", "--ff-only")
    ...

    gate = artifacts_gate(root)
    if gate:
        return gate

    gate = site_gate(root)
    if gate:
        return gate
```

- [ ] **Step 4: Подключить клон сайта к фикстуре `repo`**

Без этого шага **все существующие тесты `run_sync` покраснеют**: они гоняют настоящий git
по временному репозиторию, а `site_gate` пойдёт искать боевой
`~/.local/state/hubex-wiki/site`, не найдёт его и вернёт код 2. Гейт ветки при этом
проходит сам собой — фикстура делает `git init -b main`.

Клон сайта в тестах обязан быть настоящим репозиторием: `pull --ff-only` и `status`
против подделки каталогом — это ровно та подделка, которую `clone_problem` и отвергает.
Настоящий локальный remote и константа `site.REMOTE` совпасть не могут, поэтому в
фикстуре подменяются обе константы.

В `tools/tests/test_sync.py` добавить импорт `from publish import site as publish_site`,
хелпер и правку фикстуры:

```python
def add_site_clone(tmp_path, monkeypatch):
    """Настоящий клон «сайта» с локальным bare-remote вместо Azure."""
    remote = tmp_path / "site-remote.git"
    subprocess.run(["git", "init", "--bare", "-b", publish_site.BRANCH, str(remote)],
                   check=True, capture_output=True)
    clone = tmp_path / "site"
    clone.mkdir()
    git(clone, "init", "-b", publish_site.BRANCH)
    git(clone, "config", "user.email", "bot@example.com")
    git(clone, "config", "user.name", "Bot")
    (clone / "llms.txt").write_text("# llms\n", encoding="utf-8")
    git(clone, "add", "-A")
    git(clone, "commit", "-m", "init")
    git(clone, "remote", "add", "origin", str(remote))
    git(clone, "push", "-u", "origin", publish_site.BRANCH)
    monkeypatch.setattr(publish_site, "REMOTE", str(remote))
    monkeypatch.setattr(publish_site, "DEFAULT_DIR", clone)
    return clone
```

и в конце фикстуры `repo`, перед `return root`:

```python
    add_artifacts_worktree(root)
    add_site_clone(tmp_path, monkeypatch)
    return root
```

Сигнатура фикстуры становится `def repo(tmp_path, monkeypatch):`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_sync.py -q`
Expected: PASS, включая все прежние тесты `run_sync`. Если какой-то из них падает на новом
гейте — чинить тест, а не ослаблять гейт.

- [ ] **Step 6: Commit**

```bash
git -C /home/cvetkov_es/development/HubEx.Wiki/tools add update/sync.py tests/test_sync.py
git -C /home/cvetkov_es/development/HubEx.Wiki/tools commit -m "feat: гейты ночного прогона — ветка основного дерева и клон сайта"
```

---

### Task 6: стадия выкладки в хвосте `sync`

**Files:**
- Modify: `tools/update/sync.py`
- Test: `tools/tests/test_sync.py`

**Interfaces:**
- Consumes: `publish.pipeline.run_publish`, `publish.report.render_stage`.
- Produces: `run_sync(..., run_publish_fn=None)`; новый статус `publish-failed` с кодом 5.

- [ ] **Step 1: Write the failing test**

Дописать в `tools/tests/test_sync.py`. Тесты используют уже существующие фикстуру `repo`
и хелперы `writes`, `compact_ok`, `artifacts_ok`, `head` из этого же файла — новых
обёрток не заводить:

```python
def test_publish_runs_even_when_wiki_did_not_change(repo):
    """Прошлая ночь могла не доложить выкладку — повтор обязан случиться и без правок вики.

    Если звать стадию только на пути «вика закоммичена», один сбой канала оставляет сайт
    протухшим навсегда: правок нет — выкладки нет — правок нет.
    """
    calls = []

    def publish_ok(**kw):
        calls.append(kw)
        return {"status": "committed", "code": 0, "commit": "abc1234", "report": ""}

    res = sync.run_sync(root=repo, today=TODAY, run_update_fn=lambda **kw: [],
                        run_compact_fn=compact_ok, commit_artifacts_fn=artifacts_ok,
                        run_publish_fn=publish_ok)
    assert calls, "стадия выкладки не вызвана"
    assert res["code"] == 0
    assert "abc1234" in res["report"]


def test_publish_failure_gives_code_5_and_leaves_wiki_committed(repo):
    """Провал выкладки ничего не откатывает: коммит вики уже сделан и остаётся."""
    before = head(repo)
    res = sync.run_sync(root=repo, today=TODAY,
                        run_update_fn=writes(repo, {"pages/admin/A.md": "новое\n"}),
                        run_compact_fn=compact_ok, commit_artifacts_fn=artifacts_ok,
                        run_publish_fn=lambda **kw: {
                            "status": "failed", "code": 5, "commit": None,
                            "report": "push отвергнут\n"})
    assert res["status"] == "publish-failed"
    assert res["code"] == 5
    assert head(repo) != before
    assert "push отвергнут" in res["report"]


def test_dry_run_skips_publish_stage(repo):
    calls = []
    res = sync.run_sync(root=repo, today=TODAY, dry_run=True,
                        run_update_fn=writes(repo, {"pages/admin/A.md": "новое\n"}),
                        run_compact_fn=compact_ok, commit_artifacts_fn=artifacts_ok,
                        run_publish_fn=lambda **kw: calls.append(kw))
    assert calls == []
    assert "--dry-run" in res["report"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_sync.py -q`
Expected: FAIL — стадия не вызывается, `run_publish_fn` неизвестный аргумент.

- [ ] **Step 3: Write minimal implementation**

В `tools/update/sync.py` добавить импорт:

```python
from publish import pipeline as publish_pipeline, report as publish_report
```

Выделить хвост `run_sync` (от `git add` до `push`) в `_commit_wiki`, возвращающий
`{"status", "code", "extra"}`, и после него вызвать стадию выкладки. Итоговый хвост:

```python
    wiki = _commit_wiki(root, results=results, today=today, dry_run=dry_run)
    text += wiki["extra"]
    if wiki["code"] != 0:
        return {"status": wiki["status"], "code": wiki["code"], "report": text}

    # Выкладка идёт после коммитов и вне dry-run: наружу уезжает только то, что уже
    # зафиксировано в git. Провал ничего не откатывает — вика и артефакты закоммичены,
    # следующей ночью выкладка повторится сама, как и при разовой ошибке забора.
    if dry_run:
        text += "\n" + publish_report.render_stage(None)
        return {"status": wiki["status"], "code": 0, "report": text}

    run_publish_fn = run_publish_fn or publish_pipeline.run_publish
    pub = run_publish_fn(root=root, today=today)
    text += "\n" + publish_report.render_stage(pub)
    if pub["code"] != 0:
        return {"status": "publish-failed", "code": 5, "report": text}
    return {"status": wiki["status"], "code": 0, "report": text}
```

Ключевое: путь «изменений в `pages/` нет» больше не возвращается досрочно, а отдаёт
`{"status": "no-changes", "code": 0, "extra": ...}` из `_commit_wiki` и **доходит до
стадии выкладки**.

Добавить `run_publish_fn=None` в сигнатуру `run_sync`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest -q -m "not live"`
Expected: PASS, весь набор.

- [ ] **Step 5: Commit**

```bash
git -C /home/cvetkov_es/development/HubEx.Wiki/tools add update/sync.py tests/test_sync.py
git -C /home/cvetkov_es/development/HubEx.Wiki/tools commit -m "feat: стадия выкладки в хвосте ночного прогона"
```

---

### Task 7: шапка сжатого контекста не должна врать про вику

**Files:**
- Modify: `tools/compact/assemble.py:25-28`
- Test: `tools/tests/test_compact_assemble.py`

**Interfaces:**
- Consumes: ничего нового.
- Produces: изменённый текст `build_header`; `_DATE_LINE_RE` не трогается.

- [ ] **Step 1: Write the failing test**

Дописать в `tools/tests/test_compact_assemble.py`:

```python
def test_header_does_not_claim_absence_from_the_wiki():
    """Файл лоссовый: факт может быть в вике и просто не попасть в пересказ.

    Пока файл прикладывали в чат руками, ошибка была терпимой. На публичном URL
    `wiki.hubex.ru/hubex-context-compact.txt` — уже нет.
    """
    from compact import assemble
    header = assemble.build_header("2026-09-01")
    assert "в вике этого нет" not in header
    assert "в этом файле этого нет" in header
    assert "первоисточник" in header
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_compact_assemble.py -q`
Expected: FAIL — в шапке всё ещё «в вике этого нет».

- [ ] **Step 3: Write minimal implementation**

В `tools/compact/assemble.py` заменить в `build_header`:

```python
        "**Правило ответа.** Отвечать только фактами из этого файла. Если факта нет — "
        "сказать «в этом файле этого нет» и предложить проверить первоисточник по ссылке "
        "раздела: файл — сжатый пересказ вики, и подробность могла в него не попасть. "
        "Не додумывать, не обобщать, не переносить на HubEx логику других FSM- и "
        "Help Desk-систем.\n\n"
```

Остальные абзацы шапки не трогать.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_compact_assemble.py -q`
Expected: PASS. Тест `test_same_apart_from_date_true_when_only_date_differs` обязан
остаться зелёным — строка даты не менялась.

- [ ] **Step 5: Commit**

```bash
git -C /home/cvetkov_es/development/HubEx.Wiki/tools add compact/assemble.py tests/test_compact_assemble.py
git -C /home/cvetkov_es/development/HubEx.Wiki/tools commit -m "fix: шапка сжатого контекста не выдаёт свои пробелы за пробелы вики"
```

---

### Task 8: документация

**Files:**
- Modify: `tools/README.md` (раздел «Команды», коды возврата `sync`)
- Modify: `README.md` (разделы «Ночной автоперезабор», «Экспорт для сайта (llms.txt)», «Сжатый контекст»)

**Interfaces:**
- Consumes: поведение, реализованное в задачах 1–7.
- Produces: документацию, из которой видно, что выкладка автоматическая, и по которой её можно подключить на новой машине.

- [ ] **Step 1: Обновить `tools/README.md`**

Добавить в раздел «Команды» блок про `publish` по образцу соседних: команда, что делает,
гейты, коды возврата. Обновить перечисление шагов `sync`: новые гейты (ветка основного
дерева; клон сайта — три гейта, симметричные артефактным) и новый шаг выкладки в хвосте.
Обновить строку кодов возврата `sync`: добавить **5 — сбой выкладки**, и в код 2 добавить
«нет клона сайта», в код 3 — «дерево не на `main`», «клон сайта не чист / разошёлся».

Подключение клона описать явно, командами:

```
git clone --filter=blob:none --sparse https://dev.azure.com/melston/HubEx%20Plugins/_git/HubEx.Wiki ~/.local/state/hubex-wiki/site
git -C ~/.local/state/hubex-wiki/site sparse-checkout set llms
```

Указать, что аутентификация идёт скоупленным хелпером `credential.https://dev.azure.com.helper`
из `~/.gitconfig`, который минтит токен через `az account get-access-token`; PAT не нужен,
но нужна живая `az`-сессия.

- [ ] **Step 2: Обновить корневой `README.md`**

В «Ночной автоперезабор» — дописать стадию выкладки и новые гейты; убрать из «Следствий
для человека» фразу «`export-llms` и выкладка на хостинг остаются ручным шагом» —
она перестала быть правдой.

В «Экспорт для сайта (llms.txt)» — дописать, что ночью то же самое делается автоматически,
а команда остаётся для ручного прогона.

В «Сжатый контекст» — дописать публичный адрес `https://wiki.hubex.ru/hubex-context-compact.txt`
и что файл выкладывается ночью автоматически.

- [ ] **Step 3: Проверить, что документация не разошлась с кодом**

Run: `grep -rn "ручным шагом\|остаются ручным" README.md tools/README.md`
Expected: пусто.

- [ ] **Step 4: Прогнать весь набор**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest -q -m "not live"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/cvetkov_es/development/HubEx.Wiki/tools add README.md
git -C /home/cvetkov_es/development/HubEx.Wiki/tools commit -m "docs: автоматическая выкладка на сайт в README пайплайна"
git -C /home/cvetkov_es/development/HubEx.Wiki add README.md
git -C /home/cvetkov_es/development/HubEx.Wiki commit -m "docs: выкладка на сайт перестала быть ручным шагом"
```

---

## После плана — вручную, не задачей

Подключение клона и первая выкладка делаются человеком, а не исполнителем плана:

1. `git clone --filter=blob:none --sparse ... ~/.local/state/hubex-wiki/site` и `sparse-checkout set llms`.
2. `python3 tools/wiki_cli.py publish --dry-run` — посмотреть дифф глазами. Он будет
   большим: опубликованный llms-слой отстал на месяц, плюс добавляется новый файл.
3. `python3 tools/wiki_cli.py publish` — первая выкладка, боевой сайт пересоберётся.
4. Убедиться, что `https://wiki.hubex.ru/hubex-context-compact.txt` отдаётся как
   `text/plain` и что сайт жив.
5. Вернуть основное дерево на `main` и убедиться, что оно чисто — иначе ночной прогон
   отменится собственным гейтом.

Право на запись в Azure DevOps проверяется именно шагом 3. Если токен даёт только
чтение — это доступы, а не код.
