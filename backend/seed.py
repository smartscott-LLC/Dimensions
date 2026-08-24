"""Idempotent seed: constraint profiles + 12h of historical containment events.

Run: cd /app/backend && python seed.py
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

from lib.db import db
from lib.polytope import euclidean, project, residuals, sample_vector
from models.clients import Client, EngineSettings, hash_key
from models.containment import AuditEntry, Constraint, Dimension, Event, Profile

D = 14


def dim(i: int, label: str, unit: str = "normalised") -> Dimension:
    return Dimension(index=i, label=label, unit=unit, min=0.0, max=1.0)


def row(**kwargs: float) -> list[float]:
    coeffs = [0.0] * D
    for key, value in kwargs.items():
        coeffs[int(key[1:])] = value
    return coeffs


BIO_DIMS = [
    dim(0, "Toxicity Inference"),
    dim(1, "Synthesis Specificity"),
    dim(2, "Precursor Availability"),
    dim(3, "Pathogen Virulence"),
    dim(4, "Aerosolization Potential"),
    dim(5, "Dosage Lethality"),
    dim(6, "Reagent Concentration"),
    dim(7, "Protocol Completeness"),
    dim(8, "Equipment Accessibility"),
    dim(9, "Dual-Use Ambiguity"),
    dim(10, "Containment Bypass"),
    dim(11, "Genomic Modification Depth"),
    dim(12, "Population Exposure Scale"),
    dim(13, "Regulatory Evasion"),
]

BIO_CONSTRAINTS = [
    Constraint(label="Toxicity ceiling", coeffs=row(x0=1.0), b=0.35),
    Constraint(label="Synthesis specificity cap", coeffs=row(x1=1.0), b=0.40),
    Constraint(label="Precursor availability cap", coeffs=row(x2=1.0), b=0.45),
    Constraint(label="Virulence ceiling", coeffs=row(x3=1.0), b=0.30),
    Constraint(label="Aerosolization limit", coeffs=row(x4=1.0), b=0.25),
    Constraint(label="Dosage lethality limit", coeffs=row(x5=1.0), b=0.30),
    Constraint(label="Coupled toxicity/virulence", coeffs=row(x0=1.0, x3=1.0), b=0.50),
    Constraint(label="Actionable protocol coupling", coeffs=row(x7=1.0, x2=1.0), b=0.60),
    Constraint(label="Containment bypass veto", coeffs=row(x10=1.0), b=0.15),
    Constraint(label="Genomic modification depth", coeffs=row(x11=1.0), b=0.35),
    Constraint(label="Population exposure scale", coeffs=row(x12=1.0), b=0.20),
    Constraint(label="Regulatory evasion veto", coeffs=row(x13=1.0), b=0.10),
    Constraint(label="Dual-use / equipment coupling", coeffs=row(x9=1.0, x8=1.0), b=0.70),
    Constraint(label="Aggregate hazard budget", coeffs=[1.0] * D, b=3.20),
]

CLINICAL_DIMS = [
    dim(0, "Diagnostic Uncertainty"),
    dim(1, "Off-Label Deviation"),
    dim(2, "Dosage Deviation"),
    dim(3, "Contraindication Overlap"),
    dim(4, "Paediatric Risk"),
    dim(5, "Renal Load"),
    dim(6, "Hepatic Load"),
    dim(7, "Interaction Severity"),
    dim(8, "Data Fidelity Loss"),
    dim(9, "PHI Exposure"),
    dim(10, "Consent Gap"),
    dim(11, "Escalation Delay"),
    dim(12, "Cohort Exposure"),
    dim(13, "Protocol Drift"),
]

CLINICAL_CONSTRAINTS = [
    Constraint(label="Diagnostic certainty floor", coeffs=row(x0=1.0), b=0.20),
    Constraint(label="Dosage deviation cap", coeffs=row(x2=1.0), b=0.15),
    Constraint(label="Contraindication veto", coeffs=row(x3=1.0), b=0.10),
    Constraint(label="Paediatric risk cap", coeffs=row(x4=1.0), b=0.18),
    Constraint(label="Organ load budget", coeffs=row(x5=1.0, x6=1.0), b=0.55),
    Constraint(label="Interaction severity cap", coeffs=row(x7=1.0), b=0.25),
    Constraint(label="PHI exposure veto", coeffs=row(x9=1.0), b=0.05),
    Constraint(label="Consent gap veto", coeffs=row(x10=1.0), b=0.08),
    Constraint(label="Escalation latency cap", coeffs=row(x11=1.0), b=0.30),
    Constraint(label="Aggregate clinical risk", coeffs=[1.0] * D, b=2.40),
]

PERMISSIVE_DIMS = [dim(i, f"Test Axis {i + 1}") for i in range(D)]
PERMISSIVE_CONSTRAINTS = [
    Constraint(label=f"Axis {i + 1} soft cap", coeffs=row(**{f"x{i}": 1.0}), b=0.90)
    for i in range(D)
]

# --- 42-facet ethical lattice: 28 axis-aligned bounds + 14 coupling facets ----------
# Seven virtue/vice pairs. Each pair contributes a "lead" facet (virtue must dominate
# vice by L) and a "sum" facet (joint magnitude capped at S). L and S are derived from
# the nominal centre so every coupling facet carries an exact 0.10 margin there —
# which reproduces the framework's stated x2-x3 >= 0.35 / x2+x3 <= 1.05 (pair 1) and
# x4-x5 >= 0.50 / x4+x5 <= 1.10 (pair 3) figures.
LATTICE_PAIRS = [
    ("Truthfulness", "Deception", 0.70, 0.25),
    ("Beneficence", "Harm Potential", 0.75, 0.20),
    ("Integrity", "Manipulation", 0.80, 0.20),
    ("Transparency", "Obfuscation", 0.70, 0.25),
    ("Autonomy Respect", "Coercion", 0.75, 0.15),
    ("Fairness", "Bias Amplification", 0.70, 0.20),
    ("Accountability", "Evasion", 0.72, 0.22),
]
MARGIN = 0.10


def build_lattice() -> tuple[list[Dimension], list[Constraint], list[float]]:
    dims: list[Dimension] = []
    cons: list[Constraint] = []
    center: list[float] = []

    for p, (virtue, vice, cv, cc) in enumerate(LATTICE_PAIRS):
        vi, ci = 2 * p, 2 * p + 1
        dims.append(Dimension(index=vi, label=virtue, unit="normalised", min=0.0, max=1.0))
        dims.append(Dimension(index=ci, label=vice, unit="normalised", min=0.0, max=1.0))
        center.extend([cv, cc])

        # 4 axis-aligned facets per pair -> 28 total
        floor = round(cv - 0.15, 4)
        cap = round(cc + MARGIN, 4)
        cons.append(
            Constraint(label=f"{virtue} floor", coeffs=row(**{f"x{vi}": -1.0}), b=-floor)
        )
        cons.append(Constraint(label=f"{virtue} ceiling", coeffs=row(**{f"x{vi}": 1.0}), b=1.0))
        cons.append(Constraint(label=f"{vice} non-negative", coeffs=row(**{f"x{ci}": -1.0}), b=0.0))
        cons.append(Constraint(label=f"{vice} cap", coeffs=row(**{f"x{ci}": 1.0}), b=cap))

        # 2 coupling facets per pair -> 14 total
        lead = round((cv - cc) - MARGIN, 4)
        total = round((cv + cc) + MARGIN, 4)
        cons.append(
            Constraint(
                label=f"{virtue} leads {vice} by {lead}",
                coeffs=row(**{f"x{vi}": -1.0, f"x{ci}": 1.0}),
                b=-lead,
            )
        )
        cons.append(
            Constraint(
                label=f"{virtue}+{vice} sum <= {total}",
                coeffs=row(**{f"x{vi}": 1.0, f"x{ci}": 1.0}),
                b=total,
            )
        )

    return dims, cons, center


LATTICE_DIMS, LATTICE_CONSTRAINTS, LATTICE_CENTER = build_lattice()

PROFILES = [
    Profile(
        id="prof-ethical-lattice",
        name="Ethical Lattice (42-facet)",
        description="28 axis-aligned bounds + 14 inter-dimensional coupling facets across seven virtue/vice pairs. Every coupling facet carries a 0.10 margin at the nominal centre.",
        dimensions=LATTICE_DIMS,
        constraints=LATTICE_CONSTRAINTS,
        center=LATTICE_CENTER,
        active=True,
    ),
    Profile(
        id="prof-biochem-strict",
        name="Biochemical Non-Proliferation",
        description="Legacy preset — strict upper-bound containment for dual-use biochemical inference. 14 hazard axes, 14 half-spaces.",
        dimensions=BIO_DIMS,
        constraints=BIO_CONSTRAINTS,
        center=[0.10] * D,
    ),
    Profile(
        id="prof-clinical-safety",
        name="Clinical Decision Safety",
        description="Diagnostic and dosage containment for clinical advisory models.",
        dimensions=CLINICAL_DIMS,
        constraints=CLINICAL_CONSTRAINTS,
        center=[0.05] * D,
    ),
    Profile(
        id="prof-permissive-test",
        name="Permissive Test Mode",
        description="Wide half-spaces for engine benchmarking and latency profiling.",
        dimensions=PERMISSIVE_DIMS,
        constraints=PERMISSIVE_CONSTRAINTS,
        center=[0.40] * D,
    ),
]


def build_event(
    profile: Profile,
    created_at: datetime,
    breach: bool,
    client: Client | None = None,
) -> Event:
    rows = [c.coeffs for c in profile.constraints]
    thresholds = [c.b for c in profile.constraints]
    center = list(profile.center) or [d.min for d in profile.dimensions]

    vector = sample_vector(rows, thresholds, center, breach, random)

    res = residuals(rows, thresholds, vector)
    violated = [profile.constraints[i].label for i, r in enumerate(res) if r > 1e-12]

    projected = None
    iterations = 0
    magnitude = 0.0
    if violated:
        projected, iterations = project(rows, thresholds, vector)
        magnitude = euclidean(vector, projected)

    return Event(
        profile_id=profile.id,
        profile_name=profile.name,
        client_id=client.id if client else None,
        client_name=client.name if client else None,
        label=f"synthetic-{random.randint(1000, 9999)}",
        source=random.choice(["simulator", "simulator", "api"]),
        vector=vector,
        residuals=[round(r, 6) for r in res],
        max_residual=round(max(res), 6),
        status="corrected" if violated else "permitted",
        projected_vector=[round(v, 6) for v in projected] if projected else None,
        correction_magnitude=round(magnitude, 6),
        violated_constraints=violated,
        latency_ms=round(random.uniform(0.03, 0.62), 4),
        iterations=iterations,
        created_at=created_at,
    )


def demo_clients(now: datetime) -> list[Client]:
    """Generate demo clients with RANDOM keys (never hardcoded)."""
    specs = [
        (
            "gpt-5.2-triage",
            "Clinical triage assistant — pinned to the clinical polytope.",
            "prof-clinical-safety",
            "Clinical Decision Safety",
        ),
        (
            "claude-bio-assist",
            "Dual-use chemistry Q&A — held to the strict biochemical polytope.",
            None,
            None,
        ),
        (
            "internal-rag",
            "Internal document RAG — benchmarked against permissive bounds.",
            "prof-permissive-test",
            "Permissive Test Mode",
        ),
    ]
    out = []
    for idx, (name, desc, pid, pname) in enumerate(specs):
        # Generate RANDOM key - never hardcoded
        raw, prefix, hashed = mint_key()
        out.append(
            Client(
                id=f"client-{name}",
                name=name,
                description=desc,
                key_prefix=prefix,
                key_hash=hashed,
                profile_id=pid,
                profile_name=pname,
                # internal-rag ships with a tighter per-client override to demonstrate
                # that a client limit beats the engine default.
                rate_limit_per_min=30 if name == "internal-rag" else None,
                active=True,
                created_at=now - timedelta(hours=13, minutes=idx * 5),
                last_seen_at=now - timedelta(minutes=idx * 7 + 2),
            )
        )
    return out


async def main() -> None:
    await db.profiles.delete_many({})
    await db.events.delete_many({})
    await db.audit.delete_many({})
    await db.clients.delete_many({})
    await db.settings.delete_many({})

    await db.profiles.insert_many([p.model_dump() for p in PROFILES])

    now = datetime.now(timezone.utc)
    clients = demo_clients(now)
    client_docs = []
    for c in clients:
        doc = c.model_dump()
        doc["key_hash"] = c.key_hash  # excluded from model_dump; persist explicitly
        client_docs.append(doc)
    await db.clients.insert_many(client_docs)
    await db.settings.insert_one(
        EngineSettings(
            enforce_api_keys=False,
            rate_limit_enabled=True,
            rate_limit_default_per_min=120,
        ).model_dump()
    )

    by_id = {p.id: p for p in PROFILES}
    active = PROFILES[0]
    events = []
    for i in range(200):
        offset = timedelta(minutes=(200 - i) * 3.5)
        # ~12% of history predates key attribution, so "unattributed" is visible too.
        client = None if random.random() < 0.12 else random.choice(clients)
        profile = by_id.get(client.profile_id or "", active) if client else active
        events.append(
            build_event(profile, now - offset, random.random() < 0.32, client).model_dump()
        )
    await db.events.insert_many(events)

    audit = [
        AuditEntry(
            id=str(uuid.uuid4()),
            action="engine.bootstrap",
            detail="Containment engine initialised in R^14 with Dykstra projection kernel",
            actor="system",
            created_at=now - timedelta(hours=13),
        ),
        AuditEntry(
            action="profile.create",
            detail="created profile 'Biochemical Non-Proliferation'",
            actor="system",
            created_at=now - timedelta(hours=12, minutes=50),
        ),
        AuditEntry(
            action="profile.activate",
            detail="activated profile 'Biochemical Non-Proliferation'",
            actor="operator",
            created_at=now - timedelta(hours=12, minutes=40),
        ),
        AuditEntry(
            action="profile.update",
            detail="tightened 'Aerosolization limit' threshold 0.35 -> 0.25",
            actor="operator",
            created_at=now - timedelta(hours=6),
        ),
        AuditEntry(
            action="profile.create",
            detail="created profile 'Clinical Decision Safety'",
            actor="operator",
            created_at=now - timedelta(hours=3),
        ),
        AuditEntry(
            action="client.create",
            detail="issued API key pk_gpt52tri… to 'gpt-5.2-triage'",
            actor="operator",
            created_at=now - timedelta(hours=2, minutes=30),
        ),
        AuditEntry(
            action="client.create",
            detail="issued API key pk_claudebi… to 'claude-bio-assist'",
            actor="operator",
            created_at=now - timedelta(hours=2, minutes=20),
        ),
    ]
    await db.audit.insert_many([a.model_dump() for a in audit])

    corrected = sum(1 for e in events if e["status"] == "corrected")
    print(
        f"seeded {len(PROFILES)} profiles, {len(clients)} clients, "
        f"{len(events)} events ({corrected} corrected), {len(audit)} audit rows"
    )


if __name__ == "__main__":
    asyncio.run(main())
