"""Read-only feature reconciliation and durable TajsDesktop install state.

No caller should persist a new state until all corresponding feature actions
have completed. The planner itself never invokes an installer step.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


SCHEMA = 1


def upstream_install_present(home: Path | None = None) -> bool:
    """Conservative indicator only; foreign state never grants ownership."""
    root = home or Path.home()
    return any(path.exists() for path in (
        root / ".local/state/mac-tahoe-liquid-kde",
        root / ".local/bin/mac-tahoe-theme-switch",
        root / ".local/share/plasma/look-and-feel/"
               "org.kde.mac-tahoe-liquid-kde.light",
    ))


def state_file() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    return root / "tajsdesktop/installation.json"


@dataclass(frozen=True)
class InstalledState:
    version: str
    features: dict[str, bool]


def load_state(path: Path | None = None) -> InstalledState | None:
    target = path or state_file()
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    data = json.loads(raw)
    if (not isinstance(data, dict) or data.get("schema") != SCHEMA
            or not isinstance(data.get("installed_version"), str)
            or not isinstance(data.get("features"), dict)
            or any(not isinstance(key, str) or not isinstance(value, bool)
                   for key, value in data["features"].items())):
        raise ValueError(f"Invalid TajsDesktop install state: {target}")
    return InstalledState(data["installed_version"], data["features"])


def save_state(state: InstalledState, path: Path | None = None) -> None:
    """Atomically record only an already-successful installation result."""
    target = path or state_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA,
        "installed_version": state.version,
        "features": state.features,
    }
    fd, name = tempfile.mkstemp(prefix=".installation-", suffix=".tmp",
                                dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def plan_features(desired: Mapping[str, bool],
                  installed: InstalledState | None,
                  version: str,
                  foreign_install: bool = False) -> dict[str, object]:
    """Describe the smallest feature delta, without pretending it was run."""
    if any(not isinstance(key, str) or not isinstance(value, bool)
           for key, value in desired.items()):
        raise ValueError("Feature selections must be booleans")
    previous = installed.features if installed else {}
    names = sorted(set(previous) | set(desired))
    enable = [name for name in names if desired.get(name, False)
              and not previous.get(name, False)]
    disable = [name for name in names if previous.get(name, False)
               and not desired.get(name, False)]
    return {
        "operation": "migration-required" if installed is None and foreign_install else
                     "first-install" if installed is None else
                     "update" if installed.version != version else "features",
        "installed_version": installed.version if installed else None,
        "target_version": version,
        "enable": enable,
        "disable": disable,
        "unchanged": [name for name in names
                      if name not in enable and name not in disable],
        "foreign_install": foreign_install,
    }
