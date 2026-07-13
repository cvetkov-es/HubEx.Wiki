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
