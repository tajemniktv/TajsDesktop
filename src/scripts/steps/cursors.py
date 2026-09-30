"""TajsDesktop cursor themes: extracts the bundled
TajsDesktop-Cursors.tar.zst into ~/.local/share/icons.
Fully offline — no download phase."""

import io
import subprocess
import tarfile
from pathlib import PurePosixPath

from steps._helpers import (
    DATA_HOME, fail, have, info, install_tree, offline, remove_tree, temp_dir,
)

OFFLINE_DIR = offline("cursors")
DEST_DIR = DATA_HOME / "icons"
THEME_NAMES = ("TajsDesktop", "TajsDesktop-Dark")


def deps():
    return ["zstd"]


def install() -> None:
    tarball = OFFLINE_DIR / "TajsDesktop-Cursors.tar.zst"
    if not tarball.is_file():
        fail(f"offline tarball missing: {tarball}")
        return
    if not have("zstd"):
        fail("zstd is required to unpack cursor assets")
        return

    res = subprocess.run(["zstd", "-dc", str(tarball)],
                         check=False, capture_output=True)
    if res.returncode != 0:
        fail(f"zstd failed ({res.returncode}): {res.stderr.decode(errors='replace').strip()}")
        return

    with temp_dir("tajsdesktop-cursors") as staging:
        try:
            with tarfile.open(fileobj=io.BytesIO(res.stdout), mode="r:") as archive:
                members = archive.getmembers()
                if not members:
                    raise ValueError("empty archive")
                names = [PurePosixPath(member.name) for member in members]
                if len(set(names)) != len(names):
                    raise ValueError("duplicate cursor archive path")
                for member in members:
                    path = PurePosixPath(member.name)
                    if (path.is_absolute() or ".." in path.parts
                            or not path.parts or path.parts[0] not in THEME_NAMES):
                        raise ValueError(f"unsafe cursor path: {member.name}")
                    if member.issym():
                        # Bundled cursor aliases point to another basename in
                        # the same cursors/ directory, never outside the theme.
                        if (len(path.parts) != 3 or path.parts[1] != "cursors"
                                or not member.linkname or "/" in member.linkname
                                or member.linkname in {".", ".."}):
                            raise ValueError(f"unsafe cursor alias: {member.name}")
                        if any(other.parts[:len(path.parts)] == path.parts
                               and len(other.parts) > len(path.parts)
                               for other in names):
                            raise ValueError(f"cursor alias used as directory: {member.name}")
                    elif not (member.isfile() or member.isdir()):
                        raise ValueError(f"unsafe cursor node: {member.name}")
                archive.extractall(staging, members=members)
        except (OSError, tarfile.TarError, ValueError) as exc:
            fail(f"Cursor archive rejected: {exc}")
            return

        for name in THEME_NAMES:
            source = staging / name
            if not ((source / "index.theme").is_file()
                    and (source / "cursors").is_dir()):
                fail(f"Cursor archive missing {name} metadata or cursors")
                return
        DEST_DIR.mkdir(parents=True, exist_ok=True)
        n = sum(install_tree(staging / name, DEST_DIR / name, name)
                for name in THEME_NAMES)
    info(f"{n} cursor themes installed/reinstalled")


def update_assets() -> None:
    install()


def uninstall() -> None:
    n = 0
    for name in THEME_NAMES:
        if remove_tree(DEST_DIR / name, name):
            n += 1
    info(f"{n} cursor themes removed")
