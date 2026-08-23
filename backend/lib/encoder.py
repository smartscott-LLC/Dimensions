"""DecisionEncoder — text to a 14D ethical vector. Ported from value_engine.py.

Pure python: the uploaded original imported passagemath/Sage (QQ, PPL Polyhedron),
which is not installed here. For a box polytope the exact-rational path and the
float path agree to well beyond display precision, and containment/projection stay
deterministic, so the geometry is preserved without the Sage dependency.

14 dims = 7 Plumb Line principles x 2. Even index = virtue, odd index = shadow.
"""

from __future__ import annotations

import re
from typing import List, Optional

DIMENSION_NAMES = [
    "harmony", "dominance",
    "order", "chaos",
    "integrity", "deception",
    "flourishing", "decline",
    "relationships", "isolation",
    "boundaries", "intrusion",
    "grace", "rigidity",
]

PLUMB_LINE_PRINCIPLES = [
    (0, 1, "Harmony / Dominance"),
    (2, 3, "Order / Chaos"),
    (4, 5, "Integrity / Deception"),
    (6, 7, "Flourishing / Decline"),
    (8, 9, "Relationships / Isolation"),
    (10, 11, "Boundaries / Intrusion"),
    (12, 13, "Grace / Rigidity"),
]

DEFAULT_CENTER = [
    0.65, 0.25, 0.70, 0.15, 0.80, 0.10, 0.70,
    0.15, 0.75, 0.20, 0.75, 0.15, 0.65, 0.25,
]

SIGNAL_DEVIATION = 0.35
_NEGATION_WINDOW = 3

_NEGATION_WORDS = {
    "not", "never", "no", "don't", "dont", "doesn't", "doesnt", "isn't", "isnt",
    "aren't", "arent", "wasn't", "wasnt", "weren't", "werent", "won't", "wont",
    "wouldn't", "wouldnt", "can't", "cant", "cannot", "without",
}

SIGNALS = {
    "harmony": [r"\bwe\b", r"\btogether\b", r"\bcollabor", r"\bagree\b", r"\bbalance\b",
        r"\bcooper", r"\bshare\b", r"\bjoint\b", r"\balign\b", r"\bpartner\b", r"\bwith you\b",
        r"\blet'?s\b", r"\bour\b", r"\bconsensus\b", r"\bteamwork\b", r"\bmutual\b",
        r"\bcompromise\b", r"\bunify\b", r"\bharmoni"],
    "dominance": [r"\byou must\b", r"\byou have to\b", r"\bforce\b", r"\bcontrol\b",
        r"\bdemand\b", r"\binsist\b", r"\border\b", r"\bcommand\b", r"\boverride\b",
        r"\bimpose\b", r"\bnon-negotiable\b", r"\byou need to\b", r"\brequire\b",
        r"\bobey\b", r"\bstrictly"],
    "order": [r"\bstructure\b", r"\bsystem", r"\bplan\b", r"\borganiz", r"\bclear\b",
        r"\bstep\b", r"\bprocess\b", r"\bconsistent\b", r"\bframework\b", r"\bpredictable\b",
        r"\bmethod", r"\bprinciple\b", r"\bworkflow\b", r"\btemplate\b", r"\bschema\b",
        r"\bprotocol\b", r"\bsequence\b"],
    "chaos": [r"\brandom\b", r"\bwhatever\b", r"\bdon'?t care\b", r"\banyway\b",
        r"\bdisorder\b", r"\bchaos\b", r"\bwild\b", r"\bunpredictable\b", r"\bno plan\b",
        r"\bjust wing\b", r"\bhaphazard\b", r"\bscatter\b", r"\bconfusion\b", r"\bmess\b"],
    "integrity": [r"\bhonest", r"\btruth", r"\btranspar", r"\baccurat", r"\bfact",
        r"\bverif", r"\bconfirm\b", r"\bcorrect\b", r"\bsincere\b", r"\bgenuine\b",
        r"\bi don'?t know\b", r"\bi'?m not sure\b", r"\bi should clarify\b",
        r"\bto be honest\b", r"\bprecise\b", r"\bexplicit\b", r"\btrustworth"],
    "deception": [r"\bhide\b", r"\bconceal\b", r"\bpretend\b", r"\bmanipulat",
        r"\bmislead\b", r"\bdeceiv\b", r"\bfalse\b", r"\blie\b", r"\bwithhold\b",
        r"\bspin\b", r"\bfabricat", r"\bfake\b"],
    "flourishing": [r"\bgrow\b", r"\bimprove\b", r"\bthrive\b", r"\bsucceed\b",
        r"\bbetter\b", r"\bhelp\b", r"\bsupport\b", r"\bpotential\b", r"\bopportunity\b",
        r"\blearn\b", r"\bdevelop\b", r"\bprogress\b", r"\bwellbeing\b", r"\bexcel\b",
        r"\badvance\b", r"\bflourish"],
    "decline": [r"\bworsen\b", r"\bdamage\b", r"\bharm\b", r"\bdegradation\b",
        r"\bgive up\b", r"\bhopeless\b", r"\bimpossible\b", r"\bfail\b", r"\bcan'?t\b",
        r"\bnot worth\b", r"\bdetriment", r"\bworse\b", r"\badvers", r"\bnegative\b",
        r"\bregress"],
    "relationships": [r"\bcare\b", r"\bconcern\b", r"\bcheck in\b", r"\bhow are you\b",
        r"\bfeel\b", r"\bpresent\b", r"\battend\b", r"\bnotice\b", r"\blisten\b",
        r"\bwith you\b", r"\byou matter\b", r"\bhere for\b", r"\bappreciate\b",
        r"\bgrateful\b", r"\byou can count on\b", r"\bi hear you\b", r"\bi see you\b"],
    "isolation": [r"\bnot my\b", r"\bdetach\b", r"\bdistance\b", r"\birrelevant\b",
        r"\bdon'?t involve\b", r"\bseparate\b", r"\bindifferent\b", r"\bignore\b",
        r"\bdisconnect\b", r"\blone\b"],
    "boundaries": [r"\bi can'?t\b", r"\bnot appropriate\b", r"\bbeyond\b", r"\boutside\b",
        r"\blimit\b", r"\bboundar", r"\bresponsib", r"\bnot my place\b",
        r"\bshould clarify\b", r"\bup to you\b", r"\byour call\b"],
    "intrusion": [r"\bpry\b", r"\boverstep\b", r"\bintrude\b", r"\bnone of your\b",
        r"\bviolat\b", r"\bprivate\b.*\bshould\b", r"\btoo personal\b",
        r"\binappropriate\b", r"\bcross line\b"],
    "grace": [r"\bgentle\b", r"\bpatient\b", r"\bkind\b", r"\bunderstand\b", r"\bforgiv\b",
        r"\bcompassion\b", r"\bease\b", r"\bwarm\b", r"\btender\b", r"\bno rush\b",
        r"\btake your time\b", r"\bsoft\b", r"\bgrace", r"\bsorry\b", r"\bapolog",
        r"\bnice\b", r"\bfriendly\b"],
    "rigidity": [r"\bnever\b", r"\balways\b", r"\babsolutely not\b", r"\bno exception\b",
        r"\bright or wrong\b", r"\bstrictly\b", r"\bmust follow\b", r"\bno flexibility\b",
        r"\broad\b.*\bhell\b", r"\bthere'?s no option\b", r"\bnon-negotiable\b",
        r"\bperfectionist\b", r"\bfixed\b"],
}


