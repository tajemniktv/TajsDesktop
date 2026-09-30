"""The opt-in rendering probe must not target the user's compositor."""

from types import SimpleNamespace

import pytest

from tests import acrylic_glass_capture as capture


@pytest.mark.parametrize("key", ["HOME", "XDG_CONFIG_HOME", "MTTKDE_CAPTURE_DIR"])
def test_direct_capture_entry_refuses_non_private_environment(monkeypatch, tmp_path, key):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("MTTKDE_CAPTURE_DIR", str(tmp_path))
    monkeypatch.delenv(key)

    def forbidden(*args, **kwargs):
        raise AssertionError("No processes may start with a non-private environment")

    monkeypatch.setattr(capture.subprocess, "Popen", forbidden)
    with pytest.raises(RuntimeError, match="private session"):
        capture.inside(tmp_path)


def test_capture_refuses_a_different_dbus_owner(monkeypatch):
    calls = []

    def query(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout="999\n")

    monkeypatch.setattr(capture.subprocess, "run", query)
    with pytest.raises(RuntimeError, match="refusing mutations"):
        capture.assert_compositor_owner(123)
    assert len(calls) == 1
    assert "org.freedesktop.DBus.GetConnectionUnixProcessID" in calls[0]


def test_capture_stages_only_the_fork_effect(monkeypatch, tmp_path):
    plugin = tmp_path / "tajsdesktopglass.so"
    plugin.write_bytes(b"reviewed test plugin")
    compositor = tmp_path / "kwin_wayland"
    compositor.write_bytes(b"test compositor")
    output = tmp_path / "capture"
    launched = []
    monkeypatch.setattr(capture.shutil, "which", lambda _command: str(compositor))

    def launch(command, **kwargs):
        launched.append((command, kwargs))
        return SimpleNamespace(pid=123, wait=lambda **_kwargs: 0, poll=lambda: 0)

    monkeypatch.setattr(capture.subprocess, "Popen", launch)
    monkeypatch.setattr(capture.os, "killpg", lambda *_args: None)
    monkeypatch.setattr(capture, "compare", lambda *_args: None)

    capture.run(plugin, output, 1, "unchanged", "wayland", "VirtualBoxVM")

    assert (output / "plugins/kwin/effects/plugins/tajsdesktopglass.so").read_bytes() == plugin.read_bytes()
    assert not (output / "plugins/kwin/effects/plugins/liquidglass.so").exists()
    config = (output / "config/kwinrc").read_text()
    assert "tajsdesktopglassEnabled=false" in config
    assert "[Effect-tajsdesktopglass]" in config
    assert "liquidglass" not in config
    assert len(launched) == 1
    command, kwargs = launched[0]
    assert command[:2] == ["dbus-run-session", "--"]
    assert kwargs["env"]["XDG_CONFIG_HOME"] == str(output / "config")
    assert kwargs["env"]["QT_PLUGIN_PATH"] == str(output / "plugins")
