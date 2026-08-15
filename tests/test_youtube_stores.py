"""P2: user OAuth client store + channel connection store (encrypted, dual-connection)."""
from youtube_manager.channelstore import InMemoryChannelStore
from youtube_manager.keycrypto import KeyCrypto
from youtube_manager.oauthclients import (
    InMemoryUserClientStore, OAuthClient, app_client, save_user_client, user_client)


def _crypto():
    return KeyCrypto(KeyCrypto.generate_master_key())


def test_user_client_roundtrip_secret_is_encrypted():
    store, crypto = InMemoryUserClientStore(), _crypto()
    save_user_client(store, crypto, "u1", "cid.apps", "topsecret")
    assert store.get("u1")["client_secret_ciphertext"] != "topsecret"    # stored encrypted
    c = user_client(store, crypto, "u1")
    assert isinstance(c, OAuthClient) and c.kind == "user"
    assert c.client_id == "cid.apps" and c.client_secret == "topsecret"


def test_user_client_none_when_absent():
    assert user_client(InMemoryUserClientStore(), _crypto(), "nobody") is None


def test_app_client_from_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "appcid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "appsec")
    c = app_client()
    assert c and c.kind == "app" and c.client_id == "appcid"


def test_app_client_none_without_env(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    assert app_client() is None


def test_channel_store_holds_dual_connections_and_upserts():
    s = InMemoryChannelStore()
    s.upsert({"user_id": "u1", "channel_id": "c1", "client_kind": "app", "refresh_token_ciphertext": "a"})
    s.upsert({"user_id": "u1", "channel_id": "c1", "client_kind": "user", "refresh_token_ciphertext": "b"})
    assert {r["client_kind"] for r in s.list_for("u1")} == {"app", "user"}
    # upsert replaces the same (user, channel, kind)
    s.upsert({"user_id": "u1", "channel_id": "c1", "client_kind": "app", "refresh_token_ciphertext": "a2"})
    app_rows = [r for r in s.list_for("u1") if r["client_kind"] == "app"]
    assert len(app_rows) == 1 and app_rows[0]["refresh_token_ciphertext"] == "a2"
    # delete a single kind
    s.delete("u1", "c1", "user")
    assert {r["client_kind"] for r in s.list_for("u1")} == {"app"}