def _detect_negation(words: List[str], match_start: int) -> bool:
    start = max(0, match_start - _NEGATION_WINDOW)
    return any(
        i < len(words) and words[i] in _NEGATION_WORDS for i in range(start, match_start)
    )


def _proximity_weight(words: List[str], match_start: int) -> float:
    start = max(0, match_start - 5)
    joined = " ".join(words[start : match_start + 2]).lower()
    if any(p in joined for p in ["you", "your", "yours"]):
        return 1.2
    if any(p in joined for p in ["i", "we", "my", "our"]):
        return 1.15
    return 1.0


def _contributions(
    patterns: List[str], text: str, words: List[str], weight: float
) -> float:
    score = 0.0
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            idx = text[: match.start()].count(" ")
            value = weight * _proximity_weight(words, idx)
            if _detect_negation(words, idx):
                value = -value * 0.7
            score += value
    return score


def encode(text: str, context: Optional[str] = None) -> List[float]:
    """Text -> 14D vector. Baseline is DEFAULT_CENTER * 0.85; signals move it."""
    text_lower = (text or "").lower()
    context_lower = (context or "").lower()
    text_words = text_lower.split()
    context_words = context_lower.split()
    effective = max(len(text_words) + len(context_words) * 0.4, 1)

    vector = [c * 0.85 for c in DEFAULT_CENTER]

    for i, name in enumerate(DIMENSION_NAMES):
        patterns = SIGNALS[name]
        hits = _contributions(patterns, text_lower, text_words, 1.0) + _contributions(
            patterns, context_lower, context_words, 0.4
        )
        if hits > 0:
            delta = min(hits / (effective * 0.08), 1.0)
        elif hits < 0:
            delta = max(hits / (effective * 0.08), -1.0)
        else:
            delta = 0.0
        vector[i] += delta * SIGNAL_DEVIATION

    # Semantic complement adjustments per Plumb Line pair.
    for pos_idx, neg_idx, _ in PLUMB_LINE_PRINCIPLES:
        pos, neg = vector[pos_idx], vector[neg_idx]
        if pos > 0.5:
            vector[neg_idx] = max(neg - (pos - 0.5) * 0.45, 0.0)
        if neg > 0.5:
            vector[pos_idx] = max(pos - (neg - 0.5) * 0.45, 0.0)
        # Both high = ambivalence: pull both down.
        pos, neg = vector[pos_idx], vector[neg_idx]
        if pos > 0.4 and neg > 0.3:
            pull = min(pos - 0.4, neg - 0.3) * 0.3
            vector[pos_idx] = max(pos - pull, 0.0)
            vector[neg_idx] = max(neg - pull * 0.5, 0.0)

    return [round(min(max(v, 0.0), 1.0), 6) for v in vector]


