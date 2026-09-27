"""The fork's feature preview must not become an implicit reinstall."""

import json
import inspect

import pytest

import cli
from steps import apply
from fork_lifecycle import (
    InstalledState, load_state, plan_features, save_state,
    upstream_install_present,
)


def test_missing_and_invalid_install_state_fail_closed(tmp_path):
    target = tmp_path / "installation.json"
    assert load_state(target) is None
    target.write_text('{"schema": 99, "installed_version": "1", "features": {}}')
    with pytest.raises(ValueError):
        load_state(target)


def test_state_roundtrip_is_versioned_and_boolean(tmp_path):
    target = tmp_path / "installation.json"
    state = InstalledState("1.2.3", {"layout": True, "firefox": False})
    save_state(state, target)
    assert load_state(target) == state
    assert json.loads(target.read_text())["schema"] == 1
    assert list(tmp_path.glob("*.tmp")) == []


def test_plan_changes_only_selected_features():
    installed = InstalledState("1.2.3", {
        "layout": True, "firefox": True, "rounded_corners": False,
    })
    preview = plan_features({
        "layout": True, "firefox": False, "rounded_corners": True,
    }, installed, "1.2.3")
    assert preview["operation"] == "features"
    assert preview["enable"] == ["rounded_corners"]
    assert preview["disable"] == ["firefox"]
    assert preview["unchanged"] == ["layout"]


def test_noop_and_version_update_do_not_imply_setting_reset():
    installed = InstalledState("1.2.3", {"layout": True})
    same = plan_features({"layout": True}, installed, "1.2.3")
    assert same["enable"] == same["disable"] == []
    newer = plan_features({"layout": True}, installed, "1.2.4")
    assert newer["operation"] == "update"
    assert newer["enable"] == newer["disable"] == []


def test_update_only_refreshes_steps_with_an_asset_phase():
    installed = InstalledState("1.2.3", {
        "wallpapers": True, "layout": True, "gtk": True,
    })
    preview = plan_features(installed.features, installed, "1.2.4",
                            refreshable={"wallpapers"})
    assert preview["refresh_assets"] == ["wallpapers"]
    assert preview["pending_refresh"] == ["gtk"]
    assert preview["enable"] == preview["disable"] == []


def test_update_does_not_refresh_settings_only_features():
    previous = InstalledState("1.2.3", {
        "layout": True, "apply_theme": True, "apps": True, "portals": True,
    })
    preview = plan_features(previous.features, previous, "1.2.4")
    assert preview["refresh_assets"] == []
    assert preview["pending_refresh"] == []


def test_foreign_tahoe_install_requires_explicit_migration():
    preview = plan_features({"layout": True}, None, "0.52.0",
                            foreign_install=True)
    assert preview["operation"] == "migration-required"
    assert preview["foreign_install"] is True
    assert preview["enable"] == ["layout"]


def test_foreign_install_detection_does_not_depend_on_tajsdesktop_state(tmp_path):
    assert not upstream_install_present(tmp_path)
    marker = tmp_path / ".local/state/mac-tahoe-liquid-kde"
    marker.mkdir(parents=True)
    assert upstream_install_present(tmp_path)


def test_cli_preview_is_read_only_and_requires_no_root(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_features", lambda: {"layout": True})
    monkeypatch.setattr(cli, "load_state", lambda: InstalledState(
        "0.52.0", {"layout": True, "firefox": True}))
    monkeypatch.setattr(cli, "_require_root_and_drop_to_user",
                        lambda *_: pytest.fail("root requested"))
    monkeypatch.setattr(cli, "save_features",
                        lambda *_: pytest.fail("features.json modified"))

    assert cli.run_install(["--plan", "--only", "--firefox"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["enable"] == []
    assert "layout" in preview["disable"]
    assert preview["executable"] is False


def test_cli_explicit_machine_profile_preview_is_read_only(monkeypatch, capsys,
                                                          tmp_path):
    monkeypatch.setattr(cli, "load_features", lambda: {"apps": True})
    monkeypatch.setattr(cli, "load_state", lambda: None)
    monkeypatch.setattr(cli, "upstream_install_present", lambda: False)
    monkeypatch.setattr(cli, "profile_state_file", lambda: tmp_path / "missing")
    monkeypatch.setattr(cli, "preview_profile_defaults",
                        lambda name: [{"file": "powerdevilrc", "profile": name}])
    monkeypatch.setattr(cli, "_require_root_and_drop_to_user",
                        lambda *_: pytest.fail("root requested"))

    assert cli.run_install(["--plan", "--profile=local-laptop"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["profile"] == "local-laptop"
    assert preview["profile_defaults"] == [
        {"file": "powerdevilrc", "profile": "local-laptop"}]
    assert preview["executable"] is False


def test_cli_profile_reset_preview_requires_no_root(monkeypatch, capsys):
    monkeypatch.setattr(cli, "preview_profile_reset",
                        lambda: [{"file": "dolphinrc", "action": "delete"}])
    monkeypatch.setattr(cli, "_require_root_and_drop_to_user",
                        lambda *_: pytest.fail("root requested"))

    assert cli.run_install(["--plan-reset-profile"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["reset"] == [{"file": "dolphinrc", "action": "delete"}]
    assert preview["executable"] is False


def test_fork_lifecycle_does_not_run_upstream_kconf_migration():
    assert "kconf_update" not in cli.INSTALL_ORDER
    assert "run_migration" not in inspect.getsource(apply.uninstall)
