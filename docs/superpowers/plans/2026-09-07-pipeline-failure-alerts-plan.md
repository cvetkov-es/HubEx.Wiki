# Оповещения о сбоях ночных прогонов — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ночные прогоны вики и справочника API сообщают в телеграм о своём падении, а не ждут, пока человек заглянет в лог.

**Architecture:** в каждом из двух репозиториев пайплайна — модуль `notify` и подкоманда `notify` у CLI. Команда вызывается кроном **после** `sync`, отдельным процессом, и получает код возврата и путь к логу. Внутрь `sync` логика не кладётся: умерший процесс сообщение уже не отправит.

**Tech Stack:** Python 3.10+, `requests` (уже в зависимостях обоих пайплайнов), pytest. Telegram Bot API, метод `sendMessage`.

**Spec:** [2026-09-07-pipeline-failure-alerts-design.md](../specs/2026-09-07-pipeline-failure-alerts-design.md)

## Global Constraints

- **Два независимых репозитория, реализация делается дважды.** Вика: `/home/cvetkov_es/development/HubEx.Wiki/tools` (репо `HubEx.Wiki.Pipeline`). API: `/home/cvetkov_es/development/HubEx.API/tools` (репо `HubEx.API.Pipeline`). Оба подключены сабмодулями. Коммитить только изнутри: `git -C <путь к tools> ...`. Общий модуль на два продукта не заводить — это сорок строк, а расшифровки кодов у проектов разные.
- **Все пути в командах — абсолютные.** `cd` из предыдущей команды сохраняется и уводит запись не туда.
- **Код 0 — молчим.** Сообщение уходит только при ненулевом коде возврата.
- **`parse_mode` в телеграм не передаём.** В отчётах есть обратные кавычки, звёздочки и подчёркивания; любая разметка телеграма на них ломается.
- **`notify` никогда не падает и всегда возвращает 0.** Cron зовёт её последней, и провал доставки не должен выглядеть как провал прогона. Обо всём, что случилось, она пишет строкой в stdout — cron дописывает её в тот же лог.
- **Секреты только в `~/.config/hubex-notify.env`** (права 600). В git попадает лишь пример с пустыми значениями.
- **Предел сообщения телеграма — 4096 символов.** Обрезка обязана быть видимой: молча укоротить отчёт — значит соврать человеку о том, что он видит всё.
- **Комментарии и докстринги по-русски, объясняют ПОЧЕМУ, а не что.**
- **Ветки:** в обоих репозиториях пайплайна работать на `feat/pipeline-alerts`, создать её перед началом. Не пушить, не мержить.

---

### Task 1: оповещения в пайплайне вики

**Files:**
- Create: `/home/cvetkov_es/development/HubEx.Wiki/tools/notify.py`
- Create: `/home/cvetkov_es/development/HubEx.Wiki/tools/hubex-notify.env.example`
- Modify: `/home/cvetkov_es/development/HubEx.Wiki/tools/wiki_cli.py`
- Modify: `/home/cvetkov_es/development/HubEx.Wiki/tools/README.md`
- Test: `/home/cvetkov_es/development/HubEx.Wiki/tools/tests/test_notify.py`
- Test: `/home/cvetkov_es/development/HubEx.Wiki/tools/tests/test_cli.py`

**Interfaces:**
- Consumes: ничего из других задач.
- Produces: `notify.run_notify(*, exit_code: int, log_path: Path, config_path: Path | None = None, post=None) -> str`; `notify.load_config(path: Path | None = None) -> tuple[str, str]`; `notify.build_message(*, exit_code: int, log_path: Path, tail: str, truncated: bool) -> str`; `notify.read_tail(log_path: Path, limit: int = TAIL_LIMIT) -> tuple[str, bool]`; `notify.ConfigError`; константы `PROJECT`, `CONFIG_PATH`, `MAX_MESSAGE`, `TAIL_LIMIT`, `LOCK_BUSY`, `EXIT_MEANINGS`.

- [ ] **Step 1: Write the failing test**

