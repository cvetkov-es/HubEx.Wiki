# План A — офлайн-генерация кейсов (в HubEx.Wiki.Pipeline) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Из корпуса саммари-переписок с готовыми эмбеддингами сгенерировать обобщённые, обезличенные, отфильтрованные кейсы поддержки и записать их как `cases/*.md` + `cases-index.md` в контент-репозиторий HubEx.Wiki.

**Architecture:** Батч-конвейер по локальному корпусу: leader-кластеризация (+под-кластеризация) → LLM-обобщение (1..K кейсов на группу) → фильтры (новизна к вике → долговечность → дедуп → PII-скраб) → сопоставление идентичности с уже опубликованными → рендер `cases/` + `cases-index.md`. Живого ingest из Omnidesk в Плане A нет — эмбеддинги берём готовыми (данные спайка); ingest — План B.

**Tech Stack:** Python 3.10+, numpy, requests, python-dotenv, pytest. LLM — OpenRouter (chat completions), как в спайке. Кластеризация и BM25 — на чистом numpy/питоне (перенос из спайка `omnidesk/spike/`).

## Global Constraints

- **Код живёт в `HubEx.Wiki.Pipeline`** (сабмодуль `tools/` внутри HubEx.Wiki). Все пути ниже — **от корня этого репо** (т.е. `casegen/...` == `tools/casegen/...` из корня вики). Git-команды выполняются из `tools/`.
- Новый пакет — **`casegen/`**, рядом с существующим `update/`. Импорт в тестах: `from casegen... import ...` (в `tools/conftest.py` уже добавлен `tools/` в `sys.path`).
- Тесты — плоско в **`tools/tests/`**, имена `test_casegen_*.py` (pytest собирает из `tests/`, см. `tools/pytest.ini`). Фикстуры — `tools/tests/fixtures/`.
- Зависимости добавляются в **`tools/requirements.txt`**: `numpy>=1.24`, `python-dotenv>=1.0` (там уже есть `requests>=2.31`, `pytest>=8`). НЕ добавлять sklearn/scipy/hdbscan/rank_bm25.
- LLM только через `casegen/llm.py` (OpenRouter); ключ `OPENROUTER_API_KEY`, база `OPENROUTER_BASE_URL` из `.env` контент-репо (HubEx.Wiki/.env — там ключи уже есть). `max_tokens=4000` обязателен (в спайке без него обрезало ответы).
- Модель по умолчанию: `google/gemini-2.5-flash` (env `CASES_MODEL` переопределяет).
- В юнит-тестах реальных сетевых вызовов НЕТ — LLM всегда мокается через параметр `chat_fn`.
- Эмбеддинги в корпусе — L2-нормированы; косинус = скалярное произведение.
- Выход пишем в контент-репо HubEx.Wiki: `cases/` и `cases-index.md`. `pages/**` не трогаем.
- Кейсы обезличены: имён клиентов, телефонов, ID тенантов, номеров заявок в тексте быть не должно.
- CLI-точка входа — **сабкоманда `cases` в `tools/wiki_cli.py`** (в стиле `update`/`export-llms`), не отдельный скрипт.

---

### Task 1: Пакет casegen, конфиг, загрузчик корпуса

**Files:**
- Modify: `tools/requirements.txt` (добавить `numpy>=1.24`, `python-dotenv>=1.0`)
- Modify: `tools/.gitignore` (добавить `raw/`, `corpus/`, `state/`, `casegen/out/`, `.env`)
- Create: `casegen/__init__.py`
- Create: `casegen/config.py`
- Create: `casegen/corpus.py`
- Test: `tools/tests/test_casegen_corpus.py`
- Create: `tools/tests/fixtures/corpus_sample.csv`

**Interfaces:**
- Produces:
  - `casegen.corpus.Record(id: str, content: str, embedding: np.ndarray)` — dataclass; `embedding` 1D float32, L2-нормирован.
  - `casegen.corpus.load_corpus(csv_path: Path) -> tuple[list[Record], np.ndarray]`.
  - `casegen.config` — константы: `REPO_ROOT: Path` (корень `tools/`), `WIKI_ROOT: Path`, `PAGES_DIR`, `CASES_DIR`, `CASES_INDEX`, `CLUSTER_THRESHOLD=0.78`, `SUBCLUSTER_THRESHOLD=0.85`, `MIN_CLUSTER_SIZE=3`, `SUBCLUSTER_MIN_COHESION=0.62`, `SUBCLUSTER_MIN_SIZE=12`, `SEED=42`, `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `MODEL`, `require_openrouter()`.

- [ ] **Step 1: Создать фикстуру корпуса**

Create `tools/tests/fixtures/corpus_sample.csv` (эмбеддинги 4-мерные: две плотные темы + «мусор»):

```csv
id,content,embedding
1,"ПРОБЛЕМА:Планировщик не создаёт заявки,ОТВЕТ:Проверьте тип заявки","[1.0,0.0,0.0,0.02]"
2,"ПРОБЛЕМА:Планировщик молчит, заявок нет,ОТВЕТ:Перезапустите планировщик","[0.99,0.01,0.0,0.0]"
3,"ПРОБЛЕМА:Плановые заявки не появляются,ОТВЕТ:Поправьте вид работ","[0.98,0.02,0.01,0.0]"
4,"ПРОБЛЕМА:Не могу добавить лицензии,ОТВЕТ:Лицензии добавлены","[0.0,0.0,1.0,0.03]"
5,"ПРОБЛЕМА:Нужно больше лицензий в тенанте,ОТВЕТ:Готово","[0.01,0.0,0.99,0.0]"
6,"ПРОБЛЕМА:Увеличьте лицензии,ОТВЕТ:Сделано","[0.0,0.01,0.98,0.02]"
7,"ПРОБЛЕМА:Разовый вопрос,ОТВЕТ:ок","[0.0,1.0,0.0,0.0]"
```

- [ ] **Step 2: Написать падающий тест загрузчика**

Create `tools/tests/test_casegen_corpus.py`:

```python
from pathlib import Path

import numpy as np

from casegen.corpus import load_corpus

FIXT = Path(__file__).parent / "fixtures" / "corpus_sample.csv"


def test_load_corpus_parses_records_and_normalizes():
    records, matrix = load_corpus(FIXT)
    assert len(records) == 7
    assert records[0].id == "1"
    assert "Планировщик" in records[0].content
    assert matrix.shape == (7, 4)
    np.testing.assert_allclose(np.linalg.norm(matrix, axis=1), np.ones(7), atol=1e-5)


def test_load_corpus_skips_broken_rows(tmp_path):
    p = tmp_path / "broken.csv"
    p.write_text(
        'id,content,embedding\n'
        '1,"ok","[1.0,0.0]"\n'
        '2,"bad","[]"\n'
        '3,"bad2","not-json"\n',
        encoding="utf-8",
    )
    records, matrix = load_corpus(p)
    assert [r.id for r in records] == ["1"]
    assert matrix.shape == (1, 2)
