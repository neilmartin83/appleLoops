#!/usr/bin/python

try:
    import os
    import sys
    sys.path.append('/usr/local/munki/munkilib')
    import FoundationPlist

    garageband_app_plist = '/Applications/GarageBand.app/Contents/Info.plist'
    logic_pro_app_plist = '/Applications/Logic Pro X.app/Contents/Info.plist'
    mainstage_app_plist = '/Applications/MainStage 3.app/Contents/Info.plist'

    conditional_plist = os.path.join(FoundationPlist.readPlist('/Library/Preferences/ManagedInstalls.plist')['ManagedInstallDir'], 'ConditionalItems.plist')  # NOQA

    version_info = {}

    try:
        ver = FoundationPlist.readPlist(garageband_app_plist)['CFBundleShortVersionString']  # NOQA
        # Convert the version to '1234' format from '12.3.4' as the plist feeds
        # use '1234' format.
        version_info['garageband_ver'] = ver.replace('.', '')
    except:
        version_info['garageband_ver'] = '0'

    try:
        ver = FoundationPlist.readPlist(logic_pro_app_plist)['CFBundleShortVersionString']  # NOQA
        version_info['logic_pro_ver'] = ver
    except:
        version_info['logic_pro_ver'] = '0'.replace('.', '')

    try:
        ver = FoundationPlist.readPlist(mainstage_app_plist)['CFBundleShortVersionString']  # NOQA
        version_info['mainstage_ver'] = ver
    except:
        version_info['mainstage_ver'] = '0'.replace('.', '')

    try:
        FoundationPlist.writePlist(version_info, conditional_plist)
    except:
        pass

except:
    raise
