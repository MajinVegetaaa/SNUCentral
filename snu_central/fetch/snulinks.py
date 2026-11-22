"""S4: SNU Links student policies.

The index page lists policy nodes (`?node=N`). A node is either
  * a folder: its page lists child node links (plus a "Go Back" link), or
  * a document: its page embeds the PDF as base64 in
    `window.SNU_PDF_BASE64 = "..."` and gives the real filename in
    `window.SNU_PDF_FILENAME = "..."`.
We walk the tree breadth-first from the index page.
"""

import base64
import html
import json
import re
from collections import deque
from urllib.parse import urljoin

from .downloader import Downloader, is_pdf, safe_filename
from .models import FetchFailure, FetchedDoc, SourceResult

NODE_LINK = re.compile(r'href="([^"]*student-policies\?node=(\d+))"[^>]*>(.*?)</a>', re.S)
PDF_B64 = re.compile(r'window\.SNU_PDF_BASE64\s*=\s*("(?:[^"\\]|\\.)*")')
PDF_NAME = re.compile(r'window\.SNU_PDF_FILENAME\s*=\s*("(?:[^"\\]|\\.)*")')
SKIP_LINK_TITLES = {"go back"}
NO_ACCESS_MARKER = "doc-tree-noaccess"     # "You do not have access to view this space"


def _norm(title: str) -> str:
    """Compare titles ignoring case, punctuation and apostrophe variants."""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _clean_title(raw: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", text).strip()


def _child_links(page: str, base_url: str) -> list[tuple[str, str, str]]:
    """(absolute_url, node_id, title) for each node link on a page, in order."""
    out, seen = [], set()
    for href, node_id, raw_title in NODE_LINK.findall(page):
        title = _clean_title(raw_title)
        if not title or title.lower() in SKIP_LINK_TITLES or node_id in seen:
            continue
        seen.add(node_id)
        out.append((urljoin(base_url, html.unescape(href)), node_id, title))
    return out


def _embedded_pdf(page: str) -> tuple[bytes, str] | None:
    m = PDF_B64.search(page)
    if not m:
        return None
    b64 = json.loads(m.group(1))            # undoes JS string escapes like "\/"
    data = base64.b64decode(b64)
    name_m = PDF_NAME.search(page)
    filename = json.loads(name_m.group(1)) if name_m else ""
    return data, filename


def fetch_snulinks(source_id: str, src: dict, dl: Downloader, max_depth: int = 4) -> SourceResult:
    result = SourceResult()
    index_url = src["index_url"]
    excluded = {_norm(t) for t in src.get("exclude_titles", [])}

    try:
        index_page = dl.get_text(index_url)
    except Exception as e:  # noqa: BLE001
        result.failures.append(FetchFailure(source_id, index_url, str(e)))
        return result

    visited: set[str] = set()
    queue = deque((url, nid, title, [], 1) for url, nid, title in _child_links(index_page, index_url))

    while queue:
        url, node_id, title, path, depth = queue.popleft()
        if node_id in visited or _norm(title) in excluded:
            continue
        visited.add(node_id)
        doc_id = f"{source_id}_node{node_id}"
        try:
            resp = dl.get(url)
            ctype = resp.headers.get("content-type", "").split(";")[0].strip()
            if ctype != "text/html":
                # Some nodes serve a file directly (e.g. .docx/.xlsx forms).
                if is_pdf(resp.content):
                    result.docs.append(FetchedDoc(doc_id, source_id, title, url,
                                                  safe_filename(f"{title}.pdf"), resp.content, " > ".join(path)))
                else:
                    result.skipped.append(f"{title}: non-PDF file ({ctype})  {url}")
                continue
            page = resp.text
            pdf = _embedded_pdf(page)
        except Exception as e:  # noqa: BLE001
            result.failures.append(FetchFailure(source_id, url, str(e), doc_id))
            continue

        if pdf is None and NO_ACCESS_MARKER in page:
            result.skipped.append(f"{title}: login required  {url}")
            continue

        if pdf is not None:
            data, filename = pdf
            if not is_pdf(data):
                result.failures.append(FetchFailure(source_id, url, "embedded data is not a PDF", doc_id))
                continue
            result.docs.append(FetchedDoc(
                doc_id=doc_id,
                source_id=source_id,
                title=title,
                url=url,
                filename=safe_filename(filename or f"{title}.pdf"),
                data=data,
                folder=" > ".join(path),
            ))
            continue

        children = [c for c in _child_links(page, url) if c[1] not in visited]
        if not children:
            result.failures.append(FetchFailure(source_id, url, "no PDF and no child policies on page", doc_id))
        elif depth >= max_depth:
            result.failures.append(FetchFailure(source_id, url, f"folder deeper than {max_depth} levels skipped", doc_id))
        else:
            for c_url, c_id, c_title in children:
                queue.append((c_url, c_id, c_title, path + [title], depth + 1))

    return result