```

- [ ] **Step 3: Запустить тест — убедиться, что падает**

Run (из `tools/`): `python -m pytest tests/test_casegen_corpus.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'casegen'`.

- [ ] **Step 4: Добавить зависимости и gitignore**

Modify `tools/requirements.txt` — добавить строки:

```
numpy>=1.24
python-dotenv>=1.0
```

Modify `tools/.gitignore` — добавить строки:

```
raw/
corpus/
state/
casegen/out/
.env
```

Установить: из `tools/` выполнить `python -m pip install numpy python-dotenv`.

- [ ] **Step 5: Создать пакет и config.py**

Create `casegen/__init__.py` (пустой).

Create `casegen/config.py`:

```python
"""Конфиг пайплайна кейсов: пути, параметры, доступ к OpenRouter."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# casegen/ лежит в корне репо tools/ (HubEx.Wiki.Pipeline).
REPO_ROOT = Path(__file__).resolve().parent.parent
# Контент-репо HubEx.Wiki — родитель сабмодуля tools/.
WIKI_ROOT = Path(os.getenv("WIKI_ROOT", REPO_ROOT.parent))
load_dotenv(WIKI_ROOT / ".env")

PAGES_DIR = WIKI_ROOT / "pages"
CASES_DIR = WIKI_ROOT / "cases"
CASES_INDEX = WIKI_ROOT / "cases-index.md"

CLUSTER_THRESHOLD = 0.78
SUBCLUSTER_THRESHOLD = 0.85
MIN_CLUSTER_SIZE = 3
SUBCLUSTER_MIN_COHESION = 0.62
SUBCLUSTER_MIN_SIZE = 12
SEED = 42

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("CASES_MODEL", "google/gemini-2.5-flash")


def require_openrouter() -> None:
    if not OPENROUTER_API_KEY:
        raise SystemExit("Нет OPENROUTER_API_KEY — заполни HubEx.Wiki/.env.")
```

- [ ] **Step 6: Написать corpus.py**

Create `casegen/corpus.py`:

```python
"""Загрузка корпуса: записи (id, content, embedding) + матрица эмбеддингов.

В Плане A источник — CSV с готовыми эмбеддингами (данные спайка/фикстура).
В Плане B тот же интерфейс наполняется живым ingest из Omnidesk.
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

csv.field_size_limit(sys.maxsize)


@dataclass
class Record:
    id: str
    content: str
    embedding: np.ndarray  # 1D float32, L2-нормирован


def load_corpus(csv_path: Path) -> tuple[list[Record], np.ndarray]:
    records: list[Record] = []
    vectors: list[np.ndarray] = []
    skipped = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                emb = np.asarray(json.loads(row["embedding"]), dtype=np.float32)
                if emb.ndim != 1 or emb.size == 0:
                    raise ValueError("пустой эмбеддинг")
                norm = np.linalg.norm(emb)
                if not np.isfinite(norm) or norm == 0:
                    raise ValueError("нулевая норма")
                emb = emb / norm
                records.append(Record(id=row.get("id", ""), content=row.get("content", "") or "", embedding=emb))
                vectors.append(emb)
            except Exception as e:  # noqa: BLE001
                skipped += 1
                if skipped <= 5:
                    print(f"[corpus] скип id={row.get('id')!r}: {e}", file=sys.stderr)
    if not records:
        raise SystemExit(f"[corpus] нет валидных строк в {csv_path}")
    return records, np.vstack(vectors)
```

- [ ] **Step 7: Запустить тесты — убедиться, что проходят**

Run (из `tools/`): `python -m pytest tests/test_casegen_corpus.py -v`
Expected: PASS (2 passed).

- [ ] **Step 8: Commit**

```bash
# cwd = tools/
git add requirements.txt .gitignore casegen/ tests/test_casegen_corpus.py tests/fixtures/corpus_sample.csv
git commit -m "feat(cases): пакет casegen, конфиг, загрузчик корпуса"
```

---

### Task 2: Кластеризация + под-кластеризация

**Files:**
- Create: `casegen/cluster.py`
- Test: `tools/tests/test_casegen_cluster.py`

**Interfaces:**
- Consumes: матрица `np.ndarray [N, D]` (нормированная).
- Produces:
  - `casegen.cluster.Cluster(members: list[int], size: int, cohesion: float)`.
  - `cluster(matrix, threshold=config.CLUSTER_THRESHOLD, min_size=config.MIN_CLUSTER_SIZE) -> list[Cluster]` — leader-кластеризация, по размеру убыв.
  - `subcluster(clusters, matrix) -> list[Cluster]` — крупные/рыхлые группы дробит жёстче; плоский список групп >= min_size.

- [ ] **Step 1: Написать падающие тесты**

Create `tools/tests/test_casegen_cluster.py`:

```python
import numpy as np

from casegen.cluster import cluster, subcluster


def _norm(m):
    m = np.asarray(m, dtype=np.float32)
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def test_cluster_no_chaining():
    rng = np.random.default_rng(0)
    a = np.tile([1.0, 0.0], (10, 1)) + rng.normal(0, 0.01, (10, 2))
    b = np.tile([0.0, 1.0], (10, 1)) + rng.normal(0, 0.01, (10, 2))
    m = _norm(np.vstack([a, b]))
    clusters = cluster(m, threshold=0.9, min_size=3)
    assert len(clusters) == 2
    assert all(c.cohesion > 0.9 for c in clusters)


def test_cluster_sorted_by_size_desc():
    rng = np.random.default_rng(1)
    big = np.tile([1.0, 0.0], (20, 1)) + rng.normal(0, 0.005, (20, 2))
    small = np.tile([0.0, 1.0], (5, 1)) + rng.normal(0, 0.005, (5, 2))
    m = _norm(np.vstack([big, small]))
    clusters = cluster(m, threshold=0.9, min_size=3)
    assert [c.size for c in clusters] == [20, 5]


def test_subcluster_splits_loose_large_group():
    rng = np.random.default_rng(2)
    t1 = np.tile([1.0, 0.0, 0.0], (15, 1)) + rng.normal(0, 0.01, (15, 3))
    t2 = np.tile([0.8, 0.6, 0.0], (15, 1)) + rng.normal(0, 0.01, (15, 3))
    m = _norm(np.vstack([t1, t2]))
    loose = cluster(m, threshold=0.6, min_size=3)
    assert len(loose) == 1 and loose[0].size == 30
    refined = subcluster(loose, m)
    assert len(refined) >= 2
    assert all(c.cohesion >= 0.62 for c in refined)
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run (из `tools/`): `python -m pytest tests/test_casegen_cluster.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'casegen.cluster'`.

- [ ] **Step 3: Реализовать cluster.py**

Create `casegen/cluster.py`:

```python
"""Leader-кластеризация на косинусе (чистый numpy, без сцепления в «ком») +
под-кластеризация крупных/рыхлых групп, чтобы каждая финальная группа была
топикально чистой и влезала в контекст LLM целиком (без сэмплинга)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from casegen import config


@dataclass
class Cluster:
    members: list[int]
    size: int
    cohesion: float


def cluster(matrix: np.ndarray, threshold: float = config.CLUSTER_THRESHOLD,
            min_size: int = config.MIN_CLUSTER_SIZE) -> list[Cluster]:
    n, d = matrix.shape
    centroids = np.zeros((n, d), dtype=np.float32)
    sums = np.zeros((n, d), dtype=np.float32)
    members: list[list[int]] = []
    k = 0
    for i in range(n):
        v = matrix[i]
        if k:
            sims = centroids[:k] @ v
            j = int(np.argmax(sims))
            if sims[j] >= threshold:
                members[j].append(i)
                sums[j] += v
                centroids[j] = sums[j] / np.linalg.norm(sums[j])
                continue
        centroids[k] = v
        sums[k] = v
        members.append([i])
        k += 1
    clusters = [Cluster(mem, len(mem), _cohesion(matrix, mem)) for mem in members if len(mem) >= min_size]
    clusters.sort(key=lambda c: c.size, reverse=True)
    return clusters


def subcluster(clusters: list[Cluster], matrix: np.ndarray) -> list[Cluster]:
    """Крупные и рыхлые группы дробим жёстче; чистые пропускаем как есть."""
    out: list[Cluster] = []
    for c in clusters:
        loose = c.cohesion < config.SUBCLUSTER_MIN_COHESION
        large = c.size >= config.SUBCLUSTER_MIN_SIZE
        if not (loose and large):
            out.append(c)
            continue
        idx = np.asarray(c.members)
        sub = cluster(matrix[idx], threshold=config.SUBCLUSTER_THRESHOLD, min_size=config.MIN_CLUSTER_SIZE)
        if len(sub) <= 1:
            out.append(c)
            continue
        for s in sub:
            real = [c.members[m] for m in s.members]
            out.append(Cluster(real, len(real), _cohesion(matrix, real)))
    out.sort(key=lambda c: c.size, reverse=True)
    return out


def _cohesion(matrix: np.ndarray, members: list[int]) -> float:
    if len(members) < 2:
        return 1.0
    sub = matrix[np.asarray(members)]
    sim = sub @ sub.T
    m = sim.shape[0]
    return float((sim.sum() - np.trace(sim)) / (m * m - m))
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run (из `tools/`): `python -m pytest tests/test_casegen_cluster.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add casegen/cluster.py tests/test_casegen_cluster.py
git commit -m "feat(cases): leader-кластеризация + под-кластеризация рыхлых групп"
```

---

### Task 3: LLM-клиент (OpenRouter) и генерация кейсов

**Files:**
- Create: `casegen/llm.py`
- Create: `casegen/generate.py`
- Test: `tools/tests/test_casegen_generate.py`

**Interfaces:**
- Consumes: `Cluster` (Task 2), `Record` (Task 1).
- Produces:
  - `casegen.llm.chat(messages: list[dict], model=None, temperature=0.2, max_tokens=4000, ...) -> str`.
  - `casegen.generate.Case` — dataclass: `title, problem, symptoms, typical_answer, keywords: list[str], source_ids: list[str], cluster_size: int, cohesion: float, centroid: np.ndarray | None = None, novelty: str = "unknown", novelty_reason: str = "", durable: bool = True, slug: str = ""`.
  - `generate_cases(cluster, records, matrix, chat_fn=llm.chat) -> list[Case]` — 1..K кейсов; проставляет `centroid` = средний нормированный вектор членов.
  - `casegen.generate._parse_json_array(raw: str) -> list[dict]`.

- [ ] **Step 1: Написать падающие тесты**

Create `tools/tests/test_casegen_generate.py`:

```python
import numpy as np

from casegen.cluster import Cluster
from casegen.corpus import Record
from casegen.generate import generate_cases, _parse_json_array


def _recs():
    return [Record(str(i), f"тикет {i}", np.array([1.0, 0.0], dtype=np.float32)) for i in range(3)]


def test_parse_json_array_fenced():
    raw = 'Вот:\n```json\n[{"title":"a"},{"title":"b"}]\n```'
    assert len(_parse_json_array(raw)) == 2


def test_parse_json_array_truncated_is_empty():
    assert _parse_json_array('```json\n[{"title":"a","problem":"обор') == []


def test_generate_cases_maps_fields_and_centroid():
    recs = _recs()
    matrix = np.vstack([r.embedding for r in recs])
    cl = Cluster(members=[0, 1, 2], size=3, cohesion=0.9)

    def fake_chat(messages, **kw):
        return '[{"title":"Планировщик","problem":"не создаёт","symptoms":"нет заявок",' \
               '"typical_answer":"перезапустить","keywords":["планировщик"],"ticket_numbers":[0,1]}]'

    cases = generate_cases(cl, recs, matrix, chat_fn=fake_chat)
    assert len(cases) == 1
    c = cases[0]
    assert c.title == "Планировщик"
    assert c.source_ids == ["0", "1"]
    assert c.cluster_size == 3
    assert c.centroid is not None and c.centroid.shape == (2,)


def test_generate_cases_empty_on_junk():
    recs = _recs()
    matrix = np.vstack([r.embedding for r in recs])
    cl = Cluster(members=[0, 1, 2], size=3, cohesion=0.9)
    cases = generate_cases(cl, recs, matrix, chat_fn=lambda m, **k: "[]")
    assert cases == []
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run (из `tools/`): `python -m pytest tests/test_casegen_generate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'casegen.generate'`.

- [ ] **Step 3: Реализовать llm.py**

Create `casegen/llm.py`:

```python
"""Тонкий клиент OpenRouter (chat completions) на requests, с ретраем."""
from __future__ import annotations

import time

import requests

from casegen import config


class LLMError(RuntimeError):
    pass


def chat(messages: list[dict], model: str | None = None, temperature: float = 0.2,
         max_tokens: int = 4000, max_retries: int = 4, timeout: int = 120) -> str:
    config.require_openrouter()
    url = config.OPENROUTER_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {"model": model or config.MODEL, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    headers = {"Authorization": f"Bearer {config.OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    last = None
    for attempt in range(max_retries):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                raise LLMError(f"HTTP {r.status_code}: {r.text[:200]}")
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    raise LLMError(f"OpenRouter не ответил после {max_retries} попыток: {last}")
```

- [ ] **Step 4: Реализовать generate.py**

Create `casegen/generate.py`:

```python
"""Из группы похожих тикетов — 1..K обобщённых кейсов (LLM с разбиением)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import numpy as np

from casegen import llm
from casegen.cluster import Cluster
from casegen.corpus import Record


@dataclass
class Case:
    title: str
    problem: str
    symptoms: str
    typical_answer: str
    keywords: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    cluster_size: int = 0
    cohesion: float = 0.0
    centroid: np.ndarray | None = None
    novelty: str = "unknown"
    novelty_reason: str = ""
    durable: bool = True
    slug: str = ""


_SYSTEM = (
    "Ты аналитик поддержки продукта HubEx (FSM-система для выездного обслуживания). "
    "На входе — группа похожих обращений (проблема/вопрос/ответ). Обобщи их в "
    "переиспользуемые КЕЙСЫ базы знаний."
)

_INSTRUCTION = """Ниже пронумерованные обращения из одной кластерной группы. Они ПОХОЖИ, но
внутри может быть несколько РАЗНЫХ проблем. Выдели различные проблемы и опиши каждую как
отдельный обобщённый кейс. Если все об одном — один кейс. Если это шум без пользы — пустой массив.

Верни СТРОГО JSON-массив без markdown:
[{"title":"...","problem":"без имён клиентов","symptoms":"...","typical_answer":"...",
  "keywords":["..."],"ticket_numbers":[номера из списка]}]

Обращения:
"""


def generate_cases(cluster: Cluster, records: list[Record], matrix: np.ndarray,
                   chat_fn=llm.chat) -> list[Case]:
    numbered = "\n".join(f"[{n}] {records[idx].content[:600]}" for n, idx in enumerate(cluster.members))
    raw = chat_fn([{"role": "system", "content": _SYSTEM},
                   {"role": "user", "content": _INSTRUCTION + numbered}])
    centroid = _centroid(matrix, cluster.members)
    cases: list[Case] = []
    for obj in _parse_json_array(raw):
        nums = [n for n in (obj.get("ticket_numbers") or []) if isinstance(n, int) and 0 <= n < len(cluster.members)]
        ids = [records[cluster.members[n]].id for n in nums]
        cases.append(Case(
            title=str(obj.get("title", "")).strip(),
            problem=str(obj.get("problem", "")).strip(),
            symptoms=str(obj.get("symptoms", "")).strip(),
            typical_answer=str(obj.get("typical_answer", "")).strip(),
            keywords=[str(k).strip() for k in (obj.get("keywords") or [])],
            source_ids=ids or [records[i].id for i in cluster.members],
            cluster_size=cluster.size, cohesion=cluster.cohesion, centroid=centroid,
        ))
    return cases


def _centroid(matrix: np.ndarray, members: list[int]) -> np.ndarray:
    v = matrix[np.asarray(members)].mean(axis=0)
    n = np.linalg.norm(v)
    return (v / n).astype(np.float32) if n else v.astype(np.float32)


def _parse_json_array(raw: str) -> list[dict]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        return [d for d in json.loads(text[start:end + 1]) if isinstance(d, dict)]
    except json.JSONDecodeError:
        return []
```

- [ ] **Step 5: Запустить тесты — убедиться, что проходят**

Run (из `tools/`): `python -m pytest tests/test_casegen_generate.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add casegen/llm.py casegen/generate.py tests/test_casegen_generate.py
git commit -m "feat(cases): LLM-клиент OpenRouter + генерация кейсов с разбиением"
```

---

### Task 4: Фильтр новизны к вике (BM25 + LLM-судья)

**Files:**
- Create: `casegen/filters/__init__.py`
- Create: `casegen/filters/bm25.py`
- Create: `casegen/filters/novelty.py`
- Test: `tools/tests/test_casegen_novelty.py`

**Interfaces:**
- Consumes: `Case` (Task 3).
- Produces:
  - `casegen.filters.bm25.BM25(docs)`, `Doc(path, text, tokens)`, `tokenize(text) -> list[str]`, `load_wiki(pages_dir) -> BM25`, метод `search(query, top_k=3) -> list[tuple[Doc, float]]`.
  - `casegen.filters.novelty.assess(case, index, chat_fn=llm.chat, top_k=3) -> None` — мутирует `case.novelty` / `case.novelty_reason`.

- [ ] **Step 1: Написать падающие тесты**

Create `tools/tests/test_casegen_novelty.py`:

```python
from casegen.filters.bm25 import BM25, Doc, tokenize
from casegen.filters.novelty import assess
from casegen.generate import Case


def _idx():
    docs = [
        Doc("pages/admin/SLA.md", "Настройка SLA и сроков реакции", tokenize("Настройка SLA и сроков реакции")),
        Doc("pages/user/Import.md", "Импорт материалов из Excel", tokenize("Импорт материалов из Excel")),
    ]
    return BM25(docs)


def test_bm25_ranks_relevant_first():
    hits = _idx().search("как настроить SLA", top_k=1)
    assert hits and hits[0][0].path == "pages/admin/SLA.md"


def test_assess_sets_verdict_from_llm():
    case = Case(title="SLA", problem="как настроить сроки", symptoms="", typical_answer="в разделе SLA",
                keywords=["sla"])
    assess(case, _idx(), chat_fn=lambda m, **k: '{"verdict":"покрыто","reason":"есть статья SLA"}')
    assert case.novelty == "покрыто"
    assert "SLA" in case.novelty_reason


def test_assess_new_when_no_bm25_hits():
    case = Case(title="Квантовая телепортация заявок", problem="zzz", symptoms="", typical_answer="",
                keywords=["zzz"])
    assess(case, _idx(), chat_fn=lambda m, **k: (_ for _ in ()).throw(AssertionError("LLM звать не должны")))
    assert case.novelty == "новое"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run (из `tools/`): `python -m pytest tests/test_casegen_novelty.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'casegen.filters'`.

- [ ] **Step 3: Реализовать bm25.py**

Create `casegen/filters/__init__.py` (пустой).

Create `casegen/filters/bm25.py`:

```python
"""Крошечный BM25 по страницам вики (без зависимостей)."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

_TOKEN = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class Doc:
    path: str
    text: str
    tokens: list[str]


class BM25:
    def __init__(self, docs: list[Doc], k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.N = len(docs)
        self.avgdl = sum(len(d.tokens) for d in docs) / max(self.N, 1)
        self.df: dict[str, int] = {}
        self.tf: list[dict[str, int]] = []
        for d in docs:
            counts: dict[str, int] = {}
            for tok in d.tokens:
                counts[tok] = counts.get(tok, 0) + 1
            self.tf.append(counts)
            for tok in counts:
                self.df[tok] = self.df.get(tok, 0) + 1

    def _idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log(1 + (self.N - n + 0.5) / (n + 0.5))

    def search(self, query: str, top_k: int = 3) -> list[tuple[Doc, float]]:
        q = tokenize(query)
        scored: list[tuple[Doc, float]] = []
        for i, d in enumerate(self.docs):
            dl = len(d.tokens)
            s = 0.0
            for term in q:
                f = self.tf[i].get(term, 0)
                if not f:
                    continue
                s += self._idf(term) * (f * (self.k1 + 1)) / (
                    f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            if s > 0:
                scored.append((d, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


def load_wiki(pages_dir: Path) -> BM25:
    docs: list[Doc] = []
    for path in sorted(pages_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        docs.append(Doc(str(path.relative_to(pages_dir.parent)), text, tokenize(text)))
    if not docs:
        raise SystemExit(f"[bm25] не найдено .md в {pages_dir}")
    return BM25(docs)
```

- [ ] **Step 4: Реализовать novelty.py**

Create `casegen/filters/novelty.py`:

```python
"""Новизна кейса к вике: BM25 достаёт близкие страницы → LLM-судья."""
from __future__ import annotations

import json
import re

from casegen import llm
from casegen.filters.bm25 import BM25
from casegen.generate import Case

_VALID = {"покрыто", "частично", "новое"}
_SYSTEM = ("Ты редактор базы знаний HubEx. Определяешь, покрыт ли кейс поддержки существующей "
           "документацией. Отвечаешь строго JSON.")
_TEMPLATE = """Кейс:
ЗАГОЛОВОК: {title}
ПРОБЛЕМА: {problem}
ТИПОВОЙ ОТВЕТ: {answer}

Близкие фрагменты вики:
{snippets}