Создать `/home/cvetkov_es/development/HubEx.Wiki/tools/tests/test_notify.py`:

```python
"""Оповещение о сбое ночного прогона.

Главное свойство этого модуля — он не имеет права упасть. Его зовут в три часа ночи
последней командой прогона, и трейсбек вместо сообщения означает, что о сбое не узнает
никто. Поэтому все ветки отказа проверяются явно: нет конфига, конфиг неполон, нет лога,
сеть не ответила.
"""
from pathlib import Path

import pytest

import notify


def config(tmp_path, token="T", chat="C"):
    p = tmp_path / "hubex-notify.env"
    lines = ["# комментарий", ""]
    if token is not None:
        lines.append(f"TELEGRAM_BOT_TOKEN={token}")
    if chat is not None:
        lines.append(f"TELEGRAM_CHAT_ID={chat}")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


class Sender:
    """Фейковый requests.post: помнит вызовы и умеет проваливаться."""

    def __init__(self, boom=None):
        self.calls = []
        self.boom = boom

    def __call__(self, url, **kw):
        self.calls.append((url, kw))
        if self.boom:
            raise self.boom

        class R:
            @staticmethod
            def raise_for_status():
                return None
        return R()


def test_zero_exit_code_says_nothing(tmp_path):
    s = Sender()
    out = notify.run_notify(exit_code=0, log_path=tmp_path / "log", 
                            config_path=config(tmp_path), post=s)
    assert s.calls == []
    assert "сообщать не о чем" in out


def test_failure_sends_message_with_code_and_meaning(tmp_path):
    log = tmp_path / "sync.log"
    log.write_text("# Отчёт\nвсё плохо\n", encoding="utf-8")
    s = Sender()
    out = notify.run_notify(exit_code=3, log_path=log, config_path=config(tmp_path), post=s)
    assert "отправлено" in out
    assert len(s.calls) == 1
    text = s.calls[0][1]["json"]["text"]
    assert notify.PROJECT in text
    assert "3" in text
    assert notify.EXIT_MEANINGS[3] in text
    assert str(log) in text
    assert "всё плохо" in text


def test_lock_busy_has_its_own_meaning():
    assert notify.LOCK_BUSY == 75
    assert "замок" in notify.EXIT_MEANINGS[75]


def test_unknown_code_is_not_silently_dropped(tmp_path):
    log = tmp_path / "sync.log"
    log.write_text("текст\n", encoding="utf-8")
    s = Sender()
    notify.run_notify(exit_code=99, log_path=log, config_path=config(tmp_path), post=s)
    assert "не распознан" in s.calls[0][1]["json"]["text"]


def test_no_markup_mode_is_requested(tmp_path):
    """`parse_mode` сломался бы об обратные кавычки и звёздочки в отчёте."""
    log = tmp_path / "sync.log"
    log.write_text("`код` *звёздочка* _подчёркивание_\n", encoding="utf-8")
    s = Sender()
    notify.run_notify(exit_code=1, log_path=log, config_path=config(tmp_path), post=s)
    assert "parse_mode" not in s.calls[0][1]["json"]


def test_missing_config_is_reported_not_raised(tmp_path):
    s = Sender()
    out = notify.run_notify(exit_code=1, log_path=tmp_path / "log",
                            config_path=tmp_path / "нет.env", post=s)
    assert "НЕ ОТПРАВЛЕНО" in out
    assert s.calls == []


def test_incomplete_config_names_the_missing_key(tmp_path):
    s = Sender()
    out = notify.run_notify(exit_code=1, log_path=tmp_path / "log",
                            config_path=config(tmp_path, chat=None), post=s)
    assert "TELEGRAM_CHAT_ID" in out
    assert s.calls == []


def test_missing_log_still_sends(tmp_path):
    """Код возврата важнее отчёта: прогон мог умереть до первой строки лога."""
    s = Sender()
    out = notify.run_notify(exit_code=1, log_path=tmp_path / "нет.log",
                            config_path=config(tmp_path), post=s)
    assert "отправлено" in out
    assert "Отчёта нет" in s.calls[0][1]["json"]["text"]


def test_long_tail_is_trimmed_visibly_and_fits(tmp_path):
    log = tmp_path / "sync.log"
    log.write_text("строка отчёта\n" * 5000, encoding="utf-8")
    s = Sender()
    notify.run_notify(exit_code=1, log_path=log, config_path=config(tmp_path), post=s)
    text = s.calls[0][1]["json"]["text"]
    assert len(text) <= notify.MAX_MESSAGE
    assert text.endswith("…отчёт обрезан, целиком — в логе")


def test_delivery_failure_is_reported_not_raised(tmp_path):
    log = tmp_path / "sync.log"
    log.write_text("текст\n", encoding="utf-8")
    s = Sender(boom=RuntimeError("сеть недоступна"))
    out = notify.run_notify(exit_code=1, log_path=log, config_path=config(tmp_path), post=s)
    assert "НЕ ОТПРАВЛЕНО" in out
    assert "сеть недоступна" in out


def test_timeout_is_always_passed(tmp_path):
    """Висящий запрос к телеграму не должен держать прогон до утра."""
    log = tmp_path / "sync.log"
    log.write_text("текст\n", encoding="utf-8")
    s = Sender()
    notify.run_notify(exit_code=1, log_path=log, config_path=config(tmp_path), post=s)
    assert s.calls[0][1]["timeout"] == notify.TIMEOUT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_notify.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'notify'`

