"""Детерминированные fail-safe проверки модельной аннотации. Чистый модуль."""
import re

_LINK_RE = re.compile(r"\]\(([^)]+)\)")
MAX_LEN = 300


def problems(annotation: str, root) -> list:
    """Список проблем аннотации: битые относительные ссылки + превышение лимита длины."""
    out = []
    for target in _LINK_RE.findall(annotation):
        rel = target.split("#", 1)[0].strip()
        if not rel or rel.startswith(("http://", "https://")):
            continue
        if not (root / rel).exists():
            out.append(f"битая ссылка: {rel}")
    if len(annotation) > MAX_LEN:
        out.append(f"длина {len(annotation)} > {MAX_LEN}")
    return sorted(set(out))
