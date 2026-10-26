"""Conservative classification of citing works into evidence-synthesis classes.

A label is a guess about what kind of document a citing work is. It never
says whether the retracted trial was *included in an analysis*; that needs
checking against the review's included-studies list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

GUIDELINE = "guideline"
META_ANALYSIS = "meta_analysis"
SYSTEMATIC_REVIEW = "systematic_review"
OTHER = "other"
SYNTHESIS_CLASSES = (GUIDELINE, META_ANALYSIS, SYSTEMATIC_REVIEW)

_META = re.compile(r"\bmeta[\s-]?(?:analys[ie]s|analytic|regression)\b", re.I)
_SR = re.compile(r"\bsystematic(?:al)?\s+(?:literature\s+)?review\b|\bumbrella\s+review\b", re.I)
_GUIDE = re.compile(
    r"\b(?:clinical\s+practice|practice|treatment|management|evidence[\s-]based)\s+guidelines?\b"
    r"|^guidelines?\b|\bguidelines?\s+(?:for|on)\b|\bconsensus\s+(?:statement|guideline|recommendations?)\b",
    re.I,
)
# Titles about guidelines rather than guidelines themselves.
_ABOUT_GUIDE = re.compile(r"\b(?:adherence|compliance|concordance)\s+(?:to|with)\b|\bappraisal\s+of\b", re.I)

PUBMED_GUIDELINE_TYPES = {"practice guideline", "guideline", "consensus development conference"}
PUBMED_META_TYPES = {"meta-analysis", "network meta-analysis"}
PUBMED_SR_TYPES = {"systematic review"}


@dataclass
class Classification:
    label: str
    confidence: str  # "high" (indexer publication type) or "medium" (title pattern) or "low"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"label": self.label, "confidence": self.confidence, "reasons": self.reasons}


def classify(title: str | None, openalex_type: str | None = None, pubmed_types: list[str] | None = None) -> Classification:
    pub = {t.strip().lower() for t in (pubmed_types or [])}
    if pub & PUBMED_GUIDELINE_TYPES:
        return Classification(GUIDELINE, "high", [f"PubMed publication type: {sorted(pub & PUBMED_GUIDELINE_TYPES)[0]}"])
    if pub & PUBMED_META_TYPES:
        return Classification(META_ANALYSIS, "high", [f"PubMed publication type: {sorted(pub & PUBMED_META_TYPES)[0]}"])
    if pub & PUBMED_SR_TYPES:
        return Classification(SYSTEMATIC_REVIEW, "high", ["PubMed publication type: systematic review"])

    text = title or ""
    if _GUIDE.search(text) and not _ABOUT_GUIDE.search(text):
        return Classification(GUIDELINE, "medium", [f"title matches guideline pattern: {_GUIDE.search(text).group(0)!r}"])
    if _META.search(text):
        return Classification(META_ANALYSIS, "medium", [f"title matches: {_META.search(text).group(0)!r}"])
    if _SR.search(text):
        return Classification(SYSTEMATIC_REVIEW, "medium", [f"title matches: {_SR.search(text).group(0)!r}"])
    reasons = ["no synthesis pattern in title"]
    if openalex_type == "review":
        reasons.append("OpenAlex type 'review' (often narrative; not counted as a synthesis)")
    return Classification(OTHER, "low", reasons)
