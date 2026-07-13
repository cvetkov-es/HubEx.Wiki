from update import diff


def test_status_new():
    assert diff.page_status(None, "x") == "new"


def test_status_unchanged():
    assert diff.page_status("x\n", "x\n") == "unchanged"


def test_status_changed():
    assert diff.page_status("a\n", "b\n") == "changed"


def test_body_diff_shows_delta():
    d = diff.body_diff("line1\nold\n", "line1\nnew\n")
    assert "-old" in d and "+new" in d
