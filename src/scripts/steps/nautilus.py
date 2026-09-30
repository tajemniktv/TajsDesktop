import configparser
import hashlib
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from steps._helpers import HOME, fail, feat_enabled, have, kw_write, ok, offline, warn
from utils import is_plasma_session, run_user

NAUTILUS_DESKTOP = "org.gnome.Nautilus.desktop"
MIME_FOLDER = "inode/directory"
MIME_SEARCH = "application/x-gnome-saved-search"
_NAUTILUS_TOOL_TIMEOUT_SECONDS = 5

# XDG directories to include in the Nautilus sidebar, in display order.
# Keys correspond to XDG_xxx_DIR variables in ~/.config/user-dirs.dirs.
_XDG_SIDEBAR_ORDER = ("DESKTOP", "DOCUMENTS", "DOWNLOAD", "PICTURES", "VIDEOS", "MUSIC")


def deps():
    return ["nautilus"]


def _set_default_if_absent(desktop_id: str, mime: str) -> bool:
    """Initialize a MIME handler only if the user has no explicit value."""
    config_root = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config")
    config = config_root / "mimeapps.list"
    if config.is_symlink():
        warn("Symlinked MIME defaults preserved")
        return False
    parser = configparser.RawConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        if config.exists():
            parser.read(config, encoding="utf-8")
    except (OSError, configparser.Error):
        warn("MIME defaults cannot be read; preserving them")
        return False
    if parser.has_option("Default Applications", mime):
        return False
    return kw_write(
        "--file", "mimeapps.list",
        "--group", "Default Applications",
        "--key", mime, desktop_id,
    )


def _generate_bookmarks() -> None:
    """Initialize bookmarks only when absent; never replace a user's list."""
    if not feat_enabled("nautilus_bookmarks"):
        return
    src = HOME / ".config/user-dirs.dirs"
    if not src.is_file():
        warn("~/.config/user-dirs.dirs not found — skipping Nautilus bookmarks")
        return

    dirs: dict[str, Path] = {}
    for line in src.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r'^XDG_(\w+)_DIR="(.+)"$', line)
        if m:
            key = m.group(1)
            path_str = m.group(2).replace("$HOME", str(HOME))
            dirs[key] = Path(path_str)

    lines: list[str] = []
    for key in _XDG_SIDEBAR_ORDER:
        path = dirs.get(key)
        if path is None or not path.is_dir():
            continue
        # xdg-user-dirs disables a dir by pointing it at $HOME itself —
        # never bookmark the whole home directory.
        if path == HOME:
            continue
        uri = "file://" + quote(str(path), safe="/")
        lines.append(f"{uri} {path.name}")

    if not lines:
        warn("No XDG directories found — skipping Nautilus bookmarks")
        return

    dest = HOME / ".config/gtk-3.0"
    if dest.is_symlink():
        warn("Symlinked GTK configuration preserved")
        return
    dest.mkdir(parents=True, exist_ok=True)
    bookmarks = dest / "bookmarks"
    marker = dest / "bookmarks.tajsdesktop-owned"
    if (bookmarks.exists() or bookmarks.is_symlink() or marker.exists()
            or marker.is_symlink()):
        warn("Existing GTK bookmarks preserved")
        return
    content = "\n".join(lines) + "\n"
    try:
        with bookmarks.open("x", encoding="utf-8") as stream:
            stream.write(content)
        try:
            with marker.open("x", encoding="utf-8") as stream:
                stream.write(hashlib.sha256(content.encode("utf-8")).hexdigest() + "\n")
        except OSError:
            if bookmarks.read_text(encoding="utf-8") == content:
                bookmarks.unlink()
            raise
    except OSError as exc:
        warn(f"Could not initialize GTK bookmarks: {exc}")
        return
    ok(f"Bookmarks written ({len(lines)} entries)")


