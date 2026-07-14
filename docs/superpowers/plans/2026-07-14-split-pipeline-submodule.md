# Выделение пайплайна в сабмодуль — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Вынести пайплайн (`tools/`) из `HubEx.Wiki` в отдельный репозиторий `HubEx.Wiki.Pipeline` и подключить его обратно git-сабмодулем в `tools/`, чтобы `git clone` контент-репозитория давал чистую вику без питон-кода.

**Architecture:** Извлекаем `tools/` (и `docs/`) в новый репозиторий с сохранением истории (`git filter-repo`), пушим на GitHub рядом с контентом (владелец `cvetkov-es`), в контент-репозитории заменяем `tools/` сабмодулем с **относительным** URL. Python-код не меняется: резолюция корня `Path(__file__).resolve().parents[2]` идёт по файловой системе, а сабмодуль физически остаётся в `tools/`.

**Tech Stack:** git, git-filter-repo, gh CLI, Python 3.10, pytest.

## Global Constraints

- **Host-agnostic:** URL сабмодуля в `.gitmodules` — только **относительный** (`../HubEx.Wiki.Pipeline.git`), имени хоста в нём быть не должно.
- **Один владелец:** оба репозитория — под `cvetkov-es` (рядом), иначе относительный URL не резолвится.
- **Ноль правок Python:** ни один файл `update/**.py`, `lint/**.py`, `wiki_cli.py` не меняется по логике. Правка любого из них — красный флаг.
- **История пайплайна сохраняется:** извлечение, не копирование (в `tools/` было 16 коммитов реальной разработки).
- **Запуск локальный:** никакого CI/submodule-авторизации.
- **Коммиты:** сообщения в стиле репозитория (русский, conventional commits), последняя строка — `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **Human-gated шаги** (создание GitHub-репозитория, любой `push`, PR) исполнитель выполняет только после подтверждения пользователя — они внешние и трудно обратимы.
- Контент-репозиторий: `/home/cvetkov_es/development/HubEx.Wiki`, origin `https://github.com/cvetkov-es/HubEx.Wiki.git`, рабочая ветка `feat/split-pipeline-submodule`.
- Пайплайн-репозиторий (локально): `/home/cvetkov_es/development/HubEx.Wiki.Pipeline`.

---

## File Structure

**Новый `HubEx.Wiki.Pipeline`** (из извлечённого `tools/`, `tools/`→корень; `docs/` остаётся на месте):
- `wiki_cli.py`, `update/` (manifest, fetch, diff, recompress, guard, model_client, report, pipeline, prompts/), `lint/check_links.py`, `tests/`, `conftest.py`, `requirements.txt`, `README.md` (из `tools/README.md`) — переносятся с историей.
- `pytest.ini` — **создать** (`testpaths = tests`).
- `.gitignore` — **создать** (`update/drafts/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`).
- `docs/superpowers/` — переносится с историей.

**Контент `HubEx.Wiki`**:
- Создаётся: `.gitmodules` (относительный URL), `tools/` (сабмодуль).
- Удаляется: старые tracked-файлы `tools/`, `docs/`, `pytest.ini`.
- Правится: `.gitignore` (убрать строку `tools/update/drafts/`), `README.md`, `CLAUDE.md`, `AGENTS.md` (пометки про сабмодуль).

---

### Task 0: Подготовка и страховка

**Files:** нет (git-операции + установка инструмента).

- [ ] **Step 1: Убедиться в чистом состоянии контент-репозитория**

Run:
```bash
cd /home/cvetkov_es/development/HubEx.Wiki
git branch --show-current && git status --short
```
Expected: ветка `feat/split-pipeline-submodule`, пустой вывод `git status` (кроме, возможно, gitignored). Если ветка другая — `git switch feat/split-pipeline-submodule`.

- [ ] **Step 2: Поставить страховочный тег на текущий HEAD**

Run:
```bash
git tag pre-split-backup
git tag --list pre-split-backup
```
Expected: печатает `pre-split-backup`. (Откат всего до пуша: `git reset --hard pre-split-backup` + удалить локальный `HubEx.Wiki.Pipeline`.)

