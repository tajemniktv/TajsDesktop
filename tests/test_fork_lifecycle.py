"""The fork's feature preview must not become an implicit reinstall."""

import json

import pytest

import cli
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
