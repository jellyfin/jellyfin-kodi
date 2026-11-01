# Testing policy

The suite runs with pytest (function-style tests, **no test classes**) via
`pytest` or `coverage run -m pytest`. CI runs the same suite on a matrix of
Python versions on Windows and Ubuntu.

## Core principle: end-to-end first, mock only at boundaries

The test suite exists to catch real regressions in behavior, not to maximize
coverage numbers. Prefer tests that exercise real code paths end to end.
Mocking is allowed **only at the project's external boundaries**:

1. **The Jellyfin HTTP layer** — the point where the hand-written API client
   talks to a server.
2. **The Kodi Python API** — the `xbmc*` modules Kodi injects at runtime.

Never mock, monkeypatch, stub, or intercept **internal** functions, methods,
modules, or attributes to isolate a piece of logic in the middle of the stack.
If a test can only be written by patching internals, that is a signal to
either test at a boundary instead, or to restructure the *idea* of the test —
not to patch harder.

### What this means in practice

- Do not use `unittest.mock.patch`, `monkeypatch.setattr`, or similar to
  replace functions inside `jellyfin_kodi/` with fakes.
- Do not construct elaborate fake object graphs to simulate collaborators.
- Do not write a test that re-states the implementation line by line; if
  removing the code under test wouldn't make the test fail meaningfully,
  the test adds no value.
- Every test must justify its CI runtime: a slow test needs to protect
  against a realistic failure mode. When in doubt, weigh what the test
  actually covers against what it costs the whole matrix.

## The two sanctioned boundaries

### Jellyfin HTTP layer

Two interception styles are acceptable:

1. **Local fake Jellyfin HTTP server** (e.g. `pytest-httpserver` or
   similar) — preferred for sync-logic tests. The full `requests` stack,
   client code, and response parsing run for real; only the remote server
   is replaced. Point the API client at `http://localhost:<port>`.
2. **Record/replay at the `requests` layer** (e.g. `responses` or
   `requests-mock` plus JSON fixtures) — acceptable for narrower cases.
   Real serialization/parsing code runs; only the socket is faked.

Spinning up a **real Jellyfin server** is for special cases only and is not
part of the standard test suite: a server requires configuration, media
files, and library scans to populate its own database, which is expensive
and complex. If you believe you need one, discuss with a maintainer first.

### Kodi Python API

`Kodistubs` (in `requirements-test.txt`) provides typing stubs only — it
provides **no functionality** and does not emulate Kodi behavior. Treat the
`xbmc*` modules as a boundary: tests may import them (stubs make imports
safe), but must not assume Kodi semantics behind them.

The Kodi database side is not currently testable against a real Kodi
instance (Kodi is a GUI application, and the addon does not know the full
SQL schema Kodi expects). Testing against a plain SQLite database — real
file or in-memory — is desirable future work but out of scope for now; do
not block on it and do not invent schema fakes.

## Unit tests: the narrow exception

Standalone utility functions may be tested in isolation. A function
qualifies if it depends only on the standard library or other utilities, and
needs testing to confirm it handles special inputs correctly. Current
examples: date parsing (already tested), path normalization (a known gap).

Everything else — sync logic, API client behavior, database handling —
should be tested end-to-end through the boundaries above.

## Fixtures and test assets

- There are few existing recorded Jellyfin API responses. Build fixtures by
  hand from the **OpenAPI spec** for the target versions (see
  `docs/agent/compatibility.md`) rather than capturing from a live server.
- Fixture key names must match the spec **exactly**: the codebase's silent
  `dict.get(...) or default` fallbacks will happily mask a misspelled
  fixture key — the code under test takes its defaults, the test passes,
  and it has verified nothing.
- Never include real API keys, tokens, or user data in fixtures.
- Keep inline fixtures minimal. Larger request/response templates belong in
  a test assets directory (e.g. `tests/assets/`) rather than inline in the
  test file.
- Some existing LLM-generated tests are slated for removal — do not treat
  them as style precedents.

## Dependencies and CI

- New test-only dependencies are a maintainer decision: propose it and ask
  first. PR acceptance additionally hinges on acceptance of the new
  dependency.
- **Never modify CI** (`.github/workflows/`). If a test requires CI
  changes, it will likely not be accepted — even if submitted disabled or
  skipped. Tests that cannot run in the existing CI setup should be raised
  in discussion with a maintainer, not sneaked in behind markers.
