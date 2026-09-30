"""Uninstall must not delete a foreign GTK4 configuration tree."""

from steps import gtk


def test_gtk_uninstall_removes_only_namespaced_theme_assets(monkeypatch, tmp_path):
    themes = tmp_path / "themes"
    config = tmp_path / ".config/gtk-4.0"
    (config / "assets").mkdir(parents=True)
    (config / "assets" / "custom.svg").write_text("mine")
    (config / "gtk.css").write_text("/* mine */")
    for variant in gtk.VARIANTS:
        (themes / variant).mkdir(parents=True)
    monkeypatch.setattr(gtk, "DEST_DIR", themes)
    monkeypatch.setattr(gtk, "run_user", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("must not reset GSettings")))

    gtk.uninstall()

    assert all(not (themes / variant).exists() for variant in gtk.VARIANTS)
    assert (config / "assets/custom.svg").read_text() == "mine"
    assert (config / "gtk.css").read_text() == "/* mine */"
