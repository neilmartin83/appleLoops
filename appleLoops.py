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
    - requests module - http://docs.python-requests.org/en/master/

'''

# Imports for general use
import argparse
import logging
import os
import plistlib
import sys
import shutil
import subprocess
try:
    import requests
except:
    print 'requests module must be installed. sudo easy_install requests'
    sys.exit(1)

from collections import namedtuple
from distutils.version import LooseVersion, StrictVersion
from glob import glob
from logging.handlers import RotatingFileHandler
from time import strftime
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
__version__ = '2.1.1'
__date__ = '2017-08-01'

__license__ = 'Apache License, Version 2.0'
__github__ = 'https://github.com/carlashley/appleLoops'
__status__ = 'Testing'

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


# AppleLoops
class AppleLoops():
    '''
    Manages downloads and installs of Apple audio loops for GarageBand,
    Logic Pro X, and MainStage.
    
    Initialisations:
        apps: A list, values should be any/all of: ['garageband', 'logicpro', 'mainstage']  # NOQA
        apps_plist: A list, values should be a specific plist to process, i.e. garageband1020.plist  # NOQA
                   These plists are found in the apps Contents/Resources folder. A local copy is kept  # NOQA
                   in case the app can't reach the remote equivalent hosted by Apple.  # NOQA
        caching_server: A URL string to the caching server on your network.
                        Must be formatted: http://example.org:45698
        destination: A string, path to save packages in, and create a DMG in (if specified).  # NOQA
                     For example: '/Users/jappleseed/Desktop/loops'
                     Use "" to escape paths with weird characters (like spaces).
                     If nothing is supplied, defaults to /tmp
        dmg_filename: A string, filename to save the DMG as.
        dry_run: Boolean, when true, does a dummy run without downloading anything.  # NOQA
                 Default is True.
        mandatory_loops: Boolean, processes all mandatory loops as specified by Apple.  # NOQA
                         Default is False.
        optional_loops: Boolean, processes all optional loops as specified by Apple.  # NOQA
                        Default is False.
        quiet: Boolean, disables all stdout and stderr.
               Default is False. Replaces JSS mode in older versions.
                     
    '''
    def __init__(self, apps=None, apps_plist=None, caching_server=None,
                 destination='/tmp', deployment_mode=False,
                 dmg_filename=None, dry_run=True, mandatory_loops=False,
                 mirror_paths=False, optional_loops=False, pkg_server=False,
                 quiet_mode=False, help_init=False, hard_link=False,
                 log_path=False, space_threshold=5, debug=False):
        if not help_init:
            # Logging
            if log_path:
                self.log_path = os.path.expanduser(os.path.expandvars(log_path))  # NOQA
            elif not log_path:
                self.log_path = '/tmp'

            self.log = logging.getLogger('appleLoops')

            if not len(self.log.handlers):
                self.log_file = os.path.join(self.log_path, 'appleLoops.log')
                if debug:
                    self.debug = debug
                    self.log.setLevel(logging.DEBUG)
                else:
                    self.log.setLevel(logging.INFO)

                self.fh = RotatingFileHandler(self.log_file, maxBytes=(1048576*5), backupCount=7)  # NOQA Logs capped at ~5MB
                self.log_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")  # NOQA
                self.fh.setFormatter(self.log_format)
                self.log.addHandler(self.fh)

        # Dry run, yo.
        self.dry_run = dry_run

        # If deployment mode, and not a dry run, must be root to install loops.
        if deployment_mode:
            if not self.dry_run:
                if os.getuid() == 0:
                    self.deployment_mode = True
                else:
                    print 'Must be root to run in deployment mode.'
                    sys.exit(1)
            else:
                self.deployment_mode = True
        else:
            self.deployment_mode = False

        # Read in configuration
        # self.configuration_file = 'com.github.carlashley.appleLoops.configuration.plist'  # NOQA
        self.configuration_file = 'https://raw.githubusercontent.com/carlashley/appleLoops/test/com.github.carlashley.appleLoops.configuration.plist'  # NOQA
        try:
            req = requests.head(self.configuration_file)
            if req.status_code == 200:
                # Full configuration dictionary
                configuration = requests.get(self.configuration_file).text  # NOQA
                # For some reason, munki readPlistFromString doesn't play well with getting this plist, so reverting to plistlib.  # NOQA
                self.configuration = plistlib.readPlistFromString(configuration)  # NOQA
            else:
                print req.status_code
                self.log.debug('Unable to read configuration file. Exiting.')
                print 'Unable to read configuration file.'
                sys.exit(1)
        except Exception as e:
            self.log.debug('Unable to read configuration file %s Exiting.' % e)
            print 'Unable to read configuration file. %s' % e
            sys.exit(1)

        # Supported apps
        self.supported_apps = ['garageband', 'logicpro', 'mainstage']

        # Break configuration down into easier references
        # Base URLs
        self.base_url = 'http://audiocontentdownload.apple.com/lp10_ms3_content_'  # NOQA
        self.alt_base_url = 'https://raw.githubusercontent.com/carlashley/appleLoops/master/lp10_ms3_content_'  # NOQA

        # GarageBand loops
        self.garageband_loop_year = self.configuration['loop_feeds']['garageband']['loop_year']  # NOQA
        self.garageband_loop_plists = self.configuration['loop_feeds']['garageband']['plists']  # NOQA
        # To ensure correct version order, sort this list
        self.garageband_loop_plists.sort()

        # Logic Pro X loops
        self.logicpro_loop_year = self.configuration['loop_feeds']['logicpro']['loop_year']  # NOQA
        self.logicpro_loop_plists = self.configuration['loop_feeds']['logicpro']['plists']  # NOQA
        # To ensure correct version order, sort this list
        self.logicpro_loop_plists.sort()

        # MainStage loops
        self.mainstage_loop_year = self.configuration['loop_feeds']['mainstage']['loop_year']  # NOQA
        self.mainstage_loop_plists = self.configuration['loop_feeds']['mainstage']['plists']  # NOQA
        # To ensure correct version order, sort this list
        self.mainstage_loop_plists.sort()

        # List of supported plists for help output.
        self.supported_plists = []
        self.supported_plists.extend(self.garageband_loop_plists)
        self.supported_plists.extend(self.logicpro_loop_plists)
        self.supported_plists.extend(self.mainstage_loop_plists)
        self.supported_plists = [str(plist) for plist in list(set(self.supported_plists))]  # NOQA
        self.supported_plists.sort()

        # Don't need to do a bunch of stuff just for help output.
        if not help_init:
            # Initialise with appropriate 'arguments'
            if apps:
                self.apps = apps
            else:
                self.apps = False

            if apps_plist:
                self.apps_plist = apps_plist
            else:
                self.apps_plist = False

            if caching_server:
                if caching_server.startswith('http://'):
                    self.caching_server = caching_server.rstrip('/')
                else:
                    self.log.debug('Caching server format must be http://example.org:45698 - Exiting.')  # NOQA
                    print 'Caching Server format must be http://example.org:45698'  # NOQA
                    sys.exit(1)
            else:
                self.caching_server = False

            if destination:
                # Expand any vars/user paths
                self.destination = os.path.expanduser(os.path.expandvars(destination))  # NOQA

            # Set dmg root destination
            dmg_root_dest = os.path.dirname(self.destination)  # NOQA
            if dmg_filename:
                # self.dmg_filename = os.path.join(dmg_root_dest, 'appleLoops_%s.dmg' % strftime('%Y-%m-%d'))  # NOQA
                self.dmg_filename = os.path.join(dmg_root_dest, dmg_filename)  # NOQA
            else:
                self.dmg_filename = False

            self.mandatory_loops = mandatory_loops
            self.mirror_paths = mirror_paths
            self.optional_loops = optional_loops
            self.quiet_mode = quiet_mode

            self.user_agent = '%s/%s' % (self.configuration['user_agent'], __version__)  # NOQA

            # Determines if file copy or hard link (to reduce disk usage)
            self.hard_link = hard_link

            if pkg_server:
                # Don't need a trailing / in this address
                if pkg_server.startswith('http://'):
                    self.pkg_server = pkg_server.rstrip('/')
                elif pkg_server == 'munki':
                    try:
                        # This is the standard location for the munki client config  # NOQA
                        self.pkg_server = readPlist('/Library/Preferences/ManagedInstalls.plist')['SoftwareRepoURL']  # NOQA
                        self.log.info('Found munki ManagedInstalls.plist, using SoftwareRepoURL %s' % self.pkg_server)  # NOQA
                    except:
                        # If we can't find a munki server, fallback to using
                        # Apple's servers.
                        self.pkg_server = False
                        self.log.debug('Falling back to use Apple servers for package downloads.')  # NOQA
            else:
                # If nothing is provided
                self.pkg_server = False
                self.log.debug('No package server provided, falling back to use Apple servers for package downloads.')  # NOQA

            # Creating a list of files found in destination
            self.files_found = []
            for root, dirs, files in os.walk(self.destination, topdown=True):
                for name in files:
                    if name.endswith('.pkg'):
                        _file = os.path.join(root, name)
                        if _file not in self.files_found:
                            self.files_found.append(_file)

            # Named tuple for loops
            self.Loop = namedtuple('Loop', ['pkg_name',
                                            'pkg_url',
                                            'pkg_mandatory',
                                            'pkg_size',
                                            'pkg_install_size',
                                            'pkg_year',
                                            'pkg_loop_for',
                                            'pkg_plist',
                                            'pkg_id',
                                            'pkg_installed',
                                            'pkg_destination',
                                            'pkg_local_ver',
                                            'pkg_remote_ver'])
            # Dictionary for total download size and install sizes
            # This must be in bytes.
            # The threshold value is how much space to make sure is free.
            self.size_info = {
                'download_total': int(0),
                'install_total': int(0),
                'available_space': int(0),
            }

            if space_threshold and type(space_threshold) is int:
                self.space_threshold = space_threshold
                self.size_info['reserved_space'] = self.percentage(self.space_threshold, self.space_available())  # NOQA
                self.size_info['new_available_space'] = (self.space_available() - self.size_info['reserved_space'])  # NOQA
            else:
                self.space_threshold = False
                self.size_info['new_available_space'] = self.space_available()

            if self.dry_run:
                self.size_info['available_space'] = self.space_available()

    def main_processor(self):
        # Some feedback to stdout for CLI use
        if not self.quiet_mode:
            if self.mirror_paths:
                if not self.dry_run:
                    print 'Starting run at %s' % strftime("%Y-%m-%d %H:%M:%S")
                    print 'Loops downloading to: %s (mirroring Apple folder structure).' % self.destination  # NOQA
                    self.log.info('Loops downloading to: %s (mirroring Apple folder structure.)' % self.destination)  # NOQA
                else:
                    print 'Dry run - loops download to: %s (mirroring Apple folder structure).' % self.destination  # NOQA
                    self.log.info('Dry run - loops download to: %s (mirroring Apple folder structure.)' % self.destination)  # NOQA

            else:
                if not self.dry_run:
                    print 'Loops downloading to: %s' % self.destination
                    self.log.info('Loops downloading to: %s' % self.destination)  # NOQA
                else:
                    print 'Dry run - loops download to: %s' % self.destination
                    self.log.info('Dry run - loops download to: %s' % self.destination)  # NOQA

            if self.caching_server:
                print 'Caching Server: %s' % self.caching_server
                self.log.info('Caching server: %s' % self.caching_server)

            if self.dmg_filename:
                print 'DMG path: %s' % self.dmg_filename
                self.log.info('DMG path: %s' % self.dmg_filename)

        # If there are local plists, lets get the basenames because
        # this will be useful for munki install runs.
        # This globs the path for the local plist, which is a blunt
        # approach. If Apple changes the filenames for any of these
        # apps, this approach will fail spectacularly. Will need to
        # Find a better way of approaching this.
        # deployment_mode should only be used by itself.
        if self.deployment_mode:
            if not any([self.apps, self.apps_plist]):
                for app in self.supported_apps:
                    try:
                        urls = self.plist_url(app)
                        self.process_pkgs(self.get_feed(urls.apple, urls.fallback))  # NOQA
                    except Exception as e:
                        # If there is an exception, it's likely because the plist for the app doesn't exist. Skip.  # NOQA
                        if self.debug:
                            self.log.debug('Exception: %s' % e)
                        self.log.info('Skipping %s as it does not appear to be installed.' % app)  # NOQA
                        pass
                if self.dry_run:
                    print('-' * 15)  # NOQA
                    if all([self.size_info['download_total'], self.size_info['install_total']]) < 1:  # NOQA
                        print 'Nothing to do here, have some coffee! :)'  # NOQA
                        sys.exit(0)
                    else:
                        print 'Download total size: %s  Install total size: %s' % (self.convert_size(self.size_info['download_total']), self.convert_size(self.size_info['install_total']))  # NOQA
                        if self.space_threshold:
                            print 'Free space (threshold applied): %s' % self.convert_size(self.size_info['new_available_space'])  # NOQA
                            print 'Protected free space: %s' % self.convert_size(self.size_info['reserved_space'])  # NOQA
                            if self.size_info['install_total'] < self.size_info['new_available_space']:  # NOQA
                                print 'All loops will be installed, sufficient free space'  # NOQA
                                self.log.info('All loops will be installed, sufficient free space')  # NOQA
                            else:
                                print 'No loops will be installed, as %s is the required free space.' % self.convert_size(self.size_info['reserved_space'])  # NOQA
                                self.log.info('No loops will be installed, as %s is the required free space.' % self.convert_size(self.size_info['reserved_space']))  # NOQA

                        if not self.space_threshold:
                            print 'Free space: %s' % self.convert_size(self.space_available())  # NOQA
                            if self.size_info['install_total'] < self.space_available():  # NOQA
                                print 'All loops will be installed, sufficient free space'  # NOQA
                                self.log.info('All loops will be installed, sufficient free space')  # NOQA
                            else:
                                print 'No loops will be installed. Install exceeds available space of %s.' % self.convert_size(self.space_available())  # NOQA
                                self.log.info('No loops will be installed. Install exceeds available space of %s.' % self.convert_size(self.space_available()))  # NOQA
            else:
                print 'Can\'t use apps or app_plist with deployment_mode.'
                self.log.info('Can\'t use apps or app_plist with deployment mode.')  # NOQA
                sys.exit(1)

        # Handle where just an app name is provided. This will default
        # to getting the loop content for the latest version.
        if self.apps:
            # Check if .plist exists in self.apps
            if '.plist' in self.apps:
                print 'Please remove the .plist extension.'
                sys.exit(1)

            if not any([self.apps_plist, self.deployment_mode]):
                for app in self.apps:
                    if any(app in x for x in self.supported_apps):  # NOQA
                        if 'garageband' in app:
                            for plist in self.garageband_loop_plists:
                                apple_url = '%s%s/%s' % (self.base_url, self.garageband_loop_year, plist)  # NOQA
                                fallback_url = '%s%s/%s' % (self.alt_base_url, self.garageband_loop_year, plist)  # NOQA
                                self.process_pkgs(self.get_feed(apple_url, fallback_url))  # NOQA

                        if 'logicpro' in app:
                            for plist in self.logicpro_loop_plists:
                                apple_url = '%s%s/%s' % (self.base_url, self.logicpro_loop_year, plist)  # NOQA
                                fallback_url = '%s%s/%s' % (self.alt_base_url, self.logicpro_loop_year, plist)  # NOQA
                                self.process_pkgs(self.get_feed(apple_url, fallback_url))  # NOQA

                        if 'mainstage' in app:
                            for plist in self.mainstage_loop_plists:
                                apple_url = '%s%s/%s' % (self.base_url, self.mainstage_loop_year, plist)  # NOQA
                                fallback_url = '%s%s/%s' % (self.alt_base_url, self.mainstage_loop_year, plist)  # NOQA
                                self.process_pkgs(self.get_feed(apple_url, fallback_url))  # NOQA
            else:
                print 'Can\'t use apps_plist or deployment_mode with app mode.'
                sys.log.info('Can\'t use apps_plist or deployment_mode with app mode.')  # NOQA
                sys.exit(1)

        if self.apps_plist:
            if not any([self.apps, self.deployment_mode]):
                for plist in self.apps_plist:
                    # Strip numbers from plist name to get app name
                    app = ''.join(map(lambda c: '' if c in '0123456789' else c, plist.replace('.plist', '')))  # NOQA
                    app_year = self.configuration['loop_feeds'][app]['loop_year']  # NOQA
                    apple_url = '%s%s/%s' % (self.base_url, app_year, plist)
                    fallback_url = '%s%s/%s' % (self.alt_base_url, app_year, plist)  # NOQA
                    self.process_pkgs(self.get_feed(apple_url, fallback_url))  # NOQA
            else:
                print 'Can\'t use apps or deployment_mode with apps_plist.'
                sys.log.info('Can\'t use apps or deployment_mode with apps_plist.')  # NOQA
                sys.exit(1)

        if self.dmg_filename:
            self.build_dmg(self.dmg_filename)

        if not self.quiet_mode and not self.dry_run:
            print 'Finished run at %s' % strftime("%Y-%m-%d %H:%M:%S")

    # Functions
    def plist_url(self, app):
        '''Returns a namedtuple with the Apple URL and a fallback URL. These URLs are the feed containing the pkg info.'''  # NOQA
        if self.deployment_mode:
            app_year = '2016'
        else:
            app_year = self.configuration['loop_feeds'][app]['loop_year']

        app_plist = os.path.basename(glob(self.configuration['loop_feeds'][app]['app_path'])[0])  # NOQA
        apple_url = '%s%s/%s' % (self.base_url, app_year, app_plist)  # NOQA
        fallback_url = '%s%s/%s' % (self.alt_base_url, app_year, app_plist)
        PlistURLs = namedtuple('PlistURls', ['apple', 'fallback'])

        if not self.quiet_mode:
            print 'Processing loops from: %s' % app_plist
            self.log.info('Processing loops from: %s' % app_plist)

        return PlistURLs(
            apple=apple_url,
            fallback=fallback_url
        )

    def get_feed(self, apple_url, fallback_url):
        '''Returns the feed as a dictionary from either the Apple URL or the fallback URL, pending result code.'''  # NOQA
        # Initalise request, and check for 404's
        req = requests.head(apple_url)  # request.head for speed
        if req.status_code == 404:
            # Use fallback URL
            self.log.debug('Falling back to alternate feed: %s' % fallback_url)  # NOQA
            req = requests.head(fallback_url)  # request.head for speed
            if req.status_code == 200:
                req = {
                    'app_feed_file': os.path.basename(fallback_url),
                    'result': readPlistFromString(requests.get(fallback_url, stream=True).raw.read())  # NOQA
                }
                return req
            else:
                self.log.info('There was a problem trying to reach %s' % fallback_url)  # NOQA
                return Exception('There was a problem trying to reach %s' % fallback_url)  # NOQA
        elif req.status_code == 200:
            # Use Apple URL
            req = {
                'app_feed_file': os.path.basename(apple_url),
                'result': readPlistFromString(requests.get(apple_url, stream=True).raw.read())  # NOQA
            }
            return req
        else:
            self.log.info('There was a problem trying to reach %s' % apple_url)  # NOQA
            return Exception('There was a problem trying to reach %s' % apple_url)  # NOQA

    def process_pkgs(self, app_feed_dict):
        # Specific part of the app_feed_dict to process
        loops = []
        packages = app_feed_dict['result']['Packages']

        # Values to put in the Loop named tuple
        _pkg_loop_for = ''.join(map(lambda c: '' if c in '0123456789' else c, os.path.splitext(app_feed_dict['app_feed_file'])[0]))  # NOQA
        _pkg_plist = app_feed_dict['app_feed_file']

        _pkg_year = self.configuration['loop_feeds'][_pkg_loop_for]['loop_year']  # NOQA

        for pkg in packages:
            _pkg_name = packages[pkg]['DownloadName']
            _pkg_url = '%s%s/%s' % (self.base_url, _pkg_year, _pkg_name)

            # Reformat URL if caching server specified
            if self.caching_server:
                _pkg_url = urlparse(_pkg_url)
                _pkg_url = '%s%s?source=%s' % (self.caching_server, _pkg_url.path, _pkg_url.netloc)  # NOQA

            _pkg_destination_folder_year = _pkg_year

            # Some package names start with ../lp10_ms3_content_2013/
            if _pkg_name.startswith('../'):
                # When setting the destination path for mirroring, need to have the correct year  # NOQA
                if '2013' in _pkg_name and self.mirror_paths:
                    _pkg_destination_folder_year = '2013'

                _pkg_url = 'http://audiocontentdownload.apple.com/%s' % _pkg_name[3:]  # NOQA
                _pkg_name = os.path.basename(_pkg_name)

            # If pkg_server is true, and deployment_mode has a list, use that
            # instead of Apple servers. Important note, the pkg_server must
            # have the same `lp10_ms3_content_YYYY` folder structure. i.e.
            # http://munki.example.org/munki_repo/lp10_ms3_content_2016/
            # This can be achieved by using the `--mirror-paths` option when
            # running appleLoops.py and then copying the resulting folders
            # to the munki repo.
            if self.pkg_server and self.deployment_mode:
                if not self.caching_server:
                    # Test each package path if pkg_server is provided, fallback if not reachable  # NOQA
                    req = requests.head(_pkg_url.replace('http://audiocontentdownload.apple.com', self.pkg_server))  # NOQA
                    if req.status_code == 200:
                        _pkg_url = _pkg_url.replace('http://audiocontentdownload.apple.com', self.pkg_server)  # NOQA

            # Mandatory or optional
            try:
                _pkg_mandatory = packages[pkg]['IsMandatory']
            except:
                _pkg_mandatory = False

            # Package size
            try:
                # Use requests.head to speed up getting the header for the file.  # NOQA
                # Use int type to avoid exception errors.
                _pkg_size = int(requests.head(_pkg_url).headers.get('content-length'))  # NOQA
            except:
                _pkg_size = None

            # Installed size in bytes
            try:
                # Use int type to avoid exception errors.
                _pkg_install_size = int(packages[pkg]['InstalledSize'])
            except:
                _pkg_install_size = None

            # Some package ID's seem to have a '. ' in them which is a typo.
            _pkg_id = packages[pkg]['PackageID'].replace('. ', '.')

            # If this is a deployment run, return if the package is
            # already installed on the machine, pkg version, and pkg ID
            # Apple doesn't include any package version information in
            # the feed, so can't compare if updates are required.
            if self.deployment_mode:
                _pkg_installed = self.loop_installed(_pkg_id)

            # If pkg installed, get version
            try:
                _pkg_local_ver = self.local_version(_pkg_id)
                _pkg_local_ver = str(_pkg_local_ver)
            except:
                _pkg_local_ver = '0.0'

            # If the feed has a PackageVersion, get it.
            try:
                # Apple uses long type, but need to make it a number then a string to compare with Loose/StrictVersion()  # NOQA
                _pkg_remote_ver = str(float(packages[pkg]['PackageVersion']))  # NOQA
            except:
                _pkg_remote_ver = '0.0'

            # Do a version check to handle any pkgs that are upgrades
            # Need to try Loose/Strict as version could be either
            try:
                if LooseVersion(_pkg_local_ver) < LooseVersion(_pkg_remote_ver):  # NOQA
                    self.log.info('%s needs upgrading (based on LooseVersion())' % _pkg_name)  # NOQA
                    _pkg_installed = False
            except:
                try:
                    if StrictVersion(_pkg_local_ver) < StrictVersion(_pkg_remote_ver):  # NOQA
                        self.log.info('%s needs upgrading (based on StrictVersion())' % _pkg_name)  # NOQA
                        _pkg_installed = False
                except:
                    # Presume pkg not installed if both version tests fail
                    _pkg_installed = False
                    _pkg_local_ver = '0.0'
                    _pkg_remote_ver = '0.0'

            if not self.deployment_mode:
                _pkg_installed = False

            if self.destination:
                # The base folder will be the app name and version, i.e. garageband1020  # NOQA
                _base_folder = os.path.splitext(app_feed_dict['app_feed_file'])[0]  # NOQA
                if _pkg_mandatory:
                    _pkg_destination = os.path.join(self.destination, _base_folder, 'mandatory', _pkg_name)  # NOQA
                else:
                    _pkg_destination = os.path.join(self.destination, _base_folder, 'optional', _pkg_name)  # NOQA

                # If the output is being mirrored
                if self.mirror_paths:
                    _pkg_destination = os.path.join(self.destination, 'lp10_ms3_content_%s' % _pkg_destination_folder_year, _pkg_name)  # NOQA

            if self.deployment_mode:
                # To avoid any folders that we can't delete being created, in deployment_mode, destination is the `/tmp` folder  # NOQA
                _pkg_destination = os.path.join('/tmp', _pkg_name)

            loop = self.Loop(
                pkg_name=_pkg_name,
                pkg_url=_pkg_url,
                pkg_mandatory=_pkg_mandatory,
                pkg_size=_pkg_size,
                pkg_install_size=_pkg_install_size,
                pkg_year=_pkg_year,
                pkg_loop_for=_pkg_loop_for,
                pkg_plist=_pkg_plist,
                pkg_id=_pkg_id,
                pkg_installed=_pkg_installed,
                pkg_destination=_pkg_destination,
                pkg_local_ver=_pkg_local_ver,
                pkg_remote_ver=_pkg_remote_ver,
            )

            if loop not in loops:
                # Appending to a list allows the free disk space/threshold
                # checks to work
                loops.append(loop)
                self.log.debug(loop)

        # Internal method to check if download/download+install takes place
        def download_or_install(loop_pkg):
            '''Internal function to download/install depending on arguments'''  # NOQA
            if self.space_threshold and not self.dry_run:
                if self.size_info['install_total'] >= self.size_info['new_available_space']:  # NOQA
                    print 'Aborting, will exceed threshold space limit of %s if loops are installed.' % self.convert_size(self.size_info['new_available_space'])  # NOQA
                    self.log.info('Aborting, will exceed threshold space limit of %s if loops are installed.' % self.convert_size(self.size_info['new_available_space']))  # NOQA
                    sys.exit(1)

            if self.deployment_mode:
                if not loop_pkg.pkg_installed:
                    # Check available space is sufficient to download and install  # NOQA
                    if sum([loop_pkg.pkg_size, loop_pkg.pkg_install_size]) < self.space_available():  # NOQA
                        self.download(loop_pkg)
                        self.install_pkg(loop_pkg)
                    else:
                        print 'Insufficient space to download and install %s' % loop_pkg.pkg_name  # NOQA
                        self.log.info('Insufficient space to download and install %s' % loop_pkg.pkg_name)  # NOQA
                        # Exit with error status
                        sys.exit(1)
            else:
                # Only download if this isn't a deployment run
                if not self.deployment_mode:
                    self.download(loop_pkg)

        def update_pkg_sizes(loop):
            # Only add download and install size info if
            # the package is not installed or needs upgrading
            if not loop.pkg_installed:
                self.size_info['download_total'] = self.size_info['download_total'] + loop.pkg_size  # NOQA
                self.size_info['install_total'] = self.size_info['install_total'] + loop.pkg_install_size  # NOQA

        # To be able to check if a loop is within threshold/free disk space
        # iterate over the loops
        for _loop in loops:
            # Only care about mandatory or optional, because other arguments are taken care of elsewhere.  # NOQA
            if any([self.mandatory_loops, self.optional_loops]):
                # If mandatory argument supplied and loop is mandatory
                if self.mandatory_loops and _loop.pkg_mandatory:  # NOQA
                    update_pkg_sizes(_loop)
                    download_or_install(_loop)

                # If optional argument supplied and loop is optional
                if self.optional_loops and not _loop.pkg_mandatory:  # NOQA
                    update_pkg_sizes(_loop)
                    download_or_install(_loop)
            else:
                print 'Must specify either \'-m, --mandatory-only\' or \'-o, --optional-only\' to download loops.'  # NOQA
                self.log.info('Must specify either \'-m, --mandatory-only\' or \'-o, --optional-only\' to download loops. Exiting.')  # NOQA
                sys.exit(1)

    def space_available(self):
        cmd = ['/usr/sbin/diskutil', 'info', '-plist', '/']
        (result, error) = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()  # NOQA
        # Return an int
        return int(plistlib.readPlistFromString(result)['FreeSpace'])

    def loop_installed(self, pkg_id):
        '''Returns if a package is installed'''
        cmd = ['/usr/sbin/pkgutil', '--pkg-info-plist', pkg_id]
        (result, error) = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()  # NOQA

        if result:
            # need to use plistlib as this doesn't cause issues with tests
            _pkg_id = plistlib.readPlistFromString(result)['pkgid']
            if pkg_id in _pkg_id:
                return True
            else:
                return False
        else:
            return False

    def local_version(self, pkg_id):
        cmd = ['/usr/sbin/pkgutil', '--pkg-info-plist', pkg_id]
        (result, error) = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()  # NOQA

        if result:
            try:
                ver = plistlib.readPlistFromString(result)['pkg-version']
            except:
                # If the plist can't be read, or throws an exception, the package is probably not installed.  # NOQA
                ver = 0

        if error:
            # If there is an error, then the package is probably not installed.
            # Unlikely to happen, because Apple seems to send stderr to stdout here.  # NOQA
            ver = 0

        return ver

    def download(self, pkg):
        # The mighty power of curl. Using `-L -C - <url>` to resume the download if a file exists.  # NOQA
        if self.quiet_mode:
            cmd = ['/usr/bin/curl', '--silent', '-L', '-C', '-', pkg.pkg_url, '--create-dirs', '-o', pkg.pkg_destination, '--user-agent', self.user_agent]  # NOQA
        else:
            cmd = ['/usr/bin/curl', '--progress-bar', '-L', '-C', '-', pkg.pkg_url, '--create-dirs', '-o', pkg.pkg_destination, '--user-agent', self.user_agent]  # NOQA

        if not os.path.exists(pkg.pkg_destination):
                # Test if there is a duplicate. This also copies duplicates.
            try:
                self.duplicate_file_exists(pkg)
            except:  # Exception as e:
                # Use the exception to kick the download process.
                if self.dry_run:
                    if not self.quiet_mode:
                        if not self.deployment_mode or not pkg.pkg_installed:
                            print 'Download: %s (Package size: %s  Installed size: %s)' % (pkg.pkg_name, self.convert_size(int(pkg.pkg_size)), self.convert_size(pkg.pkg_install_size))  # NOQA
                            self.log.info('Download: %s (Package size: %s  Installed size: %s)' % (pkg.pkg_name, self.convert_size(int(pkg.pkg_size)), self.convert_size(pkg.pkg_install_size)))  # NOQA

                    # Add this to self.files_found so we can test on the next go around  # NOQA
                    if self.files_found:
                        if pkg.pkg_destination not in self.files_found:
                            self.files_found.append(pkg.pkg_destination)
                else:
                    if not self.quiet_mode:
                        # Do some quick tests if pkg_server is specified
                        print 'Downloading: %s (Package size: %s  Installed size: %s)' % (pkg.pkg_name, self.convert_size(int(pkg.pkg_size)), self.convert_size(pkg.pkg_install_size))  # NOQA
                        self.log.info('Downloading: %s (Package size: %s  Installed size: %s)' % (pkg.pkg_name, self.convert_size(int(pkg.pkg_size)), self.convert_size(pkg.pkg_install_size)))  # NOQA

                    # For some reason this was indented into the above not self.quiet, it shouldn't be  # NOQA
                    subprocess.check_call(cmd)
                    # Add this to self.files_found so we can test on the next go around  # NOQA
                    if self.files_found:
                        if pkg.pkg_destination not in self.files_found:
                            self.files_found.append(pkg.pkg_destination)

        elif os.path.exists(pkg.pkg_destination):
            if not self.quiet_mode:
                print 'Skipping: %s' % pkg.pkg_name
                self.log.info('Skipping %s' % pkg.pkg_name)

    def percentage(self, percentage, value):
        '''Returns the calculated percentage of the provided value'''
        if percentage < 100:
            return (int(percentage) * int(value)) / 100
        else:
            raise Exception('%s Exceeds 100%' % percentage)

    def convert_size(self, file_size, precision=2):
        '''Converts the package file size into a human readable number.'''
        try:
            suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
            suffix_index = 0
            while file_size > 1024 and suffix_index < 4:
                suffix_index += 1
                file_size = file_size/1024.0

            return '%.*f %s' % (precision, file_size, suffixes[suffix_index])  # NOQA
        except Exception as e:
            raise e

    def duplicate_file_exists(self, pkg):
        '''Simple test to see if a duplicate file exists elsewhere.
        This uses exceptions to indicate an item needs to be downloaded.'''
        # Don't need to check if in deployment mode, all files downloaded anyway  # NOQA
        if not self.deployment_mode:
            if len(self.files_found) > 0:
                for source_file in self.files_found:
                    if pkg.pkg_name in os.path.basename(source_file):  # NOQA
                        if self.dry_run:
                            if self.hard_link:
                                print 'Hard link existing file: %s' % pkg.pkg_name  # NOQA
                                self.log.info('Hard link existing file: %s' % pkg.pkg_name)  # NOQA
                            else:
                                print 'Copy existing file: %s' % pkg.pkg_name
                                self.log.info('Copy existing file: %s' % pkg.pkg_name)  # NOQA

                        # If not a dry run, do the thing
                        if not self.dry_run:
                            if not os.path.exists(pkg.pkg_destination):
                                # Make destination folder if it doesn't exist
                                try:
                                    if not os.path.exists(os.path.dirname(pkg.pkg_destination)):  # NOQA
                                        os.makedirs(os.path.dirname(pkg.pkg_destination))  # NOQA
                                        self.log.debug('Created %s to store packages.' % os.path.dirname(pkg.pkg_destination))  # NOQA
                                except:
                                    self.log.debug('Could not make directory %s' % os.path.dirname(pkg.pkg_destination))  # NOQA
                                    raise Exception('Could not make directory %s' % os.path.dirname(pkg.pkg_destination))  # NOQA

                                # Try to hard link or copy the file
                                if self.hard_link:
                                    try:
                                        # Create a hard link to save space
                                        os.link(source_file, pkg.pkg_destination)  # NOQA
                                        if not self.quiet_mode:
                                            print 'Hard linked existing file: %s' % pkg.pkg_name  # NOQA
                                            self.log.info('Hard link existing file: %s' % pkg.pkg_name)  # NOQA
                                    except Exception as e:
                                        self.log.info('Hard link operation failed: %s' % e)  # NOQA
                                        raise Exception('Hard link operation failed: %s' % e)  # NOQA
                                else:
                                    try:
                                        shutil.copy2(source_file, pkg.pkg_destination)  # NOQA
                                        if not self.quiet_mode:
                                            print 'Copied existing file: %s' % pkg.pkg_name  # NOQA
                                            self.log.info('Copied existing file: %s' % pkg.pkg_name)  # NOQA
                                    except Exception as e:
                                        self.log.info('Copy operation failed: %s' % e)  # NOQA
                                        raise Exception('Copy operation failed: %s' % e)  # NOQA
                    # Be explicit about not matching any item in self.files_found here, otherwise excessive downloads  # NOQA
                    elif not any(x.endswith(pkg.pkg_name) for x in self.files_found):  # NOQA
                        # Raise exception if the file doesn't match any files discovered in self.found_files  # NOQA
                        self.log.debug('%s does not exist in found files.' % pkg.pkg_name)  # NOQA
                        raise Exception('%s does not exist in found files.' % pkg.pkg_name)  # NOQA
            else:
                self.log.debug('self.files_found list is probably empty because this directory either has no identifiable loops, or the directory does not exist.')  # NOQA
                raise Exception('Files Found list does not exist')
        elif self.deployment_mode:
            # Still need to raise an exception to trigger a download
            raise Exception('Deployment mode download')

    def install_pkg(self, pkg, target=None, allow_untrusted=False):
        '''Installs the package onto the system when used in deployment mode.
        Attempts to install then delete the downloaded package.'''
        # Only install if the package isn't already installed.
        if not pkg.pkg_installed:
            if not target:
                target = '/'

            cmd = ['/usr/sbin/installer', '-pkg', pkg.pkg_destination, '-target', target]  # NOQA
            # Allow untrusted is useful if the Apple cert has expired, but is not necessarily best practice.  # NOQA
            # In this instance, if one must allow untrusted pkgs to be signed, then you'll need to change the install_pkg() in process_pkgs() function.  # NOQA
            if allow_untrusted:
                cmd = ['/usr/sbin/installer', '-allowUntrusted', '-pkg', pkg.pkg_destination, '-target', target]  # NOQA
                self.log.debug('Allowing untrusted package to be installed: %s' % pkg.pkg_name)  # NOQA

            if self.dry_run:
                if pkg.pkg_install_size < self.size_info['available_space']:
                    print '  Install: %s' % pkg.pkg_name  # NOQA
                    self.size_info['available_space'] = (self.size_info['available_space'] - pkg.pkg_install_size)  # NOQA
                elif pkg.pkg_install_size > self.size_info['available_space']:
                    print '  Cannot install (insufficient space): %s' % pkg.pkg_name  # NOQA
                    self.log.info('Cannot install (insufficient space): %s' % pkg.pkg_name)  # NOQA

            if not self.dry_run:
                self.log.debug('Not in dry run, so attempting to install %s' % pkg.pkg_name)  # NOQA
                print '  Installing: %s' % pkg.pkg_name
                (result, error) = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()  # NOQA

                if 'successful' in result:
                    print '  Installed: %s' % pkg.pkg_name
                    self.log.info('Installed: %s' % pkg.pkg_name)
                    try:
                        os.remove(pkg.pkg_destination)
                    except Exception as e:
                        self.log.debug('Error removing package: %s' % e)
                        raise e
                elif 'upgrade' in result:
                    print 'Upgraded: %s' % pkg.pkg_name
                    self.log.info('Upgraded: %s' % pkg.pkg_name)
                    try:
                        os.remove(pkg.pkg_destination)
                    except Exception as e:
                        self.log.debug('Error removing package: %s' % e)
                        raise e
                else:
                    self.log.debug('Install does not appear to be successful: %s' % result)  # NOQA
                    try:
                        self.log.debug('Attempting to remove %s after install was not successful.' % pkg.pkg_name)  # NOQA
                        os.remove(pkg.pkg_destination)
                    except Exception as e:
                        self.log.debug('Error removing package after install failure: %s' % e)  # NOQA

                if error or any(x in result.lower() for x in ['fail', 'failed']):  # NOQA
                    print 'Install failed, check /var/log/installer.log for any info: %s' % pkg.pkg_name  # NOQA
                    self.log.info('Install failed, check /var/log/installer.log for any info: %s' % pkg.pkg_name)  # NOQA
                    self.log.debug('Install error: %s' % error)
                    try:
                        os.remove(pkg.pkg_destination)
                    except Exception as e:
                        self.log.debug('Error removing package: %s' % e)
                        raise e

    def build_dmg(self, dmg_filename):
        '''Builds a DMG. Default filename is appleLoops_YYYY-MM-DD.dmg.'''  # NOQA
        cmd = ['/usr/bin/hdiutil', 'create', '-volname', 'appleLoops', '-srcfolder', self.destination, dmg_filename]  # NOQA
        if self.dry_run:
            if not self.quiet_mode:
                print 'Build %s from %s' % (dmg_filename, self.destination)
        else:
            if not os.path.exists(dmg_filename):
                if not self.quiet_mode:
                    print 'Building %s' % dmg_filename

                subprocess.check_call(cmd)
            else:
                print '%s already exists.' % dmg_filename
                sys.exit(1)


# Main!
def main():
    class SaneUsageFormat(argparse.HelpFormatter):
        """
        Makes the help output somewhat more sane.
        Code used was from Matt Wilkie.
        http://stackoverflow.com/questions/9642692/argparse-help-without-duplicate-allcaps/9643162#9643162
        """

        def _format_action_invocation(self, action):
            if not action.option_strings:
                default = self._get_default_metavar_for_positional(action)
                metavar, = self._metavar_formatter(action, default)(1)
                return metavar

            else:
                parts = []

                # if the Optional doesn't take a value, format is:
                #    -s, --long
                if action.nargs == 0:
                    parts.extend(action.option_strings)

                # if the Optional takes a value, format is:
                #    -s ARGS, --long ARGS
                else:
                    default = self._get_default_metavar_for_optional(action)
                    args_string = self._format_args(action, default)
                    for option_string in action.option_strings:
                        parts.append(option_string)

                    return '%s %s' % (', '.join(parts), args_string)

                return ', '.join(parts)

        def _get_default_metavar_for_optional(self, action):
            return action.dest.upper()

    parser = argparse.ArgumentParser(formatter_class=SaneUsageFormat)
    modes_exclusive_group = parser.add_mutually_exclusive_group()
    server_exclusive_group = parser.add_mutually_exclusive_group()

    modes_exclusive_group.add_argument(
        '--apps',
        type=str,
        nargs='+',
        dest='apps',
        metavar='<app>',
        help='Processes all loops for all releases of specified apps.',
        required=False
    )

    parser.add_argument(
        '-b', '--build-dmg',
        type=str,
        nargs=1,
        dest='dmg_filename',
        metavar='dmg_filename.dmg',
        help='Builds a DMG of the downloaded content.',
        required=False
    )

    server_exclusive_group.add_argument(
        '-c', '--cache-server',
        type=str,
        nargs=1,
        dest='cache_server',
        metavar='http://example.org:port',
        help='Use cache server to download content through',
        required=False
    )

    parser.add_argument(
        '-d', '--destination',
        type=str,
        nargs=1,
        dest='destination',
        metavar='<folder>',
        help='Download location for loops content',
        required=False
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        dest='debug',
        help='Switch logging to debug level.',
        required=False
    )

    modes_exclusive_group.add_argument(
        '--deployment',
        action='store_true',
        dest='deployment',
        help='Runs in deployment mode (download and install loops).',  # NOQA
        required=False
    )

    parser.add_argument(
        '--hard-link',
        action='store_true',
        dest='hard_link',
        help='Create hard links instead of copying files. Use this to save disk space.',  # NOQA
        required=False
    )

    parser.add_argument(
        '--log-path',
        type=str,
        nargs=1,
        dest='log_path',
        metavar='<path>',
        help='Folder path for logging',
        required=False
    )

    parser.add_argument(
        '-m', '--mandatory-only',
        action='store_true',
        dest='mandatory',
        help='Download mandatory content only',
        required=False
    )

    parser.add_argument(
        '--mirror-paths',
        action='store_true',
        dest='mirror',
        help='Mirror the Apple server paths in the destination.',
        required=False
    )

    parser.add_argument(
        '-n', '--dry-run',
        action='store_true',
        dest='dry_run',
        help='Dry run to indicate what will be downloaded',
        required=False
    )

    parser.add_argument(
        '-o', '--optional-only',
        action='store_true',
        dest='optional',
        help='Download optional content only',
        required=False
    )

    server_exclusive_group.add_argument(
        '--pkg-server',
        type=str,
        nargs=1,
        dest='pkg_server',
        metavar='http://example.org/path_to/loops',
        help='Specify http server where loops are stored in your local environment.',  # NOQA
        required=False
    )

    modes_exclusive_group.add_argument(
        '--plists',
        type=str,
        nargs='+',
        dest='plists',
        metavar=AppleLoops(help_init=True).supported_plists,
        # metavar='<plist>',
        help='Processes all loops in specified plists.',
        required=False
    )

    parser.add_argument(
        '-t', '--threshold',
        type=int,
        nargs=1,
        dest='threshold',
        metavar='<percentage>',
        help='Percentage of space to keep free. Integer only.',
        required=False
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        dest='quiet',
        help='No output.',
        required=False
    )

    parser.add_argument(
        '-v', '--version',
        action='store_true',
        dest='version',
        help='Displays information.',
        required=False
    )

    args = parser.parse_args()

    if len(sys.argv) > 1:
        if args.version:
            print version_string
            sys.exit(0)

        if args.apps:
            _apps = args.apps
        else:
            _apps = None

        if args.dmg_filename:
            _dmg_filename = args.dmg_filename[0]
        else:
            _dmg_filename = None

        if args.cache_server:  # NOQA
            _cache_server = args.cache_server[0]
        else:
            _cache_server = None

        if args.destination:
            _destination = args.destination[0]
        else:
            _destination = '/tmp'

        if args.debug:
            _debug = True
        else:
            _debug = False

        if args.deployment:
            _deployment = True
        else:
            _deployment = False

        if args.mandatory:
            _mandatory = True
        else:
            _mandatory = False

        if args.log_path:
            _log_path = args.log_path[0]
        else:
            _log_path = False

        if args.mirror:
            _mirror = True
        else:
            _mirror = False

        if args.dry_run:
            _dry_run = True
        else:
            _dry_run = False

        if args.optional:
            _optional = True
        else:
            _optional = False

        if args.pkg_server:  # NOQA
            _pkg_server = args.pkg_server[0]
        else:
            _pkg_server = False

        if args.threshold:
            _space_threshold = args.threshold[0]
        else:
            _space_threshold = False

        if args.plists:
            if all(x.endswith('.plist') for x in args.plists):
                _plists = args.plists
            else:
                print 'Specified argument option must end with .plist'
                sys.exit(1)
        else:
            _plists = None

        if args.quiet:
            _quiet = True
        else:
            _quiet = False

        if args.hard_link:
            _hard_link = True
        else:
            _hard_link = False

        al = AppleLoops(apps=_apps, apps_plist=_plists, caching_server=_cache_server, destination=_destination,  # NOQA
                        deployment_mode=_deployment, dmg_filename=_dmg_filename, dry_run=_dry_run,  # NOQA
                        mandatory_loops=_mandatory, mirror_paths=_mirror, optional_loops=_optional,  # NOQA
                        pkg_server=_pkg_server, quiet_mode=_quiet, hard_link=_hard_link, help_init=False,  # NOQA
                        log_path=_log_path, space_threshold=_space_threshold, debug=_debug)  # NOQA
        al.main_processor()
    else:
        al = AppleLoops(help_init=True)
        parser.print_help()
        sys.exit(0)


if __name__ == '__main__':
    main()