- [ ] **Step 3: Установить git-filter-repo**

Run:
```bash
python3 -m pip install --user git-filter-repo
export PATH="$HOME/.local/bin:$PATH"
git filter-repo --version
```
Expected: печатает номер версии (напр. `git-filter-repo 2.x`). Если `git filter-repo` не находится — скачать одиночный скрипт:
```bash
mkdir -p "$HOME/.local/bin"
curl -sSL https://raw.githubusercontent.com/newren/git-filter-repo/main/git-filter-repo -o "$HOME/.local/bin/git-filter-repo"
chmod +x "$HOME/.local/bin/git-filter-repo"
git filter-repo --version
```

---

### Task 1: Извлечь пайплайн-репозиторий с историей

**Files:**
- Create (локальный клон): `/home/cvetkov_es/development/HubEx.Wiki.Pipeline`

**Interfaces:**
- Produces: локальный git-репозиторий пайплайна с веткой `main`, где содержимое `tools/` поднято в корень, `docs/` на месте, `pages/`/индексов нет.

- [ ] **Step 1: Клонировать рабочую ветку в соседний каталог**

Run:
```bash
cd /home/cvetkov_es/development
git clone --single-branch --branch feat/split-pipeline-submodule ./HubEx.Wiki ./HubEx.Wiki.Pipeline
cd ./HubEx.Wiki.Pipeline
git branch -m main
git remote remove origin
```
Expected: клон создан, текущая ветка `main`, `git remote -v` пуст.

- [ ] **Step 2: Переписать историю — оставить только tools/ и docs/, поднять tools/ в корень**

Run:
```bash
git filter-repo --force --path tools/ --path docs/ --path-rename tools/:
```
Expected: filter-repo отрабатывает без ошибок, печатает статистику переписывания.

- [ ] **Step 3: Проверить раскладку и что контент отсутствует**

Run:
```bash
ls
ls docs/superpowers
( test ! -e pages && test ! -e index.md && test ! -e releasenotes-index.md ) && echo "контент отсутствует — OK"
```
Expected: в корне — `wiki_cli.py update lint tests conftest.py requirements.txt README.md docs`; в `docs/superpowers` — `specs plans`; печатает `контент отсутствует — OK`.

- [ ] **Step 4: Проверить, что история пайплайна сохранилась**

Run:
```bash
git log --oneline -- update/ | head
git log --oneline | wc -l
```
Expected: видны коммиты пайплайна (feat(update): manifest…, fetch…, и т.д.); число коммитов > 10.

---

### Task 2: Конфиги пайплайн-репозитория + зелёные офлайн-тесты

**Files:**
- Create: `/home/cvetkov_es/development/HubEx.Wiki.Pipeline/pytest.ini`
- Create: `/home/cvetkov_es/development/HubEx.Wiki.Pipeline/.gitignore`
- Modify: `/home/cvetkov_es/development/HubEx.Wiki.Pipeline/README.md` (одна поясняющая строка сверху)

**Interfaces:**
- Consumes: репозиторий из Task 1.
- Produces: самодостаточный пайплайн-репозиторий, где `python3 -m pytest -m "not live"` зелёный.

- [ ] **Step 1: Создать `pytest.ini`**

Файл `/home/cvetkov_es/development/HubEx.Wiki.Pipeline/pytest.ini`:
```ini
[pytest]
testpaths = tests
markers =
    live: тесты с реальной сетью (офлайн-прогон: -m "not live")
```

- [ ] **Step 2: Создать `.gitignore`**

Файл `/home/cvetkov_es/development/HubEx.Wiki.Pipeline/.gitignore`:
```gitignore
__pycache__/
*.pyc
.pytest_cache/
update/drafts/
```

- [ ] **Step 3: Добавить поясняющую строку в начало `README.md`**

