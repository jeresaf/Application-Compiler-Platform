# Deployment-owned OIDC adapter fixture

`identity.ts` implements OAuth 2.0 authorization-code acquisition with PKCE S256,
state, nonce, bounded callback lifetime and an in-memory bearer token. Configure
it from deployment-owned code, call `callback()` on the redirect page and
`login()` for acquisition. Issuer discovery and token endpoints must share the
configured issuer origin; HTTPS is required except explicitly selected local
development. `clearIdentity()` signals logout, tenant switch and session change.
Expiry requires acquisition again; no token is persisted or embedded.

The deployment supplies client ID, redirect URI, scopes and the mapping of
untrusted ID-token claims to UI hints. Server authorization is authoritative.
This example does not establish production provider interoperability, refresh or a production identity assurance policy. RS256 ID-token signature,
issuer, audience, expiry, issued-at, nonce and optional access-token hash are
verified through issuer JWKS before hints are exposed. Those
remain deployment review obligations. Browser-test authorities must never be
used by this adapter or packaged in production.

Adopt this file as HUMAN_OWNED before regeneration. The compiler does not select
an issuer, infer permissions or manufacture a principal binding.
