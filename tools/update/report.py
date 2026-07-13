"""Рендер результатов update в markdown-отчёт. Чистый модуль."""


def render(results: list) -> str:
    changed = [r for r in results if r["status"] in ("new", "changed")]
    removed = [r for r in results if r["status"] == "removed"]
    errors = [r for r in results if r["status"] == "error"]
    unchanged = [r for r in results if r["status"] == "unchanged"]

    out = ["# Отчёт update"]
    for r in changed:
        out.append("")
        mark = "🆕" if r["status"] == "new" else "✏️"
        out.append(f"## {mark} {r['page']} — {r['status']}")
        out.append(f"→ проверь `pages/{r['page']}.md` и строку индекса")
        if r.get("diff"):
            out.append("```diff")
            out.append(r["diff"])
            out.append("```")
    for r in removed:
        out.append("")
        out.append(f"## ❌ {r['page']} — пропала на вики "
                   "(удалить копию и строку индекса вручную)")
    for r in errors:
        out.append("")
        out.append(f"## {r['page']} — не удалось забрать: {r['error']}")

    out.append("")
    out.append(f"Итого: изменилось {len(changed)}, удалено {len(removed)}, "
               f"ошибок {len(errors)}, без изменений {len(unchanged)}.")
    if not changed and not removed and not errors:
        out.append("Изменений нет.")
    return "\n".join(out) + "\n"
