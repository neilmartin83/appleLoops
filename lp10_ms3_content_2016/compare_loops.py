#!/usr/bin/python

import plistlib
import sys


def differences(file_a, file_b):
    if all([sys.argv[1].endswith('.plist'), sys.argv[2].endswith('.plist')]):
        files = sorted([x for x in [sys.argv[1], sys.argv[2]]])
        file_a = files[0]
        file_b = files[1]

        pkg_set_a = plistlib.readPlist(file_a)['Packages']
        pkg_set_b = plistlib.readPlist(file_b)['Packages']

        pkg_set_a = [pkg_set_a[x]['DownloadName'] for x in pkg_set_a]
        pkg_set_b = [pkg_set_b[x]['DownloadName'] for x in pkg_set_b]

        not_in_pkg_set_a = [x for x in pkg_set_b if x not in pkg_set_a]
        # common_pkgs = {x for x in pkg_set_b if x in pkg_set_a}

        print 'The following packages in {} are not in {}'.format(file_b,
                                                                  file_a)
        for pkg in not_in_pkg_set_a:
            print pkg
    else:
        print 'Usage: {} <file a> <file b>'.format(sys.argv[0])
        sys.exit(1)


differences(sys.argv[1], sys.argv[2])
