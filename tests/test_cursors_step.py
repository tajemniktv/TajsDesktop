"""Cursor updates must validate first and preserve the installed themes."""

import shutil

import pytest

from steps import cursors


def test_cursor_update_extracts_namespaced_themes_offline(monkeypatch, tmp_path):
    if not shutil.which("zstd"):
        pytest.skip("zstd unavailable")
    monkeypatch.setattr(cursors, "DEST_DIR", tmp_path / "icons")

    cursors.update_assets()

    assert all((cursors.DEST_DIR / name / "index.theme").is_file()
               for name in cursors.THEME_NAMES)
    assert not (cursors.DEST_DIR / "MacTahoe").exists()


def test_bad_cursor_archive_does_not_remove_existing_theme(monkeypatch, tmp_path):
    if not shutil.which("zstd"):
        pytest.skip("zstd unavailable")
    archive_dir = tmp_path / "bundle"
    archive_dir.mkdir()
    (archive_dir / "TajsDesktop-Cursors.tar.zst").write_bytes(b"not an archive")
    existing = tmp_path / "icons/TajsDesktop/index.theme"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"custom")
    monkeypatch.setattr(cursors, "OFFLINE_DIR", archive_dir)
    monkeypatch.setattr(cursors, "DEST_DIR", tmp_path / "icons")
    monkeypatch.setattr(cursors, "fail", lambda *_: None)

    cursors.update_assets()

    assert existing.read_bytes() == b"custom"
