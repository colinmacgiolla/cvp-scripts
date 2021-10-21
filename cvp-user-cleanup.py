#!/usr/bin/python
# Copyright (c) 2021 Arista Networks, Inc.  All rights reserved.
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

def main():

    # Create connection to CloudVision
    clnt = CvpClient()


    timestamp = time.strftime("%Y%m%d-%H%M%S")
    # Setup our logger
    # This sets the logging level of the root logger - even in other logging instances, nothing below INFO will be logged
    # so this is set to DEBUG, then the logger for each switch will be INFO to the screen and DEBUG in file
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log = logging.getLogger('CVP User Cleanup')
    # We append to the log if it already exists, if not create the file
    fh = logging.FileHandler('CVP_User_Cleanup'+timestamp+'.log', mode='a+')
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
    parser = argparse.ArgumentParser(description='Script to kick any ONLINE non-local users using external AAA systems (TACACS/RADIUS) from the system')
    parser.add_argument('-u', '--username', default='username',required=True)
    parser.add_argument('-p', '--password', default=None)
    parser.add_argument('-c', '--cvpserver', action='append', required=True)
    parser.add_argument('-t','--timeout', default='24', help="The number of hours since last accessed, that a user should be deleted")
    parser.add_argument('-d','--dryrun', default=False, help="Dry-run mode - don't actually kick any users")
    parser.add_argument('--target', help="Delete a specific user ID")
    args = parser.parse_args() 

    # convert hours into seconds
    age_timer = int(args.timeout) * 60 * 60

    if args.dryrun:
        log.info("Executing in dry-run mode - no users will be kicked")
    if args.target:
        log.info("Executing in targeted mode")

    log.info("Starting to connect to CVP server(s)")
    cvp_count = 0
    user_count = 0

    for cvpserver in args.cvpserver:
        log.info("Connecting to %s" % cvpserver)
        try:
            clnt.connect(nodes=[cvpserver], username=args.username, password=args.password)
        except Exception as e:
            log.error("Unable to connect to CVP: %s" % str(e))
            continue

        cvp_count += 1
        cvp_info = clnt.api.get_cvp_info()
        users = clnt.get('/user/getUsers.do?startIndex=0&endIndex=0')

        if args.target:
            log.info('Targeting user: %s' % args.target)
            try:
                target = clnt.api.get_user(args.target)
            except Exception as e:
                log.error("Unable to delete user: %s" % e)
                break

            
            if target['userType'] != 'Local':
                log.debug('Deleting the following information:')
                log.debug(target)
                clnt.api.delete_user(target)
                user_count += 1


            pass


        else:
            for user in users['users']:
                # get all non-local users
                if user['userType'] != 'Local' and user['userStatus'] == 'Enabled' and user['currentStatus'] == 'Online':
                    # Get the current EPOCH time
                    epoch_time = int(time.time())
                    log.debug("User %s has has last been seen online %d seconds ago" % (user['userId'],user['lastAccessed']) )
                    if epoch_time - user['lastAccessed'] > age_timer:
                        if not args.dryrun:
                           clnt.api.delete_user(user['userId'])
                        log.info("Kicking user: %s" % user['userId'])
                        user_count += 1
                else:
                    log.debug('Not deleting user %s' % user['userId'])
                    log.debug(user)

        log.info("Deleted %d users from %d CVP Servers" % (cvp_count,user_count) )



    sys.exit(0)



if __name__ == "__main__":
    main()
    