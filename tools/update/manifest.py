"""Обнаружение курированного списка страниц вики из sitemap.xml. Список НЕ хардкодится.

sitemap даёт «вселенную» страниц; трекаем подмножество: секции {admin,user,ReleaseNotes}
минус легаси (*Old/*Copy) и навигация (index*/main*/GettingStarted*).
"""
import re

import requests

SITEMAP_URL = "https://wiki.hubex.ru/sitemap.xml"

_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
PAGE_RE = re.compile(r"/docs/FAQ/RU/(admin|user|ReleaseNotes)/([^/]+)\.html$")
_DENY_RE = re.compile(r"(Old|Copy)$|^(index|main|GettingStarted)")


class ManifestError(Exception):
    """Источник перечня страниц недоступен или пуст после фильтра."""


def parse_manifest(xml: str) -> list:
    entries, seen = [], set()
    for loc in _LOC_RE.findall(xml):
        m = PAGE_RE.search(loc)
        if not m:
            continue
        section, slug = m.group(1), m.group(2)
        if _DENY_RE.search(slug):
            continue
        page_id = f"{section}/{slug}"
        if page_id in seen:
            continue
        seen.add(page_id)
        entries.append((page_id, loc))
    return sorted(entries)


def fetch_manifest(*, timeout: int = 30) -> list:
    resp = requests.get(SITEMAP_URL, timeout=timeout)
    resp.raise_for_status()
    entries = parse_manifest(resp.text)
    if not entries:
        raise ManifestError(
            f"sitemap {SITEMAP_URL} не дал ни одной трекаемой страницы — проверь фильтр/формат")
    return entries
