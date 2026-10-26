from fallout.openalex import OpenAlexClient


def test_resolve_paginate_and_rate_limit(fake, tmp_path):
    slept = []
    t = [0.0]
    c = OpenAlexClient(mailto="a@b.org", api_key="SECRET", session=fake, cache_dir=tmp_path,
                       min_interval=1.0, sleep=lambda s: slept.append(s), clock=lambda: t[0])
    w = c.work_by_doi("10.1000/trial.1")
    assert w["id"].endswith("W1")
    got = [x["id"].rsplit("/", 1)[-1] for x in c.citing_works(w["id"])]
    assert got == ["W10", "W11", "W12", "W13", "W14"]
    assert all("mailto=a%40b.org" in u or "mailto=a@b.org" in u for u in fake.calls)
    assert "filter=cites:W1" in fake.calls[1]
    assert slept  # clock frozen, so every call after the first waits
    # cache hit: no new HTTP calls, and the API key never reaches disk
    n = len(fake.calls)
    c.work_by_doi("10.1000/trial.1")
    assert len(fake.calls) == n
    assert all("SECRET" not in p.read_text() for p in tmp_path.iterdir())


def test_max_results_and_missing(fake):
    c = OpenAlexClient(session=fake, min_interval=0)
    assert len(list(c.citing_works("https://openalex.org/W1", max_results=3))) == 3
    assert c.work_by_doi("10.9/none") is None
