from update import guard


def test_phantom_link_flagged(tmp_path):
    (tmp_path / "pages" / "admin").mkdir(parents=True)
    (tmp_path / "pages" / "admin" / "Real.md").write_text("x", encoding="utf-8")
    ann = "- [Real](pages/admin/Real.md) — ок. Ещё [Ghost](pages/admin/Ghost.md)."
    probs = guard.problems(ann, tmp_path)
    assert probs == ["битая ссылка: pages/admin/Ghost.md"]


def test_external_link_and_anchor_ignored(tmp_path):
    (tmp_path / "pages" / "user").mkdir(parents=True)
    (tmp_path / "pages" / "user" / "P.md").write_text("x", encoding="utf-8")
    ann = "- [P](pages/user/P.md#якорь) — с якорем и [внешней](https://wiki.hubex.ru/x.html)."
    assert guard.problems(ann, tmp_path) == []


def test_too_long_flagged(tmp_path):
    ann = "- [X](pages/user/P.md) — " + "оченьдлинно " * 40
    (tmp_path / "pages" / "user").mkdir(parents=True)
    (tmp_path / "pages" / "user" / "P.md").write_text("x", encoding="utf-8")
    probs = guard.problems(ann, tmp_path)
    assert len(probs) == 1 and probs[0].startswith("длина")


def test_clean_annotation(tmp_path):
    (tmp_path / "pages" / "user").mkdir(parents=True)
    (tmp_path / "pages" / "user" / "P.md").write_text("x", encoding="utf-8")
    assert guard.problems("- [P](pages/user/P.md) — чистая.", tmp_path) == []