Покрыт ли кейс викой? Верни JSON: {{"verdict":"покрыто|частично|новое","reason":"1 фраза"}}
- покрыто — вика уже отвечает; частично — тема есть, конкретики нет; новое — в вике нет."""


def assess(case: Case, index: BM25, chat_fn=llm.chat, top_k: int = 3) -> None:
    query = " ".join([case.title, case.problem] + case.keywords)
    hits = index.search(query, top_k=top_k)
    if not hits:
        case.novelty, case.novelty_reason = "новое", "нет лексических совпадений в вике"
        return
    snippets = "\n\n".join(f"[{d.path}]\n{d.text[:700]}" for d, _ in hits)
    try:
        raw = chat_fn([{"role": "system", "content": _SYSTEM},
                       {"role": "user", "content": _TEMPLATE.format(
                           title=case.title, problem=case.problem,
                           answer=case.typical_answer, snippets=snippets)}])
        obj = _parse_obj(raw)
        v = str(obj.get("verdict", "")).strip().lower()
        case.novelty = v if v in _VALID else "unknown"
        case.novelty_reason = str(obj.get("reason", "")).strip()
    except Exception as e:  # noqa: BLE001
        case.novelty, case.novelty_reason = "unknown", f"ошибка судьи: {e}"


def _parse_obj(raw: str) -> dict:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}
```

- [ ] **Step 5: Запустить тесты — убедиться, что проходят**

Run (из `tools/`): `python -m pytest tests/test_casegen_novelty.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add casegen/filters/__init__.py casegen/filters/bm25.py casegen/filters/novelty.py tests/test_casegen_novelty.py
git commit -m "feat(cases): фильтр новизны к вике (BM25 + LLM-судья)"
```

---

### Task 5: Фильтр долговечности (инцидент vs знание)

**Files:**
- Create: `casegen/filters/durability.py`
- Test: `tools/tests/test_casegen_durability.py`

**Interfaces:**
- Consumes: `Case` (Task 3).
- Produces: `casegen.filters.durability.classify(case, chat_fn=llm.chat) -> None` — мутирует `case.durable` (True = знание, False = разовый инцидент). При сбое судьи — False (консервативно).

- [ ] **Step 1: Написать падающие тесты**

Create `tools/tests/test_casegen_durability.py`:

```python
from casegen.filters.durability import classify
from casegen.generate import Case


def _case(title):
    return Case(title=title, problem="p", symptoms="s", typical_answer="a")


def test_incident_marked_transient():
    c = _case("Сервер тормозил, починили")
    classify(c, chat_fn=lambda m, **k: '{"durable":false,"reason":"разовый инцидент"}')
    assert c.durable is False


def test_knowledge_marked_durable():
    c = _case("Планировщик не создаёт заявки — как чинить")
    classify(c, chat_fn=lambda m, **k: '{"durable":true,"reason":"воспроизводимое знание"}')
    assert c.durable is True


def test_llm_error_defaults_transient():
    c = _case("непонятно")
    classify(c, chat_fn=lambda m, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert c.durable is False
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run (из `tools/`): `python -m pytest tests/test_casegen_durability.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'casegen.filters.durability'`.

- [ ] **Step 3: Реализовать durability.py**

Create `casegen/filters/durability.py`:

```python
"""Долговечность кейса: воспроизводимое знание vs разовый инцидент/операционный шум.

Спайк показал: без этого фильтра ~30-40% помеченного «новое» — транзиентный шум
(разовый сбой сервера, «есть ли проблемы сейчас?», запрос обратной связи).
При сбое судьи считаем НЕ долговечным (консервативно, ревью нет)."""
from __future__ import annotations

import json
import re

from casegen import llm
from casegen.generate import Case

_SYSTEM = ("Ты редактор базы знаний HubEx. Отделяешь долговечное знание о продукте от "
           "разовых инцидентов и операционного шума. Отвечаешь строго JSON.")
_TEMPLATE = """Кейс:
ЗАГОЛОВОК: {title}
ПРОБЛЕМА: {problem}
ТИПОВОЙ ОТВЕТ: {answer}

durable=true — воспроизводимое знание: настройка, поведение продукта, диагностика с решением,
которое пригодится снова.
durable=false — разовое: сбой сервера «починили, проверьте», «есть ли сейчас проблемы?»,
запрос обратной связи, частный инцидент без переиспользуемого урока.

Верни JSON: {{"durable":true|false,"reason":"1 фраза"}}"""


def classify(case: Case, chat_fn=llm.chat) -> None:
    try:
        raw = chat_fn([{"role": "system", "content": _SYSTEM},
                       {"role": "user", "content": _TEMPLATE.format(
                           title=case.title, problem=case.problem, answer=case.typical_answer)}])
        obj = _parse_obj(raw)
        case.durable = bool(obj.get("durable", False))
    except Exception:  # noqa: BLE001 — при сбое консервативно отсекаем
        case.durable = False


def _parse_obj(raw: str) -> dict:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run (из `tools/`): `python -m pytest tests/test_casegen_durability.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add casegen/filters/durability.py tests/test_casegen_durability.py
git commit -m "feat(cases): фильтр долговечности (инцидент vs знание)"
```

---

### Task 6: Дедуп (по центроидам)

**Files:**
- Create: `casegen/filters/dedup.py`
- Test: `tools/tests/test_casegen_dedup.py`

**Interfaces:**
- Consumes: `Case` (с `centroid`).
- Produces: `casegen.filters.dedup.dedupe(cases, threshold=0.92) -> list[Case]` — сливает near-duplicate по косинусу центроидов; из группы дублей — с бОльшим `cluster_size`.

- [ ] **Step 1: Написать падающие тесты**

Create `tools/tests/test_casegen_dedup.py`:

```python
import numpy as np

from casegen.filters.dedup import dedupe
from casegen.generate import Case


def _case(title, vec, size):
    v = np.asarray(vec, dtype=np.float32)
    v = v / np.linalg.norm(v)
    return Case(title=title, problem="p", symptoms="", typical_answer="", cluster_size=size, centroid=v)


def test_dedupe_merges_near_duplicates_keeps_largest():
    a = _case("замедление A", [1.0, 0.0, 0.01], size=10)
    b = _case("замедление B", [0.999, 0.001, 0.0], size=30)
    c = _case("лицензии", [0.0, 1.0, 0.0], size=5)
    out = dedupe([a, b, c], threshold=0.92)
    titles = {x.title for x in out}
    assert titles == {"замедление B", "лицензии"}


def test_dedupe_keeps_distinct():
    a = _case("x", [1.0, 0.0], size=3)
    b = _case("y", [0.0, 1.0], size=3)
    assert len(dedupe([a, b], threshold=0.92)) == 2
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run (из `tools/`): `python -m pytest tests/test_casegen_dedup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'casegen.filters.dedup'`.

- [ ] **Step 3: Реализовать dedup.py**

Create `casegen/filters/dedup.py`:

```python
"""Дедуп кейсов по близости центроидов: из группы дублей — самый крупный."""
from __future__ import annotations

from casegen.generate import Case


def dedupe(cases: list[Case], threshold: float = 0.92) -> list[Case]:
    order = sorted(range(len(cases)), key=lambda i: cases[i].cluster_size, reverse=True)
    kept: list[Case] = []
    for i in order:
        c = cases[i]
        if c.centroid is None:
            kept.append(c)
            continue
        dup = False
        for k in kept:
            if k.centroid is not None and float(k.centroid @ c.centroid) >= threshold:
                dup = True
                break
        if not dup:
            kept.append(c)
    return kept
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run (из `tools/`): `python -m pytest tests/test_casegen_dedup.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add casegen/filters/dedup.py tests/test_casegen_dedup.py
git commit -m "feat(cases): дедуп кейсов по центроидам"
```

---

### Task 7: PII-скраб

**Files:**
- Create: `casegen/filters/pii.py`
- Test: `tools/tests/test_casegen_pii.py`

**Interfaces:**
- Consumes: `Case`.
- Produces: `casegen.filters.pii.scrub(case) -> None` — regex-проход по текстовым полям, PII → плейсхолдеры (без LLM).

- [ ] **Step 1: Написать падающие тесты**

Create `tools/tests/test_casegen_pii.py`:

```python
from casegen.filters.pii import scrub
from casegen.generate import Case


def test_scrub_phone_tenant_ticket_email():
    c = Case(
        title="Проблема у тенанта 12345",
        problem="Клиент +7 916 123-45-67 по заявке №778899 писал на a.b@mail.ru",
        symptoms="тенант 42",
        typical_answer="ok",
        keywords=["tenant 42"],
    )
    scrub(c)
    blob = " ".join([c.title, c.problem, c.symptoms, c.typical_answer] + c.keywords)
    assert "12345" not in blob
    assert "916" not in blob
    assert "778899" not in blob
    assert "a.b@mail.ru" not in blob
    assert "[тенант]" in c.title
    assert "[телефон]" in c.problem
    assert "[заявка]" in c.problem
    assert "[email]" in c.problem


def test_scrub_keeps_normal_text():
    c = Case(title="Планировщик не создаёт заявки", problem="настройка вида работ",
             symptoms="", typical_answer="перезапустить планировщик")
    scrub(c)
    assert c.title == "Планировщик не создаёт заявки"
    assert c.typical_answer == "перезапустить планировщик"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run (из `tools/`): `python -m pytest tests/test_casegen_pii.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'casegen.filters.pii'`.

- [ ] **Step 3: Реализовать pii.py**

Create `casegen/filters/pii.py`:

```python
"""Обезличивание кейса: телефоны, email, ID тенанта, номера заявок → плейсхолдеры.

