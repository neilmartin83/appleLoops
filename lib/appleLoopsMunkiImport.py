#!/usr/bin/python

'''A tool to import all loops downloaded using appleLoops.py'''

import collections
import hashlib
import os
import plistlib
# import subprocess

from glob import glob

# Script information
__author__ = 'Carl Windus'
__copyright__ = 'Copyright 2016, Carl Windus'
__credits__ = ['Matt Wilkie']
__version__ = '1.0.0'
__date__ = '2017-06-08'

__license__ = 'Apache License, Version 2.0'
__maintainer__ = 'Carl Windus: https://github.com/carlashley/appleLoops'
__status__ = 'Testing'


class AppleLoopsImporter():
    def __init__(self, munki_import=False):
        if munki_import:
            conf_file = 'com.github.carlashley.appleLoops.config.plist'
            self.configuration = plistlib.readPlist(conf_file)
            self.ImportMaster = collections.namedtuple('ImportMaster',
                                                       ['pkg_path',
                                                        'update_for',
                                                        'digest'])

            self.munkiimport = self.configuration['munkiimportPath']
            self.import_path = os.path.join(
                self.configuration['munkiRepoPath'],
                self.configuration['import_destination']
            )
            self.pkgsinfo_path = os.path.join(
                self.configuration['munkiRepoPath'],
                self.configuration['pkgsinfoPath']
            )

            self.garageband_conf = self.configuration['importConfigs']['garageband']  # NOQA
            self.logicpro_conf = self.configuration['importConfigs']['logicpro']  # NOQA
            self.mainstage_conf = self.configuration['importConfigs']['mainstage']  # NOQA

    # Build digest for a specific file
    def file_digest(self, file_path, digest_type=None):
        '''Creates a digest based on the digest_type argument.
        digest_type defaults to SHA256.'''
        valid_digests = ['md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512']
        block_size = 65536

        if not digest_type:
            digest_type = 'sha256'

        if digest_type in valid_digests:
            h = hashlib.new(digest_type)
            with open(file_path, 'rb') as f:
                for block in iter(lambda: f.read(block_size), b''):
                    h.update(block)
                return h.hexdigest()
        else:
            raise Exception('%s not a valid digest - choose from %s' %
                            (digest_type, valid_digests))

    # Compare two digests
    def compare_digests(self, digest_a, digest_b):
        if digest_a == digest_b:
            return True
        else:
            return False

    # Import Routine
    def import_loop(self, loop):
        cmd = [self.munkiimport, 'foo']
        try:
            # subprocess.check_call(cmd)
            print 'Import test: %s' % cmd
        except:
            raise

    # Glob all the pkgsinfo plists for Apple loops. These should start with
    # MAContent
    def loop_pkgsinfo(self):
        return glob('%s/MAContent*.plist' % self.pkgsinfo_path)

    # Get the digest from the pkgsinfo files for the Apple loops
    def pkgsinfo_digest(self, pkgsinfo_file):
        digest = plistlib.readPlist(pkgsinfo_file)['installer_item_hash']
        return digest

    # Path for item already imported into munki
    def munki_pkg_path(self, pkgsinfo_file):
        pkg_path = plistlib.readPlist(pkgsinfo_file)['installer_item_location']
        return os.path.join(self.configuration['munkiRepoPath'], pkg_path)

    def source_path_items(self, path):
        return glob('%s/*/*/*.pkg' % path)


ali = AppleLoopsImporter(munki_import=True)

# pkgsinfo_files = ali.loop_pkgsinfo()
#
# for _file in pkgsinfo_files:
#     digest = ali.pkgsinfo_digest(_file)
#     pkg_path = ali.munki_pkg_path(_file)
#     print '%s - %s' % (pkg_path, digest)

source_items = ali.source_path_items('/Volumes/Data/packaging/software/apps/garageband/')  # NOQA


import_items = {}
for item in source_items:
    if os.path.basename(item) not in import_items.keys():
        import_items[os.path.basename(item)] = {
            'path': item,
            'digest': ali.file_digest(item)
        }

print import_items


# When working with the location in the munki_repo that audio loops have been
# imported to, it's probably a good idea to have items imported into folders
# like:
#   garageband1012/*.pkg - this would hold all packages applicable to
#                          garageband 10.1.2 only
#   garageband1016/*.pkg - this would hold all packages applicable to
#                          garageband 10.1.6, any packages that are used in
#                          this release and also in 10.1.2 release should
#                          stay in the 10.1.2 release. This would be the same
#                          for all releases.
# This seems to be a good way to manage the fact that loops can change from
# release to release and that munki doesn't have an inbuilt means to mark a
# package as an update for specific app versions.

# Yet to do...
#   * implement a function that ties together the two dicts or bundles stuff
#   into the same dict that we can compare against
#   * implement a fake import routine for testing purposes