- [ ] **Step 3: Write minimal implementation**

Создать `/home/cvetkov_es/development/HubEx.Wiki/tools/notify.py`:

```python
"""Оповещение о сбое ночного прогона в телеграм.

Живёт отдельной командой, которую cron зовёт ПОСЛЕ `sync`, а не внутри него. Если прогон
умер трейсбеком, по нехватке памяти или был убит по таймауту, изнутри сообщение уже не
уйдёт — и самый громкий сбой оказался бы единственным беззвучным. Отдельный процесс
переживает падение прогона любой природы.

Модуль не имеет права упасть сам: его зовут в три часа ночи, и трейсбек вместо сообщения
означает, что о сбое не узнает никто. Поэтому каждая ветка отказа возвращает строку для
лога, а не исключение.
"""
from pathlib import Path

import requests

PROJECT = "HubEx.Wiki"
CONFIG_PATH = Path.home() / ".config" / "hubex-notify.env"
API_URL = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT = 20
MAX_MESSAGE = 4096
TAIL_LIMIT = 2500

# Замок занят — это код не `sync`, а самого flock (`-E 75` в crontab). Без отдельного
# значения неудачный захват вернул бы 1 и слился бы с ошибкой модели: два совершенно
# разных происшествия дали бы одно сообщение с неверной причиной.
LOCK_BUSY = 75

EXIT_MEANINGS = {
    1: "ошибки забора выше порога, сбой модели или guard-проблема аннотации",
    2: "недоступен sitemap, либо не подключён worktree артефактов, либо нет клона сайта",
    3: "дерево не чисто, разошлось с origin или не на main",
    4: "сбой коммита или пуша вики либо артефактов",
    5: "сбой выкладки на wiki.hubex.ru",
    LOCK_BUSY: "замок занят — прошлый прогон не завершился",
}


class ConfigError(Exception):
    """Конфиг оповещений отсутствует или неполон."""


def load_config(path: Path | None = None) -> tuple[str, str]:
    path = path if path is not None else CONFIG_PATH
    if not path.exists():
        raise ConfigError(f"нет файла {path} — оповещения не настроены")
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    token, chat_id = values.get("TELEGRAM_BOT_TOKEN"), values.get("TELEGRAM_CHAT_ID")
    missing = [name for name, v in (("TELEGRAM_BOT_TOKEN", token),
                                    ("TELEGRAM_CHAT_ID", chat_id)) if not v]
    if missing:
        raise ConfigError(f"в {path} не заполнено: {', '.join(missing)}")
    return token, chat_id


def read_tail(log_path: Path, limit: int = TAIL_LIMIT) -> tuple[str, bool]:
    """Хвост лога и признак обрезки. Лога может не быть вовсе — прогон мог умереть
    до первой строки, и это не повод промолчать: код возврата важнее отчёта."""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", False
    if len(text) <= limit:
        return text.strip(), False
    return text[-limit:].strip(), True


def build_message(*, exit_code: int, log_path: Path, tail: str, truncated: bool) -> str:
    """Сообщение целиком. Обрезка всегда видима: молча укоротить отчёт — значит
    соврать человеку о том, что он видит всё."""
    meaning = EXIT_MEANINGS.get(exit_code, "код не распознан — смотри лог")
    head = (f"🔴 {PROJECT} — ночной прогон не прошёл\n\n"
            f"Код возврата: {exit_code} — {meaning}\n"
            f"Лог: {log_path}")
    if not tail:
        return head + "\n\nОтчёта нет — прогон не дошёл до первой строки лога"
    body = "\n\nХвост отчёта:\n"
    mark = "\n\n…отчёт обрезан, целиком — в логе"
    room = MAX_MESSAGE - len(head) - len(body) - len(mark)
    if truncated or len(tail) > room:
        return head + body + tail[-room:] + mark
    return head + body + tail


def send(text: str, *, token: str, chat_id: str, post=None) -> None:
    """`parse_mode` не задаём намеренно: в отчётах есть обратные кавычки, звёздочки и
    подчёркивания, и любая разметка телеграма на них ломается — сообщение либо не уйдёт,
    либо приедет искажённым."""
    post = post or requests.post
    resp = post(API_URL.format(token=token), timeout=TIMEOUT,
                json={"chat_id": chat_id, "text": text,
                      "disable_web_page_preview": True})
    resp.raise_for_status()


def run_notify(*, exit_code: int, log_path: Path, config_path: Path | None = None,
               post=None) -> str:
    """Строка для лога. Исключений не бросает никогда — см. докстринг модуля."""
    if exit_code == 0:
        return "notify: код 0 — сообщать не о чем"
    try:
        token, chat_id = load_config(config_path)
    except ConfigError as e:
        return f"notify: НЕ ОТПРАВЛЕНО — {e}"
    tail, truncated = read_tail(Path(log_path))
    text = build_message(exit_code=exit_code, log_path=log_path, tail=tail,
                         truncated=truncated)
    try:
        send(text, token=token, chat_id=chat_id, post=post)
    # Широкий except намеренный: сюда приходит всё, чем может ответить сеть и телеграм,
    # и ни одна из этих причин не стоит трейсбека вместо строки в логе.
    except Exception as e:
        return f"notify: НЕ ОТПРАВЛЕНО — {type(e).__name__}: {e}"
    return f"notify: отправлено, код возврата {exit_code}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest tests/test_notify.py -q`
