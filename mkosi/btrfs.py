# SPDX-License-Identifier: LGPL-2.1+

import shutil
import subprocess
from pathlib import Path
from typing import cast

from mkosi.config import ConfigFeature, MkosiConfig
from mkosi.install import copy_path
from mkosi.log import die
from mkosi.run import bwrap


def statfs(config: MkosiConfig, path: Path) -> str:
    return cast(str, bwrap(["stat", "--file-system", "--format", "%T", path.parent],
                           root=config.tools_tree, stdout=subprocess.PIPE).stdout.strip())


def btrfs_maybe_make_subvolume(config: MkosiConfig, path: Path, mode: int) -> None:
    if config.use_subvolumes == ConfigFeature.enabled and not shutil.which("btrfs"):
        die("Subvolumes requested but the btrfs command was not found")

    if statfs(config, path.parent) != "btrfs":
        if config.use_subvolumes == ConfigFeature.enabled:
            die(f"Subvolumes requested but {path} is not located on a btrfs filesystem")

        path.mkdir(mode)
        return

    if config.use_subvolumes != ConfigFeature.disabled and shutil.which("btrfs") is not None:
        result = bwrap(["btrfs", "subvolume", "create", path],
                       check=config.use_subvolumes == ConfigFeature.enabled,
                       root=config.tools_tree).returncode
    else:
        result = 1

    if result == 0:
        path.chmod(mode)
    else:
        path.mkdir(mode)


def btrfs_maybe_snapshot_subvolume(config: MkosiConfig, src: Path, dst: Path) -> None:
    subvolume = (config.use_subvolumes == ConfigFeature.enabled or
                 config.use_subvolumes == ConfigFeature.auto and shutil.which("btrfs") is not None)

    if config.use_subvolumes == ConfigFeature.enabled and not shutil.which("btrfs"):
        die("Subvolumes requested but the btrfs command was not found")

    # Subvolumes always have inode 256 so we can use that to check if a directory is a subvolume.
    if not subvolume or statfs(config, src) != "btrfs" or src.stat().st_ino != 256 or (dst.exists() and any(dst.iterdir())):
        return copy_path(src, dst, root=config.tools_tree)

    # btrfs can't snapshot to an existing directory so make sure the destination does not exist.
    if dst.exists():
        dst.rmdir()

    if shutil.which("btrfs"):
        result = bwrap(["btrfs", "subvolume", "snapshot", src, dst],
                       check=config.use_subvolumes == ConfigFeature.enabled,
                       root=config.tools_tree).returncode
    else:
        result = 1

    if result != 0:
        copy_path(src, dst, root=config.tools_tree)
