#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations


"""
workspace.py: Basic workspace functions
"""

__author__ = "Till Zirkelbach"
__copyright__ = "Copyright 2026"
__license__ = "MIT"
__version__ = "1.0.0"
__email__ = "core.dump@segfault.eu"


from pathlib import Path
import os
import shutil
from helpers.cli_helpers import setup_logging

import logging
log = logging.getLogger(__name__)



class WorkspaceError(RuntimeError):
    pass


class WorkspaceDeleteRefused(WorkspaceError):
    pass


class WorkspacePathInvalid(WorkspaceError):
    pass


class WorkspacePathRefused(WorkspaceError):
    pass



def _resolve_best_effort(p: Path) -> Path:
    try:
        return p.resolve()
    except Exception:
        return p


def _is_fs_root(p: Path) -> bool:
    rp = _resolve_best_effort(p)
    return rp.parent == rp  # '/' or 'C:\\'


def _is_under(child: Path, parent: Path) -> bool:
    child = _resolve_best_effort(child)
    parent = _resolve_best_effort(parent)
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _normalize_roots(allowed_roots) -> list[Path]:
    if allowed_roots is None:
        roots: list[Path] = []
    elif isinstance(allowed_roots, (str, os.PathLike, Path)):
        roots = [Path(allowed_roots)]
    else:
        roots = [Path(r) for r in allowed_roots]
    roots = [_resolve_best_effort(r) for r in roots]
    return roots


def _compute_allowed_bases(repo_root: Path, extra_allowed_roots: list[Path] | None = None) -> list[Path]:
    """Allowed bases: repo_root, extra roots, plus ramdisk/temp scoped to <project-name>."""
    repo_root = _resolve_best_effort(repo_root)

    if _is_fs_root(repo_root):
        raise WorkspacePathInvalid(f"repo_root must not be filesystem root: {repo_root}")

    project_name = repo_root.name

    bases: list[Path] = [repo_root]
    if extra_allowed_roots:
        bases.extend(extra_allowed_roots)

    if os.name != "nt":
        bases.extend([
            _resolve_best_effort(Path("/dev/shm") / project_name),
            _resolve_best_effort(Path("/run/user") / str(os.getuid()) / project_name),
            _resolve_best_effort(Path("/tmp") / project_name),
            _resolve_best_effort(Path("~/my_ramdisk").expanduser() / project_name),
        ])
    else:
        temp = os.environ.get("TEMP") or os.environ.get("TMP")
        if temp:
            bases.append(_resolve_best_effort(Path(temp) / project_name))

    # never allow filesystem roots as bases
    bad = [b for b in bases if _is_fs_root(b)]
    if bad:
        raise WorkspacePathInvalid(f"Refusing base roots that are filesystem root(s): {bad}")

    # de-dup
    bases = list(dict.fromkeys(bases))
    return bases


def ensure_workspace_exists(workspace_path: Path, allowed_roots=None) -> Path:
    workspace_path = _resolve_best_effort(Path(workspace_path))

    if _is_fs_root(workspace_path):
        raise WorkspacePathInvalid(f"Workspace cannot be filesystem root: {workspace_path}")

    roots = _normalize_roots(allowed_roots)
    if not roots:
        raise WorkspacePathInvalid("allowed_roots must include repo_root (non-empty).")

    if workspace_path.exists():
        if not workspace_path.is_dir():
            raise WorkspacePathInvalid(f"Workspace exists but is not a directory: {workspace_path}")
        return workspace_path

    workspace_path.mkdir(parents=True, exist_ok=True)
    return workspace_path


def safe_delete_workspace(
    workspace_path: Path,
    clean: bool,
):
    if not clean:
        return

    workspace_path = _resolve_best_effort(Path(workspace_path))

    if not workspace_path.exists():
        return

    if not workspace_path.is_dir():
        raise WorkspaceDeleteRefused(f"Workspace path is not a directory: {workspace_path}")

    if _is_fs_root(workspace_path):
        raise WorkspaceDeleteRefused(f"Refusing to delete filesystem root: {workspace_path}")

    try:
        shutil.rmtree(workspace_path)
    except Exception as e:
        raise WorkspaceDeleteRefused(f"Failed to delete workspace: {workspace_path}") from e
    
    log.info(f"Delete workspace: {workspace_path}")
    

