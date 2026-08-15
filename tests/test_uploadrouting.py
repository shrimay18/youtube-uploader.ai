"""P2: shared→BYO upload routing (single falls back to the user's client; bulk = own only)."""
import pytest

from youtube_manager.providers.base import QuotaExceeded
from youtube_manager.uploadrouting import NoCredentials, order_connections, run_with_quota_fallback

APP = {"client_kind": "app", "channel_id": "c1"}
OWN = {"client_kind": "user", "channel_id": "c1"}


def test_single_tries_app_then_user():
    assert order_connections([OWN, APP], "single") == [APP, OWN]


def test_bulk_uses_only_user():
    assert order_connections([APP, OWN], "bulk") == [OWN]


def test_single_falls_back_to_user_on_quota():
    tried = []

    def do(conn):
        tried.append(conn["client_kind"])
        if conn["client_kind"] == "app":
            raise QuotaExceeded("shared pool spent")
        return "uploaded:" + conn["client_kind"]

    assert run_with_quota_fallback([APP, OWN], "single", do) == "uploaded:user"
    assert tried == ["app", "user"]


def test_single_uses_app_when_it_has_quota():
    assert run_with_quota_fallback([APP, OWN], "single",
                                   lambda c: "uploaded:" + c["client_kind"]) == "uploaded:app"


def test_bulk_without_own_creds_raises_nocredentials():
    with pytest.raises(NoCredentials):
        run_with_quota_fallback([APP], "bulk", lambda c: "x")


def test_single_with_no_connections_raises_nocredentials():
    with pytest.raises(NoCredentials):
        run_with_quota_fallback([], "single", lambda c: "x")


def test_all_quota_exhausted_raises_quota():
    def do(conn):
        raise QuotaExceeded("spent")

    with pytest.raises(QuotaExceeded):
        run_with_quota_fallback([APP, OWN], "single", do)