Детерминированный regex-проход. При авто-публикации ревью нет, поэтому скраб —
обязательный шаг перед рендером. Общие числа не трогаем, чтобы не портить текст."""
from __future__ import annotations

import re

from casegen.generate import Case

_PHONE = re.compile(r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
_EMAIL = re.compile(r"[\w.\-]+@[\w.\-]+\.\w+")
_TICKET = re.compile(r"№\s?\d+")
_TENANT = re.compile(r"тенант[ае]?\s+\d+", re.IGNORECASE)

_FIELDS = ("title", "problem", "symptoms", "typical_answer")


def scrub(case: Case) -> None:
    for name in _FIELDS:
        setattr(case, name, _scrub_text(getattr(case, name)))
    case.keywords = [_scrub_text(k) for k in case.keywords]


def _scrub_text(text: str) -> str:
    text = _EMAIL.sub("[email]", text)
    text = _PHONE.sub("[телефон]", text)
    text = _TICKET.sub("[заявка]", text)
    text = _TENANT.sub("[тенант]", text)
    return text
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run (из `tools/`): `python -m pytest tests/test_casegen_pii.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add casegen/filters/pii.py tests/test_casegen_pii.py
git commit -m "feat(cases): PII-скраб (телефон/email/тенант/заявка)"
```

---

### Task 8: Идентичность кейсов + стейт опубликованных

**Files:**
- Create: `casegen/state.py`
- Create: `casegen/identity.py`
- Test: `tools/tests/test_casegen_identity.py`

**Interfaces:**
- Consumes: `Case` (с `centroid`).
- Produces:
  - `casegen.state.PublishedCase(id, slug, title, centroid: list[float])`; `load_state(path) -> list[PublishedCase]`; `save_state(path, cases) -> None`.
  - `casegen.identity.slugify(title: str) -> str`.
  - `casegen.identity.assign_identity(cases, published, threshold=0.9) -> list[PublishedCase]` — проставляет `case.slug`; совпал → тот же slug, иначе новый; возвращает обновлённый стейт.

- [ ] **Step 1: Написать падающие тесты**

Create `tools/tests/test_casegen_identity.py`:

```python
import numpy as np

from casegen.generate import Case
from casegen.identity import assign_identity, slugify
from casegen.state import PublishedCase, load_state, save_state


def _case(title, vec):
    v = np.asarray(vec, dtype=np.float32)
    v = v / np.linalg.norm(v)
    return Case(title=title, problem="p", symptoms="", typical_answer="", centroid=v)


def test_slugify_transliterates_and_dedups_dashes():
    assert slugify("Планировщик не создаёт заявки!") == "planirovshchik-ne-sozdaet-zayavki"


def test_assign_reuses_slug_for_matching_published():
    pub = [PublishedCase(id="c1", slug="planirovshchik", title="Планировщик", centroid=[1.0, 0.0])]
    c = _case("Планировщик молчит", [0.999, 0.001])
    updated = assign_identity([c], pub, threshold=0.9)
    assert c.slug == "planirovshchik"
    assert len(updated) == 1


def test_assign_new_slug_for_novel_case():
    c = _case("Лицензии в тенанте", [0.0, 1.0])
    updated = assign_identity([c], [], threshold=0.9)
    assert c.slug == "litsenzii-v-tenante"
    assert len(updated) == 1


def test_state_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    save_state(p, [PublishedCase(id="c1", slug="s", title="t", centroid=[0.1, 0.2])])
    loaded = load_state(p)
    assert loaded[0].slug == "s" and loaded[0].centroid == [0.1, 0.2]


def test_load_state_missing_returns_empty(tmp_path):
    assert load_state(tmp_path / "nope.json") == []
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run (из `tools/`): `python -m pytest tests/test_casegen_identity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'casegen.state'`.

- [ ] **Step 3: Реализовать state.py**

Create `casegen/state.py`:

```python
"""Стейт опубликованных кейсов (стабильность идентичности между прогонами).

Живёт на стороне пайплайна (не в вике). JSON: id, slug, title, центроид."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class PublishedCase:
    id: str
    slug: str
    title: str
    centroid: list[float]


def load_state(path: Path) -> list[PublishedCase]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [PublishedCase(**d) for d in data]


def save_state(path: Path, cases: list[PublishedCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(c) for c in cases], ensure_ascii=False, indent=2),
                    encoding="utf-8")
```

- [ ] **Step 4: Реализовать identity.py**

Create `casegen/identity.py`:

```python
"""Сопоставление новых кейсов с опубликованными: тот же кейс = тот же slug/файл.

Лёгкая замена полного stateful: стабильность файлов между батч-ребилдами без пула/lifecycle."""
from __future__ import annotations

import re

import numpy as np

from casegen.generate import Case
from casegen.state import PublishedCase

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", " ": "-",
}


