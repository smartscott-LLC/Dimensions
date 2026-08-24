# Polytope Containment Console — living spec

## What the app does
Configures and monitors a **14-dimensional geometric constraint engine**: a convex polytope
`P = { x ∈ R^14 : Ax ≤ b }`. Every AI state vector submitted is verified (`r = Ax − b`;
violation iff `max(r) > 0`) and, if it violates, projected to the nearest point of `P` using
Dykstra's cyclic projection onto half-spaces (`backend/lib/polytope.py`, pure python, no deps).
Every verification is persisted as a telemetry event; every config change as an audit entry.

## Data model (Mongo, string uuid ids)
- `profiles` — `Profile`: id, name, description, `dimensions[14]` (index/label/unit/min/max),
  `constraints[]` (id/label/`coeffs[14]`/b), `center[14]` (nominal operating point used for the
  margin readout), active, created_at, updated_at. Exactly one active.

## Lattice geometry
Facets are arbitrary linear inequalities, so both bounds and couplings are expressible:
- **Axis-aligned upper**: `x_i ≤ cap` → `coeffs[i] = 1`
- **Axis-aligned lower**: `x_i ≥ floor` → `coeffs[i] = -1, b = -floor`
- **Coupling (lead)**: `x_v − x_c ≥ L` → `coeffs[v] = -1, coeffs[c] = 1, b = -L`
- **Coupling (sum)**: `x_v + x_c ≤ S` → `coeffs[v] = coeffs[c] = 1, b = S`

`GET /api/profiles/{id}/margins` returns per-facet slack `b − a·centre` plus the normalised
distance `slack/‖a‖`, whether each facet is binding/violated, and the tightest facet. The seeded
**Ethical Lattice (42-facet)** profile is 28 axis bounds + 14 coupling facets over seven
virtue/vice pairs; L and S are derived from the centre so every coupling facet carries an exact
0.10 slack, which reproduces the framework's `x₂−x₃ ≥ 0.35` / `x₂+x₃ ≤ 1.05` and
`x₄−x₅ ≥ 0.50` / `x₄+x₅ ≤ 1.10` figures.

**Sampling caveat (important):** synthetic "permitted" vectors are drawn near the centre,
projected into P, then blended 3% back toward the centre — `lib/polytope.sample_vector`. Scaling
toward the origin is WRONG for any polytope with lower bounds, because 0 need not be in P.

## Dual-mode enforcement gate (`routers/gate.py`, `lib/encoder.py`)
- `POST /api/encode` — `{text, context}` → deterministic 14D vector + `dimension_names`
  (7 Plumb Line pairs; even index = virtue, odd = shadow). Signal-lexicon + negation +
  proximity weighting + complement damping. No LLM, no randomness.
- `POST /api/gate` — `{text, context, label, mode?, max_reflections?}`, honours `X-API-Key`,
  rate limits and profile pins exactly like `/contain`. Mode resolution:
  request → client `enforcement_mode` → engine `enforcement_mode` (reported as `mode_source`).
  - **projection**: infeasible draft is silently projected → decision `corrected`.
  - **refusal**: reflection loop — `encoder.revise()` appends deterministic mitigation
    sentences for the axes each violated facet asks to move (`revision_targets`), re-encodes,
    re-verifies, up to `max_reflections` (1..6). Feasible → `revised`; still outside P →
    `withheld` (nothing released, `withheld_reason` set).
  - Response carries the full reflection trace, wisdom-filter report (overconfidence /
    humility / professional-validation flags) and `alignment_score = 1 − ‖Δx‖`.
- Every gate call writes an `Event` with `source="gate"`, `status` = the decision,
  plus `mode` and `attempts`. Telemetry summary reports `withheld`/`revised`/`enforcement_mode`;
  the Event Log filters on all four statuses.
- Settings: `enforcement_mode` (`projection|refusal`), `max_reflections` on `EngineSettings`;
  per-client override via `PATCH /api/clients/{id}` (`enforcement_mode`, or
  `inherit_enforcement_mode: true`). UI: **Gate** tab (`components/GatePanel.tsx`).

