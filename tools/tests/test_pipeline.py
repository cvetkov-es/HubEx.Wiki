from update import pipeline


def _manifest():
    return [("admin/A", "https://wiki.hubex.ru/docs/FAQ/RU/admin/A.html"),
            ("user/B", "https://wiki.hubex.ru/docs/FAQ/RU/user/B.html")]


def _fetch(url):
    return "<html/>"  # convert_page замокан, html не важен


def _mock_convert(monkeypatch, text="md-{}"):
    monkeypatch.setattr(pipeline.fetch, "convert_page",
                        lambda html, *, page_id, url, known_pages=frozenset():
                        text.format(page_id) + "\n")


def _fake_rc(page_id, page_md, status, *, root=None):
    return {"page": page_id, "status": "ok", "problems": [], "error": None}


def test_report_only_writes_drafts_not_pages(tmp_path, monkeypatch):
    _mock_convert(monkeypatch)
    res = pipeline.run_update(manifest_fn=_manifest, fetch_html=_fetch, root=tmp_path)
    assert {r["page"]: r["status"] for r in res} == {"admin/A": "new", "user/B": "new"}
    assert not (tmp_path / "pages").exists()
    assert (pipeline.drafts_dir(tmp_path) / "admin" / "A.md").read_text(
        encoding="utf-8") == "md-admin/A\n"


def test_recompress_writes_pages_then_unchanged(tmp_path, monkeypatch):
    _mock_convert(monkeypatch)
    pipeline.run_update(manifest_fn=_manifest, fetch_html=_fetch, root=tmp_path,
                        recompress=True, recompress_impl=_fake_rc)
    assert (tmp_path / "pages" / "admin" / "A.md").exists()
    res = pipeline.run_update(manifest_fn=_manifest, fetch_html=_fetch, root=tmp_path)
    assert all(r["status"] == "unchanged" for r in res)


def test_changed_detected_with_diff(tmp_path, monkeypatch):
    _mock_convert(monkeypatch)
    pipeline.run_update(manifest_fn=_manifest, fetch_html=_fetch, root=tmp_path,
                        recompress=True, recompress_impl=_fake_rc)
    _mock_convert(monkeypatch, text="NEW-{}")
    res = {r["page"]: r for r in pipeline.run_update(
        manifest_fn=_manifest, fetch_html=_fetch, root=tmp_path)}
    assert res["admin/A"]["status"] == "changed" and "diff" in res["admin/A"]


def test_removed_flagged_only_on_full_run(tmp_path, monkeypatch):
    _mock_convert(monkeypatch)
    (tmp_path / "pages" / "user").mkdir(parents=True)
    (tmp_path / "pages" / "user" / "Gone.md").write_text("x", encoding="utf-8")
    full = pipeline.run_update(manifest_fn=_manifest, fetch_html=_fetch, root=tmp_path)
    assert any(r["page"] == "user/Gone" and r["status"] == "removed" for r in full)
    partial = pipeline.run_update(manifest_fn=_manifest, fetch_html=_fetch,
                                  root=tmp_path, pages=["admin/A"])
    assert not any(r["status"] == "removed" for r in partial)
    assert [r["page"] for r in partial if r["status"] != "removed"] == ["admin/A"]


def test_fetch_error_isolated(tmp_path, monkeypatch):
    _mock_convert(monkeypatch)

    def boom(url):
        if "admin/A" in url:
            raise RuntimeError("нет сети")
        return "<html/>"

    res = {r["page"]: r for r in pipeline.run_update(
        manifest_fn=_manifest, fetch_html=boom, root=tmp_path)}
    assert res["admin/A"]["status"] == "error" and "нет сети" in res["admin/A"]["error"]
    assert res["user/B"]["status"] == "new"


def test_recompress_receives_status(tmp_path, monkeypatch):
    _mock_convert(monkeypatch)
    calls = []

    def rc(page_id, page_md, status, *, root=None):
        calls.append((page_id, status))
        return {"page": page_id, "status": "ok", "problems": [], "error": None}

    res = pipeline.run_update(manifest_fn=lambda: [_manifest()[0]], fetch_html=_fetch,
                              root=tmp_path, recompress=True, recompress_impl=rc)
    assert calls == [("admin/A", "new")]
    assert res[0]["recompress"]["status"] == "ok"


def test_known_pages_passed_to_converter(tmp_path, monkeypatch):
    seen = {}

    def conv(html, *, page_id, url, known_pages=frozenset()):
        seen[page_id] = known_pages
        return "x\n"

    monkeypatch.setattr(pipeline.fetch, "convert_page", conv)
    pipeline.run_update(manifest_fn=_manifest, fetch_html=_fetch, root=tmp_path)
    assert seen["admin/A"] == frozenset({"admin/A", "user/B"})
