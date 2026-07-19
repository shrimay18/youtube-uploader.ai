"""Local SEO scoring + tag derivation — free, tuned to this topic's ranking data.

There's no free external SEO-score API, so we score titles ourselves against the
signals that actually predict ranking/CTR for THIS topic:
  - coverage of the vocabulary common to the top-ranking titles (proven to rank)
  - presence + front-loading of the primary topic keywords
  - match to real search phrases (YouTube autocomplete)
  - length fit (full display + not too short)
  - specificity signals (numbers, year, brand tokens, power words)

Tags are derived the same way: YouTube blocks reading competitors' tags, so we
mine the ranking titles + autocomplete + transcript for high-value tag phrases.
"""
from __future__ import annotations

import re
from collections import Counter

_STOP = set(
    """a an and the to of in for on with your you i my me we our us is are be been being am was
    were this that these those how what why when where who whom which whose it its as at from or
    if so but not no nor can could will would shall should may might must do does did done doing
    have has had having get got gets getting go goes going gone make makes made just like about
    into out up down over under again further then once here there all any both each few more most
    other some such only own same than too very s t can will don just should now new really today
    up down out off above below between want wants wanted know knows knew think thing things stuff
    guys gonna wanna okay yeah well much many also even still back come came said says say give
    gave take took see seen look looks looking because before after while during through
    it's that's don't can't won't i'm you're we're they're i've you've he's she's there's what's
    let's isn't aren't didn't doesn't wasn't weren't couldn't wouldn't shouldn't they've we've
    im ive dont cant wont vs & | -""".split()
)

# Weak as STANDALONE single-word tags (fine inside multi-word phrases).
_TAG_JUNK = {
    "going", "there", "thing", "things", "stuff", "guys", "gonna", "wanna", "okay",
    "yeah", "school", "technology", "prep", "review", "life", "people", "place",
    "places", "time", "way", "lot", "bit", "kind", "video", "watch", "subscribe",
    "channel", "today", "really", "actually", "here", "want", "know", "like",
    "they", "have", "then", "them", "their", "year", "years", "took", "make", "made",
    "dont", "cant", "wont", "well", "much", "many", "some", "also", "even", "still",
    "back", "come", "came", "said", "says", "gets", "give", "into", "about", "your",
}


def shares_topic(text: str, terms: set[str]) -> bool:
    """True if `text` shares a meaningful word with the video's topic terms.

    Used to drop competitor titles/tags that are irrelevant to THIS video (e.g. a
    'garza crew twins' video leaking into a 'scaler vs newton' comparison).
    """
    if not terms:
        return True
    words = set(_content_words(_strip_hashtags_emoji(text)))
    if words & terms:
        return True
    # Also accept when a multi-word topic term appears verbatim.
    low = text.lower()
    return any(len(t) >= 5 and t in low for t in terms if " " in t)
_BRAND = {"scaler", "sst", "nset", "iit", "jee", "delta"}

_POWER = {
    "honest", "truth", "reality", "review", "guide", "secret", "mistake", "mistakes",
    "worth", "vs", "before", "after", "why", "how", "best", "ultimate", "complete",
    "explained", "tips", "hidden", "avoid", "must", "proof", "results",
}

_WORD = re.compile(r"[a-z0-9][a-z0-9'&+.-]*")
_YEAR = re.compile(r"\b20\d{2}\b")


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _content_words(text: str) -> list[str]:
    return [w for w in _words(text) if w not in _STOP and len(w) > 2]


def _ngrams(words: list[str], n: int) -> list[str]:
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


def _strip_hashtags_emoji(title: str) -> str:
    title = re.sub(r"#\w+", " ", title)
    title = re.sub(r"[^\w\s'&+.:?!/|()-]", " ", title)  # drop emoji/symbols
    return re.sub(r"\s+", " ", title).strip()


def ranking_vocabulary(ranking_titles: list[str], top: int = 20) -> list[tuple[str, int]]:
    """Most common meaningful terms/phrases across the top-ranking titles."""
    counter: Counter = Counter()
    for t in ranking_titles:
        words = _content_words(_strip_hashtags_emoji(t))
        counter.update(words)
        counter.update(_ngrams(words, 2))
    return counter.most_common(top)


def score_title(
    title: str,
    ranking_vocab: list[tuple[str, int]],
    autocomplete: list[str],
    primary_terms: list[str],
) -> tuple[int, dict]:
    """Return (0-100 SEO score, breakdown) for a single title."""
    clean = _strip_hashtags_emoji(title)
    low = clean.lower()
    L = len(title)

    # 1. Length fit (0-15): full-display sweet spot ~35-62 chars.
    if 35 <= L <= 62:
        length = 15
    elif 28 <= L < 70:
        length = 11
    elif L < 28 or 70 <= L <= 85:
        length = 6
    else:
        length = 3

    # 2. Primary keyword present + front-loaded (0-30).
    positions = [low.find(term.lower()) for term in primary_terms if term and term.lower() in low]
    if positions:
        primary = 18
        earliest = min(positions)
        if earliest <= 25:
            primary += 12
        elif earliest <= 45:
            primary += 6
    else:
        primary = 0

    # 3. Ranking-vocabulary coverage (0-25): overlap with proven ranking terms.
    vocab_terms = [term for term, _ in ranking_vocab]
    hits = sum(1 for term in vocab_terms if term in low)
    coverage = min(25, hits * 4)

    # 4. Real search-phrase match (0-15).
    search = 0
    for phrase in autocomplete:
        p = phrase.lower().strip()
        if len(p) >= 6 and p in low:
            search = 15
            break
        toks = [w for w in _content_words(p)]
        if len(toks) >= 2 and sum(1 for w in toks if w in low) >= 2:
            search = max(search, 9)

    # 5. Specificity / CTR signals (0-15).
    signal = 0
    if re.search(r"\d", title):
        signal += 5
    if _YEAR.search(title):
        signal += 5
    if re.search(r"\b(scaler|sst|nset|iit|jee)\b", low):
        signal += 5
    if any(w in low.split() for w in _POWER):
        signal += 5
    signal = min(15, signal)

    total = min(100, length + primary + coverage + search + signal)
    breakdown = {
        "length": length, "primary_keyword": primary, "ranking_coverage": coverage,
        "search_match": search, "specificity": signal,
    }
    return total, breakdown