def slugify(title: str) -> str:
    s = "".join(_TRANSLIT.get(ch, ch) for ch in title.lower())
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "case"


def assign_identity(cases: list[Case], published: list[PublishedCase],
                    threshold: float = 0.9) -> list[PublishedCase]:
    pub_cent = {p.slug: np.asarray(p.centroid, dtype=np.float32) for p in published}
    result: dict[str, PublishedCase] = {}
    used_slugs: set[str] = set()
    for c in cases:
        matched = None
        if c.centroid is not None:
            best, best_sim = None, threshold
            for p in published:
                pc = pub_cent[p.slug]
                if pc.shape != c.centroid.shape:
                    continue
                sim = float(pc @ c.centroid)
                if sim >= best_sim:
                    best, best_sim = p, sim
            matched = best
        if matched is not None:
            c.slug = matched.slug
        else:
            c.slug = _unique(slugify(c.title), used_slugs)
        used_slugs.add(c.slug)
        result[c.slug] = PublishedCase(
            id=matched.id if matched else c.slug,
            slug=c.slug, title=c.title,
            centroid=[float(x) for x in c.centroid] if c.centroid is not None else [],
        )
    return list(result.values())


def _unique(slug: str, used: set[str]) -> str:
    if slug not in used:
        return slug
    i = 2
    while f"{slug}-{i}" in used:
        i += 1
    return f"{slug}-{i}"
```

- [ ] **Step 5: Запустить тесты — убедиться, что проходят**

Run (из `tools/`): `python -m pytest tests/test_casegen_identity.py -v`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add casegen/state.py casegen/identity.py tests/test_casegen_identity.py
git commit -m "feat(cases): идентичность кейсов + стейт опубликованных"
```

---

### Task 9: Рендер кейсов и cases-index.md

**Files:**
- Create: `casegen/render.py`
- Test: `tools/tests/test_casegen_render.py`

**Interfaces:**
- Consumes: `Case` (со `slug`, после фильтров).
- Produces:
  - `casegen.render.case_markdown(case) -> str`.
  - `casegen.render.index_markdown(cases) -> str`.
  - `casegen.render.write_cases(cases, cases_dir, index_path) -> None` — пишет `cases/<slug>.md` + `cases-index.md`; чистит старые `*.md` (батч-ребилд перегенерирует набор целиком); детерминированно (сортировка по slug).

- [ ] **Step 1: Написать падающие тесты**

Create `tools/tests/test_casegen_render.py`:

```python
from casegen.generate import Case
from casegen.render import case_markdown, index_markdown, write_cases


def _case(slug, title):
    return Case(title=title, problem="проблема", symptoms="симптомы", typical_answer="ответ",
                keywords=["k1", "k2"], source_ids=["1", "2"], cluster_size=7, cohesion=0.77,
                novelty="новое", slug=slug)


def test_case_markdown_has_sections():
    md = case_markdown(_case("planirovshchik", "Планировщик"))
    assert md.startswith("# Планировщик")
    assert "**Проблема.**" in md
    assert "**Решение / типовой ответ поддержки.**" in md
    assert "k1, k2" in md


def test_index_markdown_lists_cases_sorted():
    cases = [_case("b-case", "Б"), _case("a-case", "А")]
    idx = index_markdown(cases)
    assert idx.index("a-case") < idx.index("b-case")
    assert "cases/a-case.md" in idx


def test_write_cases_creates_and_cleans(tmp_path):
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    (cases_dir / "stale.md").write_text("old", encoding="utf-8")
    index = tmp_path / "cases-index.md"
    write_cases([_case("planirovshchik", "Планировщик")], cases_dir, index)
    assert (cases_dir / "planirovshchik.md").exists()
    assert not (cases_dir / "stale.md").exists()  # старое вычищено
    assert "Планировщик" in index.read_text(encoding="utf-8")
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run (из `tools/`): `python -m pytest tests/test_casegen_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'casegen.render'`.

- [ ] **Step 3: Реализовать render.py**

Create `casegen/render.py`:

```python
"""Рендер кейсов в markdown + сборка cases-index.md."""
from __future__ import annotations

from pathlib import Path

from casegen.generate import Case


def case_markdown(case: Case) -> str:
    return (
        f"# {case.title}\n\n"
        f"**Проблема.** {case.problem}\n\n"
        f"**Симптомы.** {case.symptoms}\n\n"
        f"**Решение / типовой ответ поддержки.** {case.typical_answer}\n\n"
        f"**Ключевые слова:** {', '.join(case.keywords)}\n\n"
        f"<!-- meta: source_ids={','.join(case.source_ids)} "
        f"cluster_size={case.cluster_size} cohesion={case.cohesion:.2f} novelty={case.novelty} -->\n"
    )


def index_markdown(cases: list[Case]) -> str:
    ordered = sorted(cases, key=lambda c: c.slug)
    lines = [
        "# Кейсы поддержки HubEx",
        "",
        "> **Что здесь:** обобщённые случаи из обращений в поддержку, которых нет в основной вике.",
        "> **Когда сюда идти:** проблема/траблшутинг, не описанный в `index.md`.",
        "> **Источник:** переписки Omnidesk, обобщены автоматически. Канон — по-прежнему `index.md`.",
        "",
    ]
    for c in ordered:
        lines.append(f"- [{c.title}](cases/{c.slug}.md) — {c.problem[:120]}")
    lines.append("")
    return "\n".join(lines)


def write_cases(cases: list[Case], cases_dir: Path, index_path: Path) -> None:
    cases_dir.mkdir(parents=True, exist_ok=True)
    for old in cases_dir.glob("*.md"):
        old.unlink()
    for c in sorted(cases, key=lambda c: c.slug):
        (cases_dir / f"{c.slug}.md").write_text(case_markdown(c), encoding="utf-8")
    index_path.write_text(index_markdown(cases), encoding="utf-8")
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run (из `tools/`): `python -m pytest tests/test_casegen_render.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add casegen/render.py tests/test_casegen_render.py
git commit -m "feat(cases): рендер кейсов + cases-index.md"
```

---

### Task 10: Конвейер, сабкоманда CLI, dry-run, e2e

**Files:**
- Create: `casegen/pipeline.py`
- Modify: `tools/wiki_cli.py` (добавить сабкоманду `cases`)
- Test: `tools/tests/test_casegen_e2e.py`

**Interfaces:**
- Consumes: всё выше.
- Produces:
  - `casegen.pipeline.build_cases(records, matrix, wiki_bm25, published, chat_fn=llm.chat) -> tuple[list[Case], list[PublishedCase], dict]` — чистая функция всего конвейера: cluster → subcluster → generate → novelty → durability → отсечь (`покрыто` и `durable=False`) → dedupe → scrub → identity. Возвращает (кейсы, стейт, статистика `{groups, generated, published}`).
  - `casegen.pipeline.run_cases(dry_run: bool) -> dict` — читает корпус/стейт/вику, зовёт `build_cases`, при `dry_run` не пишет; иначе `write_cases` + `save_state`. Пути: корпус `REPO_ROOT/corpus/corpus.csv`, стейт `REPO_ROOT/state/published.json`.
  - `wiki_cli` — новая сабкоманда `cases [--dry-run]`.