## Coaching chat (`routers/chat.py`, `components/ChatCoach.tsx`)
Real LLM turns gated before release. `agnes-2.5-flash` via the OpenAI SDK with `LLM_API_KEY` and optional `LLM_API_BASE`/`LLM_MODEL` in backend/.env; history is
owned by Mongo and replayed into the prompt each turn, and the system prompt carries live
engine facts (profile name, facet count, axis labels, mode semantics) so the coach cannot
invent engine behaviour.
- `POST /api/chat/sessions` `{title, mode?}` (mode `projection|refusal|null=inherit`),
  `GET /api/chat/sessions`, `GET /api/chat/sessions/{id}/turns`,
  `GET /api/chat/sessions/{id}/export` (markdown audit artifact: per-turn decision, facets and
  reflection trace; downloaded from the Chat coach header),
  `POST /api/chat/sessions/{id}/message` `{text}` → `ChatTurn`. `X-API-Key` honoured for
  attribution, rate limits and profile pins; 404 unknown session, 422 bad mode, 502 model failure.
- The model draft goes through `lib/gatecore.evaluate` (shared with `/gate`): projection
  releases the corrected reply, refusal releases the reflection rewrite or withholds it entirely.
- Each turn stores decision, encoded + released vectors, violated facets, `why` (per-facet
  plain-English cause with the axes to raise), the reflection rewrite, wisdom notes and the raw
  draft; also written to `events` with `source="chat"`.
- Collections: `chat_sessions` (turns/withheld counters), `chat_turns`.
- UI: **Chat coach** tab — session list, gated thread (withheld replies show as refused), and a
  turn inspector with a 14D radar (draft vs released), why-it-tripped list and rewrite.

## Auth
**Console:** email + password with a 12 h HS256 JWT (`lib/auth.py`, `routers/auth.py`,
`frontend/src/lib/auth.tsx`). bcrypt hashes; `password_hash` is `Field(exclude=True)`. Token
lives in `localStorage["polytope.console.token"]` and rides an `Authorization: Bearer` header
added by `lib/api.ts` (a 401 clears it). `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` in
backend/.env; `bootstrap_admin()` seeds the admin on startup when `users` is empty.
- Routes: `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/password`,
  `GET /api/auth/users` (admin), `POST /api/auth/users` (admin),
  `POST /api/auth/users/{id}/toggle` (admin, cannot self-deactivate).
- Roles: **admin** = everything; **operator** = Gate / Chat coach / Simulator + read-only
  Constraints. Server-side guards: profile create/update/activate, client create/patch/rotate/
  revoke and `PUT /settings` require admin (403); `POST /simulate` requires any signed-in user.
  Clients + Access tabs are admin-only in the UI, Constraints renders read-only for operators.
- The **engine API** (`/contain`, `/gate`, `/chat/*`) is unchanged: `X-API-Key` only, no JWT.
- Working credentials: `memory/test_credentials.md`.

## Rate limiting (`lib/ratelimit.py`)
Sliding 60-second window. The events collection is the usage ledger, so there is no separate
counter to drift. Limit resolution: per-client override → engine default → unlimited when
disabled. `0` blocks a client outright. Over-limit `/contain` returns **429** with `Retry-After`;
allowed calls carry `X-RateLimit-Limit` / `X-RateLimit-Remaining`. Keyed clients and the
unattributed bucket are counted separately. Settings live on `EngineSettings`
(`rate_limit_enabled`, `rate_limit_default_per_min`), per-client via `PATCH /api/clients/{id}`
(`rate_limit_per_min`, or `inherit_rate_limit: true` to clear).
- `events` — `Event`: profile_id/name, label, source (`api|simulator|console`), `vector[14]`,
  `residuals[]`, max_residual, status (`permitted|corrected`), `projected_vector`,
  correction_magnitude, violated_constraints[], latency_ms, iterations, created_at.
- `audit` — `AuditEntry`: action (`profile.create|profile.update|profile.activate|engine.bootstrap|
  client.create|client.rotate|client.revoke|settings.update`), detail, actor, created_at.
