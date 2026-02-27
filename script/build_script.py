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

import vitis
import os
import json
import sys
import errno

from pathlib import Path

## helper functions
from helpers.cli_helpers import get_arguments, setup_logging
from helpers.workspace import prepare_workspace
from helpers.path_utils import create_link, find_source_files

import logging
log = logging.getLogger(__name__)


def run_build(args):
    

    repo_root = Path(__file__).resolve().parent.parent  
    log.debug(f"Root of Repository is: %s",  repo_root)
   
    workspace_root = (repo_root / args.workspace).resolve()
    log.info(f"Workspace Path is: %s",workspace_root)    


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


    try:
        client = vitis.create_client()
        client.set_workspace(str(workspace_root))
    except Exception as e:
        log.error("Failed to initialize Vitis client/workspace '%s': %s", workspace_root, e)
        raise


    resp = client.list_platform_components()
    pcs = getattr(resp, "platformComponent", None) or []
    existing_platform_names = {pc.platform_name for pc in pcs}
    log.info("Existing Platforms: %s", sorted(existing_platform_names))

    for plat_cfg in cfg.get("platform", []):
        name = plat_cfg.get("name")
        if not name:
            raise ValueError("platform.name missing in configuration file")

        log.info("Read Platform config for: %s", name)

        xsa_rel = plat_cfg.get("xsa_path")
        if not xsa_rel:
            raise ValueError(f"Platform '{name}': xsa_path missing in configuration file")

        xsa_path = (repo_root / xsa_rel).resolve()
        if not xsa_path.is_file():
            raise FileNotFoundError(f"Platform '{name}': XSA not found: {xsa_path}")

        domains = plat_cfg.get("domains") or []
        if not domains:
            raise ValueError(f"Platform '{name}': No Domains in configuration file")

        first_dom = domains[0]
        for k in ("name", "cpu", "os"):
            if k not in first_dom:
                raise ValueError(f"Platform '{name}': Domain[0] missing key '{k}'")

        if name in existing_platform_names:
            log.info("Platform %s already exists. Loading...", name)
            try:
                plat = client.get_component(name=name)
            except Exception as e:
                log.error("Failed to load existing platform '%s': %s", name, e)
                raise
            
            log.info(f"Check if domain {first_dom['name']} have same config")
            if sum(
                d.get("domain_name") == first_dom["name"] and
                d.get("processor")   == first_dom["cpu"]  and
                d.get("os")          == first_dom["os"]
                for d in plat.list_domains()
            ) != 1:
                raise RuntimeError("Domain mismatch run with --mode clean.")
        # todo xsa check
        else:
            log.info(
                "Creating platform %s (xsa=%s, domain=%s, cpu=%s, os=%s)...",
                name, xsa_path, first_dom["name"], first_dom["cpu"], first_dom["os"]
            )
            try:
                plat = client.create_platform_component(
                    name=name,
                    hw_design=str(xsa_path),
                    os=first_dom["os"],
                    cpu=first_dom["cpu"],
                    domain_name=first_dom["name"],
                )
            except Exception as e:
                log.error("Failed to create platform '%s': %s", name, e)
                raise             

        log.info("Add domains")

        existing_domains = plat.list_domains()    
        existing_by_name = {
            d.get("domain_name"): d
            for d in existing_domains
            if isinstance(d, dict) and d.get("domain_name")
        }

    
        for dom_cfg in domains[0:]: #maybe change to [1:]
            dom_name = dom_cfg["name"]

            if dom_name in existing_by_name:
                d = existing_by_name[dom_name]
                same = (d.get("processor") == dom_cfg["cpu"] and d.get("os") == dom_cfg["os"])
                if not same:
                    raise RuntimeError(
                        f"Platform '{plat_cfg['name']}' domain '{dom_name}' exists but differs "
                        f"(existing cpu={d.get('processor')} os={d.get('os')}, "
                        f"config cpu={dom_cfg['cpu']} os={dom_cfg['os']}). "
                        f"Run with --mode clean."
                    )
                log.info("Domain '%s' already exists and matches config, skip...", dom_name)
                continue
            #else:       
            log.info("Add domain: %s for cpu: (%s)", dom_name, dom_cfg["cpu"])
            plat.add_domain(name=dom_name, cpu=dom_cfg["cpu"], os=dom_cfg["os"])
    
  
        for dom_cfg in domains:
            domain = plat.get_domain(name=dom_cfg['name'])
            ## todo maybe "proc"
            if log.isEnabledFor(logging.DEBUG):
                libs = domain.get_applicable_libs()
                lib_names = [l.get("name") for l in libs if isinstance(l, dict)]
                log.debug("Applicable libs for domain '%s': %s", dom_cfg["name"], lib_names)

            
            # 1. Add libs
            if 'libraries' in dom_cfg:
                current_libs = domain.get_libs()            
                for lib in dom_cfg['libraries']:
                    lib_name = lib['name']
                    if any(lib['name'] == lib_name for lib in current_libs):
                        log.info(f"lib {lib_name} already exists in domain {dom_cfg['name']}...")                        
                    else: 
                        log.info(f"Add lib: {lib_name} to domain {dom_cfg['name']}")
                        domain.set_lib(lib_name)

            # 2. OS config
            os_settings = dom_cfg.get('os_config', {})
            for param, value in os_settings.items():
                
                actual_config = domain.get_config(option="os", param=param)
                if actual_config['value'] != value:
                    log.info(f"Set OS-Parameter: {param} = {value}")
                    domain.set_config(option="os", param=param, value=value)                    
                else: 
                    log.info(f"OS-Parameter: {param} = {value} already set skip ...")
               
            # regenerate one time
            domain.regenerate()
    
    
        # 3. Set config     
        for dom_cfg in domains:
            domain = plat.get_domain(name=dom_cfg['name'])
            
            if 'libraries' in dom_cfg:            
                for lib in dom_cfg['libraries']:
                    lib_name = lib['name']
                    params = domain.list_params(option="lib", lib_name=lib_name)
                    for p in params:
                        isSet = 0
                        name = p['parameter_name']
                        curr = p['value']
                        default = p['default_value']
                        if curr == default:
                            isDefault = 1
                        else:
                            isDefault = 0        
                        if 'config' in lib and lib['config']:
                            for parameter, values in lib['config'].items():#lib.items():
                                if parameter == name:
                                    if curr != values:
                                        log.info(f"Set para: {parameter} to: {values} in lib: {lib_name} Domain: {dom_cfg['name']}")
                                        domain.set_config(option="lib", lib_name=lib_name, param=parameter, value=values)
                                else:
                                    log.debug(f"No change in Parameter: {parameter} with: {values} lib: {lib_name} Domain: {dom_cfg['name']}")

                                isSet = 1;                                    
                        
                        
                        if (isSet == 0 and isDefault == 0):
                            log.info(f"Set para: {parameter} to: {values} in lib: {lib_name} Domain: {dom_cfg['name']} (standard value)")
                            domain.set_config(option="lib", lib_name=lib_name, param=parameter, value=values)
                        else:
                            log.debug(f"No change in Parameter: {parameter} with: {values} in lib: {lib_name} Domain: {dom_cfg['name']} (standard value)")
                                                         
    resp = client.list_components()
    existing_component = [p["name"] for p in resp]

    for app_cfg in cfg.get('apps', []):
        name = app_cfg.get("name")

        if name in existing_component:
            log.info(f"Component {name} already exists. load")
            app = client.get_component(name)
        else:
            log.info(f"Create App: {name}")     
            platform = app_cfg['platform']
            platform_path = ( workspace_root / platform / "export" / platform / f"{platform}.xpfm")
            domain  = app_cfg['domain']
    
               
            kwargs = {
                "name": name,
                "platform": str(platform_path),
                "domain": app_cfg["domain"],
            }

            if "template" in app_cfg:
                kwargs["template"] = app_cfg["template"]
                log.info(f"Using template: {app_cfg['template']}")     

            app = client.create_app_component(**kwargs)

        imports = app_cfg.get("imports", [])
        
        app_src_path = workspace_root / name / "src"

        log.info(f"App Source path: {app_src_path}...")

        for item in imports:
            source = item.get("src")
            destination = item.get("dest")
            log.info(f"Importing {source} to {destination}...")
            create_link(source, destination, repo_root, app_src_path)

        found_sources = find_source_files(app_src_path, extensions=None)

        app.set_app_config("USER_COMPILE_SOURCES", found_sources)




        if 'linker_config' in app_cfg:
            log.info(f"Configuring Linker Script for {app_cfg['name']}...")
            lscript = app.get_ld_script()
            l_cfg = app_cfg['linker_config']

            # 1. Memory Regions
            for mem in l_cfg.get('memory_regions', []):
                if mem['action'] == 'update':
                    lscript.update_memory_region(mem['name'], mem['base'], mem['size'])
                elif mem['action'] == 'add':
                    lscript.add_memory_region(mem['name'], mem['base'], mem['size'])

            # 2. Set Stack & Heap
            if 'stack_size' in l_cfg:
                lscript.set_stack_size(l_cfg['stack_size'])
            if 'heap_size' in l_cfg:
                lscript.set_heap_size(l_cfg['heap_size'])

            # 3. Sektions-Mappings
            for sec in l_cfg.get('sections', []):
                lscript.update_ld_section(sec['section'], sec['region'])


            set_app_configs = app_cfg.get('set_app_config', {})
            for param, value in set_app_configs.items():
                log.info(f"Set app config: {param} = {value}")
                app.set_app_config(key=param, values=value)


    vitis.dispose()
 
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