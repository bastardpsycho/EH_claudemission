import urllib.parse

import pytest


class FakeSession:
    """Serves hand-built responses shaped like OpenAlex's documented /works schema."""

    def __init__(self):
        self.works = {}       # doi -> work
        self.citing = {}      # short id -> list of works
        self.page_size = 2
        self.calls = []

    def get_json(self, url):
        self.calls.append(url)
        parts = urllib.parse.urlsplit(url)
        q = dict(urllib.parse.parse_qsl(parts.query))
        if parts.path.startswith("/works/doi:"):
            return self.works.get(urllib.parse.unquote(parts.path[len("/works/doi:"):]))
        if parts.path == "/works":
            wid = q["filter"].split(":", 1)[1]
            items = self.citing.get(wid, [])
            start = 0 if q["cursor"] == "*" else int(q["cursor"])
            page = items[start:start + self.page_size]
            nxt = start + self.page_size
            return {
                "meta": {"count": len(items), "next_cursor": str(nxt) if nxt < len(items) else None},
                "results": page,
            }
        return None


def work(wid, title, date, typ="article", doi=None):
    return {
        "id": f"https://openalex.org/{wid}",
        "doi": f"https://doi.org/{doi}" if doi else None,
        "display_name": title,
        "publication_date": date,
        "type": typ,
        "ids": {"openalex": f"https://openalex.org/{wid}"},
        "cited_by_count": 0,
    }


@pytest.fixture
def fake():
    s = FakeSession()
    s.works["10.1000/trial.1"] = {**work("W1", "Trial of drug A versus placebo", "2015-06-01"), "cited_by_count": 5}
    s.citing["W1"] = [
        work("W10", "Drug A for pain: a systematic review and meta-analysis", "2022-01-10", "review", "10.2000/ma"),
        work("W11", "A randomised trial of drug D", "2016-01-01"),
        work("W12", "Clinical practice guideline for chronic pain management", "2021-06-01", doi="10.2000/gl"),
        work("W13", "Systematic review of drug A safety", "2019-01-01", "review"),
        work("W14", "Drug A: a narrative review", "2023-01-01", "review"),
    ]
    return s
