import json
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from steps._helpers import (
    DATA_HOME, HOME, fail, have, install_tree, ok, offline, qdbus_call, warn,
)
from utils import qdbus_cmd, run_user

LAYOUT_SCRIPT = offline("layouts/mac-tahoe.js")
LAYOUT_RESET = offline("layouts/default.js")
_DISCOVER_DESKTOP = "applications:org.kde.discover.desktop"
COLORIZER_ID = "luisbocanegra.panel.colorizer"
COLORIZER_SRC = offline("plasmoids") / COLORIZER_ID
MAC_TASKS_ID = "org.tajemniktv.tajsdesktop.icontasks"
DEFAULT_TASKS_ID = "org.kde.plasma.icontasks"


def _colorizer_dirs() -> list[Path]:
    dirs = [DATA_HOME / "plasma/plasmoids" / COLORIZER_ID]
    for base in ("/usr/local/share", "/usr/share"):
        dirs.append(Path(base) / "plasma/plasmoids" / COLORIZER_ID)
    return dirs


def _colorizer_version(path: Path) -> tuple[int, ...] | None:
    """Return a comparable version from a Panel Colorizer package."""
    try:
        version = json.loads(
            (path / "metadata.json").read_text(encoding="utf-8")
        )["KPlugin"]["Version"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return None
    if (
        not isinstance(version, str)
        or not re.fullmatch(r"\d+(?:\.\d+)*", version)
    ):
        return None
    parts = tuple(int(part) for part in version.split("."))
    return parts + (0,) * (3 - len(parts))


def deps():
    return ["qdbus6:qt6-tools"]


def _ensure_panel_colorizer() -> None:
    # Panel Colorizer has a shared, non-project ID. Never replace or shadow
    # another installation merely because our bundled version is newer.
    bundled_version = _colorizer_version(COLORIZER_SRC)
    if bundled_version is None:
        warn("Panel Colorizer not installed — bundled metadata is invalid.")
        return

    dirs = _colorizer_dirs()
    dest = dirs[0]
    for path in dirs:
        if path.exists() or path.is_symlink():
            version = _colorizer_version(path)
            if version is not None and version < bundled_version:
                warn("Existing Panel Colorizer is older than the bundled copy; "
                     "preserving the external installation")
            else:
                ok("Panel Colorizer (existing installation preserved)")
            return

    if install_tree(COLORIZER_SRC, dest, "Panel Colorizer"):
        return
    warn("Panel Colorizer not installed — top bar won't be transparent. "
         "Install manually from KDE Store.")


def _evaluate_layout_script(script: str) -> bool:
    if qdbus_cmd() is None:
        warn("qdbus not found — layout not installed")
        return False
    # plasmashell may still be restarting from the apply step — retry a few times.
    for _ in range(5):
        if qdbus_call(
            "org.kde.plasmashell",
            "/PlasmaShell",
            "org.kde.PlasmaShell.evaluateScript",
            script,
        ):
            return True
        time.sleep(3)
    return False


def _discover_is_installed() -> bool:
    """Check if org.kde.discover.desktop exists in any XDG applications dir."""
    for prefix in (DATA_HOME, Path("/usr/local/share"), Path("/usr/share")):
        if (prefix / "applications/org.kde.discover.desktop").is_file():
            return True
    return False


def _evaluate_layout(script_path) -> bool:
    script = script_path.read_text()
    if not _discover_is_installed():
        script = script.replace(_DISCOVER_DESKTOP + ",", "")
        script = script.replace("," + _DISCOVER_DESKTOP, "")
    return _evaluate_layout_script(script)


def _capture_pinned_launchers() -> list[str]:
    """User-pinned launchers from appletsrc, deduped in order; MacTahoe's
    own plasmoids are dropped so a reinstall doesn't double them."""
    appletsrc = HOME / ".config/plasma-org.kde.plasma.desktop-appletsrc"
    if not appletsrc.is_file():
        return []
    try:
        text = appletsrc.read_text()
    except OSError:
        return []
    seen: list[str] = []
    for m in re.finditer(r"^launchers=(.*)$", text, re.MULTILINE):
        for entry in m.group(1).split(","):
            entry = entry.strip()
            if entry and "org.tajemniktv.tajsdesktop" not in entry:
                if entry not in seen:
                    seen.append(entry)
    return seen


def _append_launcher_restore(
        script: str, pins: list[str], widget_type: str) -> str:
    if pins:
        joined = repr(",".join(pins))
        widget = repr(widget_type)
        script += (
            "\n(function () {\n"
            "  var ps = panels();\n"
            "  for (var i = 0; i < ps.length; i++) {\n"
            "    var ws = ps[i].widgetIds;\n"
            "    for (var j = 0; j < ws.length; j++) {\n"
            "      var w = ps[i].widgetById(ws[j]);\n"
            f"      if (w && w.type === {widget}) {{\n"
            "        w.currentConfigGroup = ['General'];\n"
            f"        w.writeConfig('launchers', {joined});\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "})();\n"
        )
    return script


