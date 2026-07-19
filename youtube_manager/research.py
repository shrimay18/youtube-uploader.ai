"""SEO research — free signals only, no paid keys.

- YouTube autocomplete: real phrases people type.
- Google Trends (pytrends): rising vs fading interest.
- ranking_titles(): top titles YouTube ranks for a query — the raw video title.
  This drives the title writer (learn the patterns that rank for this topic).

Free signals give relevance + relative trend, NOT exact search volume.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

import requests

_STOPWORDS = set(
    """a an and the to of in for on with your you i my me we our is are be this that
    how what why when it its as at from or if so but not can will just get got make made
    like about into out up down over more most very really new now today
    """.split()
)


@dataclass
class Research:
    seeds: list[str] = field(default_factory=list)
    autocomplete: list[str] = field(default_factory=list)
    rising: list[str] = field(default_factory=list)


def _keywords_from_text(text: str, top: int = 8) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z'-]+", text.lower())
    words = [w for w in words if w not in _STOPWORDS and len(w) > 3]
    common = [w for w, _ in Counter(words).most_common(top)]
    # Also grab a few 2-grams for phrase seeds.
    bigrams = zip(words, words[1:])
    bg = [" ".join(b) for b in bigrams if b[0] not in _STOPWORDS and b[1] not in _STOPWORDS]
    bg_common = [b for b, _ in Counter(bg).most_common(top)]
    return list(dict.fromkeys(common + bg_common))[:top]


def youtube_autocomplete(seed: str) -> list[str]:
    """Public, unauthenticated YT suggest endpoint."""
    try:
        r = requests.get(
            "https://suggestqueries.google.com/complete/search",
            params={"client": "firefox", "ds": "yt", "q": seed},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return data[1] if len(data) > 1 else []
    except (requests.RequestException, ValueError):
        return []


def google_trends_rising(seeds: list[str], geo: str = "IN") -> list[str]:
    if not seeds:
        return []
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=330)
        pytrends.build_payload(seeds[:5], timeframe="now 7-d", geo=geo)
        related = pytrends.related_queries()
        rising: list[str] = []
        for kw in seeds[:5]:
            block = related.get(kw) or {}
            df = block.get("rising")
            if df is not None and not df.empty:
                rising.extend(df["query"].head(5).tolist())
        return list(dict.fromkeys(rising))
    except Exception:
        # pytrends is unofficial and rate-limits/breaks often; degrade gracefully.
        return []


@dataclass
class RankingSignals:
    titles: list[str] = field(default_factory=list)
    # Real tags from the top videos: [(tag, num_videos_using_it)] most-common first.
    tag_counts: list[tuple[str, int]] = field(default_factory=list)


def ranking_signals(query: str, api_key: str, n: int = 10) -> RankingSignals:
    """Top-ranking videos for `query`: their titles + their ACTUAL tags.

    One search (~100 units) for ids+titles, then one videos.list (~1 unit) for the
    real `snippet.tags` of those public videos — the same data pro tools use. Falls
    back to scraping <meta name="keywords"> if the API tags call fails.
    """
    if not api_key or not query.strip():
        return RankingSignals()
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet", "q": query, "type": "video",
                "order": "relevance", "maxResults": min(max(n, 1), 25), "key": api_key,
                "relevanceLanguage": "en",
            },
            timeout=20,
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        ids = [it["id"]["videoId"] for it in items if it.get("id", {}).get("videoId")]
        titles = list(dict.fromkeys(it["snippet"]["title"] for it in items))[:n]
    except (requests.RequestException, KeyError):
        return RankingSignals()

    return RankingSignals(titles=titles, tag_counts=_video_tags(ids, api_key))


def _video_tags(video_ids: list[str], api_key: str) -> list[tuple[str, int]]:
    """Aggregate real tags across the given public videos (via API; scrape fallback)."""
    if not video_ids:
        return []
    counter: Counter = Counter()
    got_any = False
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "snippet", "id": ",".join(video_ids[:50]), "key": api_key},
            timeout=20,
        )
        r.raise_for_status()
        for it in r.json().get("items", []):
            for tag in it.get("snippet", {}).get("tags", []) or []:
                counter[tag.strip().lower()] += 1
                got_any = True
    except requests.RequestException:
        got_any = False

    if not got_any:  # API tags unavailable -> scrape the watch pages as a backup
        for vid in video_ids[:10]:
            for tag in _scrape_keywords(vid):
                counter[tag.strip().lower()] += 1
    return counter.most_common()


def _scrape_keywords(video_id: str) -> list[str]:
    try:
        html = requests.get(
            f"https://www.youtube.com/watch?v={video_id}",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15,
        ).text
        m = re.search(r'<meta name="keywords" content="([^"]*)"', html)
        if m:
            return [k.strip() for k in m.group(1).split(",") if k.strip()]
    except requests.RequestException:
        pass
    return []


def ranking_titles(query: str, api_key: str, n: int = 8) -> list[str]:
    """Back-compat shim: just the titles from ranking_signals."""
    return ranking_signals(query, api_key, n).titles


def research(transcript_text: str, cfg: dict, niche_hint: str = "") -> Research:
    n_seeds = cfg.get("autocomplete_seeds", 6)
    seeds = _keywords_from_text(f"{niche_hint} {transcript_text}", top=n_seeds)

    auto: list[str] = []
    for s in seeds:
        auto.extend(youtube_autocomplete(s))
    auto = list(dict.fromkeys(auto))

    rising = google_trends_rising(seeds) if cfg.get("trends", True) else []

    return Research(seeds=seeds, autocomplete=auto, rising=rising)
