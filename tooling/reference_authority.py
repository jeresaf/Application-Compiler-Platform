"""Replaceable test authority: host-injected sessions, grants and HMAC key. Not IAM."""
import copy
import hashlib
import hmac

from canonical_json import canonical_bytes
from changes import ChangeError, fingerprint


class ReferenceAuthority:
    def __init__(self, key, sessions, grants):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("Inject at least 32 bytes of authority key material")
        self._key = key
        self._sessions = copy.deepcopy(sessions)
        self._grants = copy.deepcopy(grants)
        self._revoked = set()

    def authenticate(self, session):
        principal = self._sessions.get(session)
        if principal is None:
            raise ChangeError("AUTHORITY", "Authentication failed.")
        return principal

    def _permitted(self, principal, request):
        return all(request["applicationId"] + ":" + scope in self._grants.get(principal, [])
                   for scope in request["requiredScopes"])

    def issue(self, session, request, now, lifetime=300):
        principal = self.authenticate(session)
        if principal == request["author"] or not self._permitted(principal, request):
            raise ChangeError("AUTHORITY", "Approval requires an independent reviewer with every required scope.")
        if type(now) is not int or type(lifetime) is not int or not 0 < lifetime <= 86400:
            raise ChangeError("AUTHORITY", "Invalid approval time or lifetime.")
        body = {"authority": "reference-hmac-v1", "principal": principal, "request": copy.deepcopy(request),
                "issuedAt": now, "expiresAt": now + lifetime}
        signature = hmac.new(self._key, canonical_bytes(body), hashlib.sha256).hexdigest()
        return {"body": body, "signature": signature}

    def revoke(self, proof):
        """Trusted authority administration only; not an unauthenticated endpoint."""
        self._revoked.add(fingerprint(proof, "proof"))

    def verify_historical(self, proof, request, committed_at):
        """Verify original signature/binding/time, not current grants or revocation."""
        try:
            body = proof["body"]
            signature = hmac.new(self._key, canonical_bytes(body), hashlib.sha256).hexdigest()
            if (not hmac.compare_digest(signature, proof["signature"]) or body["request"] != request
                    or not body["issuedAt"] <= committed_at < body["expiresAt"] or body["principal"] == request["author"]):
                raise ValueError()
            return {"principal": body["principal"], "proofDigest": fingerprint(proof, "proof"), "request": copy.deepcopy(request)}
        except (ValueError, KeyError, TypeError):
            raise ChangeError("AUTHORITY", "Historical approval signature or binding is invalid.") from None

    def verify(self, proof, request, now):
        try:
            if set(proof) != {"body", "signature"}:
                raise ValueError()
            body = proof["body"]
            expected = hmac.new(self._key, canonical_bytes(body), hashlib.sha256).hexdigest()
            if (not hmac.compare_digest(expected, proof["signature"]) or
                    set(body) != {"authority", "principal", "request", "issuedAt", "expiresAt"} or
                    body["authority"] != "reference-hmac-v1" or body["request"] != request or
                    type(now) is not int or not body["issuedAt"] <= now < body["expiresAt"] or
                    body["principal"] == request["author"] or not self._permitted(body["principal"], request) or
                    fingerprint(proof, "proof") in self._revoked):
                raise ValueError()
            return {"principal": body["principal"], "proofDigest": fingerprint(proof, "proof"),
                    "request": copy.deepcopy(request)}
        except (ValueError, TypeError, KeyError):
            raise ChangeError("AUTHORITY", "Approval is invalid, out of scope, expired, revoked or not independently reviewed.") from None
