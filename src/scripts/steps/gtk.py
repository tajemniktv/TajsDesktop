import subprocess

from steps._helpers import (
    HOME, fail, have, info, install_tree, offline, remove_tree,
)
from utils import run_user

DEST_DIR = HOME / ".themes"
VARIANTS = ("TajsDesktop-Light", "TajsDesktop-Dark")


def install() -> None:
    src = offline("gtk")
    if not src.is_dir():
        fail(f"GTK theme source not found at {src}")
        return

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for v in VARIANTS:
        if not (src / v).is_dir():
            continue
        if install_tree(src / v, DEST_DIR / v, v):
            n += 1
    if have("gsettings"):
        run_user(
            ["gsettings", "set", "org.gnome.desktop.wm.preferences",
             "button-layout", "close,minimize,maximize:"],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    info(f"{n} GTK themes installed/reinstalled")


def uninstall() -> None:
    n = 0
    for v in VARIANTS:
        if remove_tree(DEST_DIR / v, f"{v} removed"):
            n += 1

    # This step never created the user's gtk-4.0 config files and did not
    # snapshot GSettings. Removing or resetting them would destroy choices
    # made after installation (or choices predating this fork).
    info(f"{n} GTK themes removed")