В начало `/home/cvetkov_es/development/HubEx.Wiki.Pipeline/README.md`, сразу после заголовка `# tools — пайплайн обновления HubEx.Wiki`, вставить абзац:
```markdown
> Подключается git-сабмодулем в `tools/` репозитория контента `HubEx.Wiki`. Команды ниже даны из корня контент-репозитория (`python3 tools/wiki_cli.py …`).
```

- [ ] **Step 4: Прогнать офлайн-тесты**

Run:
```bash
cd /home/cvetkov_es/development/HubEx.Wiki.Pipeline
python3 -m pip install -r requirements.txt
python3 -m pytest -m "not live" -q
```
Expected: все тесты PASS (тесты инжектят `root`/`tmp_path`, реальный `pages/` не нужен).

- [ ] **Step 5: Закоммитить конфиги**

Run:
```bash
git add pytest.ini .gitignore README.md
git commit -m "chore: pytest.ini + .gitignore + пометка сабмодуля для отдельного репозитория" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
Expected: коммит создан.

---

### Task 3: [HUMAN-GATED] Создать GitHub-репозиторий и запушить

**Files:** нет (внешняя ops-операция).

**Interfaces:**
- Consumes: локальный пайплайн-репозиторий из Task 2.
- Produces: `https://github.com/cvetkov-es/HubEx.Wiki.Pipeline` с запушенной веткой `main`.

- [ ] **Step 1: Подтвердить у пользователя видимость репозитория**

Спросить: приватный или публичный? (По умолчанию — `--private`.) Не выполнять следующий шаг без ответа.

- [ ] **Step 2: Создать репозиторий и запушить**

Run (подставить `--private` или `--public` по ответу):
```bash
cd /home/cvetkov_es/development/HubEx.Wiki.Pipeline
gh repo create cvetkov-es/HubEx.Wiki.Pipeline --private --source=. --remote=origin --push
```
Expected: репозиторий создан, `main` запушена; печатает URL.

- [ ] **Step 3: Проверить, что история на remote**

Run:
```bash
gh repo view cvetkov-es/HubEx.Wiki.Pipeline --json name,visibility,defaultBranchRef
git ls-remote origin main
```
Expected: репозиторий существует, `defaultBranchRef` = `main`, `ls-remote` печатает sha ветки `main`.

---

### Task 4: Контент-репозиторий — заменить tools/ сабмодулем

**Files:**
- Delete (tracked): `tools/**` контент-репозитория
- Create: `/home/cvetkov_es/development/HubEx.Wiki/.gitmodules`
- Create (сабмодуль): `/home/cvetkov_es/development/HubEx.Wiki/tools`

**Interfaces:**
- Consumes: запушенный `HubEx.Wiki.Pipeline` из Task 3.
- Produces: `.gitmodules` с относительным URL; `tools/` — сабмодуль, запиненный на HEAD пайплайна.

- [ ] **Step 1: Убрать текущий tools/ (tracked + untracked остатки)**

Run:
```bash
cd /home/cvetkov_es/development/HubEx.Wiki
git rm -r tools/
rm -rf tools/
```
Expected: `git rm` удаляет tracked-файлы `tools/`; `rm -rf` подчищает gitignored-остатки (`drafts/`, `__pycache__/`), чтобы путь освободился под сабмодуль.

- [ ] **Step 2: Добавить сабмодуль с относительным URL**

Run:
```bash
git submodule add ../HubEx.Wiki.Pipeline.git tools
```
Expected: git резолвит `../HubEx.Wiki.Pipeline.git` от origin контента и клонирует в `tools/`; создаётся `.gitmodules`.

- [ ] **Step 3: Проверить `.gitmodules` — URL относительный, без хоста**

Run:
```bash
cat .gitmodules
```
Expected:
```
[submodule "tools"]
	path = tools
	url = ../HubEx.Wiki.Pipeline.git
```
Если в `url` появился абсолютный `https://…` — исправить на `../HubEx.Wiki.Pipeline.git` (правка файла `.gitmodules` + `git submodule sync`).

- [ ] **Step 4: Проверить, что сабмодуль выкачан и запинен**