def _apply_overrides() -> None:
    src = offline("nautilus")
    if not src.is_dir():
        return
    source = src / "gtk.css"
    if not source.is_file():
        return
    directory = HOME / ".config/nautilus"
    dest = directory / "gtk.css"
    marker = directory / "gtk.css.tajsdesktop-owned"
    if (directory.is_symlink() or dest.exists() or dest.is_symlink()
            or marker.exists() or marker.is_symlink()):
        warn("Existing Nautilus CSS preserved")
        return
    try:
        content = source.read_bytes()
        directory.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as stream:
            stream.write(content)
        try:
            with marker.open("x", encoding="utf-8") as stream:
                stream.write(hashlib.sha256(content).hexdigest() + "\n")
        except OSError:
            if dest.read_bytes() == content:
                dest.unlink()
            raise
    except OSError as exc:
        warn(f"Nautilus CSS not initialized: {exc}")
        return
    ok("Nautilus CSS initialized")


def update_assets() -> None:
    """Refresh only a fork-owned, unmodified CSS payload; no app preferences."""
    css = HOME / ".config/nautilus/gtk.css"
    marker = css.with_name("gtk.css.tajsdesktop-owned")
    if marker.is_symlink() or not marker.is_file() or css.is_symlink() or not css.is_file():
        return
    try:
        previous = marker.read_text(encoding="utf-8").strip()
        if (not re.fullmatch(r"[0-9a-f]{64}", previous)
                or hashlib.sha256(css.read_bytes()).hexdigest() != previous):
            warn("Nautilus CSS was customized; asset update skipped")
            return
        source = offline("nautilus") / "gtk.css"
        content = source.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest == previous:
            return
        fd, name = tempfile.mkstemp(prefix=".gtk.css.tajsdesktop-", dir=css.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, css)
        except BaseException:
            Path(name).unlink(missing_ok=True)
            raise
        marker.write_text(digest + "\n", encoding="utf-8")
        ok("Nautilus CSS payload updated")
    except OSError as exc:
        fail(f"Nautilus CSS asset update failed: {exc}")


_FINDER_GSETTINGS = (
    ("org.gnome.nautilus.preferences", "default-folder-viewer", "icon-view"),
    ("org.gnome.nautilus.preferences", "show-hidden-files", "false"),
    ("org.gnome.nautilus.preferences", "default-sort-order", "name"),
    ("org.gnome.nautilus.preferences", "show-create-link", "true"),
    ("org.gnome.nautilus.preferences", "click-policy", "double"),
    ("org.gnome.nautilus.icon-view", "default-zoom-level", "small"),
)