Expected: PASS, 11 тестов.

- [ ] **Step 5: Добавить подкоманду в CLI**

Дописать тест в `/home/cvetkov_es/development/HubEx.Wiki/tools/tests/test_cli.py`:

```python
def test_notify_command_passes_code_and_log(monkeypatch, capsys, tmp_path):
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return "notify: отправлено, код возврата 3"

    monkeypatch.setattr(wiki_cli.notify, "run_notify", fake)
    code = wiki_cli.main(["notify", "--exit-code", "3", "--log", str(tmp_path / "s.log")])
    assert code == 0
    assert seen["exit_code"] == 3
    assert Path(seen["log_path"]) == tmp_path / "s.log"
    assert "отправлено" in capsys.readouterr().out


def test_notify_returns_zero_even_when_delivery_failed(monkeypatch, tmp_path):
    """Провал доставки не должен выглядеть как провал прогона: notify зовут последней."""
    monkeypatch.setattr(wiki_cli.notify, "run_notify",
                        lambda **kw: "notify: НЕ ОТПРАВЛЕНО — сеть недоступна")
    assert wiki_cli.main(["notify", "--exit-code", "1", "--log", str(tmp_path / "s.log")]) == 0
```

В `/home/cvetkov_es/development/HubEx.Wiki/tools/wiki_cli.py` добавить импорт рядом с `import export_llms`:

