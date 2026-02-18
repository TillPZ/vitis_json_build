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


## helper functions
from helpers.cli_helpers import get_arguments, setup_logging


import logging
log = logging.getLogger(__name__)

def main():

    args = get_arguments()
    
    setup_logging(args.verbose, args.logfile)
    
    log.debug("Args: %s", args)
    log.debug("Logfile: %s", args.logfile)
    log.info("Config File: %s", args.config)    
    log.info("Starting build...")

    return

if __name__ == "__main__":
    main()