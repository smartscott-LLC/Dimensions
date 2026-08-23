"""Shared dual-mode enforcement core.

Both /api/gate (single draft) and /api/chat (live LLM turns) run drafts through this,
so the console and the chat coach can never drift apart on what "withheld" means.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from lib import encoder
from lib.polytope import euclidean, project, residuals
from models.containment import Profile

MODES = ("projection", "refusal")


def check(profile: Profile, vector: List[float]):
    rows = [c.coeffs for c in profile.constraints]
    thresholds = [c.b for c in profile.constraints]
    res = residuals(rows, thresholds, vector)
    violated_idx = [i for i, r in enumerate(res) if r > 1e-12]
    labels = [profile.constraints[i].label for i in violated_idx]
    return rows, thresholds, res, violated_idx, labels


def resolve_mode(
    requested: Optional[str], client_mode: Optional[str], engine_mode: str
) -> Tuple[str, str]:
    if requested in MODES:
        return requested, "request"
    if client_mode in MODES:
        return client_mode, "client"
    return (engine_mode if engine_mode in MODES else "projection"), "engine"


def evaluate(
    profile: Profile,
    text: str,
    context: str,
    mode: str,
    max_reflections: int,
) -> Dict[str, Any]:
    """Encode -> verify -> (project | reflect) -> decision. Pure, no I/O."""
    encoded = encoder.encode(text, context)
    rows, thresholds, res, violated_idx, labels = check(profile, encoded)
    max_res = max(res) if res else 0.0

    projected: Optional[List[float]] = None
    iterations = 0
    magnitude = 0.0
    if violated_idx:
        projected, iterations = project(rows, thresholds, encoded)
        magnitude = euclidean(encoded, projected)

    steps: List[Dict[str, Any]] = [
        {
            "attempt": 0,
            "text": text,
            "vector": [round(v, 6) for v in encoded],
            "max_residual": round(max_res, 6),
            "violated_constraints": labels,
            "feasible": not violated_idx,
            "correction_magnitude": round(magnitude, 6),
            "note": "original draft encoded" if violated_idx else "draft is inside P",
        }
    ]

    decision = "permitted"
    final_vector: Optional[List[float]] = [round(v, 6) for v in encoded]
    final_text: Optional[str] = text
    withheld_reason: Optional[str] = None
    suggested_rewrite: Optional[str] = None
    attempts = 1
    current_labels = labels
    current_magnitude = magnitude

    if violated_idx:
        if mode == "projection":
            decision = "corrected"
            final_vector = [round(v, 6) for v in projected] if projected else None
        else:
            draft = text
            feasible = False
            for attempt in range(1, max_reflections + 1):
                targets: List[int] = []
                for i in violated_idx:
                    targets.extend(encoder.revision_targets(profile.constraints[i].coeffs))
                revised = encoder.revise(draft, targets, attempt - 1)
                similarity = encoder.text_similarity(draft, revised)
                draft = revised
                attempts += 1

                vec = encoder.encode(draft, context)
                rows, thresholds, res, violated_idx, current_labels = check(profile, vec)
                step_res = max(res) if res else 0.0
                step_mag = 0.0
                if violated_idx:
                    proj, iters = project(rows, thresholds, vec)
                    step_mag = euclidean(vec, proj)
                    iterations += iters
                steps.append(
                    {
                        "attempt": attempt,
                        "text": draft,
                        "vector": [round(v, 6) for v in vec],
                        "max_residual": round(step_res, 6),
                        "violated_constraints": current_labels,
                        "feasible": not violated_idx,
                        "correction_magnitude": round(step_mag, 6),
                        "note": (
                            f"reflection {attempt}: revised draft entered P"
                            if not violated_idx
                            else f"reflection {attempt}: still outside P"
                            f" (similarity {similarity:.2f})"
                        ),
                    }
                )
                current_magnitude = step_mag
                if not violated_idx:
                    feasible = True
                    decision = "revised"
                    final_vector = [round(v, 6) for v in vec]
                    final_text = draft
                    suggested_rewrite = draft
                    break

            if not feasible:
                decision = "withheld"
                final_vector = None
                final_text = None
                suggested_rewrite = steps[-1]["text"]
                withheld_reason = (
                    f"draft remained outside the polytope after {max_reflections}"
                    f" reflection(s); {len(current_labels)} facet(s) still violated"
                )

    alignment = max(0.0, min(1.0, 1.0 - current_magnitude))
    return {
        "decision": decision,
        "encoded": [round(v, 6) for v in encoded],
        "residuals": [round(r, 6) for r in res],
        "max_residual": round(max_res, 6),
        "violated_constraints": labels,
        "final_vector": final_vector,
        "final_text": final_text,
        "suggested_rewrite": suggested_rewrite,
        "correction_magnitude": round(current_magnitude, 6),
        "alignment_score": round(alignment, 4),
        "attempts": attempts,
        "iterations": iterations,
        "steps": steps,
        "withheld_reason": withheld_reason,
        "wisdom": encoder.wisdom_filter(text, alignment, current_magnitude),
    }
