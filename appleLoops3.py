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
# pylint: disable=W0611
import argparse  # NOQA
import concurrent.futures  # NOQA
import logging  # NOQA
import os  # NOQA
import plistlib  # NOQA
import sys  # NOQA
import shutil  # NOQA
import ssl  # NOQA
import subprocess  # NOQA
import urllib2  # NOQA

from collections import namedtuple  # NOQA
from distutils.version import LooseVersion, StrictVersion  # NOQA
from glob import glob  # NOQA
from logging.handlers import RotatingFileHandler  # NOQA
from pprint import pprint  # NOQA
from urlparse import urlparse  # NOQA

# Imports specifically for FoundationPlist
# PyLint cannot properly find names inside Cocoa libraries, so issues bogus
# No name 'Foo' in module 'Bar' warnings. Disable them.
# pylint: disable=E0611
from Foundation import NSData  # NOQA
from Foundation import NSPropertyListSerialization  # NOQA
from Foundation import NSPropertyListMutableContainers  # NOQA
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

    def status(self, url):
        '''Return the status code of the HTTP request'''
        try:
            if self.allow_insecure:
                return urllib2.urlopen(url, timeout=self.timeout, context=ssl._create_unverified_context()).getcode()  # NOQA
            else:
                return urllib2.urlopen(url, timeout=self.timeout).getcode()
        except urllib2.HTTPError as e:
            return e.getcode()
        except urllib2.URLError as e:
            return e

    def headers(self, url):
        '''Return the headers of the requested URL'''
        try:
            if self.allow_insecure:
                return dict(urllib2.urlopen(url, timeout=self.timeout, context=ssl._create_unverified_context()).info())  # NOQA
            else:
                return dict(urllib2.urlopen(url, timeout=self.timeout).info())
        except Exception as e:
            return e

    def fetch(self, url):
        '''Return the complete response from the HTTP request'''
        try:
            if self.allow_insecure:
                return urllib2.urlopen(url, timeout=self.timeout, context=ssl._create_unverified_context()).read()  # NOQA
            else:
                return urllib2.urlopen(url, timeout=self.timeout).read()
        except Exception as e:
            return e


