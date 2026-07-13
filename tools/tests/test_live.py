import pytest

from update import fetch, manifest

pytestmark = pytest.mark.live


def test_sitemap_has_tracked_pages():
    entries = dict(manifest.fetch_manifest())
    assert "admin/BusinessProcess" in entries
    sections = {pid.split("/", 1)[0] for pid in entries}
    assert sections == {"admin", "user", "ReleaseNotes"}


def test_fetch_and_convert_business_process():
    entries = manifest.fetch_manifest()
    known = frozenset(pid for pid, _ in entries)
    url = dict(entries)["admin/BusinessProcess"]
    md = fetch.convert_page(fetch.fetch_html(url),
                            page_id="admin/BusinessProcess", url=url, known_pages=known)
    assert md.strip()
    assert 'section: "admin"' in md
    assert "crawled_at" not in md
    # картинка — абсолютная ссылка на вики
    assert "![" in md and "https://wiki.hubex.ru/attachments/" in md
    # тело статьи на месте
    assert "стади" in md.lower()
