from pathlib import Path

import pytest

from update import fetch

HTML = (Path(__file__).parent / "fixtures" / "page.html").read_text(encoding="utf-8")
URL = "https://wiki.hubex.ru/docs/FAQ/RU/admin/BusinessProcess.html"
KNOWN = frozenset({"admin/BusinessProcess", "admin/TicketLifeCycle", "user/Filters"})


def _md():
    return fetch.convert_page(HTML, page_id="admin/BusinessProcess", url=URL, known_pages=KNOWN)


def test_frontmatter_fields():
    md = _md()
    assert md.startswith("---\n")
    assert 'section: "admin"' in md
    assert f'url: "{URL}"' in md
    assert "content_hash:" in md
    assert "crawled_at" not in md


def test_body_extracted_without_chrome():
    md = _md()
    assert "Базовый бизнес-процесс" in md
    assert "меню" not in md and "подвал" not in md


def test_image_absolutized_as_link():
    assert "![Стадии](https://wiki.hubex.ru/attachments/images/FAQ/ADMIN/BusinessProcess/BasicStages.jpg)" in _md()


def test_tracking_pixel_stripped():
    assert "mc.yandex.ru" not in _md()


def test_cross_link_same_section_localized():
    assert "](TicketLifeCycle.md)" in _md()


def test_cross_link_other_section_localized():
    assert "](../user/Filters.md)" in _md()


def test_non_curated_link_stays_absolute():
    assert "https://wiki.hubex.ru/docs/FAQ/RU/admin/PowersOld.html" in _md()


def test_local_href_paths():
    assert fetch.local_href("admin/A", "admin/B") == "B.md"
    assert fetch.local_href("admin/A", "user/C") == "../user/C.md"


def test_missing_content_container_raises():
    with pytest.raises(ValueError):
        fetch.convert_page("<html><body>нет</body></html>",
                           page_id="admin/X", url=URL)


def test_deterministic():
    assert _md() == _md()


def test_normalize_collapses_blanks_and_trailing_ws():
    assert fetch.normalize("a  \n\n\n\nb\n\n") == "a\n\nb\n"