class AppleLoops():
    def __init__(self, allow_insecure_https=False, allow_untrusted_pkgs=False, apps=None, apps_plist=None, caching_server=None, create_links_only=False, debug=False, deployment_mode=False, destination='/tmp/appleloops', dmg_filename=None, dry_run=True, force_deploy=False, force_dmg=False, hard_link=False, log_path=None, mandatory_pkgs=True, mirror_source_paths=True, quiet_download=False, optional_pkgs=False, pkg_server=None, quiet_mode=False, space_threshold=5):

        # Supported apps are
        self.supported_apps = ['garageband', 'logicpro', 'mainstage']
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
        if caching_server:  # So .rstrip() can work, have to check if caching_server has a value.
            self.caching_server = caching_server.rstrip('/')  # A caching server to use, must be in format of 'http://example.org:port' or 'http://10.0.0.1:port'
        else:
            self.caching_server = caching_server
        self.create_links_only = create_links_only  # Only outputs links of the audio content so third party download tools can be used. Defaults to False.
        self.deployment_mode = deployment_mode  # If True, will install packages. Defaults to False. Must run as user with permissions to install pkgs, typically root.
        if not self.deployment_mode:
            self.destination = destination  # The path that content will be downloaded to. Defaults to '/tmp/appleloops'. Deployment mode will always use '/tmp/appleloops'.
        elif self.deployment_mode:
            self.destination = '/tmp/appleloops'
        self.dmg_filename = dmg_filename  # Filename used for creating DMG of content
        self.dry_run = dry_run  # Provides output only of what would happen. Defaults to True.
        self.force_deploy = force_deploy  # Re-installs packages regardless of whether they have been installed or not. Defaults to False.
        self.force_dmg = force_dmg  # Re-creates the DMG file regardless of whether it exists or not.
        self.hard_link = hard_link  # Creates hard links to files if they exist elsewhere. Defaults to False.
        self.mandatory_pkgs = mandatory_pkgs  # Sets the flag to download/install the required packages for a given app. Defaults to True. This is a change from previous behaviour.
        self.mirror_source_paths = mirror_source_paths  # This will mirror the folder structure of the Apple audiocontent.apple.com servers. Defaults to True. This is a change from previous behaviour.
        self.quiet_download = quiet_download  # This will suppress the progress bar while downloading files. Default is False.
        self.optional_pkgs = optional_pkgs  # Sets the flag to download/install the optional packages for a given app. Defaults to False.
        if pkg_server:  # So .rstrip() can work, have to check if pkg_server has a value.
            self.pkg_server = pkg_server.rstrip('/')  # Uses the specified local mirror of packages, must be in format of 'http://example.org/path/to/content'. Defaults to None. Removes any extraneous '/' char from end of argument value.
        else:
            self.pkg_server = pkg_server
        self.quiet_mode = quiet_mode  # Suppresses all stdout/stderr output. To view info about a run, view the log file. Defaults to False.
        self.space_threshold = space_threshold  # The percentage of disk free space to protect. Defaults to 5%. Must be an integer.
        # Create an instance of Requests()
        self.requests = Requests(allow_insecure=self.allow_insecure_https)
        # Debug log the class and what it was initialised with
        self.log.debug(vars(AppleLoops))
        self.log.debug(self.__dict__)
        # Create an empty dict to store loops that need to be process
        self.packages_to_process = {}

        # Audio Content: Apple URL, Mirror URL, and Cache URL
        class AudioContentSource(object):
            '''Simple object that returns three attributes about audio content source.'''
            def __init__(self, mirror=None, cache=None):
                self.apple = 'http://audiocontentdownload.apple.com'  # This is the fall back in case there is no hosted mirror, or cache server is not supplied.
                self.cache = cache  # For caching server, don't transform here.
                self.github = 'https://raw.githubusercontent.com/carlashley/appleLoops/test/lp10_ms3_content_2016'  # Backup location for plists only. Do not use for pkg files.
                self.mirror = mirror  # This is the preferred means of deploying loops

        self.content_source = AudioContentSource(mirror=self.pkg_server, cache=self.caching_server)
        self.log.debug('Apple Source URL: {}, Mirror Source URL: {}, Caching Server Source URL: {}'.format(self.content_source.apple, self.content_source.mirror, self.content_source.cache))

        def processLocalApp(application):
            '''Internal function that Returns information about specified application if the application path exists'''
            app_paths = {'garageband': 'GarageBand.app', 'logicpro': 'Logix Pro X.app', 'mainstage': 'MainStage 3.app'}
            if application not in app_paths.keys():
                raise Exception('Invalid application name. Choose from {}'.format(app_paths.keys()))
            Result = namedtuple('Result', ['installed', 'path', 'plist', 'plist_basename', 'apple_plist_source', 'github_plist_source'])
            app_result = {}  # An empty dict to make it easier to return None values if that is the result
            app_path = os.path.join('/Applications', app_paths[application])
            plist_glob = os.path.join(app_path, 'Contents/Resources/{}*.plist'.format(application))
            app_result['installed'] = os.path.exists(app_path)

            if os.path.exists(app_path):
                plist_path = glob(plist_glob)  # Find relevant plists for source
                plist_path.sort()  # Sort so if more than one exists, the last element should be the most recent plist file
                app_result['plist_path'] = plist_path[-1]  # Return the most recent plist from the sorted list.
                app_result['plist_basename'] = os.path.basename(plist_path[-1])
                app_result['apple_plist_source'] = '{}/lp10_ms3_content_2016/{}'.format(self.content_source.apple, os.path.basename(plist_path[-1]))
                app_result['github_plist_source'] = '{}/{}'.format(self.content_source.github, os.path.basename(plist_path[-1]))

            return Result(
                installed=app_result.get('installed', False),
                path=app_path, plist=app_result.get('plist_path', None),
                plist_basename=app_result.get('plist_basename', None),
                apple_plist_source=app_result.get('apple_plist_source', None),
                github_plist_source=app_result.get('github_plist_source', None))

        # Create the info for each local app identifying if installed, plist path, etc
        self.garageband = processLocalApp(application='garageband')
        self.log.debug('GarageBand: {}'.format(self.garageband))
        self.logicpro = processLocalApp(application='logicpro')
        self.log.debug('Logic Pro X: {}'.format(self.logicpro))
        self.mainstage = processLocalApp(application='mainstage')
        self.log.debug('MainStage 3: {}'.format(self.mainstage))

    def processPlist(self, plist):
        '''Processes a plist and returns data in the form of a dictionary.'''
        def badPackage(plist, package):
            '''Returns True if a package should not be downloaded for whatever reason.'''
            # After GarageBand 10.3+ release, there's a bunch of loops that are downloaded but don't install due to not finding a qualifying package for mainstage and logicpro
            bad_packages = {
                'garageband1021.plist': ['JamPack4_Instruments.pkg', 'MAContent10_AppleLoopsLegacy1.pkg', 'MAContent10_AppleLoopsLegacyRemix.pkg', 'MAContent10_AppleLoopsLegacyRhythm.pkg', 'MAContent10_AppleLoopsLegacySymphony.pkg', 'MAContent10_AppleLoopsLegacyVoices.pkg', 'MAContent10_AppleLoopsLegacyWorld.pkg', 'MAContent10_AssetPack_0326_AppleLoopsJamPack1.pkg', 'MAContent10_GarageBand6Legacy.pkg', 'MAContent10_IRsSurround.pkg', 'MAContent10_Logic9Legacy.pkg', 'RemixTools_Instruments.pkg', 'RhythmSection_Instruments.pkg', 'Voices_Instruments.pkg', 'WorldMusic_Instruments.pkg'],
            }
            if package in bad_packages[plist]:
                self.log.debug('Bad package check: {}'.format(package))
                return package in bad_packages[plist]

        # An internal function to transform the Apple URL into a Cache Server friendly URL.
        def transformCacheServerURL(url):
            '''Transforms a given URL into a URL that will pull through the Caching Server on the network'''
            if not url.startswith(self.content_source.apple):  # For caching, the source URL has to be the audiocontentdownload url.
                err_msg = 'Package URL must start with {}'.format(self.content_source.apple)
                self.log.debug(err_msg)
                raise Exception(err_msg)
            else:
                return '{}{}?source={}'.format(self.caching_server, urlparse(url).path, urlparse(url).netloc)

        # An internal function that will check the response code of supplied url, and update the packages_to_process dictionary with new info
        def updatePackageDetails(package):
            # If a pkg_server is specified, check that the package exists on the server, if it does, add the status code.
            # Note, this assumes anything but 200 is a failure.
            http_status = self.requests.status(self.packages_to_process[package]['PackageURL'])  # Get the HTTP Status of the package url, and store for easy reference.
            self.packages_to_process[package]['PackageHTTPStatus'] = http_status  # Create the PackageHTTPStatus entry in the packages_to_process dict for future reference.
            package_url = self.packages_to_process[package]['PackageURL']
            if self.pkg_server and not http_status == 200:
                # If the status code isn't 200, then fall back to using the Apple servers, change the package URL, and check status code of Apple server.
                new_package_url = package_url.replace(str(self.pkg_server), self.content_source.apple)
                self.packages_to_process[package]['PackageURL'] = new_package_url
                self.log.debug('HTTP Status {} for {}, fell back to {}'.format(http_status, package, new_package_url))
                http_status = new_package_url  # Re-test the HTTP Status of the new URL
                self.log.debug('HTTP Status {} for new URL {}'.format(http_status, new_package_url))
            # else:
            #     self.packages_to_process[package]['PackageHTTPStatus'] = self.requests.status(self.packages_to_process[package]['PackageURL'])

            # Get the size of the remote package, in bytes
            if self.packages_to_process[package]['PackageHTTPStatus'] == 200:
                self.packages_to_process[package]['size'] = self.requests.headers(self.packages_to_process[package]['PackageURL'])['content-length']

        # An internal function to check if the package is installed. For a bit more OS compatibility, this will only return an answer if the OS type is Darwin.
        def packageInstalled(package_id):
            '''Returns a dictionary of installed state and version.'''
            # Default dict values to return
            installed_result = {'installed': False, 'version': '0.0'}
            self.log.debug('System is {}'.format(sys.platform))
            if 'darwin' in sys.platform:
                pkgutil = ['/usr/sbin/pkgutil', '--pkg-info-plist', package_id]
                result, error = subprocess.Popen(pkgutil, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
                if result:
                    installed_result['installed'], installed_result['version'] = True, '.'.join(str(readPlistFromString(result)['pkg-version']).split('.')[:3])  # Local version is awful version type to compare, example: 2.0.0.0.1.1447702152
                if error:
                    self.log.debug('Error checking if package is installed: {}'.format(error))

            return installed_result

        # If the plist path starts with 'http', fetch from the provided URL and read direct from string, otherwise assume local path
        if plist.startswith('http'):
            packages = readPlistFromString(self.requests.fetch(plist))['Packages']
            self.log.debug('Fetched {}'.format(plist))
        else:
            packages = readPlist(plist)['Packages']
            self.log.debug('Read {}'.format(plist))

        # Iterate over the resulting packages dictionary and start getting values for dropping into a dict.
        for package in packages:
            package_name = packages[package]['DownloadName']
            package_basename = os.path.basename(package_name)
            package_url = '{}/lp10_ms3_content_2016/{}'.format(self.content_source.apple, package_basename)
            package_installed_size = packages[package].get('InstalledSize', None)
            package_id = packages[package].get('PackageID'.replace('. ', '.'), None)  # Some Package ID's have a '. ' in the string, this is a typo.
            package_version = str(float(packages[package].get('PackageVersion', 0.0)))  # Apple uses a long type here, but we're converting this so LooseVersion()/StrictVersion() can be used for comparison. Also, not all packages have a version number.
            package_install_state = packageInstalled(package_id=package_id)
            package_installed = package_install_state['installed']
            package_local_version = package_install_state['version']
            package_mandatory = packages[package].get('IsMandatory', False)  # Mandatory packages are True, if that doesn't exist, assume not required, so False.

            # If the remote package version is greater than the local version and the package is installed, then the package needs updating, so change package_installed to False.
            if LooseVersion(package_local_version) < LooseVersion(package_version) and package_installed:
                package_installed = False

            # Handle when a pkg_server is being used
            if self.pkg_server:
                package_url = '{}/lp10_ms3_content_2016/{}'.format(self.pkg_server, package_basename)

            # Handle when a caching server is being used
            if self.caching_server:
                package_url = transformCacheServerURL(url=package_url)

            # Handle when a loop path contains '../lp10_ms3_content_2013' and correct the package_url path
            if '../lp10_ms3_content_2013/' in package_name:
                package_url = package_url.replace('lp10_ms3_content_2016', 'lp10_ms3_content_2013')

            if self.mirror_source_paths:
                package_destination = os.path.join(self.destination, ''.join(package_url.partition('lp10')[1:]))  # Use partition to split on occurance of a particular string
            elif not self.mirror_source_paths:
                if package_mandatory:
                    package_destination = os.path.join(self.destination, os.path.basename(plist), 'mandatory', package_basename)
                elif not package_mandatory:
                    package_destination = os.path.join(self.destination, os.path.basename(plist), 'optional', package_basename)

            # If the package_basename does not already exist in the packages_to_process dictionary, add it
            if package_basename not in self.packages_to_process.keys() and not badPackage(plist=os.path.basename(plist), package=package_basename):
                self.packages_to_process[package_basename] = {
                    'PackageName': package_basename.replace('.pkg', ''),
                    'PackageURL': package_url,
                    'PackageIsMandatory': package_mandatory,
                    'PackageInstalledSize': package_installed_size,
                    'PackageDestination': package_destination.replace('.plist', ''),
                    'PackageID': package_id,
                    'PackageRemoteVersion': package_version,
                    'PackageLocalVersion': package_local_version,
                    'PackageInstalled': package_installed,
                }
                self.log.debug(self.packages_to_process[package_basename])

        # Concurrency for faster processing of URL's
        self.log.debug('Beginning concurrency run with updatePackageDetails()')
        workers = 20
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_package = {executor.submit(updatePackageDetails, package): package for package in self.packages_to_process}
            for future in concurrent.futures.as_completed(future_to_package):
                package = future_to_package[future]
                try:
                    future.result()
                except Exception as exception:
                    self.log.debug('Concurrency exception: {}'.format(exception))
                    print 'Exception occurred while concurrency processing underway, please be patient while debugging occurs.'
                    print 'Issues can be raised by visiting http://github.com/carlashley/appleloops/issues. Please include the exception error and the log file {}.'.format(self.log_file)
                    # Start a normal for loop to debug what happened while processing the package details.
                    self.log.debug('Beginning for loop iteration over self.packages_to_process to debug concurrency exception')
                    for _package in self.packages_to_process:
                        updatePackageDetails(_package)

        # pprint(self.packages_to_process)


def main():
    class SaneUsageFormat(argparse.HelpFormatter):
        '''Makes the help output somewhat more sane. Code used was from Matt Wilkie.'''
        '''http://stackoverflow.com/questions/9642692/argparse-help-without-duplicate-allcaps/9643162#9643162'''

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
                    return '{} {}'.format(', '.join(parts), args_string)
                return ', '.join(parts)

        def _get_default_metavar_for_optional(self, action):
            return action.dest.upper()

    def getSupportedPlists():
        '''Returns a list of valid plists that can be used to download Apple\'s audio content'''
        '''This can take a few moments to process.'''
        supported_apps = ['garageband', 'logicpro', 'mainstage']
        valid_plist_urls = []  # Empty list for all the valid plists to go into

        def supportedPlists():
            base_plist_url = 'http://audiocontentdownload.apple.com/lp10_ms3_content_2016'
            urls_to_check = []
            for app in supported_apps:
                if 'garageband' in app:
                    version_range = range(1011, 1099)
                    [urls_to_check.append('{}/{}{}.plist'.format(base_plist_url, app, x)) for x in version_range if '{}/{}{}.plist'.format(base_plist_url, app, x) not in urls_to_check]
                if 'logicpro' in app:
                    version_range = range(1021, 1099)
                    [urls_to_check.append('{}/{}{}.plist'.format(base_plist_url, app, x)) for x in version_range if '{}/{}{}.plist'.format(base_plist_url, app, x) not in urls_to_check]
                if 'mainstage' in app:
                    version_range = range(323, 399)
                    [urls_to_check.append('{}/{}{}.plist'.format(base_plist_url, app, x)) for x in version_range if '{}/{}{}.plist'.format(base_plist_url, app, x) not in urls_to_check]
            return urls_to_check

        def checkSupportedPlistURL(plist_url):
            requests = Requests()
            if requests.status(url=plist_url) == 200 and plist_url not in valid_plist_urls:
                valid_plist_urls.append(os.path.basename(plist_url))

        # Populates the self.valid_plist_urls list that is used to identify what plists can be processed by this script.
        workers = 200  # 200 workers seems enough to get this job done quick enough, if this locks up your system, drop it back down to double digits.
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_url = {executor.submit(checkSupportedPlistURL, url): url for url in supportedPlists()}
            for future in concurrent.futures.as_completed(future_to_url):
                # url = future_to_url[future]
                try:
                    future.result()
                except Exception as exception:
                    raise exception

        return valid_plist_urls

    # Now build the arguments
    parser = argparse.ArgumentParser(formatter_class=SaneUsageFormat)
    supported_plist_exclusive_group = parser.add_mutually_exclusive_group()

    supported_plist_exclusive_group.add_argument('--apps', type=str, nargs='+', dest='apps', metavar='<app>', help='Processes packages available for the specified app.', choices=['garageband', 'logicpro', 'mainstage'], required=False)

    parser.add_argument('--plist', type=str, nargs='+', dest='plists', metavar='<plist>', help='Processes packages based on the provided plist(s).', required=False)

    supported_plist_exclusive_group.add_argument('--supported-plists', action='store_true', dest='show_supported_plists', help='Retrieves a list of supported plists direct from Apple\'s servers', required=False)

    # Parse the args
    args = parser.parse_args()

    # Deal with the arguments
    if not len(sys.argv) > 1:
        parser.print_help()
        sys.exit(0)
    elif len(sys.argv) > 1:
        if args.show_supported_plists:
            print 'Determining supported plist files from Apple servers. This may take a few moments.'
            plists = getSupportedPlists()
            gb = [x for x in plists if x.startswith('garageband')]
            print 'GarageBand: {}'.format(', '.join(gb))
            lp = [x for x in plists if x.startswith('logicpro')]
            print 'Logic Pro X: {}'.format(', '.join(lp))
            ms = [x for x in plists if x.startswith('mainstage')]
            print 'MainStage 3: {}'.format(', '.join(ms))

            sys.exit(0)

        if len(args.apps) > 1:
            _apps = args.apps
        else:
            _apps = None

        #    AppleLoops() arguments: allow_insecure_https=False, allow_untrusted_pkgs=False, apps=None, apps_plist=None, caching_server=None, create_links_only=False, debug=False, deployment_mode=False, destination='/tmp/appleloops', dmg_filename=None, dry_run=True, force_deploy=False, force_dmg=False, hard_link=False, log_path=None, mandatory_pkgs=True, mirror_source_paths=True, quiet_download=False, optional_pkgs=False, pkg_server=None, quiet_mode=False, space_threshold=5
        # appleloops = AppleLoops(debug=True, apps=_apps, mirror_source_paths=False)  # NOQA
        appleloops = AppleLoops(debug=True, apps=_apps, pkg_server='http://example.org/audiocontentdownload/')  # NOQA
        # appleloops = AppleLoops(debug=True, apps=_apps, caching_server='http://example.org:8080')  # NOQA
        appleloops.processPlist(appleloops.garageband.apple_plist_source)


if __name__ == '__main__':
    main()
