# Compatibility policy

## Jellyfin server

Supported range: **10.9 through the current stable release** (12.4 at time of
writing; check https://github.com/jellyfin/jellyfin/releases for the current
one), plus the **kodi-sync-queue plugin**. Direct server upgrades may skip
versions, so do not assume every intermediate release was ever deployed.

### OpenAPI specifications

Before touching code that talks to the Jellyfin API, consult the OpenAPI
spec for the versions involved:

- Latest stable: https://api.jellyfin.org/openapi/jellyfin-openapi-stable.json
- Older versions: https://api.jellyfin.org/openapi/stable/
- 10.9.0: https://api.jellyfin.org/openapi/stable/jellyfin-openapi-10.9.0.json

Check **both ends** of the supported range when adding or changing API usage:
what exists in 10.9, and what has changed or been removed by the current
stable release.

### Deprecation caveat

Some older, deprecated functionality may be **hidden from the OpenAPI spec
while still available in the server software** — Jellyfin hides endpoints as
part of deprecation-before-removal to steer new implementations away. So:

- Absence from the spec does not prove absence from the server.
- Do not build new functionality on deprecated/hidden endpoints.
- When fixing behavior against older servers, the spec may understate what is
  available — verify against real-world behavior before removing a fallback.

### Feature gating vs version checks

Prefer **feature detection** over version comparisons where feasible. Where
version-based gating is genuinely needed, follow the existing pattern used
for Kodi versions: centralize the check in a utility function and gate only
the minimal difference behind it — don't scatter raw version comparisons
through business logic.

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
