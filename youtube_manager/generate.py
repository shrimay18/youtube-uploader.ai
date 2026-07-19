"""Generate metadata via the configured LLM.

Title strategy (per user design):
  1. RAW title  — model reads the transcript and writes one plain, accurate
     working title (what the video is actually about).
  2. RANKING    — search YouTube for that raw title, pull the top ~7-8 titles
     that currently rank for the topic.
  3. SEO title  — a "writer" drafts candidates using the raw title + ranking
     patterns + autocomplete/trends; a "judge" scores the best one and, if it
     falls short, the writer regenerates with the judge's feedback (a few rounds).
  4. BODY       — description, tags, hashtags, category, chapters, pinned
     comment (+ Shorts thumbnail hook), written to match the final title.
"""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field

from . import research as research_mod
from . import seo
from .providers import get_provider
from .providers.base import LLMProvider
from .transcribe import Transcript, naive_chapters
from .util import fit_tags


@dataclass
class Metadata:
    title_variants: list[str] = field(default_factory=list)
    title_options: list[dict] = field(default_factory=list)  # [{title, score, breakdown}]
    description: str = ""
    tags: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    category: str = ""
    category_id: str = "22"
    chapters: list[dict] = field(default_factory=list)
    pinned_comment: str = ""
    thumbnail_text: str = ""       # Shorts only
    # Title-flow diagnostics (surfaced in the preview so you can see the working).
    raw_title: str = ""
    ranking_titles: list[str] = field(default_factory=list)
    title_score: float = 0.0       # SEO score (0-100) of the chosen title
    title_critique: str = ""
    raw: dict = field(default_factory=dict)


# YouTube category name -> id (common subset).
CATEGORY_IDS = {
    "Film & Animation": "1", "Autos & Vehicles": "2", "Music": "10",
    "Pets & Animals": "15", "Sports": "17", "Travel & Events": "19",
    "Gaming": "20", "People & Blogs": "22", "Comedy": "23",
    "Entertainment": "24", "News & Politics": "25", "Howto & Style": "26",
    "Education": "27", "Science & Technology": "28",
}


# ---------------------------------------------------------------- prompts

_TITLER_SYSTEM = (
    "You are a world-class YouTube SEO title strategist. You write titles that rank in "
    "search AND earn the click, staying strictly on-brand and never using banned words. "
    "You study the titles that currently rank for the topic and adopt what works — their "
    "structure, hooks, specific references, keyword placement — WITHOUT copying them. "
    "Great titles are SPECIFIC, not generic: they front-load the exact searchable keyword, "
    "and add a concrete reference, number, year, or curiosity hook. You base everything "
    "strictly on the transcript and never invent a topic that isn't in it. "
    "Reply with one JSON object."
)

_BODY_SYSTEM = (
    "You are a world-class YouTube SEO copywriter. You write descriptions, tags and "
    "metadata that maximize search discoverability while matching the channel tone and "
    "never using banned words. You base everything strictly on the transcript. "
    "Reply with one JSON object."
)

_TOPIC_SYSTEM = (
    "You identify what a video is actually about, for YouTube SEO. You output the exact "
    "search phrase someone would type to find THIS video, plus the key entities. Reply "
    "with one JSON object."
)


def _extract_topic(provider: LLMProvider, transcript: Transcript) -> tuple[str, list[str]]:
    """One small LLM call: the precise search query + core topic terms for this video.

    Drives an ACCURATE ranking search (so we don't pull unrelated videos) and the
    relevance filter that drops off-topic competitor titles/tags.
    """
    prompt = (
        "From the transcript, identify what this video is ACTUALLY about.\n"
        "Return JSON:\n"
        '{\n'
        '  "search_query": "the concise phrase (3-8 words) someone types on YouTube to '
        'find THIS exact video — the core subject + key named entities (brands, schools, '
        'products, exams, people)",\n'
        '  "topic_terms": [8-14 lowercase key terms/entities central to the video — '
        'the specific names, brands, subjects it is about]\n'
        "}\n"
        "Base it STRICTLY on the transcript. Be specific, not generic.\n\n"
        f"TRANSCRIPT:\n{_represent(transcript.text, 9000)}"
    )
    try:
        d = provider.complete_json(_TOPIC_SYSTEM, prompt)
        q = str(d.get("search_query", "")).strip()
        terms = [str(t).strip().lower() for t in d.get("topic_terms", []) if str(t).strip()]
        return q, terms
    except Exception:
        return "", []


