"""Geometric containment engine for P = { x in R^14 : Ax <= b }.

Pure python, no extra deps. Verification is a matrix residual; correction is
Dykstra's cyclic projection onto the intersection of half-spaces, which
converges to the *nearest* point of P (unlike plain POCS).
"""

from __future__ import annotations

DIMENSIONS = 14


def residuals(rows: list[list[float]], b: list[float], x: list[float]) -> list[float]:
    """r = Ax - b. r_i > 0 means constraint i is violated."""
    out: list[float] = []
    for i, row in enumerate(rows):
        s = 0.0
        for k in range(min(len(row), len(x))):
            s += row[k] * x[k]
        out.append(s - b[i])
    return out


def _project_halfspace(a: list[float], bi: float, z: list[float]) -> list[float]:
    s = sum(a[k] * z[k] for k in range(len(z))) - bi
    if s <= 0.0:
        return list(z)
    norm_sq = sum(v * v for v in a)
    if norm_sq == 0.0:
        return list(z)
    scale = s / norm_sq
    return [z[k] - scale * a[k] for k in range(len(z))]


def project(
    rows: list[list[float]],
    b: list[float],
    x: list[float],
    max_iter: int = 200,
    tol: float = 1e-9,
) -> tuple[list[float], int]:
    """Nearest point in P to x, via Dykstra's algorithm. Returns (point, iterations)."""
    n = len(x)
    cur = list(x)
    corrections = [[0.0] * n for _ in rows]
    iterations = 0
    for _ in range(max_iter):
        iterations += 1
        prev = list(cur)
        for i, row in enumerate(rows):
            a = list(row) + [0.0] * (n - len(row)) if len(row) < n else list(row[:n])
            z = [cur[k] + corrections[i][k] for k in range(n)]
            nxt = _project_halfspace(a, b[i], z)
            corrections[i] = [z[k] - nxt[k] for k in range(n)]
            cur = nxt
        if max(abs(cur[k] - prev[k]) for k in range(n)) < tol:
            break
    return cur, iterations


def euclidean(p: list[float], q: list[float]) -> float:
    return sum((p[k] - q[k]) ** 2 for k in range(len(p))) ** 0.5


def sample_vector(
    rows: list[list[float]],
    b: list[float],
    center: list[float],
    breach: bool,
    rng,
    jitter: float = 0.08,
    breach_scale: float = 0.45,
) -> list[float]:
    """Draw a vector near the profile centre.

    A permitted sample is projected into P and then blended 3% back toward the centre:
    because P is convex and the centre is interior, that blend is guaranteed feasible
    WITH slack. Scaling toward the origin instead would be wrong for any polytope with
    lower bounds (0 need not be in P).
    """
    n = len(center)
    if breach:
        # Push a handful of axes hard in a random direction — usually leaves P.
        raw = list(center)
        for idx in rng.sample(range(n), k=max(2, n // 3)):
            raw[idx] = center[idx] + rng.choice([-1.0, 1.0]) * rng.uniform(
                breach_scale, breach_scale * 2.2
            )
        return [round(v, 4) for v in raw]

    raw = [center[k] + rng.gauss(0.0, jitter) for k in range(n)]
    inside, _ = project(rows, b, raw)
    return [round(center[k] + 0.97 * (inside[k] - center[k]), 4) for k in range(n)]
