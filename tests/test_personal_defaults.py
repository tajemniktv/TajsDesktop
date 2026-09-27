import json
import shutil
import subprocess
from pathlib import Path

import pytest

import personal_defaults as defaults
from personal_defaults import desired_defaults, preview_missing


def test_machine_profile_requires_explicit_selection():
    common = desired_defaults()
    assert "powerdevilrc" not in common
    assert desired_defaults("local-laptop")["powerdevilrc"]


def test_preview_preserves_present_and_explicit_empty_values(tmp_path):
    (tmp_path / "dolphinrc").write_text(
        "[MainWindow]\nMenuBar=\n[InformationPanel]\ndateFormat=LongFormat\n")
    preview = preview_missing(config_home=tmp_path)
    assert not any(x["key"] in {"MenuBar", "dateFormat"} for x in preview)
    assert any(x["key"] == "NewTabButton" for x in preview)


def test_no_private_or_machine_identifiers_in_profiles():
    from personal_defaults import PROFILE_DIR
    for name in ("common", "local-laptop"):
        payload = json.dumps(desired_defaults(name)).lower()
        assert not any(token in payload for token in (
            "/home/", "uuid", "password", "token", "ssid", "deviceid",
            "serial", "cookie", "sessionstore"))
        assert (PROFILE_DIR / f"{name}.json").exists()


def test_initial_defaults_backup_and_scoped_reset_with_real_kconfig(
        monkeypatch, tmp_path):
    if not shutil.which("kwriteconfig6"):
        pytest.skip("kwriteconfig6 unavailable")
    config = tmp_path / "config"
    config.mkdir()
    state = tmp_path / "state/profile-defaults.json"
    dolphin = config / "dolphinrc"
    dolphin.write_text("[MainWindow]\nMenuBar=\n[InformationPanel]\n"
                       "dateFormat=LongFormat\n")

    def write(*args):
        return subprocess.run(["kwriteconfig6", *args], check=False,
                              capture_output=True).returncode == 0

    monkeypatch.setattr(defaults, "kw_write", write)
    record = defaults.apply_initial_defaults(config_home=config, state_path=state)
    assert record["profile"] == "common"
    assert defaults._key_value(dolphin, "MainWindow", "MenuBar") == ""
    assert defaults._key_value(dolphin, "InformationPanel", "dateFormat") == "LongFormat"
    assert defaults._key_value(dolphin, "KFileDialog Settings",
                               "Places Icons Static Size") == "22"
    backup = record["backups"]["dolphinrc"]
    assert backup is not None
    assert Path(backup).read_text(encoding="utf-8") == (
        "[MainWindow]\nMenuBar=\n[InformationPanel]\ndateFormat=LongFormat\n")
    with pytest.raises(ValueError):
        defaults.apply_initial_defaults(config_home=config, state_path=state)

    # A user edit is not ours to reset; untouched initialized values are.
    write("--file", str(dolphin), "--group", "KFileDialog Settings",
          "--key", "Places Icons Static Size", "30")
    preview = defaults.preview_profile_reset(config_home=config, state_path=state)
    assert any(item["key"] == "Places Icons Static Size" and
               item["action"] == "preserve-user-value" for item in preview)
    assert any(item["key"] == "NewTabButton" and item["action"] == "delete"
               for item in preview)
    with pytest.raises(ValueError):
        defaults.reset_profile_defaults(confirmed=False, config_home=config,
                                        state_path=state)
    defaults.reset_profile_defaults(confirmed=True, config_home=config,
                                    state_path=state)
    assert defaults._key_value(dolphin, "KFileDialog Settings",
                               "Places Icons Static Size") == "30"
    assert defaults._key_value(config / "konsolerc", "TabBar", "NewTabButton") is None
    assert json.loads(state.read_text())["reset_backups"]


def test_symlinked_profile_config_fails_closed(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    foreign = tmp_path / "foreign"
    foreign.write_text("[MainWindow]\nMenuBar=Enabled\n")
    (config / "dolphinrc").symlink_to(foreign)

    with pytest.raises(ValueError, match="Symlinked config"):
        defaults.preview_missing(config_home=config)
    assert foreign.read_text() == "[MainWindow]\nMenuBar=Enabled\n"


def test_local_profile_writes_nested_kconfig_group_when_selected(
        monkeypatch, tmp_path):
    if not shutil.which("kwriteconfig6"):
        pytest.skip("kwriteconfig6 unavailable")
    config = tmp_path / "config"
    config.mkdir()

    monkeypatch.setattr(defaults, "kw_write", lambda *args: subprocess.run(
        ["kwriteconfig6", *args], check=False, capture_output=True,
    ).returncode == 0)
    defaults.apply_initial_defaults("local-laptop", config_home=config,
                                    state_path=tmp_path / "state/profile-defaults.json")

    assert defaults._key_value(config / "powerdevilrc", "AC][Display",
                               "DimDisplayIdleTimeoutSec") == "900"
