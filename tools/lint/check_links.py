"""Проверка относительных markdown-ссылок в репозитории. Выход 1, если есть битые."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)]*)?\)")
FENCE_RE = re.compile(r"^\s*`{3,}")
SKIP_PARTS = {".git", ".superpowers", "drafts"}


def strip_code_fences(text: str) -> str:
    """Убирает fenced code blocks — примеры в доках содержат ссылки будущих/чужих файлов."""
    out_lines, in_fence = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out_lines.append(line)
    return "\n".join(out_lines)


def main() -> int:
    broken = []
    for md in ROOT.rglob("*.md"):
        if SKIP_PARTS & set(md.parts):
            continue
        text = strip_code_fences(md.read_text(encoding="utf-8"))
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (md.parent / target).resolve().exists():
                broken.append(f"{md.relative_to(ROOT)} -> {target}")
    for b in broken:
        print(f"БИТАЯ ССЫЛКА: {b}")
    print(f"Проверено файлов: {len(list(ROOT.rglob('*.md')))}, битых ссылок: {len(broken)}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
