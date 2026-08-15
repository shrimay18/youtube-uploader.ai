"""P1: per-user encrypted key storage (KeyCrypto + KeyStore + KeyService)."""
from youtube_manager.keycrypto import KeyCrypto
from youtube_manager.keyservice import KeyService
from youtube_manager.keystore import InMemoryKeyStore


def _svc():
    return KeyService(InMemoryKeyStore(), KeyCrypto(KeyCrypto.generate_master_key()))


def test_crypto_roundtrip():
    c = KeyCrypto(KeyCrypto.generate_master_key())
    assert c.dec(c.enc("secret-123")) == "secret-123"


def test_save_then_masked_view_never_leaks_raw():
    s = _svc()
    s.save("u1", llm_ops={"gemini": {"keep": [], "add": ["AIzaSECRETKEY1234567"]}})
    m = s.list_masked("u1")
    assert m["has_llm"] is True
    assert len(m["llm"]["gemini"]) == 1
    masked = m["llm"]["gemini"][0]
    assert masked != "AIzaSECRETKEY1234567" and "…" in masked


def test_context_exposes_decrypted_keys():
    s = _svc()
    s.save("u1", llm_ops={"groq": {"keep": [], "add": ["gsk_realkey_abc"]}})
    ctx = s.build_context("u1")
    assert ctx.keys_for("groq") == ["gsk_realkey_abc"]
    assert ctx.has_llm()


def test_keep_by_index_plus_add():
    s = _svc()
    s.save("u1", llm_ops={"anthropic": {"keep": [], "add": ["k1", "k2"]}})
    s.save("u1", llm_ops={"anthropic": {"keep": [0], "add": ["k3"]}})   # keep k1, add k3
    assert s.build_context("u1").keys_for("anthropic") == ["k1", "k3"]


def test_dedupes_keys():
    s = _svc()
    s.save("u1", llm_ops={"gemini": {"keep": [], "add": ["dup", "dup", "x"]}})
    assert s.build_context("u1").keys_for("gemini") == ["dup", "x"]


def test_custom_provider_saved_and_ordered():
    s = _svc()
    s.save("u1", custom={"keep": [], "add": [
        {"name": "MyLLM", "base": "https://api.x.com/v1", "model": "m", "key": "ck"}]})
    m = s.list_masked("u1")
    assert len(m["custom"]) == 1 and m["custom"][0]["name"] == "MyLLM"
    assert m["custom"][0]["id"] in m["order"]                 # custom id appended to order
    assert s.build_context("u1").custom_providers()[0]["key"] == "ck"


def test_data_persists_across_service_instances():
    store, crypto = InMemoryKeyStore(), KeyCrypto(KeyCrypto.generate_master_key())
    KeyService(store, crypto).save("u1", llm_ops={"gemini": {"keep": [], "add": ["persisted"]}})
    # a brand-new service on the SAME store still sees it (it's stored, not in-instance)
    assert KeyService(store, crypto).build_context("u1").keys_for("gemini") == ["persisted"]


def test_users_are_isolated():
    s = _svc()
    s.save("u1", llm_ops={"gemini": {"keep": [], "add": ["u1key"]}})
    s.save("u2", llm_ops={"gemini": {"keep": [], "add": ["u2key"]}})
    assert s.build_context("u1").keys_for("gemini") == ["u1key"]
    assert s.build_context("u2").keys_for("gemini") == ["u2key"]
    assert s.has_llm("u3") is False                            # unknown user = empty
