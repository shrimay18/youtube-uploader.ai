"""P1: building the LLM engine chain from a per-request UserContext (no global vault)."""
from youtube_manager.providers import FallbackProvider, get_provider_for
from youtube_manager.usercontext import UserContext


def test_single_provider_from_context():
    ctx = UserContext(id="u1", llm={"gemini": ["k1"]}, order=["gemini"])
    p = get_provider_for(ctx, {})
    assert p.name == "gemini"


def test_two_providers_build_a_fallback_chain_in_order():
    ctx = UserContext(id="u1", llm={"gemini": ["k1"], "groq": ["k2"]}, order=["gemini", "groq"])
    p = get_provider_for(ctx, {})
    assert isinstance(p, FallbackProvider)
    assert [name for name, _ in p.chain] == ["gemini", "groq"]


def test_custom_provider_from_context():
    ctx = UserContext(id="u1", llm={}, order=["x1"],
                      custom=[{"id": "x1", "name": "MyLLM", "base": "", "model": "", "key": "ck"}])
    p = get_provider_for(ctx, {})
    assert p.name == "MyLLM"


def test_claude_token_maps_to_anthropic_keys():
    ctx = UserContext(id="u1", llm={"anthropic": ["ak"]}, order=["anthropic"])
    p = get_provider_for(ctx, {})
    assert p.name == "anthropic"


def test_no_keys_falls_back_to_settings_engine():
    ctx = UserContext(id="u1", llm={}, order=[])
    p = get_provider_for(ctx, {"engine": "gemini"})
    assert p.name == "gemini"          # constructed with no key; surfaces error only on call
