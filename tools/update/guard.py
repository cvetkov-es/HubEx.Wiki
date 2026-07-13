"""Детерминированные fail-safe проверки модельной аннотации. Чистый модуль."""
import re

_LINK_RE = re.compile(r"\]\(([^)]+)\)")
_FORMAT_RE = re.compile(r"^- \[[^\]]+\]\([^)]+\) — .+$")
MAX_LEN = 300


def problems(annotation: str, root, *, expected_target: str | None = None) -> list:
    """Список проблем аннотации: формат строки, битые/лишние ссылки, превышение лимита длины."""
    out = []
    if not _FORMAT_RE.match(annotation):
        out.append("формат: не строка-аннотация вида '- [Имя](ссылка) — …'")
    internal = []
    for target in _LINK_RE.findall(annotation):
        rel = target.split("#", 1)[0].strip()
        if not rel or rel.startswith(("http://", "https://")):
            continue
        internal.append(rel)
        if not (root / rel).exists():
            out.append(f"битая ссылка: {rel}")
    if expected_target is not None:
        if len(internal) != 1:
            out.append(f"внутренних ссылок {len(internal)}, должна быть ровно 1")
        elif internal[0] != expected_target:
            out.append(f"ссылка {internal[0]} не совпадает с целью {expected_target}")
    if len(annotation) > MAX_LEN:
        out.append(f"длина {len(annotation)} > {MAX_LEN}")
    return sorted(set(out))
