# LLM and contribution policy

Upstream policy lives in the
[README's contributing section](https://github.com/jellyfin/jellyfin-kodi#contributing)
(local copy at `README.md`, but might be out of date),
which points to Jellyfin's official LLM policy. The essentials for agents:

## Human review is mandatory and multi-stage

All PRs get manually reviewed. The submitter is expected to be intimately
familiar with the touched parts of the code — LLM-generated or not. Review
happens in several stages: self-review on commit, self-review at PR
creation, and maintainer review before merge. Plan changes so a human can
actually perform that review.

## Never write prose

The **PR body itself must be human-written — never generated.** If a
generated description is wanted, the maintainer will ask an agent for it
themselves. The same applies to PR comments, issue text and similar. PRs
perceived as LLM-written are usually rejected outright on principle.

Automated commits are **not strictly forbidden**, but must be clearly marked
as such: concise commit messages, with an `Assisted-by:` trailer at the
bottom carrying model and agent information (user-agent style), for example:

    Assisted-by: some-agent/1.2.3 (model: vendor-model-name)

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
- flake8 and mypy run locally from the dev requirements — review their
  warnings and either address them or consciously dismiss them with a reason
  you can articulate.
- **SonarQube findings arrive as automated PR comments from CI**; there is
  no local setup for them. Treat them as what they are: "this might need
  extra scrutiny" — look at the flagged code and either fix it or be able to
  say why not. Do not restructure code solely to silence a linter.
- **Follow the existing code style.** Consistency with the codebase beats
  personal preference.
- **Code should be self-descriptive; comments are the exception, not the
  rule.** Never commit rubber-duck-debugging style comments narrating the
  reasoning or discovery process. A comment earns its place only by
  explaining something the code cannot (a non-obvious constraint, a
  workaround and why it exists, a version incompatibility).
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
