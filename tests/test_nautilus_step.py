"""Nautilus sidebar bookmarks.

``nautilus._generate_bookmarks()`` writes ``~/.config/gtk-3.0/bookmarks``
from ``~/.config/user-dirs.dirs`` so the labels follow the system
language (Desktop, Documentos, Download, …) instead of a hardcoded
template.
"""

from __future__ import annotations

from pathlib import Path


def _run_generate_bookmarks(
    tmp_path, monkeypatch, user_dirs_text
) -> Path:
    """Wire nautilus.py to a fake home with a user-dirs.dirs and real
    XDG directories, then run ``_generate_bookmarks()``. Returns the
    written bookmarks path."""
    from steps import nautilus

    home = tmp_path / "home"
    home.mkdir(exist_ok=True)

    # Write user-dirs.dirs
    (home / ".config").mkdir(parents=True, exist_ok=True)
    (home / ".config/user-dirs.dirs").write_text(
        user_dirs_text, encoding="utf-8"
    )

    # Create the actual XDG directories so path.is_dir() passes
    for line in user_dirs_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if 'XDG_' in line and '_DIR="' in line:
            import re
            m = re.match(r'^XDG_\w+_DIR="(.+)"$', line)
            if m:
                path_str = m.group(1).replace("$HOME", str(home))
                Path(path_str).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(nautilus, "HOME", home)
    monkeypatch.setattr(nautilus, "ok", lambda _msg: None)
    monkeypatch.setattr(nautilus, "warn", lambda _msg: None)
    monkeypatch.setattr(nautilus, "fail", lambda _msg: None)

    nautilus._generate_bookmarks()

    return home / ".config" / "gtk-3.0" / "bookmarks"


def test_bookmarks_generated_from_xdg_user_dirs_pt(tmp_path, monkeypatch):
    """Portuguese locale: labels match the XDG dir names on disk."""
    bookmarks = _run_generate_bookmarks(
        tmp_path,
        monkeypatch,
        user_dirs_text=(
            '# Portuguese locale\n'
            'XDG_DESKTOP_DIR="$HOME/Área de trabalho"\n'
            'XDG_DOCUMENTS_DIR="$HOME/Documentos"\n'
            'XDG_DOWNLOAD_DIR="$HOME/Downloads"\n'
            'XDG_PICTURES_DIR="$HOME/Imagens"\n'
            'XDG_VIDEOS_DIR="$HOME/Vídeos"\n'
            'XDG_MUSIC_DIR="$HOME/Músicas"\n'
        ),
    )

    assert bookmarks.is_file(), "bookmarks file was not written"
    content = bookmarks.read_text(encoding="utf-8")
    assert "Área de trabalho" in content
    assert "Imagens" in content


def test_bookmarks_generated_from_xdg_user_dirs_en(tmp_path, monkeypatch):
    """English locale: labels match the XDG dir names on disk."""
    bookmarks = _run_generate_bookmarks(
        tmp_path,
        monkeypatch,
        user_dirs_text=(
            'XDG_DESKTOP_DIR="$HOME/Desktop"\n'
            'XDG_DOCUMENTS_DIR="$HOME/Documents"\n'
            'XDG_DOWNLOAD_DIR="$HOME/Downloads"\n'
            'XDG_PICTURES_DIR="$HOME/Pictures"\n'
            'XDG_VIDEOS_DIR="$HOME/Videos"\n'
            'XDG_MUSIC_DIR="$HOME/Music"\n'
        ),
    )

    content = bookmarks.read_text(encoding="utf-8")
    assert "Desktop" in content
    assert "Documents" in content
    assert "Music" in content
    assert "Pictures" in content


def test_bookmarks_missing_user_dirs_is_silent(tmp_path, monkeypatch):
    """When ~/.config/user-dirs.dirs does not exist, no bookmarks file
    should be written and no crash should occur."""
    from steps import nautilus

    home = tmp_path / "home"
    home.mkdir()

    monkeypatch.setattr(nautilus, "HOME", home)
    monkeypatch.setattr(nautilus, "ok", lambda _msg: None)
    monkeypatch.setattr(nautilus, "warn", lambda _msg: None)
    monkeypatch.setattr(nautilus, "fail", lambda _msg: None)

    nautilus._generate_bookmarks()

    bookmarks = home / ".config" / "gtk-3.0" / "bookmarks"
    assert not bookmarks.exists()