def _nautilus_running() -> bool:
    return run_user(
        ["pgrep", "-x", "nautilus"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def _restart_running_nautilus() -> bool:
    if not _nautilus_running():
        return False
    if not have("gdbus"):
        warn("gdbus not found — skipping live Nautilus restart")
        return False
    # Nautilus 50+ quits via org.gtk.Actions Activate("quit"), not the legacy
    # Application.Quit; the ack is immediate but exit takes ~5-10s.
    try:
        rc = run_user(
            [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Nautilus",
                "--object-path", "/org/gnome/Nautilus",
                "--method", "org.gtk.Actions.Activate",
                "quit", "[]", "{}",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).returncode
    except subprocess.TimeoutExpired:
        warn("Timed out waiting for Nautilus to quit")
        return False
    if rc != 0:
        warn(f"Live Nautilus restart skipped (gdbus rc={rc})")
        return False
    # 15s exit window — Nautilus 50.1 with multiple windows takes ~10s to
    # drain; the 100ms poll lets the relaunch start promptly.
    for _ in range(150):
        if not _nautilus_running():
            break
        time.sleep(0.1)
    else:
        warn("Nautilus did not exit cleanly — leaving it alone")
        return False

    if have("gapplication"):
        from utils import drop_privs_in_child as _drop
        subprocess.Popen(
            ["gapplication", "launch", "org.gnome.Nautilus"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            preexec_fn=_drop,
        )
        ok("Nautilus restarted")
        return True

    warn("gapplication not found — skipping Nautilus relaunch")
    return False


def _apply_gsettings() -> None:
    # GSettings `get` includes schema defaults and cannot distinguish an
    # explicit user value. The dconf backend exposes only stored overrides.
    if (not have("gsettings") or not have("dconf")
            or os.environ.get("GSETTINGS_BACKEND", "dconf") != "dconf"):
        warn("Nautilus preferences left unchanged; dconf ownership unavailable")
        return
    for schema, key, value in _FINDER_GSETTINGS:
        path = "/" + schema.replace(".", "/") + "/" + key
        try:
            existing = run_user(
                ["dconf", "read", path], check=False, capture_output=True,
                text=True, timeout=_NAUTILUS_TOOL_TIMEOUT_SECONDS,
            )
            if existing.returncode != 0 or existing.stdout.strip():
                continue
            result = run_user(
                ["gsettings", "set", schema, key, value],
                check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=_NAUTILUS_TOOL_TIMEOUT_SECONDS,
            )
            if result.returncode != 0:
                warn(f"Nautilus preference {schema}:{key} not initialized")
        except (OSError, subprocess.TimeoutExpired):
            warn(f"Nautilus preference {schema}:{key} unavailable — skipping")


def install() -> None:
    if not is_plasma_session():
        warn("Not running under KDE Plasma — skipping Nautilus setup")
        return

    if not have("nautilus"):
        fail("Nautilus not installed (expected deps to have provided it)")
        return

    if _set_default_if_absent(NAUTILUS_DESKTOP, MIME_FOLDER):
        ok("Nautilus initialized as default for folders")
    _set_default_if_absent(NAUTILUS_DESKTOP, MIME_SEARCH)

    _generate_bookmarks()
    _apply_overrides()
    _apply_gsettings()
    if _nautilus_running():
        _restart_running_nautilus()
    ok("Nautilus configured")


def uninstall() -> None:
    if not is_plasma_session():
        return
    # No pre-install MIME snapshot exists, so replacing the current handler
    # with Dolphin would destroy a later user choice (or a choice predating
    # this fork). Explicit reset needs a separate ownership record.
    _remove_owned_css()
    _restore_bookmarks()


def _remove_owned_css() -> None:
    nautilus_css = HOME / ".config/nautilus/gtk.css"
    marker = nautilus_css.with_name("gtk.css.tajsdesktop-owned")
    if marker.is_symlink() or not marker.is_file():
        return
    try:
        expected = marker.read_text(encoding="utf-8").strip()
        if (not re.fullmatch(r"[0-9a-f]{64}", expected)
                or nautilus_css.is_symlink() or not nautilus_css.is_file()):
            return
        if hashlib.sha256(nautilus_css.read_bytes()).hexdigest() != expected:
            warn("Nautilus CSS was modified; preserving user changes")
            return
        nautilus_css.unlink()
        marker.unlink()
        ok("TajsDesktop Nautilus CSS removed")
    except OSError as exc:
        warn(f"Could not remove TajsDesktop Nautilus CSS: {exc}")


def _restore_bookmarks() -> None:
    """Remove only an unmodified bookmark file created by this fork."""
    dest = HOME / ".config/gtk-3.0"
    bookmarks = dest / "bookmarks"
    marker = dest / "bookmarks.tajsdesktop-owned"
    if marker.is_symlink() or not marker.is_file():
        return
    try:
        expected = marker.read_text(encoding="utf-8").strip()
        if (not re.fullmatch(r"[0-9a-f]{64}", expected)
                or bookmarks.is_symlink() or not bookmarks.is_file()):
            return
        if hashlib.sha256(bookmarks.read_bytes()).hexdigest() != expected:
            warn("GTK bookmarks were modified; preserving user changes")
            return
        bookmarks.unlink()
        marker.unlink()
        ok("TajsDesktop GTK bookmarks removed")
    except OSError as exc:
        warn(f"Could not remove TajsDesktop GTK bookmarks: {exc}")
