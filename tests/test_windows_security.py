import pytest
import win32security

from zhenzhen_seedance_video.windows_security import (
    CredentialBindings,
    SecurityError,
    current_user_sid,
)


def test_bindings_survive_restart_without_plaintext(tmp_path):
    key = "synthetic-secret-do-not-log"
    store = CredentialBindings(tmp_path / "private")
    identity = store.bind(api_key=key, endpoint="https://api.seedance.nz")
    assert key.encode() not in store.path.read_bytes()
    assert key not in repr(store)
    restarted = CredentialBindings(tmp_path / "private")
    assert restarted.bind(api_key=key, endpoint="https://api.seedance.nz") == identity
    assert restarted.bind(api_key="new-key", endpoint="https://api.seedance.nz") != identity
    assert restarted.bind(api_key=key, endpoint="https://other.example") != identity
    assert restarted.bind(api_key=key, endpoint="https://api.seedance.nz") == identity
    restarted.require_continuity(identity, identity)
    with pytest.raises(SecurityError, match="IDENTITY_UNVERIFIED"):
        restarted.require_continuity(identity, "new-binding")


def test_private_directory_dacl(tmp_path):
    directory = tmp_path / "private"
    CredentialBindings(directory)
    info = win32security.GetNamedSecurityInfo(
        str(directory), win32security.SE_FILE_OBJECT, win32security.DACL_SECURITY_INFORMATION
    )
    acl = info.GetSecurityDescriptorDacl()
    sids = {win32security.ConvertSidToStringSid(acl.GetAce(i)[2]) for i in range(acl.GetAceCount())}
    assert sids == {win32security.ConvertSidToStringSid(current_user_sid()), "S-1-5-18"}
    assert info.GetSecurityDescriptorControl()[0] & win32security.SE_DACL_PROTECTED


def test_corrupt_binding_store_never_regenerates(tmp_path):
    store = CredentialBindings(tmp_path / "private")
    store.path.write_bytes(b"broken-dpapi")
    with pytest.raises(SecurityError, match="UNREADABLE"):
        CredentialBindings(tmp_path / "private")
    assert store.path.read_bytes() == b"broken-dpapi"


def test_failed_write_does_not_publish_binding(tmp_path, monkeypatch):
    store = CredentialBindings(tmp_path / "private")
    before = store.path.read_bytes()

    def fail():
        raise OSError("sensitive detail")

    monkeypatch.setattr(store, "_save", fail)
    with pytest.raises(SecurityError, match="WRITE_FAILED") as error:
        store.bind(api_key="new-key", endpoint="https://example.com")
    assert "sensitive" not in str(error.value)
    assert store._records == []
    assert store.path.read_bytes() == before
