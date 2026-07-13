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
