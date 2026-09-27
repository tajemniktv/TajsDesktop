"""Reviewed portable preferences; never read or copy a live config wholesale.

Mutation is restricted to explicit first-install/reset calls. Routine asset
updates and feature reconciliation must not call these entry points.
"""

from __future__ import annotations

import configparser
import json
import os
import shutil
import tempfile
from pathlib import Path

from paths import REPO_ROOT
from utils import build_group_args, kw_write


PROFILE_DIR = REPO_ROOT / "profiles"
ALLOWED_FILES = {
    "kwinrc", "kcminputrc", "powerdevilrc", "dolphinrc", "konsolerc",
    "katerc", "kglobalshortcutsrc", "mimeapps.list",
}
STATE_SCHEMA = 1


def profile_state_file() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    return root / "tajsdesktop/profile-defaults.json"


def _config_root(config_home: Path | None) -> Path:
    return config_home or Path(os.environ.get("XDG_CONFIG_HOME") or
                               Path.home() / ".config")


def _read_config(path: Path) -> configparser.RawConfigParser:
    if path.is_symlink():
        raise ValueError(f"Symlinked config is not safe to modify: {path}")
    parser = configparser.RawConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    if path.exists():
        with path.open(encoding="utf-8") as stream:
            parser.read_file(stream)
    return parser


def _key_value(path: Path, group: str, key: str) -> str | None:
    parser = _read_config(path)
    return parser.get(group, key) if parser.has_option(group, key) else None


def _write_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".profile-defaults-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(record, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def _read_record(path: Path) -> dict | None:
    if not path.exists():
        return None
    if path.is_symlink():
        raise ValueError(f"Symlinked profile ownership record: {path}")
    record = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(record, dict) or record.get("schema") != STATE_SCHEMA
            or not isinstance(record.get("entries"), list)
            or not isinstance(record.get("backups"), dict)):
        raise ValueError(f"Invalid profile ownership record: {path}")
    for entry in record["entries"]:
        if (not isinstance(entry, dict)
                or set(entry) != {"file", "group", "key", "value", "status"}
                or entry["file"] not in ALLOWED_FILES
                or any(not isinstance(entry[field], str)
                       for field in ("group", "key", "value", "status"))
                or entry["status"] not in {"pending", "applied", "skipped", "failed", "reset"}):
            raise ValueError(f"Invalid profile ownership entry: {path}")
    return record


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
    root = _config_root(config_home)
    changes = []
    for filename, sections in desired_defaults(machine_profile).items():
        path = root / filename
        parser = _read_config(path)
        for section, keys in sections.items():
            for key, value in keys.items():
                if not parser.has_option(section, key):
                    changes.append({"file": filename, "group": section,
                                    "key": key, "value": value})
    return changes


def apply_initial_defaults(machine_profile: str | None = None,
                           *, config_home: Path | None = None,
                           state_path: Path | None = None) -> dict:
    """Initialize absent keys once, with recoverable file backups and a ledger.

    Only a first-install orchestrator may call this. The ledger is written
    before the first config mutation and after each key, so a crash never
    silently turns an update into a reapplication.
    """
    root = _config_root(config_home)
    state = state_path or profile_state_file()
    if state.exists() or state.is_symlink():
        raise ValueError("Personal defaults were already initialized or need recovery")
    changes = preview_missing(machine_profile, root)
    state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup_dir = Path(tempfile.mkdtemp(prefix="profile-backup-", dir=state.parent))
    backups: dict[str, str | None] = {}
    try:
        for filename in sorted({change["file"] for change in changes}):
            source = root / filename
            if source.is_symlink():
                raise ValueError(f"Symlinked config is not safe to modify: {source}")
            if source.is_file():
                backup = backup_dir / filename
                shutil.copy2(source, backup)
                backups[filename] = str(backup)
            elif source.exists():
                raise ValueError(f"Config is not a regular file: {source}")
            else:
                backups[filename] = None
        record = {
            "schema": STATE_SCHEMA,
            "profile": machine_profile or "common",
            "backups": backups,
            "entries": [{**change, "status": "pending"} for change in changes],
        }
        _write_record(state, record)
    except BaseException:
        shutil.rmtree(backup_dir)
        raise

    for entry in record["entries"]:
        path = root / entry["file"]
        try:
            if _key_value(path, entry["group"], entry["key"]) is not None:
                entry["status"] = "skipped"
            else:
                args = ("--file", str(path),
                        *build_group_args(entry["group"]),
                        "--key", entry["key"], entry["value"])
                if not kw_write(*args):
                    entry["status"] = "failed"
                    _write_record(state, record)
                    raise RuntimeError(f"Could not initialize {entry['file']}:{entry['key']}")
                entry["status"] = "applied" if _key_value(
                    path, entry["group"], entry["key"]) == entry["value"] else "failed"
                if entry["status"] == "failed":
                    _write_record(state, record)
                    raise RuntimeError(f"Could not verify {entry['file']}:{entry['key']}")
            _write_record(state, record)
        except BaseException:
            # A pending entry remains recoverable if interrupted after
            # kwriteconfig6 changed the file but before the ledger update.
            raise
    return record


def preview_profile_reset(*, config_home: Path | None = None,
                          state_path: Path | None = None) -> list[dict[str, str]]:
    """Show exactly which initialized keys are still equal to our values."""
    root = _config_root(config_home)
    record = _read_record(state_path or profile_state_file())
    if record is None:
        return []
    preview = []
    for entry in record["entries"]:
        if entry["status"] != "applied":
            continue
        current = _key_value(root / entry["file"], entry["group"], entry["key"])
        action = ("delete" if current == entry["value"] else
                  "already-absent" if current is None else "preserve-user-value")
        preview.append({**entry, "action": action})
    return preview


def reset_profile_defaults(*, confirmed: bool,
                           config_home: Path | None = None,
                           state_path: Path | None = None) -> list[dict[str, str]]:
    """Explicit, backed-up reset; delete only unchanged fork-initialized keys."""
    if not confirmed:
        raise ValueError("Profile reset requires explicit confirmation")
    root = _config_root(config_home)
    state = state_path or profile_state_file()
    record = _read_record(state)
    if record is None:
        return []
    preview = preview_profile_reset(config_home=root, state_path=state)
    targets = [entry for entry in preview if entry["action"] == "delete"]
    if not targets:
        return preview
    backup_dir = Path(tempfile.mkdtemp(prefix="profile-reset-backup-", dir=state.parent))
    for filename in sorted({entry["file"] for entry in targets}):
        path = root / filename
        if path.is_file() and not path.is_symlink():
            shutil.copy2(path, backup_dir / filename)
    record.setdefault("reset_backups", []).append(str(backup_dir))
    _write_record(state, record)
    for target in targets:
        path = root / target["file"]
        if _key_value(path, target["group"], target["key"]) != target["value"]:
            continue
        args = ("--file", str(path), *build_group_args(target["group"]),
                "--key", target["key"], "--delete", "")
        if not kw_write(*args):
            raise RuntimeError(f"Could not reset {target['file']}:{target['key']}")
        for entry in record["entries"]:
            if all(entry[field] == target[field] for field in
                   ("file", "group", "key", "value")):
                entry["status"] = "reset"
                break
        _write_record(state, record)
    return preview
