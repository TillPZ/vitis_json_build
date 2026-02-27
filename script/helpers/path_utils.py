#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
path_utils.py: 
"""

__author__ = "Till Zirkelbach"
__copyright__ = "Copyright 2026"
__license__ = "MIT"
__version__ = "1.0.0"
__email__ = "core.dump@segfault.eu"

import os
import shutil
from pathlib import Path


from helpers.cli_helpers import setup_logging

import logging
log = logging.getLogger(__name__)


def create_link(src: str, dest: str, base_src: Path = None, base_dest: Path = None):
    """
    Creates Symlink: Relative Path are combined with the base path
    """
    # convert to path object
    src_path = Path(src)
    dest_path = Path(dest)

    log.info(f"Base_dest: {base_dest} Dest Path: {dest}")

    # combine relative path with base path 
    if not src_path.is_absolute() and base_src:
        src_path = (base_src / src_path).resolve()
        
    if not dest_path.is_absolute() and base_dest:
        dest_path = (base_dest / dest_path).absolute()

    log.info(f"Source Path: {src_path} Dest Path: {dest_path}")


    # 3. create path 
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # 4. create link
    if dest_path.exists() or dest_path.is_symlink():
        if dest_path.is_dir() and not dest_path.is_symlink():
            shutil.rmtree(dest_path) 
        else:
            dest_path.unlink()

    try:
        # target_is_directory 
        is_dir = src_path.is_dir()
        dest_path.symlink_to(src_path, target_is_directory=is_dir)
        log.info(f"Linked: {src_path} -> {dest_path}")
    except OSError as e:
        log.error(f"ehler beim Erstellen des Link: {e}")



def find_source_files(base_path: Path, extensions=None):
    """
    
    """
    if extensions is None:
        extensions = {".c", ".cpp"}
    
    base_path = Path(base_path).resolve()
    source_files = []

    
    for root, dirs, files in os.walk(base_path, followlinks=True):
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix in extensions:
                try:
                    
                    rel_path = file_path.relative_to(base_path)
                    source_files.append(str(rel_path))
                except ValueError:
                    
                    source_files.append(str(file_path))
            
    return sorted(list(set(source_files))) 
 