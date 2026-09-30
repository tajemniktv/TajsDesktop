"""Fork wallpaper payloads are discoverable without adopting Tahoe assets."""

from steps import wallpapers


def test_install_selects_only_tajsdesktop_wallpaper_bundles(monkeypatch, tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    for name in ("TajsDesktop-Tahoe", "MacTahoe-Foreign"):
        bundle = source / name
        bundle.mkdir(parents=True)
        (bundle / "metadata.json").write_text("{}")
    copied = []
    monkeypatch.setattr(wallpapers, "OFFLINE_DIR", source)
    monkeypatch.setattr(wallpapers, "DEST_DIR", dest)
    monkeypatch.setattr(wallpapers, "safe_copy",
                        lambda src, target: copied.append((src.name, target.name)) or True)

    wallpapers.install()

    assert copied == [("TajsDesktop-Tahoe", "TajsDesktop-Tahoe")]
