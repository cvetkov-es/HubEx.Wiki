from pathlib import Path
from unittest.mock import MagicMock

import pytest

from update import manifest

FIXTURE = (Path(__file__).parent / "fixtures" / "sitemap.xml").read_text(encoding="utf-8")


def test_parse_keeps_tracked_sections():
    entries = dict(manifest.parse_manifest(FIXTURE))
    assert entries["admin/BusinessProcess"] == \
        "https://wiki.hubex.ru/docs/FAQ/RU/admin/BusinessProcess.html"
    assert "user/CreatingTicket" in entries
    assert "ReleaseNotes/v2_50_0" in entries


def test_parse_drops_legacy_copy():
    ids = [pid for pid, _ in manifest.parse_manifest(FIXTURE)]
    assert "admin/PowersCopy" not in ids
    assert "admin/PowersOld" not in ids


def test_parse_drops_root_navigation():
    ids = [pid for pid, _ in manifest.parse_manifest(FIXTURE)]
    assert not any("index_admin" in i or "GettingStarted" in i for i in ids)
    assert "user/GettingStartedUser" not in ids
    assert "admin/indexOverview" not in ids


def test_parse_sorted():
    ids = [pid for pid, _ in manifest.parse_manifest(FIXTURE)]
    assert ids == sorted(ids)


def test_parse_dedupes():
    ids = [pid for pid, _ in manifest.parse_manifest(FIXTURE)]
    assert ids.count("admin/BusinessProcess") == 1


def test_fetch_raises_on_empty(monkeypatch):
    resp = MagicMock(text="<urlset></urlset>")
    resp.raise_for_status = MagicMock()
    monkeypatch.setattr(manifest, "requests", MagicMock(get=MagicMock(return_value=resp)))
    with pytest.raises(manifest.ManifestError):
        manifest.fetch_manifest()
