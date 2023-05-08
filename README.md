# cvp-scripts
## Overview
Collection of scripts for use with Arista's CloudVision Portal [CVP]

## Script Details
### [cvp-user-cleanup](https://github.com/colinmacgiolla/cvp-scripts/blob/main/cvp-user-cleanup.py)
#### Problem Statement
When using non-Local accounts e.g. TACACS or Radius, there is an issue where the user can still be considered to be *Online* from a CVP perspective, and so using (potentially) cached credentials.

This becomes an issue if they update their password on TACACS/RADIUS server, but CVP continues to use the cached credentials as they haven't logged out. Potentially this can snowball if they try to touch a large number of devices, and hit failed auth limits on the AAA server.

This script (by default) boots any users that are;
1. Online
2. Not Local users
3. Haven't been seen in the last 24 hours (configurable)
#### Usage
CLI arguments are as follows;
* -u / --username - your CVP username (assumes your account has permissions to manipulate users)
* -p / --password - your CVP password. This is optional, and the password will be requested if not provided
* Selecting the CVP server offers 2 options
  * -c / --cvpserver - the cvp server hostname or IP
  * -f / --file - File containing the server hostnames or IP addresses (1 per line)
* -t / --timeout - Kick off any users that have been away for more then this interval (hours)
* -d / --dryrun - Log the actions that would be taken, but don't actually kick any users
* --target - only target a specific user, and kick them, regardless of when they were last seen

#### Requires
* cvprac

#### Tested Python Versions
* 2.7
* 3.7

### [legacy-device-onboard](http://github.com/colinmacgiolla/cvp-scripts/blob/main/legacy-device-onboard.py)

#### Problem Statement
If you have a number of device that are streaming to CVP but still haven't been onboarded to the provisioning workflow, this script does some of the heavy lifting by;
* Assuming the running-config is the desired config, with the schema `auto_<hostname>`
* Creating a configlet with the running-config
* Creating a Task that will move the device to the target container, and assign the configlet with the entire running-config to the device

#### Usage
CLI arguments are as follows;
* -u / --username - your CVP username (assumes your account has permissions to manipulate users)
* -c / --cvpserver - (required) the cvp server hostname or IP
* --continer - (required) the name of the container you want to move the devices to
* --filter - a string/substring to match on the hostname, if you want to match a subset of devices
Authentication is mutually exclusive between;
* -p / --password - your CVP password. The password will be requested if not provided in the arguments
* --token - your CVP service token

#### Requires


#### Tested Python Versions
* 3.10