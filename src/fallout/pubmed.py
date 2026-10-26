"""Fetch PubMed publication types (e.g. "Meta-Analysis", "Practice Guideline") via NCBI E-utilities.

Indexer-assigned publication types are a stronger signal than title patterns,
so ``fallout enrich`` uses them to re-classify citing works that have a PMID.
Without an NCBI API key, E-utilities allows 3 requests per second.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Iterable, Protocol

ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


class PostSession(Protocol):
    def post_form(self, url: str, data: dict) -> dict:
        """POST form data and return decoded JSON."""


class UrllibPostSession:
    def __init__(self, user_agent: str, timeout: float = 60.0, retries: int = 4):
        self.user_agent = user_agent
        self.timeout = timeout
        self.retries = retries

    def post_form(self, url: str, data: dict) -> dict:
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=body, headers={"User-Agent": self.user_agent})
        delay = 2.0
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except (urllib.error.HTTPError, urllib.error.URLError) as err:
                code = getattr(err, "code", None)
                if attempt < self.retries and (code is None or code in (429, 500, 502, 503, 504)):
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
        return {}


class PubMedClient:
    def __init__(
        self,
        email: str | None = None,
        api_key: str | None = None,
        session: PostSession | None = None,
        min_interval: float | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.email = email or os.environ.get("NCBI_EMAIL") or os.environ.get("OPENALEX_MAILTO")
        self.api_key = api_key or os.environ.get("NCBI_API_KEY")
        self.session = session or UrllibPostSession("fallout/0.1 (+https://github.com/bastardpsycho/EH_claudemission)")
        # NCBI limits: 3 requests/s without a key, 10/s with one.
        self.min_interval = min_interval if min_interval is not None else (0.11 if self.api_key else 0.35)
        self._sleep = sleep
        self._clock = clock
        self._last = float("-inf")
        self.requests_made = 0

    def publication_types(self, pmids: Iterable[str], batch_size: int = 200) -> dict[str, list[str]]:
        """Map each PMID to its publication types. PMIDs PubMed does not return are left out."""
        ids = sorted({p for p in pmids if p and p.isdigit()}, key=int)
        out: dict[str, list[str]] = {}
        for i in range(0, len(ids), batch_size):
            batch = ids[i:i + batch_size]
            data = {"db": "pubmed", "retmode": "json", "id": ",".join(batch), "tool": "fallout"}
            if self.email:
                data["email"] = self.email
            if self.api_key:
                data["api_key"] = self.api_key
            wait = self.min_interval - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
            self._last = self._clock()
            resp = self.session.post_form(ESUMMARY_URL, data)
            self.requests_made += 1
            result = resp.get("result") or {}
            for uid in result.get("uids") or []:
                doc = result.get(uid) or {}
                if "error" in doc:
                    continue
                out[uid] = list(doc.get("pubtype") or [])
        return out