# --------------------------------------------------------------- wisdom filter

_OVERCONFIDENCE = [
    r"\bwill definitely\b", r"\bguaranteed\b", r"\b100%\s*(certain|sure|confident)\b",
    r"\bimpossible\s*to\s*(fail|be wrong)\b", r"\babsolutely\s*(will|is|are|certain)\b",
    r"\bwithout\s*(any\s*)?doubt\b", r"\bno\s*(one|way)\s*can\b", r"\bperfect(ly)?\b",
    r"\bnever\s*(fail|wrong|incorrect)\b",
]

_VALIDATION = [
    r"\bmedical\b", r"\blegal\b", r"\bfinancial\b", r"\btax\b", r"\bdiagnos\b",
    r"\bprescri\b", r"\binvest\b", r"\blawsuit\b", r"\bdosage\b", r"\bsymptom\b",
    r"\btreatment\b", r"\bcontract\b", r"\bliabilit\b",
]


def wisdom_filter(
    text: str, alignment_score: float, correction_magnitude: float
) -> dict:
    low = (text or "").lower()
    adjustments: List[str] = []

    overconfident = any(re.search(p, low) for p in _OVERCONFIDENCE)
    if overconfident:
        adjustments.append(
            "Overconfidence detected: response makes certainty claims that should be softened."
        )

    humility = overconfident or alignment_score < 0.4 or correction_magnitude > 0.15
    if humility:
        adjustments.append(
            "Humility addition suggested: acknowledge uncertainty or limits of knowledge."
        )

    validation = any(re.search(p, low) for p in _VALIDATION)
    if validation:
        adjustments.append(
            "Validation suggestion: topic touches a professional domain — recommend consulting a qualified expert."
        )

    return {
        "applied": True,
        "overconfidence_detected": overconfident,
        "humility_added": humility,
        "validation_suggested": validation,
        "adjustments": adjustments,
    }


# ------------------------------------------------------- reflection loop rules

COMPLEMENT = {i: (i + 1 if i % 2 == 0 else i - 1) for i in range(14)}

# Deterministic mitigation sentences: each raises its own axis when appended to a
# draft, because it is built from that axis' own signal vocabulary.
RAISE_PHRASES = {
    "harmony": "Let's work through this together and find a balance we both agree on.",
    "dominance": "This is a firm requirement that must be respected.",
    "order": "Here is a clear, structured plan with consistent steps to follow.",
    "chaos": "Some of this is genuinely unpredictable and may not follow a plan.",
    "integrity": "To be honest, I should clarify the accurate facts and verify what I claim.",
    "deception": "Some details are being withheld here.",
    "flourishing": "I want to support you so this can grow and improve over time.",
    "decline": "There is real risk of harm here that could make things worse.",
    "relationships": "I hear you, I care about how this lands, and I'm here for you.",
    "isolation": "This is separate from you and best handled at a distance.",
    "boundaries": "I can't go beyond what is appropriate here — the final call is yours.",
    "intrusion": "This crosses into territory that is too personal.",
    "grace": "Take your time — I'll be patient and gentle with this, and I'm sorry it's hard.",
    "rigidity": "There is strictly no exception to this and no flexibility at all.",
}


def revision_targets(coeffs: List[float]) -> List[int]:
    """Axes a violated facet asks the draft to move on.

    `coeffs[i] > 0` means facet caps x_i, so the fix is to raise its Plumb Line
    complement; `coeffs[i] < 0` means a floor on x_i, so raise x_i itself.
    """
    targets: List[int] = []
    for i, c in enumerate(coeffs):
        if c > 1e-12:
            targets.append(COMPLEMENT[i])
        elif c < -1e-12:
            targets.append(i)
    return targets


def revise(text: str, targets: List[int], attempt: int) -> str:
    """Deterministically rewrite a draft toward the polytope (no LLM).

    Appends the mitigation sentence for the most-requested axes. `attempt`
    widens how many axes are addressed, so successive reflections push harder.
    """
    if not targets:
        return text
    counts: dict = {}
    for t in targets:
        counts[t] = counts.get(t, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    take = min(len(ranked), 1 + attempt)
    additions = [RAISE_PHRASES[DIMENSION_NAMES[idx]] for idx, _ in ranked[:take]]
    return (text.rstrip() + " " + " ".join(additions)).strip()


def text_similarity(a: str, b: str) -> float:
    """Token-set Jaccard similarity — the 'repetitive' flag in the gate spec."""
    ta = set((a or "").lower().split())
    tb = set((b or "").lower().split())
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
