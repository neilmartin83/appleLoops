#!/usr/bin/python

import plistlib


def make_conf(plist_dict, plist_file):
    plistlib.writePlist(plist_dict, plist_file)


configuration = {
    'importConfigs': {
        'garageband': {
            'category': 'Audio',
            'unattendInstall': True,
            'displayNamePrefex': 'GB_',
            'developer': 'Apple',
            'catalog': 'testing',
            'updateFor': 'com.github.carlashley.appleLoops.app.garageband'
        },
        'logicpro': {
            'category': 'Audio',
            'unattendInstall': True,
            'displayNamePrefex': 'LP_',
            'developer': 'Apple',
            'catalog': 'testing',
            'updateFor': 'com.github.carlashley.appleLoops.app.logic-pro'
        },
        'mainstage': {
            'category': 'Audio',
            'unattendInstall': True,
            'displayNamePrefex': 'MS_',
            'developer': 'Apple',
            'catalog': 'testing',
            'updateFor': 'com.github.carlashley.appleLoops.app.mainstage'
        },
    },
    'pkgsinfoPath': 'pkgsinfo/upd',
    'import_destination': 'pkgs/upd',
    'munkiRepoPath': '/Volumes/munki_repo',
    'munkiimportPath': '/usr/local/munkiimport',
}


make_conf(configuration, 'com.github.carlashley.appleLoops.config.plist')
