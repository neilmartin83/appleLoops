#!/usr/bin/python

'''
Downloads required audio loops for GarageBand, Logic Pro X, and MainStage 3.

------------------------------------------------------------------------------
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Elements of FoundationPlist.py are used in this tool.
https://github.com/munki/munki
------------------------------------------------------------------------------

Requirements:
    - python 2.7.10 (as shipped in macOS X)
'''

# Imports for general use
import argparse
import logging
import os
import plistlib
import sys
import shutil
import ssl
import subprocess
import traceback
import urllib2

from collections import namedtuple
from distutils.version import LooseVersion, StrictVersion
from glob import glob
from logging.handlers import RotatingFileHandler
from urlparse import urlparse

# Imports specifically for FoundationPlist
# PyLint cannot properly find names inside Cocoa libraries, so issues bogus
# No name 'Foo' in module 'Bar' warnings. Disable them.
# pylint: disable=E0611
from Foundation import NSData  # NOQA
from Foundation import NSPropertyListSerialization
from Foundation import NSPropertyListMutableContainers
from Foundation import NSPropertyListXMLFormat_v1_0  # NOQA
# pylint: enable=E0611

# Script information
__script__ = 'appleLoops.py'
__author__ = 'Carl Windus'
__maintainer__ = __author__
__copyright__ = 'Copyright 2016, Carl Windus'
__credits__ = ['Greg Neagle', 'Matt Wilkie']
__version__ = '3.0.0'
__date__ = '2018-07-05'

__license__ = 'Apache License, Version 2.0'
__github__ = 'https://github.com/carlashley/appleLoops'
__status__ = 'Production'

version_string = '%s version %s (%s). Author: %s (licensed under the %s). Status: %s. GitHub: %s' % (__script__, __version__, __date__, __copyright__, __license__, __status__, __github__)  # NOQA


# FoundationPlist from munki
class FoundationPlistException(Exception):
    """Basic exception for plist errors"""
    pass


class NSPropertyListSerializationException(FoundationPlistException):
    """Read/parse error for plists"""
    pass


def readPlist(filepath):
    """
    Read a .plist file from filepath.  Return the unpacked root object
    (which is usually a dictionary).
    """
    plistData = NSData.dataWithContentsOfFile_(filepath)
    dataObject, dummy_plistFormat, error = (
        NSPropertyListSerialization.
        propertyListFromData_mutabilityOption_format_errorDescription_(
            plistData, NSPropertyListMutableContainers, None, None))
    if dataObject is None:
        if error:
            error = error.encode('ascii', 'ignore')
        else:
            error = "Unknown error"
        errmsg = "%s in file %s" % (error, filepath)
        raise NSPropertyListSerializationException(errmsg)
    else:
        return dataObject


def readPlistFromString(data):
    '''Read a plist data from a string. Return the root object.'''
    try:
        plistData = buffer(data)
    except TypeError, err:
        raise NSPropertyListSerializationException(err)
    dataObject, dummy_plistFormat, error = (
        NSPropertyListSerialization.
        propertyListFromData_mutabilityOption_format_errorDescription_(
            plistData, NSPropertyListMutableContainers, None, None))
    if dataObject is None:
        if error:
            error = error.encode('ascii', 'ignore')
        else:
            error = "Unknown error"
        raise NSPropertyListSerializationException(error)
    else:
        return dataObject


# Requests
class Requests():
    '''Simplify url requests'''
    def __init__(self, allow_insecure=False):
        self.allow_insecure = allow_insecure
        self.timeout = 5

    def response_code(self, url):
        try:
            if self.allow_insecure:
                return urllib2.urlopen(url, timeout=self.timeout, context=ssl._create_unverified_context()).getcode()  # NOQA
            else:
                return urllib2.urlopen(url, timeout=self.timeout).getcode()
        except urllib2.HTTPError as e:
            return e.getcode()
        except urllib2.URLError as e:
            return e

    def get_headers(self, url):
        try:
            if self.allow_insecure:
                return dict(urllib2.urlopen(url, timeout=self.timeout, context=ssl._create_unverified_context()).info())  # NOQA
            else:
                return dict(urllib2.urlopen(url, timeout=self.timeout).info())
        except Exception as e:
            return e

    def read_data(self, url):
        try:
            if self.allow_insecure:
                return urllib2.urlopen(url, timeout=self.timeout, context=ssl._create_unverified_context()).read()  # NOQA
            else:
                return urllib2.urlopen(url, timeout=self.timeout).read()
        except Exception as e:
            return e


