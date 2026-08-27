# Вход для Claude Code

Это автономная копия вики HubEx для ИИ-агентов. **Перед задачей прочитай [README.md](README.md).**

Критичное, дублируется намеренно:
- Вопрос о продукте → [index.md](index.md) (релиз-ноуты → [releasenotes-index.md](releasenotes-index.md)) → страница в `pages/`.
- `pages/**` руками не правь — их ведёт пайплайн (`python3 tools/wiki_cli.py update --recompress`).
- `context/body.md` и `hubex-context.md` руками не правь — их ведёт пайплайн (`python3 tools/wiki_cli.py compact --rebuild`).
- Ночью в 00:00 МСК крон гонит `wiki_cli.py sync`: перезабор, пересборка `hubex-context.md` и автопуш в `main`. Незакоммиченные правки в дереве прогон отменяют — не оставляй их на ночь.
- `tools/` — git-сабмодуль (пайплайн в отдельном репо `HubEx.Wiki.Pipeline`); перед запуском `update` выкачай его: `git submodule update --init`.
- Не выдумывай факты о продукте: нет в страницах — так и скажи.
