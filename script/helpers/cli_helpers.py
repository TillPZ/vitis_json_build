#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
cli_helper.py: Helper function for build_script.py
"""

__author__ = "Till Zirkelbach"
__copyright__ = "Copyright 2026"
__license__ = "MIT"
__version__ = "1.0.0"
__email__ = "VitisBuildScriptNoReply@segfault.eu"

import argparse


def get_arguments():
    parser = argparse.ArgumentParser(
        description="Vitis Workspace Builder",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # 1. & 2.  Path to config and Workspace
    parser.add_argument("-c", "--config", default="./config/config.json",
                        help="Path to JSON File")
 
    # 5. Build Components
    parser.add_argument("--build", action="store_true",
                        help="Compiles components after creation")

    # 7. Force
    parser.add_argument("--force", action="store_true",
                        help="Override safety checks during the delete operation. "
                             "Use with caution: this option disables validation intended to prevent "
                             "accidental deletion of critical paths (e.g. entire disks) when the "
                             "workspace path is overwritten during a clean build.")
    #parser.add_argument( "--logfile", type=str,
    #                    help="Write log output to file (e.g. build.log)")
    
    workspace_group = parser.add_argument_group("Workspace Options")
    workspace_group.add_argument("-w", "--workspace", default="./workspace", help="Target path for workspace")
    workspace_group.add_argument("-m", "--mode", choices=["rebuild", "incremental"], default="rebuild",
                                 help=( "Workspace mode: "
                                 "'rebuild': Deletes the existing workspace directory before "
                                 "recreating and building all components from scratch. "
                                 "'incremental': reuses and updates the existing workspace (experimental)"
                                 "(default: %(default)s)."
    )
)
    workspace_group.add_argument("--no-prompt", action="store_true",
                        help="CI/CD mode: Deletes workspace Path without user confirmation")

                        
    log_group = parser.add_argument_group("Logging Options")
    log_group.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity Level (-v INFO, -vv Debug")
    log_group.add_argument("--logfile", type=str, help="Write log output to file (e.g. build.log)")

    return parser.parse_args()

