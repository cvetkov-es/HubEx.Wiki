import wiki_cli
from update import manifest


def test_update_prints_report(monkeypatch, capsys):
    monkeypatch.setattr(wiki_cli.pipeline, "run_update",
                        lambda **kw: [{"page": "admin/A", "status": "new", "error": None}])
    assert wiki_cli.main(["update"]) == 0
    assert "Отчёт update" in capsys.readouterr().out


def test_manifest_error_exit_2(monkeypatch, capsys):
    def boom(**kw):
        raise manifest.ManifestError("sitemap пуст")
    monkeypatch.setattr(wiki_cli.pipeline, "run_update", boom)
    assert wiki_cli.main(["update"]) == 2
    assert "sitemap пуст" in capsys.readouterr().err


def test_fetch_error_exit_1(monkeypatch):
    monkeypatch.setattr(wiki_cli.pipeline, "run_update",
                        lambda **kw: [{"page": "a/b", "status": "error", "error": "x"}])
    assert wiki_cli.main(["update"]) == 1


def test_guard_problem_exit_1(monkeypatch):
    monkeypatch.setattr(wiki_cli.pipeline, "run_update", lambda **kw: [
        {"page": "admin/A", "status": "changed", "error": None,
         "recompress": {"page": "admin/A", "status": "ok",
                        "problems": ["битая ссылка: x"], "error": None}}])
    assert wiki_cli.main(["update", "--recompress"]) == 1


def test_clean_recompress_exit_0_with_summary(monkeypatch, capsys):
    monkeypatch.setattr(wiki_cli.pipeline, "run_update", lambda **kw: [
        {"page": "admin/A", "status": "changed", "error": None,
         "recompress": {"page": "admin/A", "status": "ok", "problems": [], "error": None}}])
    assert wiki_cli.main(["update", "--recompress"]) == 0
    assert "Пересжатие" in capsys.readouterr().out


def test_report_file_written(monkeypatch, tmp_path):
    monkeypatch.setattr(wiki_cli.pipeline, "run_update",
                        lambda **kw: [{"page": "a/b", "status": "unchanged", "error": None}])
    out = tmp_path / "r.md"
    assert wiki_cli.main(["update", "--report-file", str(out)]) == 0
    assert "Изменений нет." in out.read_text(encoding="utf-8")


def test_flags_passed_to_pipeline(monkeypatch):
    seen = {}

    def spy(**kw):
        seen.update(kw)
        return []

    monkeypatch.setattr(wiki_cli.pipeline, "run_update", spy)
    wiki_cli.main(["update", "--page", "admin/A", "--page", "user/B",
                   "--recompress", "--jobs", "4"])
    assert seen["pages"] == ["admin/A", "user/B"]
    assert seen["recompress"] is True and seen["jobs"] == 4