class AppleLoops():
    def __init__(self, allow_insecure_https=False, allow_untrusted_pkgs=False, apps=None, apps_plist=None, caching_server=None, create_links_only=False, debug=False, deployment_mode=False, destination='/tmp', dmg_filename=None, dry_run=True, force_deploy=False, force_dmg=False, hard_link=False, log_path=None, mandatory_pkgs=True, mirror_source_paths=True, quiet_download=False, optional_pkgs=False, pkg_server=None, quiet_mode=False, space_threshold=5):

        # Logging
        if log_path:  # Log path will vary depending on context of who is using it, and what mode.
            self.log_path = log_path  # Specifying a log path will override default locations.
        else:
            if os.getuid() is 0 or deployment_mode:  # If running as root, or in deployment mode, logs go to /var/log
                self.log_path = '/var/log/'
            else:
                self.log_path = os.path.join(os.path.expanduser('~'), 'Library', 'Logs')  # This is chosen as log path for non root/deployment use to avoid needing to run with unnecessary privileges
        # Create the log file path
        self.log_file = os.path.join(self.log_path, 'appleloops.log')
        # Create an instance of the logger
        self.log = logging.getLogger('appleLoops')
        # Debug is either True/False, but defaults to False
        self.debug = debug
        # Set log level based on debug mode.
        if self.debug:
            self.log.setLevel(logging.DEBUG)
        else:
            self.log.setLevel(logging.INFO)
        # Set log format,
        self.file_handler = RotatingFileHandler(self.log_file)  # Dropped rotating on maxBytes and setting backupCount, not enough logging to warrant.
        self.log_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        self.file_handler.setFormatter(self.log_format)
        self.log.addHandler(self.file_handler)
        self.log.info('Version: {}'.format(__version__))
        # Setup other settings.
        self.allow_insecure_https = allow_insecure_https  # Used to tell curl to ignore cert errors. Defaults to False
        self.allow_untrusted_pkgs = allow_untrusted_pkgs  # When deploying apps, use this to ignore certificate errors when packages are installed
        self.apps = apps  # A list of apps to do things with. Supported values are ['all', 'garageband', 'logicpro', 'mainstage']
        self.apps_plist = apps_plist  # A list of specific plists to do things with, i.e. ['garageband1021.plist', 'logicpro1040.plist']
        self.caching_server = caching_server  # A caching server to use, must be in format of 'http://example.org:port' or 'http://10.0.0.1:port'
        self.create_links_only = create_links_only  # Only outputs links of the audio content so third party download tools can be used. Defaults to False.
        self.deployment_mode = deployment_mode  # If True, will install packages. Defaults to False. Must run as user with permissions to install pkgs, typically root.
        if not self.deployment_mode:
            self.destination = destination  # The path that content will be downloaded to. Defaults to '/tmp'. Deployment mode will always use '/tmp'.
        elif self.deployment_mode:
            self.destination = '/tmp'
        self.dmg_filename = dmg_filename  # Filename used for creating DMG of content
        self.dry_run = dry_run  # Provides output only of what would happen. Defaults to True.
        self.force_deploy = force_deploy  # Re-installs packages regardless of whether they have been installed or not. Defaults to False.
        self.force_dmg = force_dmg  # Re-creates the DMG file regardless of whether it exists or not.
        self.hard_link = hard_link  # Creates hard links to files if they exist elsewhere. Defaults to False.
        self.mandatory_pkgs = mandatory_pkgs  # Sets the flag to download/install the required packages for a given app. Defaults to True. This is a change from previous behaviour.
        self.mirror_source_paths = mirror_source_paths  # This will mirror the folder structure of the Apple audiocontent.apple.com servers. Defaults to True. This is a change from previous behaviour.
        self.quiet_download = quiet_download  # This will suppress the progress bar while downloading files. Default is False.
        self.optional_pkgs = optional_pkgs  # Sets the flag to download/install the optional packages for a given app. Defaults to False.
        self.pkg_server = pkg_server  # Uses the specified local mirror of packages, must be in format of 'http://example.org/path/to/content'. Defaults to None. Removes any extraneous '/' char from end of argument value.
        self.quiet_mode = quiet_mode  # Suppresses all stdout/stderr output. To view info about a run, view the log file. Defaults to False.
        self.space_threshold = space_threshold  # The percentage of disk free space to protect. Defaults to 5%. Must be an integer.

        # Debug log the class and what it was initialised with
        self.log.debug(vars(AppleLoops))
        self.log.debug(self.__dict__)

        # Apple URL, Mirror URL, and Cache URL
        class AudioContentSource(object):
            def __init__(self, mirror=None, cache=None):
                self.apple = 'http://audiocontentdownload.apple.com'
                self.mirror = mirror
                self.cache = cache

        self.content_source = AudioContentSource(mirror=self.pkg_server, cache=self.caching_server)
        self.log.debug('Apple Source URL: {}, Mirror Source URL: {}, Caching Server Source URL: {}'.format(self.content_source.apple, self.content_source.mirror, self.content_source.cache))

        # Basic App Details
        class GarageBand(object):
            def __init__(self):
                self.app_path = '/Applications/GarageBand.app'
                self.app_installed = os.path.exists(self.app_path)
                if self.app_installed:
                    self.app_plist = glob('{}/Contents/Resources/garageband*.plist'.format(self.app_path))
                    self.app_plist.sort()
                    self.app_plist = self.app_plist[-1]  # Make sure this returns the latest plist if more than one exists.
                    self.app_plist_basename = os.path.basename(self.app_plist)
                else:
                    self.app_plist = None

        self.garageband = GarageBand()
        self.log.debug('GarageBand().app_path: {}, GarageBand().app_plist: {}, GarageBand().app_installed: {}'.format(self.garageband.app_path, self.garageband.app_plist, self.garageband.app_installed))

        class LogicProX(object):
            def __init__(self):
                self.app_path = '/Applications/Logic Pro X.app'
                self.app_installed = os.path.exists(self.app_path)
                if self.app_installed:
                    self.app_plist = glob('{}/Contents/Resources/logicpro*.plist'.format(self.app_path))
                    self.app_plist.sort()
                    self.app_plist = self.app_plist[-1]  # Make sure this returns the latest plist if more than one exists.
                    self.app_plist_basename = os.path.basename(self.app_plist)
                else:
                    self.app_plist = None

        self.logicpro = LogicProX()
        self.log.debug('LogicProX().app_path: {}, LogicProX().app_plist: {}, LogicProX().app_installed: {}'.format(self.logicpro.app_path, self.logicpro.app_plist, self.logicpro.app_installed))

        class MainStage3(object):
            def __init__(self):
                self.app_path = '/Applications/MainStage 3.app'
                self.app_installed = os.path.exists(self.app_path)
                if self.app_installed:
                    self.app_plist = glob('{}/Contents/Resources/mainstage*.plist'.format(self.app_path))
                    self.app_plist.sort()
                    self.app_plist = self.app_plist[-1]  # Make sure this returns the latest plist if more than one exists.
                    self.app_plist_basename = os.path.basename(self.app_plist)
                else:
                    self.app_plist = None

        self.mainstage = MainStage3()
        self.log.debug('MainStage3().app_path: {}, MainStage3().app_plist: {}, MainStage3().app_installed: {}'.format(self.mainstage.app_path, self.mainstage.app_plist, self.mainstage.app_installed))

    def URLResponds(self, url):
        if Requests().response_code(url) == 200:
            return True
        else:
            return False


def main():
    appleloops = AppleLoops(debug=True)


if __name__ == '__main__':
    main()
