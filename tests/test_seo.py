"""Local SEO logic: topic relevance filter + deterministic title scorer."""
from youtube_manager.seo import score_title, shares_topic


def test_shares_topic_true_when_no_terms():
    assert shares_topic("literally anything", set()) is True


def test_shares_topic_true_on_shared_word():
    assert shares_topic("Best hostel in Manali", {"hostel", "food"}) is True


def test_shares_topic_false_when_unrelated():
    # the classic 'garza crew' leak into a 'scaler vs newton' video
    assert shares_topic("Garza crew twins skincare routine", {"scaler", "newton"}) is False


def test_shares_topic_true_on_multiword_verbatim():
    assert shares_topic("the scaler academy review", {"scaler academy"}) is True


def test_score_title_returns_bounded_int_and_breakdown():
    score, breakdown = score_title(
        "How I Cracked JEE in 2024: An Honest Guide",
        [("jee", 3), ("guide", 2)], ["jee tips"], ["jee"],
    )
    assert isinstance(score, int) and 0 <= score <= 100
    assert isinstance(breakdown, dict) and breakdown


def test_score_title_rewards_keyword_rich_over_bland():
    vocab, autocomplete, primary = [("hostel", 3), ("manali", 2), ("review", 2)], ["hostel review"], ["hostel"]
    rich, _ = score_title("Honest Hostel Review in Manali 2024 (Worth It?)", vocab, autocomplete, primary)
    bland, _ = score_title("My trip", vocab, autocomplete, primary)
    assert rich > bland
