"""Minimal OpenAlex client: resolve a work by DOI and page through the works citing it.

Uses only the standard library. Requests carry a ``mailto`` for OpenAlex's
"polite pool". If ``OPENALEX_API_KEY`` is set it is sent as the ``api_key``
query parameter, as OpenAlex's authentication docs specify. Without a key the
daily usage budget is small (see README).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Iterator, Protocol

BASE_URL = "https://api.openalex.org"
CITING_FIELDS = "id,doi,display_name,publication_date,type,ids,cited_by_count"


class Session(Protocol):
    def get_json(self, url: str) -> dict | None:
        """Return decoded JSON, or None for a 404."""


class UrllibSession:
    def __init__(self, user_agent: str, timeout: float = 60.0, retries: int = 4):
        self.user_agent = user_agent
        self.timeout = timeout
        self.retries = retries

    def get_json(self, url: str) -> dict | None:
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        delay = 2.0
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as err:
                if err.code == 404:
                    return None
                if err.code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
            except urllib.error.URLError:
                if attempt < self.retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
        return None


class OpenAlexClient:
    def __init__(
        self,
        mailto: str | None = None,
        api_key: str | None = None,
        session: Session | None = None,
        cache_dir: str | Path | None = None,
        min_interval: float = 0.12,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.mailto = mailto or os.environ.get("OPENALEX_MAILTO")
        self.api_key = api_key or os.environ.get("OPENALEX_API_KEY")
        agent = "fallout/0.1 (+https://github.com/bastardpsycho/EH_claudemission)"
        if self.mailto:
            agent += f" mailto:{self.mailto}"
        self.session = session or UrllibSession(agent)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self._sleep = sleep
        self._clock = clock
        self._last = float("-inf")
        self.requests_made = 0

    def _url(self, path: str, params: dict | None = None) -> str:
        params = dict(params or {})
        if self.mailto:
            params["mailto"] = self.mailto
        if self.api_key:
            params["api_key"] = self.api_key
        query = urllib.parse.urlencode(params, safe=":,*|")
        return f"{BASE_URL}{path}" + (f"?{query}" if query else "")

    def _cache_path(self, url: str) -> Path | None:
        if not self.cache_dir:
            return None
        # Strip credentials so the cache key is stable and keys never touch disk.
        parsed = urllib.parse.urlsplit(url)
        kept = [(k, v) for k, v in urllib.parse.parse_qsl(parsed.query) if k not in ("api_key", "mailto")]
        stable = parsed._replace(query=urllib.parse.urlencode(kept)).geturl()
        return self.cache_dir / (hashlib.sha256(stable.encode()).hexdigest() + ".json")

    def get(self, path: str, params: dict | None = None) -> dict | None:
        url = self._url(path, params)
        cache = self._cache_path(url)
        if cache and cache.exists():
            return json.loads(cache.read_text())
        wait = self.min_interval - (self._clock() - self._last)
        if wait > 0:
            self._sleep(wait)
        self._last = self._clock()
        data = self.session.get_json(url)
        self.requests_made += 1
        if cache is not None:
            cache.write_text(json.dumps(data))
        return data

    def work_by_doi(self, doi: str) -> dict | None:
        return self.get(f"/works/doi:{urllib.parse.quote(doi, safe='/')}")

    def citing_works(self, openalex_id: str, max_results: int | None = None, per_page: int = 200) -> Iterator[dict]:
        """Yield works whose reference lists include ``openalex_id`` (cursor pagination)."""
        short_id = openalex_id.rsplit("/", 1)[-1]
        cursor = "*"
        seen = 0
        while cursor:
            page = self.get(
                "/works",
                {"filter": f"cites:{short_id}", "per-page": per_page, "cursor": cursor, "select": CITING_FIELDS},
            )
            if not page:
                return
            results = page.get("results") or []
            for work in results:
                yield work
                seen += 1
                if max_results is not None and seen >= max_results:
                    return
            if not results:
                return
            cursor = (page.get("meta") or {}).get("next_cursor")