```python
import notify  # noqa: E402
```

В `build_parser()` после блока `publish` добавить:

```python
    nt = sub.add_parser("notify",
                        help="сообщить в телеграм о ненулевом коде возврата прогона; "
                             "вызывается кроном после sync, отдельным процессом")
    nt.add_argument("--exit-code", type=int, required=True,
                    help="код возврата sync (или flock: 75 — замок занят)")
    nt.add_argument("--log", type=Path, required=True, help="путь к логу прогона")
```

В `main()` перед обработкой `compact` добавить:

```python
    if args.command == "notify":
        print(notify.run_notify(exit_code=args.exit_code, log_path=args.log))
        return 0
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /home/cvetkov_es/development/HubEx.Wiki/tools && python3 -m pytest -q -m "not live"`
Expected: PASS, весь набор; было 382.

- [ ] **Step 7: Пример конфига и документация**

Создать `/home/cvetkov_es/development/HubEx.Wiki/tools/hubex-notify.env.example`:

```
# Скопировать в ~/.config/hubex-notify.env и заполнить, права 600.
# Токен выдаёт @BotFather при создании бота; chat_id своей переписки с ботом
# можно узнать, написав боту и запросив https://api.telegram.org/bot<токен>/getUpdates
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

В `/home/cvetkov_es/development/HubEx.Wiki/tools/README.md` добавить в раздел «Команды» блок про `notify` по образцу соседних: сигнатура, когда молчит, что в сообщении, где конфиг, и почему команда вызывается кроном отдельно от `sync`, а не внутри него. Отдельно указать, что `notify` всегда возвращает 0.

- [ ] **Step 8: Commit**

```bash
git -C /home/cvetkov_es/development/HubEx.Wiki/tools add notify.py hubex-notify.env.example wiki_cli.py README.md tests/test_notify.py tests/test_cli.py
git -C /home/cvetkov_es/development/HubEx.Wiki/tools commit -m "feat: оповещение о сбое ночного прогона в телеграм"
```

---

### Task 2: оповещения в пайплайне справочника API

Задача повторяет первую в другом репозитории. Отличаются три вещи: имя проекта в сообщении, таблица расшифровок кодов и место модуля — в этом репозитории верхнеуровневых модулей нет, всё лежит в пакете `update/` (там же `update/export_llms.py`).

**Files:**
- Create: `/home/cvetkov_es/development/HubEx.API/tools/update/notify.py`
- Create: `/home/cvetkov_es/development/HubEx.API/tools/hubex-notify.env.example`
- Modify: `/home/cvetkov_es/development/HubEx.API/tools/api_cli.py`
- Modify: `/home/cvetkov_es/development/HubEx.API/tools/README.md`
- Test: `/home/cvetkov_es/development/HubEx.API/tools/tests/test_notify.py`
- Test: `/home/cvetkov_es/development/HubEx.API/tools/tests/test_cli.py`

**Interfaces:**
- Consumes: ничего из других задач (репозиторий другой).
- Produces: `update.notify` с тем же набором имён, что и в задаче 1: `run_notify`, `load_config`, `build_message`, `read_tail`, `send`, `ConfigError`, `PROJECT`, `CONFIG_PATH`, `MAX_MESSAGE`, `TAIL_LIMIT`, `TIMEOUT`, `LOCK_BUSY`, `EXIT_MEANINGS`.

- [ ] **Step 1: Write the failing test**

Задача 1 к этому моменту завершена, и её файлы лежат на диске. Скопируй тестовый файл и
внеси ровно две правки — не переписывай его заново:

```bash
cp /home/cvetkov_es/development/HubEx.Wiki/tools/tests/test_notify.py \
   /home/cvetkov_es/development/HubEx.API/tools/tests/test_notify.py
