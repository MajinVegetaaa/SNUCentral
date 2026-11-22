"""HTTP downloads with retries, a politeness delay and content hashing."""

import hashlib
import re
import time

import requests

# Generic client name; no personal details are sent to the sites.
USER_AGENT = "SNU-Central-IR-coursework/1.0"


class Downloader:
    def __init__(self, timeout: float = 60, retries: int = 2, delay: float = 0.5):
        self.timeout = timeout
        self.retries = retries
        self.delay = delay              # seconds between requests, to be polite
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last_request = 0.0

    def get(self, url: str) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            wait = self.delay - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            try:
                self._last_request = time.monotonic()
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                return resp
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
                last_error = e
                # 4xx other than 429 will not succeed on retry
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status is not None and 400 <= status < 500 and status != 429:
                    break
                time.sleep(2 ** attempt)
        raise RuntimeError(f"GET {url} failed: {last_error}")

    def get_bytes(self, url: str) -> bytes:
        return self.get(url).content

    def get_text(self, url: str) -> str:
        resp = self.get(url)
        resp.encoding = resp.encoding or "utf-8"
        return resp.text


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_pdf(data: bytes) -> bool:
    return data.lstrip()[:5] == b"%PDF-"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def safe_filename(name: str) -> str:
    """Keep a readable original filename but drop anything path-like or odd."""
    name = name.replace("\\", "/").split("/")[-1]
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, "pdf"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "document"
    return f"{stem}.{ext.lower()}"
