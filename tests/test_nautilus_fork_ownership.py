"""Foreign Nautilus preferences and app data must survive the fork."""

import subprocess

from steps import nautilus


def test_existing_mime_default_is_not_replaced(monkeypatch, tmp_path):
    home = tmp_path / "home"
    (home / ".config").mkdir(parents=True)
    config = home / ".config/mimeapps.list"
    original = "[Default Applications]\ninode/directory=custom.desktop;\n"
    config.write_text(original)
    monkeypatch.setattr(nautilus, "HOME", home)
    monkeypatch.setattr(nautilus, "kw_write", lambda *args: (_ for _ in ()).throw(
        AssertionError("must not replace explicit MIME default")))

    assert not nautilus._set_default_if_absent(
        nautilus.NAUTILUS_DESKTOP, nautilus.MIME_FOLDER)
    assert config.read_text() == original


def test_nautilus_css_is_created_only_when_absent_and_removed_if_unchanged(
        monkeypatch, tmp_path):
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "gtk.css").write_text("/* fork */")
    monkeypatch.setattr(nautilus, "HOME", home)
    monkeypatch.setattr(nautilus, "offline", lambda *args: source)

    nautilus._apply_overrides()
    css = home / ".config/nautilus/gtk.css"
    marker = css.with_name("gtk.css.tajsdesktop-owned")
    assert css.read_text() == "/* fork */"
    assert marker.is_file()

    nautilus._remove_owned_css()
    assert not css.exists()
    assert not marker.exists()


def test_nautilus_css_user_edit_survives_uninstall(monkeypatch, tmp_path):
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "gtk.css").write_text("/* fork */")
    monkeypatch.setattr(nautilus, "HOME", home)
    monkeypatch.setattr(nautilus, "offline", lambda *args: source)

    nautilus._apply_overrides()
    css = home / ".config/nautilus/gtk.css"
    css.write_text("/* my edit */")
    nautilus._remove_owned_css()

    assert css.read_text() == "/* my edit */"


def test_nautilus_gsettings_respects_explicit_dconf_values(monkeypatch):
    monkeypatch.setattr(nautilus, "have", lambda _tool: True)
    calls = []

    def run(command, **_kwargs):
        calls.append(command)
        if command[0] == "dconf":
            return subprocess.CompletedProcess(command, 0, stdout="'list-view'\n")
        raise AssertionError("must not set an explicit user preference")

    monkeypatch.setattr(nautilus, "run_user", run)
    monkeypatch.setattr(nautilus, "_FINDER_GSETTINGS", (
        ("org.gnome.nautilus.preferences", "default-folder-viewer", "icon-view"),
    ))
    nautilus._apply_gsettings()

    assert calls == [["dconf", "read",
                      "/org/gnome/nautilus/preferences/default-folder-viewer"]]


def test_nautilus_gsettings_initializes_only_unset_dconf_key(monkeypatch):
    monkeypatch.setattr(nautilus, "have", lambda _tool: True)
    calls = []

    def run(command, **_kwargs):
        calls.append(command)
        if command[0] == "dconf":
            return subprocess.CompletedProcess(command, 0, stdout="")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(nautilus, "run_user", run)
    monkeypatch.setattr(nautilus, "_FINDER_GSETTINGS", (
        ("org.gnome.nautilus.preferences", "default-folder-viewer", "icon-view"),
    ))
    nautilus._apply_gsettings()

    assert calls[-1] == ["gsettings", "set", "org.gnome.nautilus.preferences",
                         "default-folder-viewer", "icon-view"]