- `clients` — `Client`: id, name, description, `key_prefix` (display only), `key_hash`
  (SHA-256, **never serialised** — `Field(exclude=True)`), `profile_id`/`profile_name` (optional
  pinned polytope), active, created_at, rotated_at, last_seen_at.
- `settings` — single doc `{id:"engine", enforce_api_keys: bool}`.
- `events` also carry `client_id` / `client_name` (null = unattributed).

## API keys / multi-tenant attribution
- `POST /api/contain` reads the **`X-API-Key`** header. Unknown or revoked key → 401. Missing key
  → 401 when enforcement is on, otherwise accepted and logged as *unattributed*.
- A key may **pin a profile**: that client is contained by its own polytope instead of the globally
  active one. `/simulate` spreads synthetic load across active clients and honours their pins.
- Keys are minted as `pk_<40 hex>`, hashed with SHA-256 at rest, and returned in plaintext
  exactly once (creation or rotation). Rotate also re-activates a revoked client.
- Routes: `GET/POST /clients`, `POST /clients/{id}/rotate`, `POST /clients/{id}/revoke`,
  `GET /clients/stats`, `GET/PUT /settings`.

## API (all on api_router under /api)
- `GET /profiles`, `GET /profiles/active`, `GET /profiles/{id}`, `POST /profiles`,
  `PUT /profiles/{id}`, `POST /profiles/{id}/activate`
- `POST /contain` — body `{vector[14], source, label}`, header `X-API-Key` optional → `Event`
  (422 if vector length ≠ 14, 401 on bad key / missing key under enforcement)
- `POST /simulate` — `{count 1..100, violation_probability 0..1}` → `{generated, corrected, events}`
- `GET /events?limit&status&source&client_id` (`client_id=unattributed` selects unkeyed calls),
  `GET /telemetry/summary` (includes `by_client`, `enforce_api_keys`, `client_count`),
  `GET /audit?limit`

## Key flows
1. **Overview** — KPI tiles (verifications, violation rate, mean ‖Δx‖, p99 latency, throughput),
   violation trend (12 h), latency histogram, most-breached half-spaces.
2. **Live monitor** — vector probe (14 inputs, `safe`/`breach` presets) POSTs `/contain` and shows
   status/residual/‖Δx‖; live stream list of recent events with per-axis bars.
3. **Polytope** — 2D slice of R^14: pick axis X/Y, feasible chamber polygon (half-plane clipping),
   hyperplane lines, plotted vectors + projection segments.
4. **Constraints** — activate a profile; edit constraint labels, `b` thresholds, full A rows
   (dialog) and the 14 dimension labels; commit writes an audit entry.
5. **Event log** — filter all/permitted/corrected + text search; row → per-axis generated vs
   projected detail.
6. **Audit** — timeline of configuration changes.
7. **Simulator** — header toggle posts `/simulate` every 4 s while on.
8. **Gate** — deterministic draft gate + engine mode / max-reflection controls.
9. **Chat coach** — gated LLM sessions, turn inspector, transcript export.
10. **Access** (admin) — issue console accounts, toggle accounts, change own password.
11. **Clients** — enforcement mode column (inherit/projection/refusal cycle); issue a key (name, description, pinned polytope) with a
   once-only reveal + copy; per-client KPI table (calls, violation rate, mean ‖Δx‖, p99, last seen);
   rotate / revoke / reissue; curl integration snippet. Event Log gains a client filter + column,
   and Overview gains a stacked "Attribution by client" chart.

## Seed (`cd /app/backend && python seed.py`, destructive + idempotent)
3 profiles: `prof-biochem-strict` "Biochemical Non-Proliferation" (ACTIVE, 14 half-spaces),
`prof-clinical-safety` "Clinical Decision Safety" (10), `prof-permissive-test`
"Permissive Test Mode" (14). 3 demo clients with fixed keys (see
`memory/test_credentials.md`): `gpt-5.2-triage` (pinned clinical), `claude-bio-assist`
(follows active), `internal-rag` (pinned permissive). Plus 200 events over the last ~12 h
(~25-35% corrected, ~12% deliberately unattributed) and 7 audit entries. Enforcement seeds **off**.
