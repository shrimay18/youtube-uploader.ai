"""Small shared helpers."""
from __future__ import annotations


def fit_tags(tags: list[str], limit: int = 500) -> list[str]:
    """Trim a tag list to YouTube's ~500-char total budget.

    YouTube limits the COMBINED length of all tags to 500 characters. Tags that
    contain spaces are wrapped in quotes by YouTube (which costs 2 extra chars),
    and tags are comma-separated. We greedily keep tags in order until the next
    one would blow the budget, so the most important tags (listed first) survive.
    """
    kept: list[str] = []
    used = 0
    for raw in tags:
        tag = str(raw).strip()
        if not tag:
            continue
        cost = len(tag)
        if " " in tag:
            cost += 2                     # quotes YouTube adds around multi-word tags
        if kept:
            cost += 1                     # comma separator
        if used + cost > limit:
            continue                      # skip this one, try the next (shorter) tag
        kept.append(tag)
        used += cost
    return kept
