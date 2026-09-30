"""Routine component refresh must not reapply desktop preferences."""

from steps import acrylic_glass, gtk, kvantum, sounds, window_decorations


def _unexpected(*_args, **_kwargs):
    raise AssertionError("asset refresh must not change live configuration")


def test_gtk_asset_refresh_does_not_set_gsettings(monkeypatch, tmp_path):
    source = tmp_path / "source"
    for variant in gtk.VARIANTS:
        (source / variant).mkdir(parents=True)
    monkeypatch.setattr(gtk, "offline", lambda *_: source)
    monkeypatch.setattr(gtk, "DEST_DIR", tmp_path / "installed")
    monkeypatch.setattr(gtk, "run_user", _unexpected)

    gtk.update_assets()

    assert all((gtk.DEST_DIR / variant).is_dir() for variant in gtk.VARIANTS)


def test_aurorae_asset_refresh_does_not_reconfigure_kwin(monkeypatch, tmp_path):
    source = tmp_path / "source"
    for mode in window_decorations.VARIANTS:
        (source / f"TajsDesktop-{mode}").mkdir(parents=True)
        (source / f"TajsDesktop-{mode}" / "decoration.svg").write_text("<svg/>")
        (source / f"icons-{mode}").mkdir()
    monkeypatch.setattr(window_decorations, "offline", lambda *_: source)
    monkeypatch.setattr(window_decorations, "DEST_DIR", tmp_path / "installed")
    monkeypatch.setattr(window_decorations, "kw_write", _unexpected)
    monkeypatch.setattr(window_decorations, "qdbus_call", _unexpected)

    window_decorations.update_assets()

    assert (window_decorations.DEST_DIR / "TajsDesktop-Light/decoration.svg").is_file()


def test_kvantum_asset_refresh_does_not_select_widget_style(monkeypatch):
    monkeypatch.setattr(kvantum, "_copy_assets", lambda: True)
    monkeypatch.setattr(kvantum, "kw_write", _unexpected)

    kvantum.update_assets()


def test_sound_asset_refresh_does_not_select_sound_theme(monkeypatch, tmp_path):
    monkeypatch.setattr(sounds, "DEST_DIR", tmp_path / "sounds")
    monkeypatch.setattr(sounds, "install_tree", lambda *_: True)
    monkeypatch.setattr(sounds, "kw_write", _unexpected)

    sounds.update_assets()


def test_acrylic_asset_refresh_does_not_cycle_live_effect(monkeypatch, tmp_path):
    build = tmp_path / "build"
    effect = build / "src/tajsdesktopglass.so"
    kcm = build / "src/kcm/kwin_tajsdesktopglass_config.so"
    effect.parent.mkdir(parents=True)
    kcm.parent.mkdir(parents=True)
    effect.write_bytes(b"effect")
    kcm.write_bytes(b"kcm")
    installed = []
    monkeypatch.setattr(acrylic_glass, "BUILD", build)
    monkeypatch.setattr(acrylic_glass, "_plugin_dir", lambda: tmp_path / "plugins")
    monkeypatch.setattr(acrylic_glass, "sudo_install_file",
                        lambda src, dest, label: installed.append(dest.name) or True)
    monkeypatch.setattr(acrylic_glass, "kw_write", _unexpected)
    monkeypatch.setattr(acrylic_glass, "qdbus_call", _unexpected)
    monkeypatch.setattr(acrylic_glass, "_install_corner_defaults", _unexpected)

    acrylic_glass.update_assets()

    assert installed == ["tajsdesktopglass.so", "kwin_tajsdesktopglass_config.so"]
