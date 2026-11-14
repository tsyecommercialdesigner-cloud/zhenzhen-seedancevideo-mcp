"""Partial compatibility contract; opt-in internal composition, not a live default."""

import json
import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from .artifact_manifest import ArtifactManifest
from .draft_evidence import local_draft_fact
from .models import BASE_URL, QUERY_PATH, SUBMIT_PATH, get_model
from .network import NetworkError
from .parameters import ParameterError, normalize
from .provider import Capabilities, ProviderFailure, classify_http
from .provider_response import decode_response


class CompatibilityAdapter:
    capabilities = Capabilities()

    def __init__(self, network, database=None):
        self.network = network
        self.db = database

    async def prepare(self, row):
        model = get_model(row["model"], api_id=row["api_id"])
        try:
            payload = json.loads(row["effective_parameters"])
        except (ValueError, TypeError, RecursionError):
            raise ProviderFailure("TASK_PAYLOAD_INVALID") from None
        if not isinstance(payload, dict) or payload.get("model") != row["model"]:
            raise ProviderFailure("TASK_PAYLOAD_IDENTITY_MISMATCH")
        if model.kind == "draft-to-video" and self.db is not None:
            fact = await self.db.execute(
                lambda c: local_draft_fact(c, payload, row["connection_binding"]), write=False
            )
            try:
                normalize(payload, api_id=row["api_id"], draft_fact=fact)
            except ParameterError as error:
                raise ProviderFailure(error.code) from None

        def unresolved(value):
            if isinstance(value, dict):
                return bool({"material_id", "local_path"} & value.keys()) or any(
                    unresolved(v) for v in value.values()
                )
            return isinstance(value, list) and any(unresolved(v) for v in value)

        if unresolved(payload):
            raise ProviderFailure("MATERIAL_PREPARATION_REQUIRED")
        return payload

    async def _request(self, method, path, row, *, phase, payload=None, expected_id=None):
        body = {"json": payload} if payload is not None else {}
        try:
            status, response = await self.network.request(
                method,
                BASE_URL + path,
                phase=phase,
                credential=True,
                limit=2 * 1024 * 1024,
                allow_redirects=False,
                **body,
            )
        except NetworkError as error:
            if phase == "submit":
                raise ProviderFailure("PROVIDER_SUBMISSION_UNCERTAIN") from None
            temporary = str(error) in (
                "NETWORK_TIMEOUT",
                "NETWORK_REQUEST_FAILED",
                "NETWORK_DNS_FAILED",
            )
            raise ProviderFailure("QUERY_NETWORK_FAILED", temporary=temporary) from None
        if not 200 <= status < 300:
            raise classify_http(status, phase=phase, api_id=row["api_id"])
        return decode_response(response, expected_model=row["model"], expected_id=expected_id)

    async def submit(self, row, payload):
        # Admission/preparation has fixed all defaults and consent; never recalculate them here.
        if not isinstance(payload, dict) or payload.get("model") != row["model"]:
            raise ProviderFailure("TASK_PAYLOAD_IDENTITY_MISMATCH")
        return await self._request("POST", SUBMIT_PATH, row, phase="submit", payload=payload)

    async def query(self, row):
        remote_id = row.get("remote_id")
        if not isinstance(remote_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,512}", remote_id):
            raise ProviderFailure("REMOTE_ID_PATH_UNVERIFIED")
        return await self._request(
            "GET", QUERY_PATH.format(id=remote_id), row, phase="query", expected_id=remote_id
        )

    async def artifacts(self, row):
        if self.db is None:
            raise ProviderFailure("ARTIFACT_SET_UNVERIFIED")
        if row["remote_state"] != "succeeded" or not row.get("remote_id"):
            raise ProviderFailure("RESULT_URL_UNAVAILABLE")
        record = await self.db.execute(
            lambda c: c.execute(
                "SELECT facts FROM remote_observations WHERE task_id=? AND remote_id=? "
                "AND raw_status='completed' AND terminal_conflict=0 ORDER BY rowid DESC LIMIT 1",
                (row["task_id"], row["remote_id"]),
            ).fetchone(),
            write=False,
        )
        url = json.loads(record[0]).get("url") if record else None
        if not isinstance(url, str) or not url:
            raise ProviderFailure("RESULT_URL_UNAVAILABLE")
        metadata = json.loads(row["effective_parameters"]).get("metadata", {})
        explicit = metadata.get("output_format")
        try:
            suffix = PurePosixPath(urlsplit(url).path).suffix.lower().lstrip(".")
        except ValueError:
            raise ProviderFailure("ARTIFACT_FORMAT_UNVERIFIED") from None
        inferred = suffix if suffix in ("mp4", "mov") else None
        if explicit is not None and explicit not in ("mp4", "mov"):
            raise ProviderFailure("ARTIFACT_FORMAT_UNVERIFIED")
        if explicit and inferred and explicit != inferred:
            raise ProviderFailure("ARTIFACT_FORMAT_CONFLICT")
        fmt = explicit or inferred
        if fmt is None:
            raise ProviderFailure("ARTIFACT_FORMAT_UNVERIFIED")
        references = [{"url": url, "format": fmt, "required": True}]
        last_frame = json.loads(record[0]).get("last_frame_url")
        if last_frame:
            # Observed URLs/results say PNG but bytes are JPEG. Validate actual bytes;
            # never rename PNG into JPEG or infer encoding from the signed URL.
            references.append({"url": last_frame, "format": "jpg", "required": True})
        return ArtifactManifest(references, complete=False)
