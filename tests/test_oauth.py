"""P2: OAuth2 web flow (auth URL + code exchange + refresh)."""
from urllib.parse import parse_qs, urlparse

from youtube_manager import oauth


def test_build_auth_url_has_required_params():
    url = oauth.build_auth_url("cid.apps", "https://app/cb", "state123")
    q = parse_qs(urlparse(url).query)
    assert q["client_id"] == ["cid.apps"]
    assert q["redirect_uri"] == ["https://app/cb"]
    assert q["response_type"] == ["code"]
    assert q["access_type"] == ["offline"]        # guarantees a refresh token
    assert q["prompt"] == ["consent"]
    assert q["state"] == ["state123"]
    assert "youtube.force-ssl" in q["scope"][0]


def test_exchange_code_posts_correctly(monkeypatch):
    captured = {}

    class R:
        def raise_for_status(self): pass
        def json(self): return {"access_token": "at", "refresh_token": "rt", "expires_in": 3600}

    def fake_post(url, data=None, timeout=20):
        captured.update(url=url, data=data)
        return R()

    monkeypatch.setattr(oauth.requests, "post", fake_post)
    out = oauth.exchange_code("cid", "sec", "https://app/cb", "the-code")
    assert out["refresh_token"] == "rt"
    assert captured["url"] == oauth.TOKEN_URI
    assert captured["data"]["grant_type"] == "authorization_code"
    assert captured["data"]["code"] == "the-code"


def test_refresh_access_token(monkeypatch):
    class R:
        def raise_for_status(self): pass
        def json(self): return {"access_token": "fresh", "expires_in": 3600}

    seen = {}
    monkeypatch.setattr(oauth.requests, "post",
                        lambda url, data=None, timeout=20: (seen.update(data=data) or R()))
    out = oauth.refresh_access_token("cid", "sec", "rt")
    assert out["access_token"] == "fresh"
    assert seen["data"]["grant_type"] == "refresh_token"