def _layout_script_with_launchers(
        script_path: Path, pins: list[str], widget_type: str) -> str | None:
    if not script_path.is_file():
        return None
    script = script_path.read_text()
    if not _discover_is_installed():
        script = script.replace(_DISCOVER_DESKTOP + ",", "")
        script = script.replace("," + _DISCOVER_DESKTOP, "")
    return _append_launcher_restore(script, pins, widget_type)


def _evaluate_layout_with_launchers(
        script_path: Path, pins: list[str], widget_type: str) -> bool:
    script = _layout_script_with_launchers(script_path, pins, widget_type)
    return script is not None and _evaluate_layout_script(script)


def _restore_pins(pins: list[str], widget_type: str) -> bool:
    if not pins:
        return True
    return _evaluate_layout_script(
        _append_launcher_restore("", pins, widget_type),
    )


def _reset_with_pins(pins: list[str]) -> bool:
    """Build the bundled Breeze panel and restore only user launchers."""
    script = _layout_script_with_launchers(
        LAYOUT_RESET, pins, DEFAULT_TASKS_ID,
    )
    if script is None:
        return False
    return _evaluate_layout_script(script)


def _reset_layout_builtin() -> bool:
    if not have("plasma-apply-lookandfeel"):
        return False
    try:
        res = run_user(
            ["plasma-apply-lookandfeel", "-a", "org.kde.breeze.desktop", "--resetLayout"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        return False
    if res.returncode != 0:
        return False
    blob = "\n".join(part for part in (res.stdout, res.stderr) if part)
    if "Usage: plasma-apply-lookandfeel" in blob:
        return False
    return True


_DEFAULT_PANEL_NEEDLES = (
    "plugin=org.kde.plasma.kickoff",
    "plugin=org.kde.plasma.pager",
    "plugin=org.kde.plasma.icontasks",
    "plugin=org.kde.plasma.systemtray",
    "plugin=org.kde.plasma.digitalclock",
    "plugin=org.kde.plasma.showdesktop",
)
_CUSTOM_PANEL_NEEDLES = (
    "plugin=org.tajemniktv.tajsdesktop.globalmenu",
    "plugin=org.tajemniktv.tajsdesktop.icontasks",
    "plugin=org.tajemniktv.tajsdesktop.launcher",
    "plugin=org.tajemniktv.tajsdesktop.trashcan",
)
_THEME_PLUGIN_RE = re.compile(
    r"^plugin=org\.kde\.(?:"
    r"tajsdesktop|"
    r"mac\.tahoe(?:\.liquid)?|"
    r"mactahoe-liquid-kde"
    r")\.",
    re.MULTILINE,
)


def _layout_marker() -> Path:
    return HOME / ".local/state/tajsdesktop/layout-installed"


_CONTAINMENT_RE = re.compile(r"(?m)^\[Containments\]\[(\d+)\](?:\[[^\n]*\])?\n")
_VIEW_RE = re.compile(r"(?m)^\[PlasmaViews\]\[Panel (\d+)\](?:\[[^\n]*\])?\n")


def _sections(text: str, pattern: re.Pattern[str]) -> dict[int, str]:
    matches = list(pattern.finditer(text))
    result: dict[int, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        key = int(match.group(1))
        result[key] = result.get(key, "") + text[match.start():end]
    return result


def _panel_snapshots() -> dict[int, str]:
    appletsrc = HOME / ".config/plasma-org.kde.plasma.desktop-appletsrc"
    prc = HOME / ".config/plasmashellrc"
    if appletsrc.is_symlink() or prc.is_symlink():
        raise OSError("symlinked Plasma configuration cannot be snapshotted")
    applets = _sections(appletsrc.read_text(encoding="utf-8"), _CONTAINMENT_RE) if appletsrc.is_file() else {}
    views = _sections(prc.read_text(encoding="utf-8"), _VIEW_RE) if prc.is_file() else {}
    result = {}
    for panel_id, content in applets.items():
        marker = f"[Containments][{panel_id}][TajsDesktop]\nowner=tajsdesktop"
        if marker not in content:
            continue
        digest = hashlib.sha256((content + "\0" + views.get(panel_id, "")).encode()).hexdigest()
        result[panel_id] = digest
    return result


def _containment_ids() -> set[int]:
    appletsrc = HOME / ".config/plasma-org.kde.plasma.desktop-appletsrc"
    if appletsrc.is_symlink():
        raise OSError("symlinked Plasma configuration cannot be inspected")
    if not appletsrc.is_file():
        return set()
    return set(_sections(appletsrc.read_text(encoding="utf-8"), _CONTAINMENT_RE))


def _mark_layout_installed(snapshots: dict[int, str]) -> None:
    marker = _layout_marker()
    if marker.parent.is_symlink():
        raise OSError("layout state directory is a symlink")
    marker.parent.mkdir(parents=True, exist_ok=True)
    if marker.is_symlink():
        raise OSError("layout ownership marker is a symlink")
    fd, name = tempfile.mkstemp(prefix=".layout-", dir=marker.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"schema": 1, "panels": {str(k): v for k, v in snapshots.items()}}, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, marker)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def _clear_layout_marker() -> None:
    try:
        _layout_marker().unlink()
    except OSError:
        pass


def _layout_has_any_theme_widget() -> bool:
    appletsrc = HOME / ".config/plasma-org.kde.plasma.desktop-appletsrc"
    try:
        text = appletsrc.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return _THEME_PLUGIN_RE.search(text) is not None


def _layout_looks_reset() -> bool:
    """'Reset' = no MacTahoe plugin IDs left in appletsrc. Default Breeze
    needles may land asynchronously (plasma-apply-lookandfeel), so their
    presence is not required."""
    appletsrc = HOME / ".config/plasma-org.kde.plasma.desktop-appletsrc"
    if not appletsrc.is_file():
        return True
    try:
        text = appletsrc.read_text()
    except OSError:
        return False
    return _THEME_PLUGIN_RE.search(text) is None


def _layout_looks_installed() -> bool:
    appletsrc = HOME / ".config/plasma-org.kde.plasma.desktop-appletsrc"
    if not appletsrc.is_file():
        return False
    try:
        text = appletsrc.read_text()
    except OSError:
        return False
    return all(needle in text for needle in _CUSTOM_PANEL_NEEDLES)


def _wait_for_layout_install(timeout_seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _layout_looks_installed():
            return True
        time.sleep(0.2)
    return _layout_looks_installed()


def _wait_for_owned_snapshots(before: set[int], timeout_seconds: float = 5.0) -> dict[int, str]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        created = {key: value for key, value in _panel_snapshots().items()
                   if key not in before}
        if created or time.monotonic() >= deadline:
            return created
        time.sleep(0.2)


# Plasma's JS API doesn't expose panelOpacity / floatingApplets, so they
# are patched into plasmashellrc directly after the layout runs.
_PRC_PANEL_RE = re.compile(
    r"(\[PlasmaViews\]\[Panel \d+\]\n(?:[^\[]*\n)*)", re.MULTILINE,
)


def _patch_plasmashellrc() -> None:
    prc = HOME / ".config/plasmashellrc"
    if not prc.is_file():
        return
    text = prc.read_text()

    def fix(m: re.Match) -> str:
        section = m.group(0)
        # Force Translucent (2) on every panel so the top bar doesn't fall
        # back to Plasma's Adaptive default, which turns opaque whenever a
        # window touches the screen edge under it — defeating the glass look
        # on the one panel that isn't floating.
        if "panelOpacity=" in section:
            section = re.sub(r"panelOpacity=\d+", "panelOpacity=2", section)
        else:
            section = section.rstrip() + "\npanelOpacity=2\n"
        if "floating=0" in section:
            # Keep the top bar applets-only floating while Panel Colorizer
            # hides the continuous native panel background (see mac-tahoe.js).
            if "floatingApplets=" in section:
                section = re.sub(r"floatingApplets=\d+", "floatingApplets=1", section)
            else:
                section = section.rstrip() + "\nfloatingApplets=1\n"
        return section

    new_text = _PRC_PANEL_RE.sub(fix, text)
    if new_text != text:
        prc.write_text(new_text)
        ok("Panel glass forced translucent")


def _reset_plasmashellrc() -> bool:
    """Remove only the panel values written by this project.

    Rebuilding the panel layout does not clear ``plasmashellrc``'s per-panel
    view state.  Plasma can reuse the same panel id for the new Breeze panel,
    so our translucent opacity survives uninstall unless it is removed
    explicitly.  Values other than our exact preset are user-owned and stay.
    """
    prc = HOME / ".config/plasmashellrc"
    if not prc.is_file():
        return False
    try:
        text = prc.read_text()
    except OSError:
        return False

    def reset(m: re.Match) -> str:
        section = m.group(0)
        section = re.sub(r"^panelOpacity=2\n?", "", section,
                         flags=re.MULTILINE)
        section = re.sub(r"^floatingApplets=1\n?", "", section,
                         flags=re.MULTILINE)
        return section

    new_text = _PRC_PANEL_RE.sub(reset, text)
    if new_text == text:
        return False
    try:
        prc.write_text(new_text)
    except OSError:
        return False
    return True


def install() -> None:
    # The panel layout is an initial default, not an update migration. A
    # marker alone can be stale, but live project widgets are definitive:
    # neither case authorizes replacing existing applet instances or geometry.
    if _layout_marker().is_file() or _layout_has_any_theme_widget():
        ok("Existing layout preserved")
        return
    _ensure_panel_colorizer()
    if not LAYOUT_SCRIPT.is_file():
        warn("Layout script not found — skipping")
        return
    try:
        before = set(_panel_snapshots())
    except OSError as exc:
        fail(f"Layout ownership preflight failed: {exc}")
        return
    pins = _capture_pinned_launchers()
    applied = _evaluate_layout_with_launchers(
        LAYOUT_SCRIPT, pins, MAC_TASKS_ID,
    )
    if applied and _wait_for_layout_install():
        try:
            created = _wait_for_owned_snapshots(before)
            if not created:
                raise OSError("new panel ownership markers were not saved by Plasma")
            _mark_layout_installed(created)
        except OSError as exc:
            fail(f"Layout created but ownership snapshot failed: {exc}")
            return
        ok(f"Layout installed (kept {len(pins)} pinned app(s))" if pins
           else "Layout installed")
    else:
        warn("layout failed — set layout manually")
        return
    # _patch_plasmashellrc() edits every panel view, including panels that
    # predate this install. Defer those optional glass overrides until the
    # fork can identify its own panel IDs rather than touching user panels.


def is_installed() -> bool:
    return _layout_marker().is_file() or _layout_looks_installed()


def uninstall() -> None:
    marker = _layout_marker()
    if not marker.exists() and not marker.is_symlink():
        if _layout_has_any_theme_widget():
            fail("Layout ownership is unknown; preserving all panels")
        else:
            ok("Layout already clean")
        return
    if marker.is_symlink():
        fail("Symlinked layout ownership marker; preserving all panels")
        return
    try:
        record = json.loads(marker.read_text(encoding="utf-8"))
        expected = record["panels"]
        if (record.get("schema") != 1 or not isinstance(expected, dict)
                or not expected or any(not key.isdigit() or not isinstance(value, str)
                                        or not re.fullmatch(r"[0-9a-f]{64}", value)
                                        for key, value in expected.items())):
            raise ValueError("invalid panel ownership snapshot")
        current = _panel_snapshots()
        existing_ids = _containment_ids()
    except (OSError, ValueError, TypeError, KeyError) as exc:
        fail(f"Layout ownership cannot be verified; preserving all panels ({exc})")
        return
    changed = [key for key, digest in expected.items()
               if int(key) in existing_ids and current.get(int(key)) != digest]
    if changed:
        fail("Layout panels changed since installation; preserving all panels: "
             + ", ".join(changed))
        return
    target_ids = sorted(int(key) for key in expected if int(key) in current)
    if not target_ids:
        try:
            marker.unlink()
        except OSError as exc:
            fail(f"Could not clear layout ownership state: {exc}")
            return
        ok("Layout already removed")
        return
    # Keep exact recovery copies before Plasma destroys any containment.
    backup = marker.parent / "panel-backups" / time.strftime("%Y%m%d-%H%M%S")
    try:
        if marker.parent.is_symlink() or backup.parent.is_symlink():
            raise OSError("symlinked panel backup directory")
        backup.mkdir(mode=0o700, parents=True, exist_ok=False)
        for source in (HOME / ".config/plasma-org.kde.plasma.desktop-appletsrc",
                       HOME / ".config/plasmashellrc"):
            if source.is_symlink():
                raise OSError(f"symlinked Plasma configuration: {source}")
            if source.is_file():
                shutil.copy2(source, backup / source.name)
    except OSError as exc:
        fail(f"Panel backup failed; preserving layout ({exc})")
        return
    ids = json.dumps(target_ids)
    script = (
        "(function () { var ids = " + ids + "; for (var i = 0; i < ids.length; i++) {"
        " var panel = panelById(ids[i]); if (!panel) continue;"
        " panel.currentConfigGroup = ['TajsDesktop'];"
        " if (panel.readConfig('owner', '') === 'tajsdesktop') panel.remove();"
        " } })();"
    )
    if not _evaluate_layout_script(script):
        fail(f"Panel removal failed; recovery copies: {backup}")
        return
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if not set(target_ids) & _containment_ids():
            try:
                marker.unlink()
            except OSError as exc:
                fail(f"Panels removed but ownership state remains: {exc}")
                return
            ok(f"Removed {len(target_ids)} unchanged TajsDesktop panel(s)")
            return
        time.sleep(0.2)
    fail(f"Panel removal not confirmed; recovery copies: {backup}")
