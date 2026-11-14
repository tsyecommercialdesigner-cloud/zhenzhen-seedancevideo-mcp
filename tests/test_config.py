from pathlib import Path

import pytest

from zhenzhen_seedance_video import config as config_module
from zhenzhen_seedance_video.config import (
    PREFIX,
    ConfigurationConflict,
    ConfigurationError,
    accept_client_configuration,
    load_configuration,
)

RESOLVE_INSTALLATION = config_module.installation_root
READ_USER_ENVIRONMENT = config_module._read_user_environment


@pytest.fixture
def env(tmp_path):
    return {"LOCALAPPDATA": str(tmp_path), PREFIX + "API_KEY": "synthetic-key"}


def test_fixed_root_priority_and_no_cwd_search(env, tmp_path, monkeypatch):
    root = tmp_path / "ZhenzhenSeedanceVideo"
    (tmp_path / "installation" / ".env").write_text(
        PREFIX + "API_KEY=synthetic-file-key\n" + PREFIX + "QUEUE_LIMIT=9\n", encoding="utf-8"
    )
    other = tmp_path / "project"
    other.mkdir()
    (other / ".env").write_text(PREFIX + "QUEUE_LIMIT=999", encoding="utf-8")
    monkeypatch.chdir(other)
    cfg = load_configuration(env)
    assert cfg.api_key == "synthetic-file-key"
    assert cfg.limits["QUEUE_LIMIT"] == 9
    assert cfg.root == root
    assert cfg.sources["API_KEY"] == "dotenv"
    assert cfg.sources["QUEUE_LIMIT"] == "dotenv"
    assert cfg.output_dir == root / "outputs"
    assert cfg.state_dir == root / "state"


def test_no_interpolation(env, tmp_path):
    (tmp_path / "installation" / ".env").write_text(
        PREFIX + "API_KEY=${MISSING_KEY}", encoding="utf-8"
    )
    del env[PREFIX + "API_KEY"]
    assert load_configuration(env).api_key == "${MISSING_KEY}"


def test_alias_missing_key_and_explicit_empty(env):
    del env[PREFIX + "API_KEY"]
    env["API_KEY"] = "do-not-use"
    with pytest.raises(ConfigurationError, match="generic API_KEY"):
        load_configuration(env)
    env[PREFIX + "API_KEY"] = ""
    with pytest.raises(ConfigurationError, match="must not be empty"):
        load_configuration(env)


def test_snapshot_does_not_change_with_environment(env):
    cfg = load_configuration(env)
    env[PREFIX + "API_KEY"] = "new-synthetic-key"
    env[PREFIX + "GENERATION_CONCURRENCY"] = "7"
    assert cfg.api_key == "synthetic-key"
    assert cfg.limits["GENERATION_CONCURRENCY"] == 3
    with pytest.raises(TypeError):
        cfg.limits["GENERATION_CONCURRENCY"] = 7
    assert "synthetic-key" not in repr(cfg)


@pytest.mark.parametrize("value", ["-1", "0", "1.5", "true", "１２", str(2**64)])
def test_invalid_limits(env, value):
    env[PREFIX + "QUEUE_LIMIT"] = value
    with pytest.raises(ConfigurationError, match="QUEUE_LIMIT"):
        load_configuration(env)


def test_disabled_tracking_and_defaults(env):
    env[PREFIX + "TRACKING_TIMEOUT_SECONDS"] = "0"
    cfg = load_configuration(env)
    assert cfg.limits["TRACKING_TIMEOUT_SECONDS"] == 0
    assert cfg.limits["INPUT_BYTES_LIMIT"] == 536870912
    assert cfg.limits["DOWNLOAD_BYTES_LIMIT"] is None
    assert cfg.limits["QUERY_RETRIES"] == 5


@pytest.mark.parametrize(
    "value", ["relative", "C:relative", r"\\server\share\out", r"C:\out:stream"]
)
def test_output_path_restrictions(env, value):
    env[PREFIX + "OUTPUT_DIR"] = value
    with pytest.raises(ConfigurationError, match="OUTPUT_DIR"):
        load_configuration(env)


def test_output_does_not_move_state(env, tmp_path):
    env[PREFIX + "OUTPUT_DIR"] = str(tmp_path / "new-output")
    cfg = load_configuration(env)
    assert cfg.output_dir == tmp_path / "new-output"
    assert cfg.state_dir == tmp_path / "ZhenzhenSeedanceVideo" / "state"


