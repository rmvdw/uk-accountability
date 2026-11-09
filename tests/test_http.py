import io
import urllib.error

import pytest

from ukdash.sources import http


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def err(code, retry_after=None):
    headers = {"Retry-After": retry_after} if retry_after else {}
    return urllib.error.HTTPError("u", code, "x", headers, None)


@pytest.fixture(autouse=True)
def clean():
    http.clear_cache()
    yield
    http.clear_cache()


def test_caches_one_download_per_url(monkeypatch):
    calls = []

    def fake_open(req, timeout):
        calls.append(req.full_url)
        return FakeResp(b"data")

    monkeypatch.setattr(http.urllib.request, "urlopen", fake_open)
    assert http.get("https://x/a") == b"data"
    assert http.get("https://x/a") == b"data"
    assert calls == ["https://x/a"]


def test_retries_429_honouring_retry_after(monkeypatch):
    outcomes = [err(429, "7"), err(503), FakeResp(b"ok")]
    waits = []

    def fake_open(req, timeout):
        o = outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return o

    monkeypatch.setattr(http.urllib.request, "urlopen", fake_open)
    assert http.get("https://x/b", sleep=waits.append) == b"ok"
    assert waits == [7.0, 30.0]


def test_does_not_retry_404(monkeypatch):
    def fake_open(req, timeout):
        raise err(404)

    monkeypatch.setattr(http.urllib.request, "urlopen", fake_open)
    with pytest.raises(urllib.error.HTTPError):
        http.get("https://x/c", sleep=lambda s: None)


def test_gives_up_after_max_attempts(monkeypatch):
    n = {"calls": 0}

    def fake_open(req, timeout):
        n["calls"] += 1
        raise err(429)

    monkeypatch.setattr(http.urllib.request, "urlopen", fake_open)
    with pytest.raises(urllib.error.HTTPError):
        http.get("https://x/d", sleep=lambda s: None)
    assert n["calls"] == http.MAX_ATTEMPTS
