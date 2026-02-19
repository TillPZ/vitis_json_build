#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_script.py: Build Vitis Workspace from json config with Xilinx Python cli
"""

__author__ = "Till Zirkelbach"
__copyright__ = "Copyright 2026"
__license__ = "MIT"
__version__ = "1.0.0"
__email__ = "core.dump@segfault.eu"


import os
import json
import sys
import errno

from pathlib import Path

## helper functions
from helpers.cli_helpers import get_arguments, setup_logging
from helpers.workspace import prepare_workspace


import logging
log = logging.getLogger(__name__)


def run_build(args):
    

    repo_root = Path(__file__).resolve().parent.parent  
    log.debug(f"Root of Repository is: %s",  repo_root)
   
    workspace_root = (repo_root / args.workspace).resolve()
    log.debug(f"Workspace Path is: %s",workspace_root)    


    config_file_path = (repo_root / args.config).resolve()
    log.debug(f"Open config File: %s", config_file_path)
    try:
        with open(config_file_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError as e:
        log.error("Config file not found: %s", config_file_path)
        raise SystemExit(errno.ENOENT) from e
    except json.JSONDecodeError as e:
        log.error("Invalid JSON in config file %s: %s", config_file_path, e)
        raise SystemExit(getattr(errno, 'EBADMSG', 1)) from e


    # delete workspace if clean is selected and workspace path seems plausible
    # then create workspace path    
    workspace_root = prepare_workspace(
    workspace_path=workspace_root,
    clean=(args.mode == "rebuild"),
    force=args.force,
    no_prompt=args.no_prompt,
    allowed_roots=[repo_root],
    )

    return




def main():

    args = get_arguments()
    
    setup_logging(args.verbose, args.logfile)
    
    log.debug("Args: %s", args)
    log.debug("Logfile: %s", args.logfile)
    log.info("Config File: %s", args.config)

    # start build process    
    log.info("Starting build...")
    run_build(args)

    

if __name__ == "__main__":
    main()