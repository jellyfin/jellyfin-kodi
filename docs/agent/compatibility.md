# Compatibility policy

## Jellyfin server

Support is **tiered**:

- **Primary targets** — the latest patch releases of the current and
  previous stable major (right now **10.11.11 and 12.4**). These get the
  most care and scrutiny; check the OpenAPI spec for both before adding or
  changing API usage.
- **Best-effort floor: 10.9.0.** Servers down to the floor should keep
  working, but fixes for them are best-effort — do not let the floor block
  clean implementations targeting the primary versions.

The versioning dropped the `10.` prefix starting at 12. Direct server
upgrades may skip versions, so do not assume every intermediate release was
ever deployed. Also required: the **kodi-sync-queue plugin**.

### OpenAPI specifications

Before touching code that talks to the Jellyfin API, consult the OpenAPI
spec for the versions involved:

- Latest stable: https://api.jellyfin.org/openapi/jellyfin-openapi-stable.json
- Older versions: https://api.jellyfin.org/openapi/stable/
- 10.11.11 (primary target, previous major): https://api.jellyfin.org/openapi/stable/jellyfin-openapi-10.11.11.json
- 10.9.0 (best-effort floor): https://api.jellyfin.org/openapi/stable/jellyfin-openapi-10.9.0.json

Check **both primary targets** when adding or changing API usage: what
exists in 10.11, and what has changed or been removed by the current stable
release. When touching code paths that must honor the 10.9 floor, check that
spec too.

### Deprecation caveat

Some older, deprecated functionality may be **hidden from the OpenAPI spec
while still available in the server software** — Jellyfin hides endpoints as
part of deprecation-before-removal to steer new implementations away. So:

- Absence from the spec does not prove absence from the server.
- Do not build new functionality on deprecated/hidden endpoints.
- When fixing behavior against older servers, the spec may understate what is
  available — verify against real-world behavior before removing a fallback.

### Version checks (preferred over feature probing)

Prefer explicit **server version checks** over feature detection. The client
learns the server version during the initial connection (the auth flow
already fetches it), so comparing a few numbers against known
incompatibilities is essentially free, deterministic, and reliable. Probing
endpoints to detect features costs extra requests and is ambiguous — a
missing endpoint or key can mean "not supported", "renamed", "permission
denied", or a bug, and side-effectful endpoints cannot be probed safely at
all.

- Centralize version comparisons in a utility function and compare against
  the known-incompatibility list; gate only the minimal difference behind
  them. Don't scatter raw version comparisons through business logic.
- **Compare parsed numeric tuples, never version strings.** Lexicographic
  comparison is wrong across the board: `"10.11" < "10.9"` as strings, and
  the dropped `10.` prefix at 12 breaks naive parsing. Parse to `(major,
  minor, patch)` once, in one place.
- Version checks assume upstream Jellyfin. Forks or patched servers may
  report odd versions — decide explicitly how unknown versions behave
  (usually: newest known), rather than falling through accidentally.

### Response-shape tolerance (`dict.get` fallbacks)

The codebase relies heavily on `response.get("key") or default_value`. That
is a **tolerance mechanism for additive server changes, not a versioning
strategy** — fine for absorbing newly added optional fields, unreliable for
anything else:

- `or default_value` silently replaces **falsy** values (`0`, `False`, `""`,
  `None`, `[]`) with the default. Media metadata is full of meaningful zeros
  (run time ticks, index numbers, parent index numbers for specials). Prefer
  `response.get("key", default)` or an explicit presence check whenever the
  value can legitimately be falsy.
- Silent fallbacks hide real incompatibilities: a renamed or missing key
  yields subtly wrong synced data instead of an error, and nothing will
  catch it. For version-dependent behavior, prefer an explicit version
  check; if a fallback must stay, make it loud (log once) rather than
  permanently silent.
- When writing new code, consult the OpenAPI spec for whether a key is
  genuinely optional. Use `.get(key, default)` for spec-optional keys; do not
  blanket-copy the defensive style — every unconditional fallback destroys
  the signal of which accesses are version-sensitive and which are typos.
- See `docs/agent/testing.md`: silent fallbacks also mask broken test
  fixtures — the code under test happily takes defaults when a fixture key
  is misspelled, so the test passes while verifying nothing.

## The API client layer

The Jellyfin API client is **hand-written and embedded in the codebase** (a
large part of the project). It has a few too many abstraction layers that
would ideally be cleaned up over time, but:

- Maintain a layer between raw HTTP and the code that uses it; all endpoint
  URLs, auth headers, serialization, and version differences belong in that
  layer, not scattered through consumers (where feasible).
- Do not replace it with a generated OpenAPI client, and do not add new
  abstraction layers on top of the existing ones.

## Kodi

- Runtime is Kodi's bundled Python interpreter: **never add runtime
  dependencies** unless already shipped in Kodi's package repos. When in
  doubt, check the Kodi repos for what's available on the targeted Kodi
  versions.
- Kodi version differences are handled the same way as Jellyfin's: explicit
  version checks centralized in utility functions, gating minimal differences.
- `Kodistubs` (test dependency) tracks a specific Kodi API version (~21.0);
  the addon itself supports multiple Kodi versions. `typing_extensions` is
  pinned to a version available to the addon at runtime — don't bump it
  casually.