```

Правка первая — строка импорта. Было:

```python
import notify
```

Стало:

```python
from update import notify
```

Правка вторая — дописать в конец файла тест, которого в вики нет:

```python
def test_api_has_no_publish_stage_code():
    """У справочника API нет стадии выкладки на сайт, значит нет и кода 5."""
    assert 5 not in notify.EXIT_MEANINGS
    assert notify.PROJECT == "HubEx.API"
```

Остальное содержимое файла остаётся дословно. Обрати внимание: расшифровки кодов тест
нигде не хардкодит, он сверяется с `notify.EXIT_MEANINGS[3]` — поэтому другой текст
расшифровок в этом проекте его не ломает.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cvetkov_es/development/HubEx.API/tools && python3 -m pytest tests/test_notify.py -q`
Expected: FAIL — `ImportError: cannot import name 'notify' from 'update'`

- [ ] **Step 3: Write minimal implementation**

Так же копией, а не набором заново:

```bash
cp /home/cvetkov_es/development/HubEx.Wiki/tools/notify.py \
   /home/cvetkov_es/development/HubEx.API/tools/update/notify.py
```

Дальше в скопированном файле меняются ровно две вещи. Имя проекта:

```python
PROJECT = "HubEx.API"
```

И таблица расшифровок — под коды этого пайплайна. Их источник истины —
`/home/cvetkov_es/development/HubEx.API/tools/README.md`, раздел про `sync`: сверься с
ним, а не только с текстом ниже.

```python
EXIT_MEANINGS = {
    1: "ошибки сервисов, сбой модели или guard-проблема заметок notes/",
    2: "недоступен индекс doc.hubex.ru",
    3: "дерево не чисто, разошлось с origin, или tools/ не на main",
    4: "сбой коммита или пуша",
    LOCK_BUSY: "замок занят — прошлый прогон не завершился",
}
```

Кода 5 здесь нет и быть не должно: стадии выкладки на сайт у справочника API нет.
Всё остальное — докстринг модуля, `ConfigError`, `load_config`, `read_tail`,
`build_message`, `send`, `run_notify` и прочие константы — остаётся дословно.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/cvetkov_es/development/HubEx.API/tools && python3 -m pytest tests/test_notify.py -q`
Expected: PASS, 12 тестов.

- [ ] **Step 5: Добавить подкоманду в CLI**

Дописать в `/home/cvetkov_es/development/HubEx.API/tools/tests/test_cli.py`:

```python
def test_notify_command_passes_code_and_log(monkeypatch, capsys, tmp_path):
    import api_cli
    from update import notify as notify_mod
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return "notify: отправлено, код возврата 3"

    monkeypatch.setattr(notify_mod, "run_notify", fake)
    code = api_cli.main(["notify", "--exit-code", "3", "--log", str(tmp_path / "s.log")])
    assert code == 0
    assert seen["exit_code"] == 3
    assert "отправлено" in capsys.readouterr().out


def test_notify_returns_zero_even_when_delivery_failed(monkeypatch, tmp_path):
    """Провал доставки не должен выглядеть как провал прогона: notify зовут последней."""
    import api_cli
    from update import notify as notify_mod
    monkeypatch.setattr(notify_mod, "run_notify",
                        lambda **kw: "notify: НЕ ОТПРАВЛЕНО — сеть недоступна")
    assert api_cli.main(["notify", "--exit-code", "1", "--log", str(tmp_path / "s.log")]) == 0
```

В `/home/cvetkov_es/development/HubEx.API/tools/api_cli.py` добавить `notify` в список импортов из `update`:

```python
from update import (api_manifest, export_llms, notes_patch, notify, pipeline,
                    publish_lens, report, sync)
