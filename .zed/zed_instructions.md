# Repository Agent File: Polytope Security & Precision Core
**Directive**: Autonomous execution must adhere strictly to safety-critical standards, zero-placeholder principles, and deterministic boundaries.

## 1. Core Architectural Constraints
* **Zero Placeholders**: Never use `TODO`, `FIXME`, `// implement here`, or truncated code blocks. Write out every single line of production-ready logic, complete event handlers, and input validators.
* **Deterministic Enforcement**: Maintain absolute fidelity to the 14-dimensional geometric polytope constraints ($Ax \le b$). Never bypass the encoder, residual clamps, or dual-mode enforcement layers.
* **Strict Typing & Error Boundaries**: Enforce explicit Pydantic v2 schemas on the backend and strict TypeScript interfaces on the frontend. Wrap asynchronous IPC/API boundaries in secure try/catch blocks with graceful degradation.
* **Security-First Pipeline**: All changes must preserve cryptographic invariants, including MongoDB `w=majority` consistency, SHA-256 API key hashing, JWT denylist checks, and CSRF token validation.

## 2. Code Quality & Verification Gates
* **Syntax & Compiling**: Always run syntax validations and type checks (`python -m py_compile`, `pnpm typecheck`, and `python scripts/type_sync_check.py`) before completing any task.
* **Test Integrity**: Ensure all modifications maintain or expand the 145+ passing test suite. Any new logic requires corresponding unit and integration test coverage (`pytest tests/ -v`).
* **Clean State Management**: Prevent global scope leakage, uninitialized variables, or unhandled race conditions across FastAPI routers and React component trees.
* **Documentation Sync**: When modifying schema definitions, routing logic, or security headers, automatically update the living specification (`memory/SPEC.md`) and operational handoff (`memory/HANDOFF.md`) to reflect current state.