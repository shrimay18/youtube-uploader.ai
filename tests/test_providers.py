"""LLM provider layer: JSON extraction + multi-key rotation (OCP/LSP core)."""
import pytest

from youtube_manager.providers.base import KeyedProvider, QuotaExceeded, extract_json


# ---- extract_json ---------------------------------------------------------

def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_code_fence():
    assert extract_json('```json\n{"a": 1, "b": "x"}\n```') == {"a": 1, "b": "x"}


def test_extract_json_embedded_in_prose():
    assert extract_json('Sure thing! {"title": "Hi", "n": 2} hope that helps') == {"title": "Hi", "n": 2}


def test_extract_json_repairs_truncated_reply():
    # model hit the token limit mid-object (dangling string, no closing brace)
    out = extract_json('{"title": "Hello", "desc": "world')
    assert out["title"] == "Hello" and out["desc"] == "world"


def test_extract_json_no_object_raises():
    with pytest.raises(ValueError):
        extract_json("there is no json here at all")


# ---- KeyedProvider key rotation ------------------------------------------

class _FakeProvider(KeyedProvider):
    name = "fake"

    def __init__(self, keys, behavior):
        super().__init__(keys=keys)
        self.behavior = dict(zip(keys, behavior))  # key -> 'ok' | 'quota' | 'error'
        self.calls = []

    def _call(self, key, system, user):
        self.calls.append(key)
        b = self.behavior[key]
        if b == "quota":
            raise QuotaExceeded("429 rate limited")
        if b == "error":
            raise RuntimeError("network boom")
        return f"ok:{key}"


def test_rotates_past_quota_to_a_working_key():
    p = _FakeProvider(["k1", "k2", "k3"], ["quota", "quota", "ok"])
    assert p.complete("s", "u") == "ok:k3"
    assert p.calls == ["k1", "k2", "k3"]          # tried each in order


def test_rotates_past_transient_error():
    p = _FakeProvider(["k1", "k2"], ["error", "ok"])
    assert p.complete("s", "u") == "ok:k2"


def test_all_keys_exhausted_raises_quota():
    p = _FakeProvider(["k1", "k2"], ["quota", "quota"])
    with pytest.raises(QuotaExceeded):
        p.complete("s", "u")


def test_error_on_last_key_propagates():
    p = _FakeProvider(["only"], ["error"])
    with pytest.raises(RuntimeError):
        p.complete("s", "u")


def test_no_keys_raises_runtime_error():
    p = _FakeProvider([], [])
    with pytest.raises(RuntimeError):
        p.complete("s", "u")