def _norm_tag(tag: str) -> str | None:
    tag = re.sub(r"\s+", " ", str(tag).replace("#", "").strip().lower())
    if not (2 <= len(tag) <= 45) or tag.isdigit():
        return None
    words = tag.split()
    # Drop tags with a bare 1-2 digit number token (e.g. 'scaler 3') — junk fragments.
    if any(w.isdigit() and len(w) <= 2 for w in words):
        return None
    # Drop tags that are ENTIRELY stopwords/filler (e.g. "which", "that's", "it's me").
    if all(w in _STOP for w in words):
        return None
    if len(words) == 1 and tag not in _BRAND and (tag in _TAG_JUNK or len(tag) <= 3):
        return None
    return tag


def derive_tags(
    llm_tags: list[str],
    ranking_titles: list[str],
    autocomplete: list[str],
    seeds: list[str],
    competitor_tags: list[tuple[str, int]] | None = None,
    must_include: list[str] | None = None,
    video_title: str = "",
    topic_terms: set[str] | None = None,
    max_chars: int = 500,
    video_min_chars: int = 130,
) -> list[str]:
    """Blend competitor tags + THIS video's topic tags into a packed 450-500 char list.

    Quality rules (to keep junk out):
      - single-word tags are kept ONLY if they're a brand term or a REAL competitor tag
        (kills 'regret', 'joining', 'haveli', 'companies', 'which', ...);
      - transcript keyword "seeds" are NOT used as tags (that's the main junk source);
      - n-gram fragments from titles must share a brand/topic term;
      - LLM tags, autocomplete phrases and competitor tags are trusted (curated/real).
    """
    competitor_tags = competitor_tags or []
    topic_terms = topic_terms or set()
    strong = [t for t, c in competitor_tags if c >= 2]
    weak = [t for t, c in competitor_tags if c < 2]

    comp_count: dict[str, int] = {}
    for t, c in competitor_tags:
        nt = _norm_tag(t)
        if nt:
            comp_count[nt] = max(comp_count.get(nt, 0), c)

    # Fragment pools (n-grams) need topic relevance; curated pools are trusted.
    title_ngrams = _ngrams(_content_words(_strip_hashtags_emoji(video_title)), 3) \
        + _ngrams(_content_words(_strip_hashtags_emoji(video_title)), 2)
    ranking_ngrams: list[str] = []
    for t in ranking_titles:
        w = _content_words(_strip_hashtags_emoji(t))
        ranking_ngrams += _ngrams(w, 3) + _ngrams(w, 2)

    def keepable(tag: str, strict: bool) -> bool:
        words = tag.split()
        branded = any(b in tag for b in _BRAND)
        if len(words) == 1:
            # Single word: only a brand token or a genuinely-used competitor tag.
            return branded or tag in comp_count
        if strict:  # title/ranking fragment: must be on-topic
            return branded or bool(set(words) & topic_terms)
        return True  # curated multi-word (LLM tag / autocomplete phrase / competitor)

    kept: list[str] = []
    seen: set[str] = set()
    used = 0

    def add(raw: str, budget: int, strict: bool = False, force: bool = False) -> bool:
        nonlocal used
        tag = _norm_tag(raw)
        if not tag or tag in seen:
            return False
        if not force and not keepable(tag, strict):
            return False
        cost = len(tag) + (2 if " " in tag else 0) + (1 if kept else 0)
        if used + cost > budget:
            return False
        kept.append(tag)
        seen.add(tag)
        used += cost
        return True

    # 1. brand must-include first (always kept)
    for t in must_include or []:
        add(t, max_chars, force=True)
    # 2. reserve a slice for THIS video's own tags (LLM + title + real searches)
    floor = min(max_chars, used + video_min_chars)
    for t in llm_tags:                       # curated for this video
        if used >= floor: break
        add(t, floor)
    for t in title_ngrams:                   # from our title (topic-relevant only)
        if used >= floor: break
        add(t, floor, strict=True)
    for t in autocomplete:                   # real YouTube searches (on-topic only)
        if used >= floor: break
        add(t, floor, strict=True)
    # 3. real competitor tags fill the rest of the budget
    for t in strong + weak:
        add(t, max_chars)
    # 4. leftover -> ranking-title fragments (on-topic), then remaining curated tags
    for t in ranking_ngrams:
        add(t, max_chars, strict=True)
    for t in list(llm_tags):
        add(t, max_chars)
    for t in list(autocomplete):
        add(t, max_chars, strict=True)
    return kept
