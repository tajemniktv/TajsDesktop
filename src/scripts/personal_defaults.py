"""Reviewed portable preferences; never read or copy a live config wholesale.

This module only plans initial values. Applying them belongs to the guarded
first-install/reset lifecycle, not to a theme update or feature toggle.
"""

from __future__ import annotations

import configparser
import json
import os
from pathlib import Path

from paths import REPO_ROOT


PROFILE_DIR = REPO_ROOT / "profiles"
ALLOWED_FILES = {
    "kwinrc", "kcminputrc", "powerdevilrc", "dolphinrc", "konsolerc",
    "katerc", "kglobalshortcutsrc", "mimeapps.list",
}


def load_profile(name: str) -> dict[str, dict[str, dict[str, str]]]:
    """Load a committed allowlisted profile; reject arbitrary paths/keys."""
    if name not in {"common", "local-laptop"}:
        raise ValueError(f"Unknown personal-defaults profile: {name}")
    data = json.loads((PROFILE_DIR / f"{name}.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not set(data) <= ALLOWED_FILES:
        raise ValueError(f"Invalid personal-defaults profile: {name}")
    for sections in data.values():
        if not isinstance(sections, dict):
            raise ValueError(f"Invalid sections in profile: {name}")
        for keys in sections.values():
            if not isinstance(keys, dict) or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in keys.items()
            ):
                raise ValueError(f"Invalid key/value in profile: {name}")
    return data


def desired_defaults(machine_profile: str | None = None) -> dict:
    """A local profile is an explicit choice, overlaid on the common set."""
    result = load_profile("common")
    if machine_profile is not None:
        for filename, sections in load_profile(machine_profile).items():
            for section, keys in sections.items():
                result.setdefault(filename, {}).setdefault(section, {}).update(keys)
    return result


def preview_missing(machine_profile: str | None = None,
                    config_home: Path | None = None) -> list[dict[str, str]]:
    """Report absent user keys only; an explicit empty value is an override."""
    root = config_home or Path(os.environ.get("XDG_CONFIG_HOME") or
                               Path.home() / ".config")
    changes = []
    for filename, sections in desired_defaults(machine_profile).items():
        parser = configparser.RawConfigParser(interpolation=None, strict=False)
        parser.optionxform = str
        path = root / filename
        if path.exists():
            parser.read(path, encoding="utf-8")
        for section, keys in sections.items():
            for key, value in keys.items():
                if not parser.has_option(section, key):
                    changes.append({"file": filename, "group": section,
                                    "key": key, "value": value})
    return changes