def test_bookmarks_order_follows_xdg_sidebar_order(tmp_path, monkeypatch):
    """The order of entries in the bookmarks file must match
    _XDG_SIDEBAR_ORDER, not the order in user-dirs.dirs."""
    bookmarks = _run_generate_bookmarks(
        tmp_path,
        monkeypatch,
        user_dirs_text=(
            'XDG_MUSIC_DIR="$HOME/Music"\n'
            'XDG_DOWNLOAD_DIR="$HOME/Downloads"\n'
            'XDG_DESKTOP_DIR="$HOME/Desktop"\n'
            'XDG_PICTURES_DIR="$HOME/Pictures"\n'
            'XDG_VIDEOS_DIR="$HOME/Videos"\n'
            'XDG_DOCUMENTS_DIR="$HOME/Documents"\n'
        ),
    )

    lines = bookmarks.read_text(encoding="utf-8").strip().splitlines()
    # Should be: DESKTOP, DOCUMENTS, DOWNLOAD, PICTURES, VIDEOS, MUSIC
    labels = [line.split()[-1] for line in lines]
    assert labels == ["Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music"], (
        f"Expected fixed order, got: {labels}"
    )


_EN_DIRS = (
    'XDG_DESKTOP_DIR="$HOME/Desktop"\n'
    'XDG_DOCUMENTS_DIR="$HOME/Documents"\n'
    'XDG_DOWNLOAD_DIR="$HOME/Downloads"\n'
)


def test_bookmarks_flag_disabled_skips_generation(tmp_path, monkeypatch):
    """FEAT_NAUTILUS_BOOKMARKS=false must skip bookmark generation
    entirely — the user's file is never touched."""
    monkeypatch.setenv("FEAT_NAUTILUS_BOOKMARKS", "false")
    bookmarks = _run_generate_bookmarks(
        tmp_path, monkeypatch, user_dirs_text=_EN_DIRS,
    )
    assert not bookmarks.exists()


def test_existing_bookmarks_are_not_overwritten(tmp_path, monkeypatch):
    """An existing GTK bookmark list is user-owned, even at first install."""
    home = tmp_path / "home"
    (home / ".config/gtk-3.0").mkdir(parents=True)
    original = "file:///home/user/MyStuff MyStuff\n"
    (home / ".config/gtk-3.0/bookmarks").write_text(original)

    bookmarks = _run_generate_bookmarks(
        tmp_path, monkeypatch, user_dirs_text=_EN_DIRS,
    )

    assert bookmarks.read_text() == original
    assert not (bookmarks.parent / "bookmarks.tajsdesktop-owned").exists()


def test_bookmarks_reinstall_preserves_user_changes(tmp_path, monkeypatch):
    """A later install must never rebuild a user's edited bookmark list."""
    home = tmp_path / "home"
    (home / ".config/gtk-3.0").mkdir(parents=True)
    bookmarks = _run_generate_bookmarks(
        tmp_path, monkeypatch, user_dirs_text=_EN_DIRS,
    )
    bookmarks.write_text("file:///home/user/MyStuff MyStuff\n")
    from steps import nautilus
    nautilus._generate_bookmarks()  # reinstall

    assert bookmarks.read_text() == "file:///home/user/MyStuff MyStuff\n"


def _run_uninstall_bookmarks(tmp_path, monkeypatch):
    """Wire nautilus.py to a fake home and run uninstall(). Returns the
    (bookmarks, ownership marker) paths."""
    from steps import nautilus

    home = tmp_path / "home"
    (home / ".config/gtk-3.0").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(nautilus, "HOME", home)
    monkeypatch.setattr(nautilus, "is_plasma_session", lambda: True)
    monkeypatch.setattr(nautilus, "have", lambda _name: False)
    monkeypatch.setattr(nautilus, "ok", lambda _msg: None)
    monkeypatch.setattr(nautilus, "warn", lambda _msg: None)
    monkeypatch.setattr(nautilus, "fail", lambda _msg: None)

    nautilus.uninstall()

    dest = home / ".config/gtk-3.0"
    return dest / "bookmarks", dest / "bookmarks.tajsdesktop-owned"


def test_uninstall_preserves_legacy_tahoe_backup_and_bookmarks(tmp_path, monkeypatch):
    """A Tahoe backup is foreign state, not fork ownership evidence."""
    home = tmp_path / "home"
    (home / ".config/gtk-3.0").mkdir(parents=True)
    original = "file:///home/user/MyStuff MyStuff\n"
    (home / ".config/gtk-3.0/bookmarks").write_text("file:///gen Generated\n")
    (home / ".config/gtk-3.0/bookmarks.mac-tahoe-backup").write_text(original)

    bookmarks, marker = _run_uninstall_bookmarks(tmp_path, monkeypatch)

    assert bookmarks.read_text() == "file:///gen Generated\n"
    assert (bookmarks.parent / "bookmarks.mac-tahoe-backup").read_text() == original
    assert not marker.exists()


