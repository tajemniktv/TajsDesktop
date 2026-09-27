from steps._helpers import (
    DATA_HOME, fail, info, install_tree, kw_write, offline, remove_tree, warn,
)

DEST_DIR = DATA_HOME / "plasma/desktoptheme"
VARIANTS = ("TajsDesktop-Dark", "TajsDesktop-Light")


def install() -> None:
    src = offline("plasma-theme")
    if not src.is_dir():
        fail(f"Plasma theme source not found at {src}")
        return
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    n = 0
    for v in VARIANTS:
        if not (src / v).is_dir():
            continue
        if install_tree(src / v, DEST_DIR / v, v):
            n += 1
    info(f"{n} Plasma themes installed/reinstalled")


def update_assets() -> None:
    install()


def uninstall() -> None:
    n = 0
    for v in VARIANTS:
        if remove_tree(DEST_DIR / v, v):
            n += 1
    if not kw_write("--file", "plasmarc", "--group", "Theme",
                    "--key", "name", "default"):
        warn("Active Plasma theme not reset to 'default' — "
             "kwriteconfig6 unavailable. Files are removed but "
             "Plasma will still try to load TajsDesktop "
             "until you set plasmarc:Theme.name=default manually.")
    info(f"{n} Plasma themes removed")
