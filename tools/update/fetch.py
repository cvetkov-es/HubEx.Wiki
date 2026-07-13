"""Забор страницы вики и конвертация HTML→md: тело статьи, локальные кросс-ссылки,
картинки абсолютными URL, чистый frontmatter (без волатильных полей)."""
import hashlib
import posixpath
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

from update.manifest import PAGE_RE

BASE = "https://wiki.hubex.ru"
_CONTENT_ID = "main_content_wrap"
_TRACKING_HOSTS = ("mc.yandex.ru", "google-analytics.com", "googletagmanager.com")


def fetch_html(url: str, *, timeout: int = 30) -> str:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def normalize(md: str) -> str:
    md = md.replace("\r\n", "\n").replace("\r", "\n")
    out, blank = [], 0
    for line in md.split("\n"):
        line = line.rstrip()
        if line == "":
            blank += 1
            if blank <= 1:
                out.append(line)
        else:
            blank = 0
            out.append(line)
    return "\n".join(out).strip("\n") + "\n"


def local_href(from_page_id: str, to_page_id: str) -> str:
    """Относительный путь между страницами: admin/A → admin/B = "B.md", admin/A → user/C = "../user/C.md"."""
    return posixpath.relpath(f"{to_page_id}.md", posixpath.dirname(from_page_id))


def _title(soup: BeautifulSoup) -> str:
    t = soup.find("title")
    return (t.get_text(strip=True) if t else "").replace('"', "'")


def convert_page(html: str, *, page_id: str, url: str,
                 known_pages: frozenset = frozenset()) -> str:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.find(id=_CONTENT_ID)
    if body is None:
        raise ValueError(f"не найден #{_CONTENT_ID} — вёрстка страницы изменилась")
    for junk in body(["script", "style"]):
        junk.decompose()
    for img in body.find_all("img"):
        if any(h in (img.get("src") or "") for h in _TRACKING_HOSTS):
            img.decompose()
    for tag, attr in (("a", "href"), ("img", "src")):
        for el in body.find_all(tag):
            if el.get(attr):
                el[attr] = urljoin(url, el[attr])
    # ссылки с якорями/параметрами не матчатся PAGE_RE ($ после .html) и остаются URL-ами
    for a in body.find_all("a"):
        m = PAGE_RE.search(a.get("href") or "")
        if m and f"{m.group(1)}/{m.group(2)}" in known_pages:
            a["href"] = local_href(page_id, f"{m.group(1)}/{m.group(2)}")
    md = normalize(markdownify(str(body), heading_style="ATX"))
    section = page_id.split("/", 1)[0]
    content_hash = hashlib.sha256(md.encode("utf-8")).hexdigest()[:16]
    frontmatter = (
        "---\n"
        f'title: "{_title(soup)}"\n'
        f'url: "{url}"\n'
        f'section: "{section}"\n'
        f'content_hash: "{content_hash}"\n'
        "---\n\n"
    )
    return frontmatter + md