Run:
```bash
git submodule status
ls tools/wiki_cli.py tools/update tools/tests
```
Expected: `git submodule status` печатает строку с sha и `tools (heads/main)`; файлы пайплайна на месте.

- [ ] **Step 5: Закоммитить замену**

Run:
```bash
git add .gitmodules tools
git commit -m "feat: пайплайн вынесен в сабмодуль tools/ → HubEx.Wiki.Pipeline" \
  -m "tools/ заменён git-сабмодулем с относительным URL (host-agnostic). git clone контента больше не тянет пайплайн; для обновления — git submodule update --init." \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
Expected: коммит создан.

---

### Task 5: Контент-репозиторий — конфиги и роутер

**Files:**
- Delete: `/home/cvetkov_es/development/HubEx.Wiki/pytest.ini`
- Modify: `/home/cvetkov_es/development/HubEx.Wiki/.gitignore`
- Modify: `/home/cvetkov_es/development/HubEx.Wiki/README.md`
- Modify: `/home/cvetkov_es/development/HubEx.Wiki/CLAUDE.md`
- Modify: `/home/cvetkov_es/development/HubEx.Wiki/AGENTS.md`

- [ ] **Step 1: Удалить pytest.ini (тестов в контенте больше нет)**

Run:
```bash
cd /home/cvetkov_es/development/HubEx.Wiki
git rm pytest.ini
```
Expected: файл удалён из индекса.

- [ ] **Step 2: Убрать строку drafts из `.gitignore`**

В `/home/cvetkov_es/development/HubEx.Wiki/.gitignore` удалить строку:
```
tools/update/drafts/
```
Результат файла:
```gitignore
__pycache__/
*.pyc
.pytest_cache/
.superpowers/
```

- [ ] **Step 3: README.md — пометка про сабмодуль**

В `/home/cvetkov_es/development/HubEx.Wiki/README.md` заменить:
```
## Обновление

```
на:
```
## Обновление

`tools/` — git-сабмодуль: пайплайн вынесен в отдельный репозиторий `HubEx.Wiki.Pipeline` (рядом, у того же владельца). Перед первым запуском выкачай его — `git submodule update --init` (или клонируй репозиторий с `--recursive`). Тем, кому нужна только вика, сабмодуль не нужен: обычный `git clone` его не тянет.

```

- [ ] **Step 4: CLAUDE.md — пометка про сабмодуль**

В `/home/cvetkov_es/development/HubEx.Wiki/CLAUDE.md` после строки:
```
- `pages/**` руками не правь — их ведёт пайплайн (`python3 tools/wiki_cli.py update --recompress`).
```
добавить строку:
```
- `tools/` — git-сабмодуль (пайплайн в отдельном репо `HubEx.Wiki.Pipeline`); перед запуском `update` выкачай его: `git submodule update --init`.
```

- [ ] **Step 5: AGENTS.md — та же пометка**

В `/home/cvetkov_es/development/HubEx.Wiki/AGENTS.md` после строки:
```
- `pages/**` руками не правь — их ведёт пайплайн (`python3 tools/wiki_cli.py update --recompress`).
```
добавить строку:
```
- `tools/` — git-сабмодуль (пайплайн в отдельном репо `HubEx.Wiki.Pipeline`); перед запуском `update` выкачай его: `git submodule update --init`.
```

- [ ] **Step 6: Закоммитить конфиги и роутер**

Run:
```bash
git add pytest.ini .gitignore README.md CLAUDE.md AGENTS.md
git commit -m "chore: конфиги и роутер под сабмодуль tools/" \
  -m "Убран pytest.ini (тесты уехали в пайплайн-репо), из .gitignore — строка drafts; README/CLAUDE/AGENTS предупреждают про git submodule update --init." \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
Expected: коммит создан.

---

### Task 6: Приёмка, вынос docs/, [HUMAN-GATED] пуш и PR

**Files:**
- Delete: `/home/cvetkov_es/development/HubEx.Wiki/docs/`

- [ ] **Step 1: Офлайн-тесты пайплайна на месте (внутри сабмодуля)**

