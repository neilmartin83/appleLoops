#!/usr/bin/python

import plistlib


def make_conf(plist_dict, plist_file):
    plistlib.writePlist(plist_dict, plist_file)


configuration = {
    'munkiRepoPath': '/Volumes/munki_repo',
    'import_destination': '/pkgs/upd',
    'munkiimportPath': '/usr/local/munkiimport',
    'importConfigs': {
        'garageband': {
            'category': 'Audio',
            'unattendInstall': True,
            'displayNamePrefex': 'GB_',
            'developer': 'Apple',
            'catalog': 'testing',
            'updateFor': 'au.edu.qld.redlands.app.garageband'
        },
        'logicpro': {
            'category': 'Audio',
            'unattendInstall': True,
            'displayNamePrefex': 'LP_',
            'developer': 'Apple',
            'catalog': 'testing',
            'updateFor': 'au.edu.qld.redlands.app.garageband'
        },
        'mainstage': {
            'category': 'Audio',
            'unattendInstall': True,
            'displayNamePrefex': 'MS_',
            'developer': 'Apple',
            'catalog': 'testing',
            'updateFor': 'au.edu.qld.redlands.app.garageband'
        },

    }
}


make_conf(configuration, 'com.github.carlashley.appleLoops.config.plist')
