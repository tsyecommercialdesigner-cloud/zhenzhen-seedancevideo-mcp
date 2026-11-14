"""Internal adapter boundary; no unverified production capabilities are enabled."""

from dataclasses import dataclass


class ProviderFailure(RuntimeError):
    def __init__(self, code="PROVIDER_UNCERTAIN", *, temporary=False, scope=None):
        super().__init__(code)
        self.code = code
        self.temporary = temporary
        self.scope = scope


@dataclass(frozen=True)
class NotCreatedEvidence:
    """Constructed only by an adapter with verified evidence, never from tool arguments."""

    source: str
    digest: str


class Capabilities:
    remote_cancel = False
    submission_lookup = False
    artifact_refresh = False
    account_identity = False

    def require(self, operation):
        if operation not in (
            "remote_cancel",
            "submission_lookup",
            "artifact_refresh",
            "account_identity",
        ) or not getattr(self, operation):
            raise ProviderFailure("CAPABILITY_UNVERIFIED")


def classify_http(status, *, phase, api_id):
    """Status can guide protection/retry, never prove that a POST was not accepted."""
    if status in (401, 403):
        return ProviderFailure("PROVIDER_AUTH_OR_PERMISSION", scope="all")
    if phase in ("submit", "upload"):
        return ProviderFailure("PROVIDER_SUBMISSION_UNCERTAIN")
    if status == 429 or status >= 500:
        return ProviderFailure("PROVIDER_TEMPORARY", temporary=True)
    return ProviderFailure("PROVIDER_RESPONSE_REJECTED", scope=api_id)
