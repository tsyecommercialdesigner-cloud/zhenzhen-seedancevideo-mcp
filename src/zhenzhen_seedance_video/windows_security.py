"""Current-user storage protection; credential continuity is not account identity."""

import hashlib
import hmac
import json
import os
import secrets
import stat
import uuid
from pathlib import Path

import ntsecuritycon
import win32api
import win32con
import win32crypt
import win32security


class SecurityError(RuntimeError):
    pass


def current_user_sid():
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        return win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    finally:
        token.Close()


def reject_reparse_path(path: Path):
    for item in (path, *path.parents):
        try:
            attributes = item.lstat().st_file_attributes
        except FileNotFoundError:
            continue
        if attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise SecurityError("UNSAFE_STORAGE_PATH")


def protect_directory(path: Path):
    """Only call for service-owned storage, never for a user's general output folder."""
    reject_reparse_path(path)
    path.mkdir(parents=True, exist_ok=True)
    reject_reparse_path(path)
    sid = current_user_sid()
    system = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid, None)
    acl = win32security.ACL()
    for principal in (sid, system):
        acl.AddAccessAllowedAceEx(
            win32security.ACL_REVISION_DS,
            win32con.OBJECT_INHERIT_ACE | win32con.CONTAINER_INHERIT_ACE,
            ntsecuritycon.FILE_ALL_ACCESS,
            principal,
        )
    win32security.SetNamedSecurityInfo(
        str(path),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        None,
        None,
        acl,
        None,
    )


class CredentialBindings:
    """Private DPAPI file. Public task records receive random binding IDs only.

    Call under the backend ownership lock. Changed keys get separate bindings;
    no upstream identity verifier has been established, so old tasks stay gated.
    """

    def __init__(self, directory: Path):
        self.path = directory / "credential-bindings.dpapi"
        protect_directory(directory)
        reject_reparse_path(self.path)
        self._load()

    def __repr__(self):
        return "CredentialBindings(<protected>)"

    def _load(self):
        if not self.path.exists():
            self._secret = secrets.token_bytes(32)
            self._records = []
            try:
                self._save()
            except Exception:
                raise SecurityError("CREDENTIAL_BINDINGS_WRITE_FAILED") from None
            return
        try:
            if self.path.stat().st_size > 1024 * 1024:
                raise ValueError("oversized")
            _, plaintext = win32crypt.CryptUnprotectData(
                self.path.read_bytes(), None, None, None, 1
            )
            data = json.loads(plaintext)
            if data["version"] != 1:
                raise ValueError("version")
            self._secret = bytes.fromhex(data["secret"])
            self._records = data["records"]
            if len(self._secret) != 32 or not isinstance(self._records, list):
                raise ValueError("shape")
            for record in self._records:
                uuid.UUID(record["binding_id"])
                if len(bytes.fromhex(record["fingerprint"])) != 32:
                    raise ValueError("fingerprint")
        except Exception:
            raise SecurityError("CREDENTIAL_BINDINGS_UNREADABLE") from None

    def _save(self):
        plaintext = json.dumps(
            {
                "version": 1,
                "secret": self._secret.hex(),
                "records": self._records,
            }
        ).encode()
        encrypted = win32crypt.CryptProtectData(plaintext, None, None, None, None, 1)
        temporary = self.path.with_name(uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(encrypted)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def bind(self, *, api_key: str, endpoint: str) -> str:
        message = json.dumps([endpoint, api_key], separators=(",", ":")).encode()
        fingerprint = hmac.new(self._secret, message, hashlib.sha256).hexdigest()
        for record in self._records:
            if hmac.compare_digest(record["fingerprint"], fingerprint):
                return record["binding_id"]
        binding_id = str(uuid.uuid4())
        self._records.append({"binding_id": binding_id, "fingerprint": fingerprint})
        try:
            self._save()
        except Exception:
            self._records.pop()
            raise SecurityError("CREDENTIAL_BINDINGS_WRITE_FAILED") from None
        return binding_id

    @staticmethod
    def require_continuity(task_binding: str, active_binding: str):
        if task_binding != active_binding:
            raise SecurityError("CONNECTION_IDENTITY_UNVERIFIED")
