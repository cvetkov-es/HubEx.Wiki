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