Run:
```bash
cd /home/cvetkov_es/development/HubEx.Wiki
python3 -m pytest tools/tests -m "not live" -q
```
Expected: все PASS. (Резолюция `parents[2]` из `tools/update/…` указывает на корень контента — корректно.)

- [ ] **Step 2: Линтер ссылок чист**

Run:
```bash
python3 tools/lint/check_links.py
```
Expected: сообщение об отсутствии битых ссылок (0 broken).

- [ ] **Step 3: Голый клон не тянет пайплайн**

Run:
```bash
rm -rf /tmp/wiki-plain-check
git clone /home/cvetkov_es/development/HubEx.Wiki /tmp/wiki-plain-check
( test -z "$(ls -A /tmp/wiki-plain-check/tools 2>/dev/null)" ) && echo "tools/ пуст — OK"
ls /tmp/wiki-plain-check/pages >/dev/null && echo "pages/ на месте — OK"
rm -rf /tmp/wiki-plain-check
```
Expected: `tools/ пуст — OK` и `pages/ на месте — OK` (обычный `clone` сабмодуль не инициализирует).

- [ ] **Step 4: Вынести docs/ (dev-артефакты не нужны потребителю вики)**

> Примечание: этот шаг удаляет и файл текущего плана из рабочего дерева контента. План сохранён в истории git и в `HubEx.Wiki.Pipeline/docs/`; держи его открытым/под рукой до конца задачи.

Run:
```bash
cd /home/cvetkov_es/development/HubEx.Wiki
git rm -r docs/
git commit -m "chore: docs/ (specs/plans) переехали в HubEx.Wiki.Pipeline" \
  -m "Dev-артефакты не нужны потребителю вики; история сохранена в пайплайн-репо." \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
Expected: коммит создан, `docs/` удалён.

- [ ] **Step 5: Финальная проверка дерева контента**

Run:
```bash
git status --short
ls
```
Expected: `git status` чист; в корне — `README.md CLAUDE.md AGENTS.md index.md releasenotes-index.md pages tools .gitmodules .gitignore .claude` (без `docs`, `tools/*.py`, `pytest.ini`).

- [ ] **Step 6: [HUMAN-GATED] Пуш ветки и PR**

Подтвердить у пользователя. Затем:
```bash
git push -u origin feat/split-pipeline-submodule
gh pr create --title "Выделение пайплайна в сабмодуль tools/ → HubEx.Wiki.Pipeline" \
  --body "Пайплайн вынесен в отдельный репозиторий, подключён обратно git-сабмодулем (относительный host-agnostic URL). git clone контента даёт чистую вику без питон-кода; для обновления — git submodule update --init. Спека: docs/superpowers/specs/2026-07-14-split-pipeline-submodule-design.md (в HubEx.Wiki.Pipeline).

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```
Expected: ветка запушена, PR создан.

- [ ] **Step 7: [HUMAN-GATED, опционально] Сквозная проверка --recursive с GitHub**

После пуша — проверить, что относительный URL резолвится на GitHub:
```bash
rm -rf /tmp/wiki-recursive-check
git clone --recursive --branch feat/split-pipeline-submodule https://github.com/cvetkov-es/HubEx.Wiki.git /tmp/wiki-recursive-check
ls /tmp/wiki-recursive-check/tools/wiki_cli.py && echo "сабмодуль выкачан по относительному URL — OK"
rm -rf /tmp/wiki-recursive-check
```
Expected: `сабмодуль выкачан по относительному URL — OK`.

---

## Rollback

До пуша (Task 6 Step 6) всё локально и обратимо:
```bash
cd /home/cvetkov_es/development/HubEx.Wiki
git reset --hard pre-split-backup
git submodule deinit -f tools 2>/dev/null; rm -rf .git/modules/tools tools
git checkout -- .gitmodules 2>/dev/null; rm -f .gitmodules
rm -rf /home/cvetkov_es/development/HubEx.Wiki.Pipeline
```
После пуша/создания GitHub-репозитория откат — отдельное действие (удалить remote-ветку, удалить/приватизировать `HubEx.Wiki.Pipeline`).
