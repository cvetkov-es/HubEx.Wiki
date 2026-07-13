from update import report


def test_render_groups_and_totals():
    results = [
        {"page": "admin/A", "status": "changed", "error": None, "diff": "-a\n+b"},
        {"page": "user/B", "status": "new", "error": None},
        {"page": "admin/Gone", "status": "removed", "error": None},
        {"page": "user/Err", "status": "error", "error": "таймаут"},
        {"page": "admin/Same", "status": "unchanged", "error": None},
    ]
    text = report.render(results)
    assert "admin/A" in text and "user/B" in text
    assert "-a" in text  # дифф changed-страницы попадает в отчёт
    assert "admin/Gone" in text and "таймаут" in text
    assert "изменилось 2" in text and "удалено 1" in text and "ошибок 1" in text


def test_render_no_changes():
    text = report.render([{"page": "a/b", "status": "unchanged", "error": None}])
    assert "Изменений нет." in text
