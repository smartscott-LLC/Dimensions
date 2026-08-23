# Polytope Containment Console — handoff

Everything needed to run, test, operate and extend this app. Deeper design notes live in
`memory/SPEC.md`; logins live in `memory/test_credentials.md`.

Live preview: https://blue-telemetry.preview.emergentagent.com

---

## 1. What it is

A 14-dimensional geometric containment engine plus its operations console.

- A convex polytope `P = { x ∈ R¹⁴ : Ax ≤ b }` defines allowed AI behaviour.
- Verification: `r = Ax − b`, violated iff `max(r) > 0`.
- Correction: `x* = argmin_{x∈P} ‖x − x_gen‖²` via Dykstra cyclic projection onto half-spaces
  (pure Python, no numpy/scipy dependency).
- Seeded active lattice: **Ethical Lattice (42-facet)** = 28 axis bounds + 14 coupling facets
  over 7 virtue/shadow pairs (harmony/dominance, order/chaos, integrity/deception,
  flourishing/decline, relationships/isolation, boundaries/intrusion, grace/rigidity).
- A deterministic **text → 14D encoder** (ported from your SageMath `value_engine.py`; no LLM,
  no randomness) turns prose into a vector.
- **Dual-mode enforcement**: *projection* silently corrects, *refusal* runs a deterministic
  reflection loop and withholds the reply if it never enters P.
- **Chat coach**: real Claude Sonnet 4.5 replies, gated by the same engine, with a teaching
  inspector (14D radar, why it tripped, suggested rewrite) and transcript export.

## 2. Sign in

| role | email | password | can do |
|---|---|---|---|
| admin | `admin@polytope.console` | `Prussian#42Blue` | everything |
| operator | `ops@polytope.console` | `Khaki#514Ops` | Gate, Chat coach, Simulator, read-only Constraints |

Console = email/password + 12 h JWT. Engine API = `X-API-Key` (unchanged by console login).

## 3. Tabs

1. **Overview** — KPIs, violation trend, latency histogram, most-breached facets, attribution.
2. **Live monitor** — 14-input vector probe + live event stream.
3. **Gate** — paste a draft, pick mode, see decision + reflection trace + wisdom filter; set the
   engine-wide mode and max reflections here.
4. **Chat coach** — sessions with the gated agent; per-turn inspector; **Export transcript**.
5. **Polytope** — 2D slice explorer with feasible chamber, hyperplanes, projection segments.
6. **Constraints** — activate/edit profiles, facet `b` values, full A rows, axis labels; margins.
7. **Clients** (admin) — API keys, per-client rate limits, per-client enforcement mode, stats.
8. **Access** (admin) — issue/deactivate console accounts, change own password.
9. **Event log** — filter permitted / corrected / revised / withheld, by client, text search.
10. **Audit** — every configuration change.

## 4. API (all under `/api`)

Engine (machine clients, `X-API-Key` header):
```
POST /api/contain                  {vector[14], source, label}      -> Event
POST /api/encode                   {text, context}                  -> 14D vector
POST /api/gate                     {text, context, mode?, max_reflections?} -> decision + trace
POST /api/chat/sessions            {title, mode?}                   -> ChatSession
POST /api/chat/sessions/{id}/message  {text}                        -> ChatTurn (gated reply)
GET  /api/chat/sessions/{id}/turns | /export
```
Telemetry (read): `GET /api/telemetry/summary`, `/events`, `/audit`, `/profiles`,
`/profiles/active`, `/profiles/{id}/margins`, `/clients`, `/clients/stats`, `/settings`.

Admin-only (JWT, 403 otherwise): `POST/PUT /profiles*`, `POST /profiles/{id}/activate`,
`POST /clients`, `PATCH /clients/{id}`, `POST /clients/{id}/rotate|revoke`, `PUT /settings`,
`GET/POST /auth/users`, `POST /auth/users/{id}/toggle`. Signed-in (any role): `POST /simulate`.

Example:
```bash
curl -X POST https://blue-telemetry.preview.emergentagent.com/api/gate \
  -H 'Content-Type: application/json' \
  -d '{"text":"You must obey, this is non-negotiable.","mode":"refusal"}'
```

## 5. Layout

```
backend/
  server.py              FastAPI app; every route on api_router (/api); include last
  lib/polytope.py        residuals / Dykstra projection / sampling  (pure python)
  lib/encoder.py         deterministic text -> 14D + revise() + wisdom filter
  lib/gatecore.py        shared dual-mode decision core (gate + chat)
  lib/ratelimit.py       sliding 60 s window, events collection as ledger
  lib/auth.py            bcrypt + JWT + role dependencies + admin bootstrap
  models/                containment.py, clients.py, gate.py, chat.py, auth.py
  routers/               containment.py, clients.py, gate.py, chat.py, auth.py
  seed.py                profiles, demo clients, ~200 events, audit entries
frontend/src/
  lib/api.ts             typed fetch, relative /api, Bearer token attach
  lib/types.ts           hand-written mirrors of every Pydantic model
  lib/queries.ts         TanStack Query hooks
  lib/auth.tsx           AuthProvider / useAuth
  pages/                 Dashboard.tsx, Login.tsx
  components/            GatePanel, ChatCoach, AccessPanel, ClientsPanel, PolytopeExplorer,
                         ConstraintEditor, MarginPanel, EventLog, AuditTrail, KpiBar, ...
memory/                  SPEC.md (living spec), test_credentials.md, PRD/handoff docs
```

Mongo collections: `profiles`, `events`, `audit`, `clients`, `settings`, `chat_sessions`,
`chat_turns`, `users`.

## 6. Environment (`backend/.env`)

| var | purpose |
|---|---|
| `MONGO_URL`, `DB_NAME` | database |
| `CORS_ORIGINS` | allowed origins |
| `EMERGENT_LLM_KEY` | Claude Sonnet 4.5 for the chat coach (credits deduct from your balance) |
| `JWT_SECRET` | console session signing key |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | seeded admin, applied only when `users` is empty |

Frontend calls relative `/api` paths — nothing to configure.

## 7. Operating

```bash
sudo supervisorctl status                 # backend | frontend | mongodb
sudo supervisorctl restart backend        # after .env or dependency changes only
cd /app/backend && python seed.py         # reseed engine demo data (destructive)
cd /app/frontend && yarn typecheck        # Pydantic <-> TS drift check
tail -f /var/log/supervisor/backend.err.log
```

Rotate the seeded admin password from **Access → Change my password** before real use, and
change `JWT_SECRET` if this ever leaves the sandbox.

## 8. Known limits / good next steps

- Chat replies are non-streaming by design: the full draft must exist before it can be gated.
- The reflection rewrite is deterministic (appends mitigation sentences from the axis lexicon);
  it repairs tone-level breaches, not deeply unsafe content.
- Refusal analytics (withheld vs revised over time) are in the event log but not yet charted.
- Audit entries from the console are attributed to `operator`/actor email on auth actions only —
  wiring the signed-in email into every config change is a small, useful follow-up.
- No password-reset email flow; an admin issues a temporary password instead.