```

В `build_parser()` после блока `publish-lens` добавить:

```python
    nt = sub.add_parser("notify",
                        help="сообщить в телеграм о ненулевом коде возврата прогона; "
                             "вызывается кроном после sync, отдельным процессом")
    nt.add_argument("--exit-code", type=int, required=True,
                    help="код возврата sync (или flock: 75 — замок занят)")
    nt.add_argument("--log", type=Path, required=True, help="путь к логу прогона")
```

**Важно про порядок в `main()`.** В начале `main()` стоит проверка `_content_repo_root_ok()`, которая отказывает с кодом 2, если команду запустили не из корня контент-репозитория. `notify` в этот список включать НЕЛЬЗЯ: она не читает и не пишет контент, а отказ по такой причине как раз и означал бы молчание вместо сообщения. Добавить обработку до этой проверки:

```python
    if args.command == "notify":
        print(notify.run_notify(exit_code=args.exit_code, log_path=args.log))
        return 0
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /home/cvetkov_es/development/HubEx.API/tools && python3 -m pytest -q`
Expected: PASS, весь набор.

- [ ] **Step 7: Пример конфига и документация**

Скопировать пример конфига: `cp /home/cvetkov_es/development/HubEx.Wiki/tools/hubex-notify.env.example /home/cvetkov_es/development/HubEx.API/tools/hubex-notify.env.example`. Он одинаков намеренно: конфиг у двух пайплайнов общий — один бот, одна переписка, а проекты различаются заголовком сообщения.

В `/home/cvetkov_es/development/HubEx.API/tools/README.md` добавить блок про `notify` по образцу соседних команд, с таблицей расшифровок кодов этого пайплайна.

- [ ] **Step 8: Commit**

```bash
git -C /home/cvetkov_es/development/HubEx.API/tools add update/notify.py hubex-notify.env.example api_cli.py README.md tests/test_notify.py tests/test_cli.py
git -C /home/cvetkov_es/development/HubEx.API/tools commit -m "feat: оповещение о сбое ночного прогона в телеграм"
```

---

## После плана — вручную, не задачей

Это делает человек: заводится секрет и правится конфиг машины вне git.

1. Создать бота у `@BotFather`, узнать свой `chat_id`, положить оба значения в `~/.config/hubex-notify.env`, выставить права: `chmod 600 ~/.config/hubex-notify.env`.
2. Проверить доставку живьём, не дожидаясь ночи: создать файл-заглушку с текстом и позвать `notify --exit-code 3 --log <файл>` у обоих пайплайнов. Сообщение должно прийти в телеграм, а в stdout лечь строка `notify: отправлено`.
3. Заменить две строки в `crontab -e`. Ключевое: `notify` стоит **за** пределами `flock`, иначе она не выполнится ровно в том случае, когда особенно нужна — когда замок занят зависшим прогоном. И `-E 75` обязателен: без него неудачный захват замка даёт код 1, тот же, которым `sync` сообщает об ошибках модели.

```
0 21 * * * L=$HOME/.local/state/hubex-wiki/sync-$(date -u +\%Y-\%m-\%d).log; flock -n -E 75 /tmp/hubex-wiki-sync.lock python3 /home/cvetkov_es/development/HubEx.Wiki/tools/wiki_cli.py sync >> $L 2>&1; python3 /home/cvetkov_es/development/HubEx.Wiki/tools/wiki_cli.py notify --exit-code $? --log $L >> $L 2>&1

15 21 * * * L=$HOME/.local/state/hubex-api/sync-$(date -u +\%Y-\%m-\%d).log; flock -n -E 75 /tmp/hubex-api-sync.lock python3 /home/cvetkov_es/development/HubEx.API/tools/api_cli.py sync >> $L 2>&1; python3 /home/cvetkov_es/development/HubEx.API/tools/api_cli.py notify --exit-code $? --log $L >> $L 2>&1
```

4. Заодно поправить комментарий в crontab: он до сих пор перечисляет коды возврата вики как `0–4`, а их теперь шесть, включая `5 — сбой выкладки` и `75 — замок занят`.
5. Оба указателя сабмодулей бампнуть в контент-репозиториях после мержа веток пайплайнов.
