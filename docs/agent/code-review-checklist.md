# Pre-completion checklist

Run through this before claiming a task is complete. If any answer is "no",
fix it or explain why in your handoff to the human.

## Code

- [ ] Every commit is **black-formatted** (hard rule).
- [ ] flake8 / mypy warnings reviewed and addressed or consciously dismissed.
      SonarQube findings usually arrive later as automated PR comments —
      expect them as "might need extra scrutiny" prompts, not mandates.
- [ ] No changes to unrelated code, build scripts, dependencies, or CI.
- [ ] No refactoring or style-only changes mixed in — only what the task
      asked for.
- [ ] No rubber-duck-debugging comments; comments only where the code cannot
      speak for itself.
- [ ] Automated commits are concise and marked with an `Assisted-by:`
      trailer.
- [ ] The diff is as small as it can be while doing the job; if it grew
      large, it should be split into staged PRs.
- [ ] Existing code style followed; new code prioritizes human
      maintainability.
- [ ] The human submitter could explain every line of this diff. If they
      couldn't, restructure the change.

## Jellyfin / Kodi compatibility

- [ ] API usage checked against the OpenAPI spec for **both primary targets**
      (latest patch of current and previous stable major), and against the
      10.9 best-effort floor where applicable (see
      `docs/agent/compatibility.md`).
- [ ] No new runtime dependencies (Kodi-bundled Python constraint); any new
      test dependency proposed to a maintainer first.
- [ ] Version checks centralized in utility functions, not scattered
      comparisons.

## Tests

- [ ] Mocking happens only at project boundaries (Jellyfin HTTP layer, Kodi
      Python API) — no internal monkeypatching (see `docs/agent/testing.md`).
- [ ] Tests are function-style, not class-style.
- [ ] Each new test would fail meaningfully without the code it covers, and
      its CI runtime is justified by what it protects.
- [ ] Fixtures hand-built from the OpenAPI spec; no real API keys or user
      data; large templates in the test assets directory.
- [ ] `pytest` (ideally `coverage run -m pytest`) passes locally.

## Handoff

- [ ] PR description, comments, and other prose are left for the human.
- [ ] Anything the agent was unsure about is flagged for the human, not
      silently decided.
