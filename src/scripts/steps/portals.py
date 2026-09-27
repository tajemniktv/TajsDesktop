import os
import signal
import subprocess
from pathlib import Path

from distro import user_service_manager_command
from steps._helpers import HOME, fail, ok, warn
from utils import run_user

CONF_DIR = HOME / ".config/xdg-desktop-portal"
CONF_FILE = CONF_DIR / "kde-portals.conf"
OWNERSHIP_MARKER = HOME / ".local/state/tajsdesktop/portal-routing-owned"
_MARKER_VALUE = "tajsdesktop portal routing v1\n"


# Settings → gtk: portal-kde answers with Aurorae's "XIA" button layout, which
# libadwaita can't parse (mac traffic lights vanish); portal-gtk returns the
# "close,minimize,maximize:" form it expects.
# FileChooser / AppChooser → kde: native Qt dialogs. No `default=` line so
# other portals keep their compiled-in default.
ROUTING = """\
[preferred]
org.freedesktop.impl.portal.Settings=gtk
org.freedesktop.impl.portal.FileChooser=kde
org.freedesktop.impl.portal.AppChooser=kde
"""

PORTAL_SERVICES = (
    "xdg-desktop-portal",
    "xdg-desktop-portal-kde",
    "xdg-desktop-portal-gtk",
)
_PROC_ROOT = Path("/proc")


def _bounce_services() -> None:
    command_prefix = user_service_manager_command("restart")
    if command_prefix is not None:
        manager_ok = True
        for svc in PORTAL_SERVICES:
            try:
                result = run_user(
                    [*command_prefix, svc], check=False, timeout=8,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                manager_ok = result.returncode == 0 and manager_ok
            except (OSError, subprocess.TimeoutExpired):
                manager_ok = False
        if manager_ok:
            return

    # OpenRC and other non-systemd sessions rely on D-Bus activation. This is
    # also the fallback for a temporarily unavailable systemd user manager.
    # Stop only matching same-user portal processes; the next portal request
    # starts them again with the new routing config.
    try:
        uid = int(os.environ.get("SUDO_UID") or os.getuid())
    except ValueError:
        uid = os.getuid()
    wanted = set(PORTAL_SERVICES)
    try:
        processes = list(_PROC_ROOT.iterdir())
    except OSError:
        return
    for process in processes:
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != uid:
                continue
            argv0 = (process / "cmdline").read_bytes().split(b"\0", 1)[0]
            name = Path(os.fsdecode(argv0)).name
            if name in wanted:
                os.kill(int(process.name), signal.SIGTERM)
        except (OSError, ValueError):
            continue


def install() -> None:
    if OWNERSHIP_MARKER.exists() or OWNERSHIP_MARKER.is_symlink():
        warn("KDE portal ownership marker already exists; preserving current routing")
        return
    if CONF_FILE.exists() or CONF_FILE.is_symlink():
        warn("Existing KDE portal routing preserved; explicit reset is "
             "required to replace it")
        return
    CONF_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with CONF_FILE.open("x", encoding="utf-8") as stream:
            stream.write(ROUTING)
    except FileExistsError:
        warn("Existing KDE portal routing preserved")
        return
    except OSError as exc:
        fail(f"KDE portal routing: {exc}")
        return
    marker_created = False
    try:
        OWNERSHIP_MARKER.parent.mkdir(parents=True, exist_ok=True)
        with OWNERSHIP_MARKER.open("x", encoding="utf-8") as stream:
            marker_created = True
            stream.write(_MARKER_VALUE)
    except OSError as exc:
        if marker_created:
            OWNERSHIP_MARKER.unlink(missing_ok=True)
        try:
            if not CONF_FILE.is_symlink() and CONF_FILE.read_text(
                    encoding="utf-8") == ROUTING:
                CONF_FILE.unlink()
        except OSError:
            pass
        fail(f"KDE portal ownership record: {exc}")
        return
    ok("KDE portal routing installed")
    _bounce_services()


def uninstall() -> None:
    if OWNERSHIP_MARKER.is_symlink() or not OWNERSHIP_MARKER.is_file():
        warn("KDE portal routing has no TajsDesktop ownership record; preserving it")
        return
    try:
        if OWNERSHIP_MARKER.read_text(encoding="utf-8") != _MARKER_VALUE:
            warn("KDE portal ownership record is unknown; preserving routing")
            return
    except OSError:
        warn("KDE portal ownership record cannot be read; preserving routing")
        return
    if CONF_FILE.is_symlink():
        warn("KDE portal routing is a symlink; preserving it")
        return
    if CONF_FILE.is_file():
        try:
            if CONF_FILE.read_text(encoding="utf-8") != ROUTING:
                warn("KDE portal routing was modified; preserving user changes")
                return
            CONF_FILE.unlink()
            OWNERSHIP_MARKER.unlink()
            ok("KDE portal routing removed")
        except OSError:
            fail("KDE portal routing")
    else:
        ok("KDE portal routing (not installed)")
        return
    _bounce_services()
