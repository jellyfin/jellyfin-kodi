# AGENTS.md — agent instructions for jellyfin-kodi

jellyfin-kodi is a Kodi addon that syncs a Jellyfin library into Kodi's
database, enabling native browsing and playback. It bundles a hand-written
Jellyfin HTTP API client and the sync/mapping logic built on top of it.
**Human maintainability is the highest priority for all code.**

## Environment

- Python 3.8+. Dev setup: `pip install -r requirements-dev.txt` (which pulls in
  `requirements-test.txt`) or `uv pip install -r requirements-dev.txt`.
- Runtime is Kodi's bundled Python interpreter: **never add runtime
  dependencies** unless one is already shipped in Kodi's package repos.
  Test-only dependencies are also a maintainer decision — ask first.
- Tests: `pytest` (or `coverage run -m pytest` for the CI-equivalent run).
- Formatting: **black is mandatory** before every commit. flake8, mypy and
  SonarQube warnings are advisory — judge whether they warrant action.

## Layout

- `jellyfin_kodi/` — most of the source code.
- Root `*.py` — addon entrypoints (excluding `build.py`).
- `addon.xml` is generated from `.build/template.xml` via `build.py` using
  `release.yaml`; do not hand-edit generated files.
- `tests/` — pytest suite.
- `.github/workflows/`, dependency files, build scripts — off limits (see
  `docs/agent/llm-policy.md`).

## Read before working

- `docs/agent/testing.md` — testing strategy and mock policy. **Read this
  before writing any test.**
- `docs/agent/compatibility.md` — Jellyfin and Kodi version support rules,
  OpenAPI spec usage.
- `docs/agent/llm-policy.md` — contribution rules and the project's LLM policy.
- `docs/agent/code-review-checklist.md` — run through before claiming a task
  is complete.

## Hard rules (details in the linked docs)

1. **The PR body is human-written, never generated.** Automated commits are
   permitted but must be concise and clearly marked with an `Assisted-by:`
   trailer (see `docs/agent/llm-policy.md`).
2. **black-format every commit.** This is non-negotiable.
3. **No refactoring unless explicitly asked.** Do not mix refactors into
   unrelated work — it adds review noise.
4. **Do not touch dependencies, CI, or build scripts.** Renovate handles
   dependency bumps; even necessary changes there may be grounds for rejection.
5. **Keep changesets small** and easily reviewed. Large work should be broken
   into staged PRs.
6. **Tests: mock only at project boundaries** (the Jellyfin HTTP layer and the
   Kodi Python API) — never monkeypatch internals to isolate mid-stack code.
   Tests are function-style, not class-style. See `docs/agent/testing.md`.
7. **Jellyfin support is tiered**: primary focus on the latest patch of the
   current and previous stable major (10.11.11 and 12.4 at time of writing;
   the "10." prefix was dropped at 12), with a best-effort floor of 10.9.0.
   Check the OpenAPI spec for the versions you target before touching API
   code. See `docs/agent/compatibility.md`.
8. **Follow the existing code style.** Zen of Python is a guiding principle,
   but does not override explicit rules. Code should be self-descriptive;
   comments are the exception — no rubber-duck-debugging comments.
