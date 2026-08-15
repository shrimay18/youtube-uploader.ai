"""Tag-budget packing (YouTube's 500-char cap) + profile validation."""
from youtube_manager.config import check_profile
from youtube_manager.util import fit_tags


# ---- fit_tags -------------------------------------------------------------

def test_fit_tags_keeps_all_within_budget_and_order():
    assert fit_tags(["ab", "cd", "ef"], limit=500) == ["ab", "cd", "ef"]


def test_fit_tags_trims_when_over_budget():
    # "aaaa"(4) + "bbbb"(1 comma + 4 = 5) = 9; "cccc" would push to 14 -> dropped
    assert fit_tags(["aaaa", "bbbb", "cccc"], limit=9) == ["aaaa", "bbbb"]


def test_fit_tags_charges_quotes_for_multiword():
    assert fit_tags(["a b"], limit=4) == []          # 3 chars + 2 quotes = 5 > 4
    assert fit_tags(["a b"], limit=5) == ["a b"]


def test_fit_tags_skips_blank_tags():
    assert fit_tags(["", "   ", "ok"]) == ["ok"]


# ---- check_profile --------------------------------------------------------

def test_check_profile_flags_all_when_empty():
    assert set(check_profile({})) == {"niche", "audience", "tone", "default_cta"}


def test_check_profile_passes_when_filled():
    p = {"niche": "edtech", "audience": "students", "tone": "honest", "default_cta": "Subscribe"}
    assert check_profile(p) == []


def test_check_profile_treats_placeholder_as_missing():
    p = {"niche": "???", "audience": "x", "tone": "y", "default_cta": "z"}
    assert check_profile(p) == ["niche"]
