"""S1-S3: sources that are plain PDF URLs."""

from urllib.parse import urlparse

from .downloader import Downloader, is_pdf, safe_filename, slugify
from .models import FetchFailure, FetchedDoc, SourceResult


def _entries(src: dict) -> list[dict]:
    """`urls` items may be a bare URL string or {url, title}."""
    out = []
    for item in src.get("urls", []):
        entry = {"url": item} if isinstance(item, str) else dict(item)
        out.append(entry)
    return out


def fetch_direct(source_id: str, src: dict, dl: Downloader) -> SourceResult:
    result = SourceResult()
    entries = _entries(src)
    for entry in entries:
        url = entry["url"]
        filename = safe_filename(urlparse(url).path)
        stem = filename.rsplit(".", 1)[0]
        doc_id = f"{source_id}_{slugify(stem)}"
        # A single-URL source uses the source name; otherwise the entry title or filename.
        title = entry.get("title") or (src["name"] if len(entries) == 1 else stem.replace("_", " ").title())
        try:
            data = dl.get_bytes(url)
            if not is_pdf(data):
                raise ValueError("response is not a PDF")
        except Exception as e:  # noqa: BLE001 - report every failure, keep going
            result.failures.append(FetchFailure(source_id, url, str(e), doc_id))
            continue
        result.docs.append(FetchedDoc(doc_id, source_id, title, url, filename, data,
                                      category=entry.get("category", ""), department=entry.get("department", "")))
    return result
