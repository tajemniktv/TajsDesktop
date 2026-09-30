"""Portal routing restarts through the active init backend safely."""

import os
import signal
import subprocess

from steps import portals


def test_portal_install_preserves_existing_user_config(monkeypatch, tmp_path):
    config = tmp_path / "kde-portals.conf"
    config.write_text("[preferred]\ncustom=portal\n")
    monkeypatch.setattr(portals, "CONF_DIR", tmp_path)
    monkeypatch.setattr(portals, "CONF_FILE", config)
    monkeypatch.setattr(portals, "OWNERSHIP_MARKER", tmp_path / "owned")
    monkeypatch.setattr(portals, "_bounce_services", lambda: (_ for _ in ()).throw(
        AssertionError("must not restart services when nothing changed")))

    portals.install()
    portals.uninstall()

    assert config.read_text() == "[preferred]\ncustom=portal\n"


def test_portal_owned_file_installs_and_uninstalls(monkeypatch, tmp_path):
    config = tmp_path / "kde-portals.conf"
    monkeypatch.setattr(portals, "CONF_DIR", tmp_path)
    monkeypatch.setattr(portals, "CONF_FILE", config)
    monkeypatch.setattr(portals, "OWNERSHIP_MARKER", tmp_path / "owned")
    bounces = []
    monkeypatch.setattr(portals, "_bounce_services", lambda: bounces.append(True))

    portals.install()
    assert config.read_text() == portals.ROUTING
    portals.uninstall()

    assert not config.exists()
    assert len(bounces) == 2


def test_portal_uninstall_preserves_identical_foreign_file(monkeypatch, tmp_path):
    config = tmp_path / "kde-portals.conf"
    config.write_text(portals.ROUTING)
    monkeypatch.setattr(portals, "CONF_DIR", tmp_path)
    monkeypatch.setattr(portals, "CONF_FILE", config)
    monkeypatch.setattr(portals, "OWNERSHIP_MARKER", tmp_path / "owned")
    monkeypatch.setattr(portals, "_bounce_services", lambda: (_ for _ in ()).throw(
        AssertionError("must not restart services when nothing changed")))

    portals.install()
    portals.uninstall()

    assert config.read_text() == portals.ROUTING


def test_portal_uninstall_preserves_user_edit_after_install(monkeypatch, tmp_path):
    config = tmp_path / "kde-portals.conf"
    marker = tmp_path / "owned"
    monkeypatch.setattr(portals, "CONF_DIR", tmp_path)
    monkeypatch.setattr(portals, "CONF_FILE", config)
    monkeypatch.setattr(portals, "OWNERSHIP_MARKER", marker)
    monkeypatch.setattr(portals, "_bounce_services", lambda: None)

    portals.install()
    config.write_text(portals.ROUTING + "custom=true\n")
    portals.uninstall()

    assert config.read_text().endswith("custom=true\n")
    assert marker.exists()


def test_systemd_portals_use_distro_user_manager(monkeypatch):
    calls = []
    monkeypatch.setattr(
        portals, "user_service_manager_command",
        lambda *args: ["manager", "--user", *args],
    )
    monkeypatch.setattr(
        portals, "run_user",
        lambda command, **kwargs: (
            calls.append(command) or subprocess.CompletedProcess(command, 0)
        ),
    )
    monkeypatch.setattr(
        portals.os, "kill",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("systemd path terminated processes directly")),
    )

    portals._bounce_services()

    assert calls == [
        ["manager", "--user", "restart", service]
        for service in portals.PORTAL_SERVICES
    ]


def test_openrc_portals_terminate_only_same_user_managed_processes(
        monkeypatch, tmp_path):
    proc = tmp_path / "proc"
    managed = proc / "101"
    unrelated = proc / "102"
    managed.mkdir(parents=True)
    unrelated.mkdir()
    (managed / "cmdline").write_bytes(
        b"/usr/lib/xdg-desktop-portal-kde\0--replace\0")
    (unrelated / "cmdline").write_bytes(b"/usr/bin/other-process\0")
    monkeypatch.setattr(portals, "_PROC_ROOT", proc)
    monkeypatch.setattr(portals, "user_service_manager_command",
                        lambda *args: None)
    monkeypatch.setenv("SUDO_UID", str(os.getuid()))
    killed = []
    monkeypatch.setattr(portals.os, "kill",
                        lambda pid, sig: killed.append((pid, sig)))

    portals._bounce_services()

    assert killed == [(101, signal.SIGTERM)]