def test_network_settings(env, tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_text("synthetic: SSL validation belongs to NetworkPolicy", encoding="utf-8")
    env.update(
        {
            PREFIX + "CA_FILE": str(ca),
            PREFIX + "PROXY_URL": "http://user:secret@127.0.0.1:8080",
            PREFIX + "PROXY_BYPASS": "example.com,.example.org,127.0.0.0/8,::1",
        }
    )
    cfg = load_configuration(env)
    assert cfg.ca_file == ca
    assert "secret" not in repr(cfg)
    assert len(cfg.proxy_bypass) == 4


@pytest.mark.parametrize(
    "name,value",
    [
        ("PROXY_URL", "socks5://secret@localhost:8080"),
        ("PROXY_URL", "http://secret@localhost:bad"),
        ("PROXY_BYPASS", "*"),
        ("CA_FILE", r"C:\nonexistent\synthetic-ca.pem"),
        ("WAIT_DEFAULT_SECONDS", "31"),
        ("LEASE_TIMEOUT_SECONDS", "5"),
    ],
)
def test_invalid_network_or_cross_limits(env, name, value):
    env[PREFIX + name] = value
    with pytest.raises(ConfigurationError) as error:
        load_configuration(env)
    assert "secret" not in str(error.value)


def test_process_environment_precedes_user_environment(monkeypatch, tmp_path):
    monkeypatch.setenv(PREFIX + "API_KEY", "synthetic-inherited")
    cfg = load_configuration()
    assert cfg.api_key == "synthetic-inherited"
    assert cfg.root == Path(str(tmp_path / "local-app-data")) / "ZhenzhenSeedanceVideo"


def test_unspecified_client_adopts_running_configuration(env):
    env[PREFIX + "QUEUE_LIMIT"] = "7"
    backend = load_configuration(env)
    assert accept_client_configuration(backend, {"LOCALAPPDATA": env["LOCALAPPDATA"]}) is backend


def test_client_conflict_does_not_mutate_existing_configuration(env):
    backend = load_configuration(env)
    client = dict(env, **{PREFIX + "API_KEY": "another-secret", PREFIX + "QUEUE_LIMIT": "8"})
    with pytest.raises(ConfigurationConflict) as error:
        accept_client_configuration(backend, client)
    assert error.value.names == (PREFIX + "API_KEY", PREFIX + "QUEUE_LIMIT")
    assert "secret" not in str(error.value)
    assert backend.api_key == "synthetic-key"
    assert backend.limits["QUEUE_LIMIT"] == 100
    assert accept_client_configuration(backend, env) is backend


def test_output_snapshot_survives_new_backend_configuration(env, tmp_path):
    backend = load_configuration(env)
    accepted_output = str(backend.output_dir)
    changed = dict(env, **{PREFIX + "OUTPUT_DIR": str(tmp_path / "new")})
    with pytest.raises(ConfigurationConflict):
        accept_client_configuration(backend, changed)
    restarted = load_configuration(changed)
    assert accepted_output == str(backend.output_dir)
    assert str(restarted.output_dir) != accepted_output


def test_field_fallback_and_shadowed_values(env, tmp_path, monkeypatch):
    (tmp_path / "installation/.env").write_text(PREFIX + "API_KEY=file-key\n")
    env[PREFIX + "API_KEY"] = ""  # Shadowed, not a fallback candidate.
    env[PREFIX + "QUEUE_LIMIT"] = "8"

    def user(excluded):
        assert PREFIX + "API_KEY" in excluded
        assert PREFIX + "QUEUE_LIMIT" in excluded
        return {PREFIX + "QUERY_CONCURRENCY": "6"}

    monkeypatch.setattr(config_module, "_read_user_environment", user)
    cfg = load_configuration(env)
    assert cfg.api_key == "file-key"
    assert cfg.limits["QUEUE_LIMIT"] == 8
    assert cfg.limits["QUERY_CONCURRENCY"] == 6
    assert cfg.limits["DOWNLOAD_CONCURRENCY"] == 2
    assert cfg.sources["QUERY_CONCURRENCY"] == "user_environment"


@pytest.mark.parametrize(
    "content",
    [
        "ZHENZHEN_SEEDANCE_API_KEY=",
        "ZHENZHEN_SEEDANCE_API_KEY",
        "ZHENZHEN_SEEDANCE_API_KEY=secret with spaces",
        "ZHENZHEN_SEEDANCE_QUEUE_LIMIT=invalid-secret",
        'ZHENZHEN_SEEDANCE_API_KEY="unterminated-secret',
        "ZHENZHEN_SEEDANCE_API_KEY=a\nzhenzhen_seedance_api_key=b",
    ],
)
def test_bad_file_never_falls_back(env, tmp_path, content, capsys):
    (tmp_path / "installation/.env").write_text(content)
    with pytest.raises(ConfigurationError) as error:
        load_configuration(env)
    assert "secret" not in str(error.value)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("failure", [PermissionError, UnicodeError])
def test_unreadable_file_fails_closed(env, monkeypatch, failure):
    original = Path.open

    def fail(path, *args, **kwargs):
        if path.name == ".env":
            raise failure("sensitive path")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail)
    with pytest.raises(ConfigurationError, match="cannot read") as error:
        load_configuration(env)
    assert "sensitive" not in str(error.value)


