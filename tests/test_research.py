"""YouTube research key rotation (quota-exhaustion fallover) + key parsing."""
from youtube_manager import config, research


class _Resp:
    def __init__(self, status, text="", data=None):
        self.status_code = status
        self.text = text
        self._data = data or {}
        self.ok = 200 <= status < 300

    def json(self):
        return self._data


def test_yt_get_rotates_past_quota_exhausted_key(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=20):
        calls.append(params["key"])
        if params["key"] == "dead":
            return _Resp(403, text="quotaExceeded")
        return _Resp(200, data={"items": [{"id": {"videoId": "x"}}]})

    monkeypatch.setattr(research.requests, "get", fake_get)
    r = research._yt_get("http://u", {"part": "snippet"}, ["dead", "good"])
    assert r is not None and r.json()["items"]
    assert calls == ["dead", "good"]                 # tried dead first, rotated to good


def test_yt_get_returns_none_when_all_keys_dead(monkeypatch):
    monkeypatch.setattr(research.requests, "get",
                        lambda *a, **k: _Resp(403, text="quotaExceeded"))
    assert research._yt_get("http://u", {}, ["a", "b"]) is None


def test_ranking_signals_accepts_key_list(monkeypatch):
    def fake_get(url, params=None, timeout=20):
        if "search" in url:
            return _Resp(200, data={"items": [{"id": {"videoId": "v1"}, "snippet": {"title": "Hello"}}]})
        return _Resp(200, data={"items": [{"snippet": {"tags": ["a", "b"]}}]})

    monkeypatch.setattr(research.requests, "get", fake_get)
    sig = research.ranking_signals("q", ["k1", "k2"], n=5)
    assert "Hello" in sig.titles


def test_youtube_api_keys_parses_and_dedupes(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "a, b ,a,c")
    for i in range(2, 8):
        monkeypatch.delenv(f"YOUTUBE_API_KEY_{i}", raising=False)
    assert config.youtube_api_keys() == ["a", "b", "c"]