import re as _re


def _clean_line(text: str) -> str:
    """Strip stray markdown (**bold**, #, backticks) and surrounding quotes/space."""
    t = str(text or "").strip().strip('"').strip("'")
    t = _re.sub(r"[*`]+", "", t)          # bold/italic/code markers models sometimes add
    return t.strip()


def _represent(text: str, budget: int, windows: int = 14) -> str:
    """Represent the WHOLE transcript within a char budget.

    Short/medium videos pass through in full. Only very long transcripts are
    condensed — by taking evenly-spaced excerpts spanning start -> end, so the
    metadata reflects the entire video (not just the opening), without blowing up
    the token count.
    """
    text = text or ""
    if len(text) <= budget:
        return text
    win = max(300, budget // windows)
    step = (len(text) - win) / (windows - 1)
    parts = [text[int(i * step): int(i * step) + win] for i in range(windows)]
    return " […] ".join(parts)


def apply_fixed_description(desc: str, text: str, position: str) -> str:
    """Merge a user's fixed/boilerplate block into a generated description.

    top    -> before everything
    bottom -> at the very end
    auto   -> inserted before the trailing hashtags line so hashtags stay last and it
              reads naturally (verbatim — never paraphrased, so links stay intact).
    """
    text = (text or "").strip()
    if not text:
        return desc or ""
    desc = (desc or "").strip()
    if not desc:
        return text
    if position == "top":
        return f"{text}\n\n{desc}"
    if position == "bottom":
        return f"{desc}\n\n{text}"
    # auto
    lines = desc.split("\n")
    idx = len(lines) - 1
    while idx >= 0 and not lines[idx].strip():
        idx -= 1
    if idx >= 0 and lines[idx].strip().startswith("#"):
        before = "\n".join(lines[:idx]).rstrip()
        return f"{before}\n\n{text}\n\n{lines[idx].strip()}"
    return f"{desc}\n\n{text}"


def apply_fixed_comment(pinned: str, text: str, mode: str) -> str:
    """Combine the AI pinned comment with a user's fixed comment per the chosen mode."""
    text = (text or "").strip()
    pinned = (pinned or "").strip()
    if mode == "fixed":
        return text or pinned
    if mode == "integrate" and text:
        return f"{pinned}\n\n{text}" if pinned else text
    return pinned  # "ai" (default)


def _clean_description(text: str) -> str:
    """Tidy a model description for YouTube: no indentation, no markdown, single
    blank lines between paragraphs, and tight (unspaced) bullet lists."""
    raw = [ln.rstrip().lstrip(" \t") if ln.strip() else "" for ln in str(text or "").splitlines()]
    raw = [_re.sub(r"\*+", "", ln) for ln in raw]           # strip stray ** markdown
    out: list[str] = []
    for i, ln in enumerate(raw):
        if ln == "":
            if out and out[-1] == "":
                continue                                     # collapse 2+ blank lines -> 1
            nxt = next((l for l in raw[i + 1:] if l != ""), "")
            if out and out[-1].startswith("- ") and nxt.startswith("- "):
                continue                                     # no blank line between bullets
            out.append("")
        else:
            out.append(ln)
    return "\n".join(out).strip()


def _channel_block(profile: dict) -> dict:
    links = {k: v for k, v in (profile.get("links") or {}).items() if v}
    return {
        "niche": profile.get("niche"),
        "audience": profile.get("audience"),
        "tone": profile.get("tone"),
        "banned_words": [w for w in (profile.get("banned_words") or []) if w],
        "links": links,
        "default_cta": profile.get("default_cta"),
        "about": profile.get("about"),
    }


# ---------------------------------------------------------------- stages

def _titler(
    provider: LLMProvider, profile: dict, transcript: Transcript, research,
    ranking: list[str], kind: str, feedback: str | None,
) -> dict:
    """One LLM call: understand the video + write a reference title + 7 candidates.

    We DON'T ask the model to self-score — scoring is done locally against the
    ranking data (deterministic, free). Feedback from a low local score drives a
    regeneration round.
    """
    ctx = {
        "channel": _channel_block(profile),
        "video_format": "short" if kind == "short" else "long-form",
        "current_year": _dt.date.today().year,
        "titles_that_currently_rank_for_this_topic": ranking,
        "autocomplete_phrases": research.autocomplete[:30],
        "rising_trends": research.rising[:15],
        "transcript": _represent(transcript.text, 20000),
    }
    fb = f"\nThe previous titles scored low on SEO. {feedback}\n" if feedback else ""
    prompt = f"""
Read the transcript, study the titles that currently rank, and produce titles.{fb}
Return JSON with EXACTLY these keys:
{{
  "raw_title": "one plain, accurate description of what the video is actually about",
  "reference_title": "the single BEST title, synthesized from the winning patterns in
                      titles_that_currently_rank (specific, keyword-front-loaded)",
  "title_variants": [7 distinct titles, each 35-65 chars ideally (<=70 max), the exact
                     searchable keyword FRONT-loaded, matching the channel tone, no banned
                     words. Make them SPECIFIC — include concrete references, a number, a
                     year, or a curiosity hook. Avoid vague/generic titles.]
}}
Rules:
- Base titles STRICTLY on the transcript. Never invent a topic not in it.
- Learn only the STRUCTURE/keyword patterns from titles_that_currently_rank. NEVER
  borrow a specific hook, phrase, or claim from them that describes a DIFFERENT video
  (e.g. don't reuse "took years to film" unless the transcript actually says so).
- Weave in autocomplete_phrases / rising_trends naturally (these are real searches).
- Front-load the primary keyword. No banned_words. No misleading clickbait.
- If a title references a year, use current_year (never an older year).
- Output ONLY the JSON.

CONTEXT:
{json.dumps(ctx, ensure_ascii=False)}
""".strip()
    return provider.complete_json(_TITLER_SYSTEM, prompt)


def _final_title(
    provider, profile, transcript, research, ranking, kind,
    min_score: int, max_rounds: int, log=print,
) -> dict:
    """Generate candidates, score EACH locally, pick best; regenerate if weak.

    Returns {best, options:[{title,score,breakdown}], score, raw_title, reference_title}.
    """
    vocab = seo.ranking_vocabulary(ranking) if ranking else []
    primary = _primary_terms(profile, research)

    best_overall = {"best": "", "options": [], "score": -1, "raw_title": "", "reference_title": ""}
    feedback = None
    for attempt in range(1, max_rounds + 1):
        # QuotaExceeded intentionally propagates (aborts the draft cleanly).
        w = _titler(provider, profile, transcript, research, ranking, kind, feedback)
        cands = [_clean_line(v) for v in w.get("title_variants", []) if v]
        ref = _clean_line(w.get("reference_title", ""))
        if ref and ref not in cands:
            cands.insert(0, ref)
        raw_title = _clean_line(w.get("raw_title", ""))

        scored = []
        for t in cands:
            s, bd = seo.score_title(t, vocab, research.autocomplete, primary)
            scored.append({"title": t, "score": s, "breakdown": bd})
        scored.sort(key=lambda x: x["score"], reverse=True)
        top = scored[0]["score"] if scored else 0

        log(f"      round {attempt}: best SEO score {top}/100 -> {scored[0]['title']!r}" if scored else "      round: no titles")
        if top > best_overall["score"]:
            best_overall = {
                "best": scored[0]["title"] if scored else raw_title,
                "options": scored[:7],
                "score": top,
                "raw_title": raw_title,
                "reference_title": ref,
            }
        if top >= min_score:
            break
        # Feed the local scorer's insight back to the model.
        miss = [term for term, _ in vocab[:8] if term not in (scored[0]["title"].lower() if scored else "")]
        feedback = (
            "Make titles more specific and front-load these high-ranking keywords where "
            f"truthful: {', '.join(miss[:6])}. Add a concrete reference, number, or year."
        )
    return best_overall


def _primary_terms(profile: dict, research) -> list[str]:
    """Key phrases a strong title should contain — brand/entity terms + transcript seeds."""
    terms: list[str] = []
    about = f"{profile.get('niche','')} {profile.get('about','')}".lower()
    for brand in ("scaler school of technology", "delta education", "nset", "sst",
                  "scaler", "jee", "iit"):
        if brand in about:
            terms.append(brand)
    terms.extend(research.seeds[:6])
    # Dedupe, keep order.
    seen, out = set(), []
    for t in terms:
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def _write_body(
    provider: LLMProvider, profile: dict, transcript: Transcript, research,
    final_title: str, kind: str, fallback_chapters: list[dict],
) -> dict:
    ctx = {
        "channel": _channel_block(profile),
        "final_title": final_title,
        "video_format": "short" if kind == "short" else "long-form",
        "duration_seconds": round(transcript.duration),
        "transcript": _represent(transcript.text, 45000),
        "autocomplete_phrases": research.autocomplete[:40],
        "rising_trends": research.rising[:20],
        "auto_chapter_timestamps": fallback_chapters,
        "categories_available": list(CATEGORY_IDS.keys()),
    }
    prompt = f"""
The final title is fixed as final_title. Write the rest of the metadata to match it.
Return JSON with EXACTLY these keys:
{{
  "description": "A rich, well-structured, READABLE YouTube description (aim 1100-1800
     characters). Weave in natural keyword VARIATIONS (synonyms + related phrases from
     autocomplete_phrases) — do NOT repeat the same keyword or stuff keywords; every
     sentence must read naturally to a human. Structure it EXACTLY like this, separated
     by blank lines:
       - Lines 1-2: a keyword-rich hook that restates the topic (this shows in search).
       - Paragraph: 2-4 sentences of genuinely useful context about what the video covers.
       - 'Who this is for:' 1-2 lines naming the target viewer (from channel.audience),
         phrased with natural keyword variations.
       - 'What you'll learn:' 3-6 short bullet lines (start each with '- ') listing the
         concrete takeaways/things covered, working in real search keywords naturally.
       {'- Chapters: one M:SS Title line per chapter (first 0:00) — see the chapters rule below.' if kind == 'long' else '- (No chapters for a Short.)'}
       - A call-to-action line using the channel default_cta.
       - Links: one per line from channel.links (skip empty ones).
       - Last line: exactly 3 relevant hashtags.
     Use plain text with normal line breaks. NO markdown, NO leading indentation, NO '**'.",
  "tags": [20-30 lowercase search tags/phrases, most important first, mixing exact-match
           keywords, long-tail phrases, and broader terms. These will be blended with
           ranking-derived tags and packed to 450-500 chars.],
  "hashtags": [exactly 3, each starting with #],
  "category": one of categories_available,
  "chapters": {'''[one {{"time":"M:SS","title":"..."}} per DISTINCT topic or key QUESTION
     the video covers — use as MANY as the content naturally has (a video that covers 12
     topics gets ~12 chapters, one with 4 gets 4). Do not force a number and do not pad.
     Each chapter must be a real topic/question shift (e.g. "Is Scaler worth it?",
     "Placements & fees") — meaningful, NOT granular play-by-play of every sentence. Use
     auto_chapter_timestamps for timing; first chapter at 0:00; titles reflect the actual
     content at that point.''' if kind == 'long' else '[]'},
  "pinned_comment": "1-2 sentences that spark discussion, ending with a question aimed at
     the TARGET VIEWER described in channel.audience (usually someone CONSIDERING/PROSPECTIVE,
     not an existing insider). Ask something they can actually answer right now — e.g. their
     goal, doubt, or plan — NOT something that assumes they already have insider experience.",
  "thumbnail_text": "for shorts: a punchy 2-5 word on-screen hook (plain text, no markdown);
                     empty string for long-form"
}}
Rules: never use banned_words; weave in autocomplete_phrases / rising_trends; for shorts
chapters=[] and thumbnail_text is required. Output ONLY the JSON.

CONTEXT:
{json.dumps(ctx, ensure_ascii=False)}
""".strip()
    return provider.complete_json(_BODY_SYSTEM, prompt)


# ---------------------------------------------------------------- orchestrator

def generate(
    settings: dict, profile: dict, transcript: Transcript, research, kind: str,
    yt_api_key: str | None = None, log=print,
) -> Metadata:
    provider = get_provider(settings)
    rcfg = settings.get("research", {})
    tcfg = settings.get("title", {})

    # 1. Topic: what is this video about? -> accurate search query + relevance terms.
    topic_query, topic_terms = _extract_topic(provider, transcript)
    if topic_query:
        log(f"      topic: {topic_query!r}")

    # Terms used to judge whether ranking results are actually about THIS video.
    relevance_terms = set(topic_terms) | set(research.seeds) | {
        t for t in _primary_terms(profile, research)
    }
    relevance_terms = {w for term in relevance_terms for w in str(term).lower().split()}

    # 2. Ranking signals for the topic; drop results that aren't relevant.
    ranking: list[str] = []
    competitor_tags: list[tuple[str, int]] = []
    if rcfg.get("ranking_titles", True):
        query = topic_query or " ".join(research.seeds[:5]) or transcript.text[:80]
        sig = research_mod.ranking_signals(
            query, yt_api_key or "", n=rcfg.get("ranking_titles_count", 10)
        )
        ranking = [t for t in sig.titles if seo.shares_topic(t, relevance_terms)]
        competitor_tags = [(tag, c) for tag, c in sig.tag_counts
                           if seo.shares_topic(tag, relevance_terms)]
        if sig.titles:
            log(f"      ranking titles: {len(ranking)}/{len(sig.titles)} relevant; "
                f"competitor tags: {len(competitor_tags)}/{len(sig.tag_counts)} relevant")
        elif not yt_api_key:
            log("      (no YOUTUBE_API_KEY -> skipping ranking-title optimization)")

    # 2. SEO titles: generate candidates, score each locally, regenerate if weak.
    tf = _final_title(
        provider, profile, transcript, research, ranking, kind,
        min_score=int(tcfg.get("min_seo_score", 70)),
        max_rounds=int(tcfg.get("max_rounds", 2)),
        log=log,
    )
    final_title = tf["best"]
    raw_title = tf["raw_title"]
    log(f"      raw understanding: {raw_title!r}")
    log(f"      chosen title ({tf['score']}/100): {final_title!r}")

    # 3. Body metadata matched to the final title
    fallback = naive_chapters(transcript) if kind == "long" else []
    body = _write_body(provider, profile, transcript, research, final_title, kind, fallback)

    category = body.get("category", "People & Blogs")
    cat_id = CATEGORY_IDS.get(category, settings.get("defaults", {}).get("category_id", "22"))

    # 4. Tags: budget-split so THIS video's topic is represented, not just competitors.
    must = _primary_terms(profile, research)
    tagcfg = settings.get("tags", {})
    tags = seo.derive_tags(
        llm_tags=body.get("tags", []), ranking_titles=ranking,
        autocomplete=research.autocomplete, seeds=research.seeds,
        competitor_tags=competitor_tags, must_include=must, video_title=final_title,
        topic_terms=relevance_terms,
        max_chars=int(tagcfg.get("max_chars", 500)),
        video_min_chars=int(tagcfg.get("video_min_chars", 130)),
    )
    strong_ct = sum(1 for _, c in competitor_tags if c >= 2)
    log(f"      tags: {len(tags)} tags, {_tags_chars(tags)} chars "
        f"({strong_ct} proven competitor tags + reserved slice for this video's topic)")

    return Metadata(
        title_variants=[o["title"] for o in tf["options"]],
        title_options=tf["options"],
        description=_clean_description(body.get("description", "")),
        tags=tags,
        hashtags=body.get("hashtags", [])[:3],
        category=category,
        category_id=cat_id,
        chapters=body.get("chapters", []),
        pinned_comment=_clean_line(body.get("pinned_comment", "")),
        thumbnail_text=_clean_line(body.get("thumbnail_text", "")),
        raw_title=raw_title,
        ranking_titles=ranking,
        title_score=tf["score"],
        title_critique=tf.get("reference_title", ""),
        raw={"title_flow": tf, "body": body},
    )


def _tags_chars(tags: list[str]) -> int:
    return sum(len(t) + (2 if " " in t else 0) + (1 if i else 0) for i, t in enumerate(tags))