def test_user_env_read_without_process_inheritance(env, monkeypatch):
    env.pop(PREFIX + "API_KEY")
    monkeypatch.setattr(
        config_module,
        "_read_user_environment",
        lambda excluded: {PREFIX + "API_KEY": "registry-key"},
    )
    assert load_configuration(env).api_key == "registry-key"
    env[PREFIX + "API_KEY"] = ""
    with pytest.raises(ConfigurationError, match="empty"):
        load_configuration(env)


def test_registry_reader_is_read_only_filtered_and_no_expansion(monkeypatch):
    import winreg
    from contextlib import nullcontext

    rows = [
        ("irrelevant", 42, winreg.REG_DWORD),
        (PREFIX + "API_KEY", "registry-key", winreg.REG_SZ),
        (PREFIX + "OUTPUT_DIR", "%USERPROFILE%/videos", winreg.REG_EXPAND_SZ),
        (PREFIX + "QUEUE_LIMIT", 99, winreg.REG_DWORD),
    ]

    def open_key(hive, path):
        assert hive == winreg.HKEY_CURRENT_USER and path == "Environment"
        return nullcontext("synthetic-key-handle")

    monkeypatch.setattr(winreg, "OpenKey", open_key)
    monkeypatch.setattr(winreg, "QueryInfoKey", lambda key: (0, len(rows), 0))
    monkeypatch.setattr(winreg, "EnumValue", lambda key, index: rows[index])
    assert READ_USER_ENVIRONMENT({PREFIX + "QUEUE_LIMIT"}) == {
        PREFIX + "API_KEY": "registry-key",
        PREFIX + "OUTPUT_DIR": "%USERPROFILE%/videos",
    }
    with pytest.raises(ConfigurationError, match="requires string"):
        READ_USER_ENVIRONMENT(set())

    def denied(*args):
        raise PermissionError("private")

    monkeypatch.setattr(winreg, "OpenKey", denied)
    with pytest.raises(ConfigurationError, match="cannot read"):
        READ_USER_ENVIRONMENT(set())


@pytest.mark.parametrize("layout", ["source", "project-wheel", "standalone-wheel"])
def test_installation_layout_independent_of_cwd(tmp_path, monkeypatch, layout):
    install = tmp_path / "new-install"
    if layout == "source":
        module = install / "src/zhenzhen_seedance_video/config.py"
        module.parent.mkdir(parents=True)
        (install / "pyproject.toml").write_text('[project]\nname="zhenzhen-seedancevideo-mcp"\n')
    else:
        prefix = install / ".venv" if layout == "project-wheel" else install
        module = prefix / "Lib/site-packages/zhenzhen_seedance_video/config.py"
        module.parent.mkdir(parents=True)
        (prefix / "pyvenv.cfg").write_text("home=synthetic")
        monkeypatch.setattr(config_module.sys, "prefix", str(prefix))
    monkeypatch.setattr(config_module, "__file__", str(module))
    assert RESOLVE_INSTALLATION() == install


def test_unknown_installation_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "__file__", str(tmp_path / "unknown/config.py"))
    with pytest.raises(ConfigurationError, match="cannot identify"):
        RESOLVE_INSTALLATION()


def test_install_switch_conflicts_without_moving_state(env, tmp_path, monkeypatch):
    first = tmp_path / "installation/.env"
    first.write_text(PREFIX + "API_KEY=first-key\n")
    backend = load_configuration(env)
    second = tmp_path / "second"
    second.mkdir()
    (second / ".env").write_text(PREFIX + "API_KEY=second-key\n")
    monkeypatch.setattr(config_module, "installation_root", lambda: second)
    with pytest.raises(ConfigurationConflict) as error:
        accept_client_configuration(backend, env)
    assert error.value.names == (PREFIX + "API_KEY",)
    assert backend.api_key == "first-key"
    assert load_configuration(env).root == backend.root


def test_resolved_rpc_values_do_not_reread_backend_file(env, tmp_path):
    path = tmp_path / "installation/.env"
    path.write_text(PREFIX + "API_KEY=first-key\n")
    backend = load_configuration(env)
    path.write_text(PREFIX + 'API_KEY="invalid-file')
    assert config_module.accept_explicit_configuration(backend, backend.root, {}) is backend
    with pytest.raises(ConfigurationConflict):
        config_module.accept_explicit_configuration(backend, backend.root, {"API_KEY": "new-key"})