def test_uninstall_preserves_unmarked_bookmarks(tmp_path, monkeypatch):
    """An unmarked file is foreign even if it looks generated."""
    home = tmp_path / "home"
    (home / ".config/gtk-3.0").mkdir(parents=True)
    (home / ".config/gtk-3.0/bookmarks").write_text("file:///gen Generated\n")

    bookmarks, marker = _run_uninstall_bookmarks(tmp_path, monkeypatch)

    assert bookmarks.read_text() == "file:///gen Generated\n"
    assert not marker.exists()


def test_uninstall_removes_only_unchanged_fork_bookmarks(tmp_path, monkeypatch):
    bookmarks = _run_generate_bookmarks(
        tmp_path, monkeypatch, user_dirs_text=_EN_DIRS,
    )
    from steps import nautilus
    marker = bookmarks.parent / "bookmarks.tajsdesktop-owned"
    assert marker.is_file()

    nautilus._restore_bookmarks()

    assert not bookmarks.exists()
    assert not marker.exists()


def test_uninstall_preserves_edited_fork_bookmarks(tmp_path, monkeypatch):
    bookmarks = _run_generate_bookmarks(
        tmp_path, monkeypatch, user_dirs_text=_EN_DIRS,
    )
    from steps import nautilus
    marker = bookmarks.parent / "bookmarks.tajsdesktop-owned"
    bookmarks.write_text(bookmarks.read_text() + "file:///custom Custom\n")

    nautilus._restore_bookmarks()

    assert bookmarks.read_text().endswith("file:///custom Custom\n")
    assert marker.is_file()


def test_bookmarks_cjk_labels(tmp_path, monkeypatch):
    """Chinese locale: CJK directory names survive as labels."""
    bookmarks = _run_generate_bookmarks(
        tmp_path,
        monkeypatch,
        user_dirs_text=(
            'XDG_DESKTOP_DIR="$HOME/桌面"\n'
            'XDG_DOCUMENTS_DIR="$HOME/文档"\n'
            'XDG_DOWNLOAD_DIR="$HOME/下载"\n'
            'XDG_MUSIC_DIR="$HOME/音乐"\n'
        ),
    )

    content = bookmarks.read_text(encoding="utf-8")
    assert "桌面" in content
    assert "下载" in content


def test_bookmarks_cyrillic_labels(tmp_path, monkeypatch):
    """Russian locale: Cyrillic names with spaces survive as labels."""
    bookmarks = _run_generate_bookmarks(
        tmp_path,
        monkeypatch,
        user_dirs_text=(
            'XDG_DESKTOP_DIR="$HOME/Рабочий стол"\n'
            'XDG_DOCUMENTS_DIR="$HOME/Документы"\n'
            'XDG_DOWNLOAD_DIR="$HOME/Загрузки"\n'
        ),
    )

    content = bookmarks.read_text(encoding="utf-8")
    assert "Рабочий стол" in content
    assert "Загрузки" in content


def test_bookmarks_non_ascii_uri_is_percent_encoded(tmp_path, monkeypatch):
    """GTK expects percent-encoded UTF-8 in the URI part; the label
    part keeps the raw name. Both must hold for non-ASCII dirs."""
    bookmarks = _run_generate_bookmarks(
        tmp_path,
        monkeypatch,
        user_dirs_text='XDG_DOCUMENTS_DIR="$HOME/Documentos españoles"\n',
    )

    line = bookmarks.read_text(encoding="utf-8").strip()
    uri, label = line.split(" ", 1)
    assert uri.startswith("file://")
    assert " " not in uri, "URI part must not contain raw spaces"
    assert "%20" in uri and "%C3%B1" in uri, f"URI not percent-encoded: {uri}"
    assert label == "Documentos españoles"


def test_bookmarks_disabled_xdg_dir_is_skipped(tmp_path, monkeypatch):
    """xdg-user-dirs disables a directory by pointing it at $HOME
    itself. That entry must be skipped — never bookmark the whole
    home directory."""
    bookmarks = _run_generate_bookmarks(
        tmp_path,
        monkeypatch,
        user_dirs_text=(
            'XDG_DESKTOP_DIR="$HOME/Desktop"\n'
            'XDG_MUSIC_DIR="$HOME/"\n'      # disabled → points at $HOME
            'XDG_VIDEOS_DIR="$HOME"\n'      # variant without slash
        ),
    )

    lines = bookmarks.read_text(encoding="utf-8").strip().splitlines()
    labels = [line.split(" ", 1)[1] for line in lines]
    assert labels == ["Desktop"], (
        f"disabled dirs must be skipped, got: {labels}"
    )
