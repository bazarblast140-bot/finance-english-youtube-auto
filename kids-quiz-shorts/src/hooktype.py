"""Hook typewriter timing. Grapheme clusters, not raw code points.

Devanagari conjuncts (क्ष, च्छ) and matras (कि, का, फ़े) stay in one step
so a frame never shows a dangling halant or a matra without its consonant.
Typing finishes by TYPE_SECONDS (inside 1.2–1.5s) so the line is fully
readable before the 2s hook is over.
"""
from __future__ import annotations

import unicodedata

# Last cluster lands here. 1.40s is inside the 1.2–1.5s window.
TYPE_SECONDS = 1.40
_LEAD = 0.04

# Devanagari virama (halant). A following consonant stays in the cluster.
_VIRAMA = "\u094d"


def grapheme_clusters(text: str) -> list[str]:
    """Extended grapheme clusters, including Indic virama + consonant (GB9c)."""
    clusters: list[str] = []
    buf = ""
    for ch in text or "":
        if not buf:
            buf = ch
            continue
        cat = unicodedata.category(ch)
        if cat in ("Mn", "Mc", "Me") or ch in ("\u200c", "\u200d"):
            buf += ch
            continue
        # Consonant (or independent letter) right after a halant: one conjunct.
        if buf.endswith(_VIRAMA) and cat.startswith("L"):
            buf += ch
            continue
        clusters.append(buf)
        buf = ch
    if buf:
        clusters.append(buf)
    return clusters


def cluster_time(index: int, count: int) -> float:
    """When cluster `index` becomes visible. Last one is at TYPE_SECONDS."""
    if count <= 1:
        return _LEAD
    return _LEAD + (TYPE_SECONDS - _LEAD) * index / (count - 1)


def visible_count(text: str, t: float) -> int:
    clusters = grapheme_clusters(" ".join((text or "").split()))
    n = len(clusters)
    shown = 0
    for i in range(n):
        if t + 1e-4 >= cluster_time(i, n):
            shown = i + 1
        else:
            break
    return shown


def visible_text(text: str, t: float) -> str:
    clusters = grapheme_clusters(" ".join((text or "").split()))
    return "".join(clusters[: visible_count(text, t)])
