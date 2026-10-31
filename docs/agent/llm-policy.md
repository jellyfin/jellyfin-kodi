# LLM and contribution policy

Upstream policy lives in the
[README's contributing section](https://github.com/jellyfin/jellyfin-kodi#contributing),
which points to Jellyfin's official LLM policy. The essentials for agents:

## Human review is mandatory and multi-stage

All PRs get manually reviewed. The submitter is expected to be intimately
familiar with the touched parts of the code — LLM-generated or not. Review
happens in several stages: self-review on commit, self-review at PR
creation, and maintainer review before merge. Plan changes so a human can
actually perform that review.

## Never write prose

PR bodies, comments, commit descriptions, issue text and similar are written
by the **human**, not the agent. Maintain review anything that reads as
LLM-written; such PRs are usually rejected outright on principle.

## Scope discipline

- **Do not touch unrelated parts of the code** unless explicitly asked.
- **Avoid build scripts, dependencies and CI.** Dependency bumps are handled
  by Renovate; the agent should not touch them. Even genuinely necessary
  changes there may be grounds for rejecting the changes — raise it in
  discussion instead.
- **No refactoring unless explicitly asked.** Refactors mixed into other work
  add review noise. A refactor is its own, explicitly requested task.
- **Prefer small, easily reviewed changesets.** Large changesets may need to
  be broken down into multiple staged PRs.

## Code quality expectations

- **black is a hard rule**: every commit must be properly formatted.
- flake8, mypy and SonarQube warnings require judgment — they may not always
  warrant action, but do not ignore them without a reason you can articulate.
- **Follow the existing code style.** Consistency with the codebase beats
  personal preference.
- The **Zen of Python** (`python -c 'import this'`) provides guiding
  principles, but does not override other explicit rules.
- **Maintainability — human ability to maintain the codebase — has a very
  high priority.** Optimize for the next human reader, not for cleverness or
  brevity of the diff.

## Where agents fit

LLM assistance is fine for debugging, research, and proof-of-concept work,
and for getting up to speed on the codebase. Production code has a high
probability of rejection if it looks low-effort. The burden of review falls
on maintainers, so the value of a change must be worth their time to verify.
