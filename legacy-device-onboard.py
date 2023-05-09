#!/usr/bin/python
# Copyright (c) 2023 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
# * Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,  this list of conditions and the following disclaimer in the documentation 
#   and/or other materials provided with the distribution.
# * Neither the name of the Arista nor the names of its contributors may be used to endorse or promote products derived from this software without 
#   specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, 
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE
# GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
# DAMAGE.


import logging
import sys, ssl
import time
import requests
import argparse
from cvprac.cvp_client import CvpClient
from getpass import getpass

if ((sys.version_info.major == 3) or
    (sys.version_info.major == 2 and sys.version_info.minor == 7 and sys.version_info.micro >= 5)):
    ssl._create_default_https_context = ssl._create_unverified_context

requests.packages.urllib3.disable_warnings()

def user_prompt(question: str) -> bool:
    """ Prompt the yes/no-*question* to the user. """
    from distutils.util import strtobool

    while True:
        user_input = input(question + " [y/n]: ")
        try:
            return bool(strtobool(user_input))
        except ValueError:
            print("Please use y/n or yes/no.\n")


def main():

    # Create connection to CloudVision
    clnt = CvpClient()


    timestamp = time.strftime("%Y%m%d-%H%M%S")
    # Setup our logger
    # This sets the logging level of the root logger - even in other logging instances, nothing below INFO will be logged
    # so this is set to DEBUG, then the logger for each switch will be INFO to the screen and DEBUG in file
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log = logging.getLogger('CVP Legacy Device Onboarder')
    # We append to the log if it already exists, if not create the file
    fh = logging.FileHandler('CVP_Legacy_Device_Onboarder'+timestamp+'.log', mode='a+')
    # Set the log level going to the file
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    log.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    log.addHandler(ch)
    log.propagate = False

    # Dial down logging in the other packages
    logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
    logging.getLogger('cvprac').setLevel(logging.INFO)

    log.info("Script started successfully")

    log.debug("Parsing CLI Arguments")
    parser = argparse.ArgumentParser(description='Legacy device Onborder - find any streaming device that are not under provisioning control, keep their running config, and move them to a container')
    parser.add_argument('-u', '--username', default='username')
    parser.add_argument('-c', '--cvpserver', required=True, help="CVP Server hostname or IP address")
    parser.add_argument("--container", required=True, help="Container name to move the device to")
    parser.add_argument("--filter", default="", help="substring to filter device name on e.g. oob")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--password', default=None)
    group.add_argument('--token')


    args = parser.parse_args() 

    log.debug(args)
    if args.password is None and not args.token:
        args.password = getpass()

    log.info("Starting to connect to CVP server(s)")
    log.info("Connecting to %s" % args.cvpserver)
    try:
        if args.token:
            clnt.connect(nodes=[args.cvpserver], username='', password='', is_cvaas=True, api_token=args.token)
        else:
            clnt.connect(nodes=[args.cvpserver], username=args.username, password=args.password)
    except Exception as e:
        log.error("Unable to connect to CVP: %s" % str(e))
        return

    result = clnt.api.get_cvp_info()
    if result['version'] == 'cvaas':
        log.info('Successfully connected to a CVaaS instance')
    else:
        log.info('Connected to CVP running version: %s' % result['version'])


    log.debug("Collecting Inventory")
    inventory = clnt.api.get_inventory()

    onboard_list = []
    for device in inventory:
        if (
            device['parentContainerId'] == "undefined_container" and
            device["streamingStatus"] == "active" and
            device["type"] == "netelement" and
            device["status"] == "Registered" and
            args.filter in device["hostname"]

        ):
            log.info("Adding %s to onboarding list" % device["hostname"])
            onboard_list.append(device)
        else:
            log.debug("Skipping: %s" % device["hostname"])

    if len(onboard_list) == 0:
        log.info("No devices found that are streaming, but not onboarded.")
        return(0)
    
    print("The following devices are in scope:")
    for device in onboard_list:
        print("* %s" % device["hostname"])

    if not user_prompt("Proceed with onboarding?"):
        log.debug("User aborted onboarding")
        exit(1) 


    for device in onboard_list:
        log.info("Collecting running config for %s" % device["hostname"])
        device["running_config"] = clnt.api.get_device_configuration(device["systemMacAddress"])

        log.info("Running config collected: %d lines" % len(device["running_config"].split('\n')))

        name = "auto_" + device["hostname"]
        try:
            configlet = clnt.api.get_configlet_by_name(name)
            key = configlet["key"]
            log.debug("%s configlet already exists with id: %s" % (name,key) )
            _ = clnt.api.update_configlet(device["running_config"],key,name)
        except:
            key = clnt.api.add_configlet(name, device["running_config"])
            log.info("%s configlet created with id: %s" % (name,key))

        log.info("Preparing to move %s to container: %s" % (device["hostname"], args.container))
        target_container = clnt.api.get_container_by_name(args.container)
        if target_container is not None:
            _ = clnt.api.move_device_to_container("Legacy device onborder", device, target_container)
        else:
            log.error("Target container: %s does not exist" % args.container)
            exit(1)
        
        # We have to assign the configlets after the "move" - note that all this just creates
        # a task to do the action - nothing is executed until you push the button
        log.info("Assigning configlet to device")
        config = [{"name": name, "key": key}]
        _ = clnt.api.apply_configlets_to_device("Legacy device onboarder", device, config)


    log.info("Script run completed")

    

if __name__ == "__main__":
    main()
    
