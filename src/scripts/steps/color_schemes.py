from steps._helpers import DATA_HOME, fail, info, ok, offline, reinstall

DEST_DIR = DATA_HOME / "color-schemes"


def install() -> None:
    src = offline("color-schemes")
    if not src.is_dir():
        fail(f"Color scheme source not found at {src}")
        return
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    n_inst = n_re = 0
    for cs in sorted(src.glob("*.colors")):
        dest = DEST_DIR / cs.name
        existed = dest.is_file()
        try:
            dest.write_bytes(cs.read_bytes())
        except OSError as exc:
            fail(f"{cs.stem}: {exc}")
            continue
        if existed:
            reinstall(cs.stem); n_re += 1
        else:
            ok(f"{cs.stem} (installed)"); n_inst += 1
    info(f"{n_inst + n_re} color schemes — {n_inst} installed, {n_re} reinstalled")


def update_assets() -> None:
    install()


def uninstall() -> None:
    n = 0
    for cs in DEST_DIR.glob("TajsDesktop*.colors"):
        try:
            cs.unlink()
            ok(f"{cs.stem} removed")
            n += 1
        except OSError:
            fail(cs.stem)
    info(f"{n} color schemes removed")