def check_workspace_path(
    workspace_path: Path,
    clean: bool,
    force: bool = False,
    no_prompt: bool = False,
    allowed_names=None,
    allowed_roots=None,
):

    workspace_path = _resolve_best_effort(Path(workspace_path))

    if workspace_path.exists():
        if not workspace_path.is_dir():
            raise WorkspacePathRefused(f"Workspace path is not a directory: {workspace_path}")

    if _is_fs_root(workspace_path):
        raise WorkspacePathRefused(f"Refusing to delete filesystem root: {workspace_path}")

    roots = _normalize_roots(allowed_roots)

    if not roots:
        raise WorkspacePathRefused("allowed_roots must include repo_root (non-empty).")

    repo_root = roots[0]
    extra = roots[1:] if len(roots) > 1 else []
    bases = _compute_allowed_bases(repo_root, extra)

    base_ok = any(_is_under(workspace_path, b) for b in bases)
    if not base_ok:
        if not force:
            # Erstellt eine formatierte Liste der Pfade für die Fehlermeldung
            allowed_list = "\n  - ".join(str(b) for b in bases)
            raise WorkspacePathRefused(
                f"Refusing workspace path for security reasons.\n\n"
                f"Actual path:\n  {workspace_path}\n\n"
                f"Allowed base paths:\n  - {allowed_list}\n\n"
                f"To bypass this safety check, use the '--force' flag."
            )
        else: 
            log.warning(f"Force-mode: Using not allowed workspace path: {workspace_path}")



    allowed_names = set(allowed_names or {"workspace", "vitis_ws", "vitis_workspace"})
    if workspace_path.name.lower() not in {n.lower() for n in allowed_names}:
        if not force:
            allowed_str = "\n  - ".join(sorted(allowed_names))
            raise WorkspacePathRefused(
                 f"Refusing workspace name for security reasons.\n\n"
                f"Actual name: {workspace_path.name}\n"
                f"Allowed names:\n  - {allowed_str}\n\n"
                f"To bypass this, use the '--force' flag."
            )
    
        else: 
            log.warning(f"Force-mode: Using unauthorized workspace name: {workspace_path.name}")


    if not no_prompt:
        # Dynamische Status-Meldung
        action = "CLEAN & RECREATE (all data will be lost)" if clean else "INCREMENTAL UPDATE"
        
        print(f"\n--- Workspace Action ---")
        print(f"Path:   {workspace_path}")
        print(f"Mode:   {action}")
        print(f"------------------------")
        
        ans = input(f"Proceed with these changes? [y/N]: ").strip().lower()
        if ans not in {"y", "yes"}:
            raise WorkspacePathRefused("User aborted workspace operation.")

        
        log.info(f"User confirmed workspace action: {action} on {workspace_path}")
    else:
        action = "CLEAN" if clean else "INCREMENTAL"
        log.info(f"Automated workspace action (no_prompt): {action} on {workspace_path}")



def prepare_workspace(
    workspace_path: Path,
    clean: bool,
    force: bool = False,
    no_prompt: bool = False,
    allowed_names=None,
    allowed_roots=None,
) -> Path:
    """Convenience: delete (optional) then ensure exists."""

    check_workspace_path(
        workspace_path=workspace_path,
        clean=clean,
        force=force,
        no_prompt=no_prompt,
        allowed_names=allowed_names,
        allowed_roots=allowed_roots,
    )


    safe_delete_workspace(
        workspace_path=workspace_path,
        clean=clean,
    )

    return ensure_workspace_exists(workspace_path=workspace_path, allowed_roots=allowed_roots)