"""macOS wallpapers: copies src/offline/wallpapers/<id>/ bundles (Plasma
layout: metadata.json + contents/images[_dark]/) into ~/.local/share/wallpapers.
Fully offline — no download phase."""

import shutil
from pathlib import Path

from steps._helpers import (
    DATA_HOME, fail, info, offline, ok, reinstall,
)
from utils import safe_copy

DEST_DIR = DATA_HOME / "wallpapers"
OFFLINE_DIR = offline("wallpapers")


def install() -> None:
    pre = {p.name for p in DEST_DIR.glob("*/") if p.is_dir()}
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    n_inst = n_re = 0
    for wp in sorted(OFFLINE_DIR.glob("TajsDesktop-*/")):
        if not wp.is_dir():
            continue
        # metadata.json is what Plasma lists the wallpaper by — skip the
        # bundle rather than ship a half-installed entry.
        if not (wp / "metadata.json").is_file():
            fail(f"{wp.name} (missing metadata.json in offline bundle)")
            continue
        if not safe_copy(wp, DEST_DIR / wp.name):
            fail(f"{wp.name} (copy failed)")
            continue
        if wp.name in pre:
            reinstall(wp.name); n_re += 1
        else:
            ok(f"{wp.name} (installed)"); n_inst += 1
    info(f"{n_inst + n_re} wallpapers — {n_inst} installed, {n_re} reinstalled")


def update_assets() -> None:
    install()


_FIXED_NAMES = (
    "TajsDesktop-Tahoe", "TajsDesktop-Tahoe-Beach-Dawn", "TajsDesktop-Tahoe-Beach-Day",
    "TajsDesktop-Tahoe-Beach-Dusk", "TajsDesktop-Tahoe-Beach-Night",
    "TajsDesktop-Tahoe-Iridescence",
    "TajsDesktop-Tahoe-Landscape-Morning", "TajsDesktop-Tahoe-Landscape-Evening",
    "TajsDesktop-Tahoe-Landscape-Night",
    "TajsDesktop-Heritage-Sequoia", "TajsDesktop-Heritage-Sequoia-Sunrise",
    "TajsDesktop-Heritage-Sonoma", "TajsDesktop-Heritage-Sonoma-Horizon",
    "TajsDesktop-Heritage-Ventura", "TajsDesktop-Heritage-Monterey", "TajsDesktop-Heritage-BigSur",
)


def uninstall() -> None:
    n = 0
    for name in _FIXED_NAMES:
        d = DEST_DIR / name
        if d.is_dir():
            try:
                shutil.rmtree(d)
                ok(name); n += 1
            except OSError:
                fail(name)
    # Legacy index-numbered landscapes from earlier releases.
    for d in DEST_DIR.glob("TajsDesktop-Tahoe-Landscape-[0-9][0-9]/"):
        try:
            shutil.rmtree(d)
            ok(d.name); n += 1
        except OSError:
            fail(d.name)
    info(f"{n} wallpapers removed")
