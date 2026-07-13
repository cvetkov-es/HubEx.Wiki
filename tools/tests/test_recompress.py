import pytest

from update import recompress


def _root(tmp_path):
    (tmp_path / "pages" / "admin").mkdir(parents=True)
    (tmp_path / "pages" / "admin" / "BusinessProcess.md").write_text("x", encoding="utf-8")
    (tmp_path / "index.md").write_text(
        "# Индекс\n\n## Заявки\n\n- [Old](pages/admin/BusinessProcess.md) — старьё.\n",
        encoding="utf-8")
    return tmp_path


def test_changed_replaces_line(tmp_path):
    root = _root(tmp_path)
    model = lambda p: "- [Бизнес-процесс](pages/admin/BusinessProcess.md) — ЖЦ заявки на ремонт."
    res = recompress.update_annotation(
        "admin/BusinessProcess", "тело\n", "changed", model=model, root=root)
    assert res["status"] == "ok" and res["problems"] == []
    index = (root / "index.md").read_text(encoding="utf-8")
    assert "ЖЦ заявки на ремонт" in index and "старьё" not in index


def test_new_with_existing_line_skips_model(tmp_path):
    root = _root(tmp_path)

    def boom(p):
        raise AssertionError("модель не должна вызываться")

    res = recompress.update_annotation(
        "admin/BusinessProcess", "тело\n", "new", model=boom, root=root)
    assert res["status"] == "skipped"
    assert "старьё" in (root / "index.md").read_text(encoding="utf-8")


def test_new_without_line_appended_to_new_section(tmp_path):
    root = _root(tmp_path)
    (root / "pages" / "user").mkdir(parents=True)
    (root / "pages" / "user" / "NewPage.md").write_text("x", encoding="utf-8")
    model = lambda p: "- [Новая](pages/user/NewPage.md) — про новое."
    res = recompress.update_annotation(
        "user/NewPage", "тело\n", "new", model=model, root=root)
    assert res["status"] == "ok"
    index = (root / "index.md").read_text(encoding="utf-8")
    assert "Новые страницы (разложить по темам)" in index and "про новое" in index


def test_releasenotes_use_own_index(tmp_path):
    root = _root(tmp_path)
    (root / "pages" / "ReleaseNotes").mkdir(parents=True)
    (root / "pages" / "ReleaseNotes" / "v2_50_0.md").write_text("x", encoding="utf-8")
    model = lambda p: "- [v2.50](pages/ReleaseNotes/v2_50_0.md) — что нового."
    recompress.update_annotation(
        "ReleaseNotes/v2_50_0", "тело\n", "new", model=model, root=root)
    assert "что нового" in (root / "releasenotes-index.md").read_text(encoding="utf-8")
    assert "что нового" not in (root / "index.md").read_text(encoding="utf-8")


def test_model_failure_leaves_index_untouched(tmp_path):
    root = _root(tmp_path)
    before = (root / "index.md").read_text(encoding="utf-8")

    def boom(p):
        raise RuntimeError("claude упал")

    res = recompress.update_annotation(
        "admin/BusinessProcess", "тело\n", "changed", model=boom, root=root)
    assert res["status"] == "error" and "claude упал" in res["error"]
    assert (root / "index.md").read_text(encoding="utf-8") == before


def test_guard_problems_reported_but_spliced(tmp_path):
    root = _root(tmp_path)
    model = lambda p: "- [X](pages/admin/Ghost.md) — не та ссылка."
    res = recompress.update_annotation(
        "admin/BusinessProcess", "тело\n", "changed", model=model, root=root)
    assert any("битая ссылка: pages/admin/Ghost.md" in p for p in res["problems"])
    assert any("не совпадает с целью" in p for p in res["problems"])
    # строка всё равно вклеена — человек увидит её в git diff вместе с предупреждением
    assert "не та ссылка" in (root / "index.md").read_text(encoding="utf-8")


def test_render_summary():
    results = [
        {"page": "admin/A", "recompress": {"page": "admin/A", "status": "ok",
                                           "problems": [], "error": None}},
        {"page": "admin/B", "recompress": {"page": "admin/B", "status": "skipped",
                                           "problems": [], "error": None}},
        {"page": "admin/C", "recompress": {"page": "admin/C", "status": "ok",
                                           "problems": ["битая ссылка: x"], "error": None}},
        {"page": "admin/D", "recompress": {"page": "admin/D", "status": "error",
                                           "problems": [], "error": "упало"}},
        {"page": "admin/E"},
    ]
    text = recompress.render_summary(results)
    assert "admin/A" in text and "guard чист" in text
    assert "admin/B" in text and "модель не вызывалась" in text
    assert "битая ссылка: x" in text and "упало" in text
