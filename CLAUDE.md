# Вход для Claude Code

Это автономная копия вики HubEx для ИИ-агентов. **Перед задачей прочитай [README.md](README.md).**

Критичное, дублируется намеренно:
- Вопрос о продукте → [index.md](index.md) (релиз-ноуты → [releasenotes-index.md](releasenotes-index.md)) → страница в `pages/`.
- `pages/**` руками не правь — их ведёт пайплайн (`python3 tools/wiki_cli.py update --recompress`).
- `tools/` — git-сабмодуль (пайплайн в отдельном репо `HubEx.Wiki.Pipeline`); перед запуском `update` выкачай его: `git submodule update --init`.
- Не выдумывай факты о продукте: нет в страницах — так и скажи.