- [ ] **Step 1: Написать падающий e2e-тест**

Create `tools/tests/test_casegen_e2e.py`:

```python
from pathlib import Path

from casegen.corpus import load_corpus
from casegen.filters.bm25 import BM25, Doc, tokenize
from casegen.pipeline import build_cases

FIXT = Path(__file__).parent / "fixtures" / "corpus_sample.csv"


def _wiki_bm25():
    return BM25([Doc("pages/user/Objects.md", "Учёт объектов и оборудования",
                     tokenize("Учёт объектов и оборудования"))])


def test_e2e_produces_durable_novel_cases():
    records, matrix = load_corpus(FIXT)

    def fake_chat(messages, **kw):
        system = messages[0]["content"]
        user = messages[-1]["content"]
        if "долговечное знание" in system:
            return '{"durable":true,"reason":"знание"}'
        if "покрыт ли" in user.lower() or "verdict" in user:
            return '{"verdict":"новое","reason":"нет в вике"}'
        first = user.split("[0]")[1][:40]
        return f'[{{"title":"Кейс {first}","problem":"p","symptoms":"s",' \
               f'"typical_answer":"a","keywords":["k"],"ticket_numbers":[0]}}]'

    cases, state, stats = build_cases(records, matrix, _wiki_bm25(), published=[], chat_fn=fake_chat)
    assert len(cases) >= 2
    assert all(c.slug for c in cases)
    assert all(c.novelty == "новое" for c in cases)
    assert len(state) == len(cases)
    assert stats["published"] == len(cases)
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run (из `tools/`): `python -m pytest tests/test_casegen_e2e.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'casegen.pipeline'`.

- [ ] **Step 3: Реализовать pipeline.py**

Create `casegen/pipeline.py`:

```python
"""Оркестратор конвейера кейсов: корпус → кластеры → кейсы → фильтры → cases/."""
from __future__ import annotations

import numpy as np

from casegen import config, llm
from casegen.cluster import cluster, subcluster
from casegen.corpus import load_corpus
from casegen.filters import dedup, durability
from casegen.filters.bm25 import BM25, load_wiki
from casegen.filters.novelty import assess
from casegen.filters.pii import scrub
from casegen.generate import Case, generate_cases
from casegen.identity import assign_identity
from casegen.render import write_cases
from casegen.state import PublishedCase, load_state, save_state

STATE_PATH = config.REPO_ROOT / "state" / "published.json"
CORPUS_CSV = config.REPO_ROOT / "corpus" / "corpus.csv"


def build_cases(records, matrix: np.ndarray, wiki_bm25: BM25,
                published: list[PublishedCase], chat_fn=llm.chat):
    groups = subcluster(cluster(matrix), matrix)
    raw_cases: list[Case] = []
    for g in groups:
        raw_cases.extend(generate_cases(g, records, matrix, chat_fn=chat_fn))

    kept: list[Case] = []
    for c in raw_cases:
        assess(c, wiki_bm25, chat_fn=chat_fn)
        if c.novelty == "покрыто":
            continue
        durability.classify(c, chat_fn=chat_fn)
        if not c.durable:
            continue
        kept.append(c)

    kept = dedup.dedupe(kept)
    for c in kept:
        scrub(c)
    state = assign_identity(kept, published)
    stats = {"groups": len(groups), "generated": len(raw_cases), "published": len(kept)}
    return kept, state, stats


def run_cases(dry_run: bool) -> dict:
    config.require_openrouter()
    records, matrix = load_corpus(CORPUS_CSV)
    wiki_bm25 = load_wiki(config.PAGES_DIR)
    published = load_state(STATE_PATH)
    cases, state, stats = build_cases(records, matrix, wiki_bm25, published)
    if not dry_run:
        write_cases(cases, config.CASES_DIR, config.CASES_INDEX)
        save_state(STATE_PATH, state)
    stats["dry_run"] = dry_run
    stats["titles"] = [c.title for c in cases]
    return stats
```

- [ ] **Step 4: Добавить сабкоманду `cases` в wiki_cli.py**

Modify `tools/wiki_cli.py`:

В блоке `build_parser`, после определения парсера `ex` (export-llms), добавить:

```python
    ca = sub.add_parser("cases",
                        help="сгенерировать кейсы поддержки из корпуса → cases/ + cases-index.md")
    ca.add_argument("--dry-run", action="store_true",
                    help="прогнать конвейер и напечатать кейсы, ничего не записывая")
```

В функции `main`, перед финальным `return 2`, добавить ветку:

```python
    if args.command == "cases":
        from casegen import pipeline
        stats = pipeline.run_cases(dry_run=args.dry_run)
        print(f"[cases] группы={stats['groups']} сгенерировано={stats['generated']} "
              f"к публикации={stats['published']}"
              + (" (dry-run)" if stats["dry_run"] else ""))
        for t in stats["titles"]:
            print(f"  - {t}")
        return 0
```

- [ ] **Step 5: Запустить весь набор тестов пайплайна — убедиться, что всё зелёное**

Run (из `tools/`): `python -m pytest tests/test_casegen_e2e.py -v` затем `python -m pytest -m "not live" -q`
Expected: e2e PASS; полный прогон — существующие тесты репо + все `test_casegen_*` зелёные (регрессий нет).

- [ ] **Step 6: Commit**

```bash
git add casegen/pipeline.py wiki_cli.py tests/test_casegen_e2e.py
git commit -m "feat(cases): конвейер + сабкоманда wiki_cli cases + dry-run + e2e"
```

---

## Дальнейшие планы (вне Плана A)

- **План B — ingest из Omnidesk:** живая инкрементальная выгрузка (watermark) → чистка HTML/бан-слов → LLM-саммари + эмбеддинг с дисковым кэшем → наполняет `corpus/corpus.csv`. Здесь резолвится эмбеддинг-модель (§11 спека).
- **План C — интеграция с Совой:** расширить `build_kb` в `HubEx Сова 2.0` третьим источником (`cases/` → `knowledge/cases/` + секция в `llms.txt`).
- **Публикация и навигация:** обёртка вокруг `run_cases` — коммит `cases/` в HubEx.Wiki + пер-прогонный отчёт; разовая правка `CLAUDE.md`/`index.md` с третьей веткой маршрутизации на `cases-index.md`.

## Self-Review

- **Покрытие спека:** §3 стадии 3–6 → Tasks 2,3,9,10; §5 фильтры (новизна/долговечность/дедуп/PII) → Tasks 4,5,6,7; §6 идентичность → Task 8; §4 «коммитим только cases/», кэш вне репо → gitignore (Task 1) + пути `REPO_ROOT/corpus|state` (Task 10). Стадии §3.1–3.2 (ingest, summarize+embed) — **намеренно вне Плана A** (План B), корпус берётся готовым. §8 (Сова) и §7 инкрементальность живого ingest — План B/C.
- **Плейсхолдеров нет:** каждый шаг содержит полный код и точную команду с ожидаемым результатом.
- **Согласованность типов:** `Case`, `Cluster`, `Record`, `PublishedCase`, `BM25/Doc`, `chat_fn`, `assign_identity`, `build_cases`, `run_cases` — имена и сигнатуры едины между задачами.
