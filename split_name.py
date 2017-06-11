#!/usr/bin/python

from string import ascii_lowercase, ascii_uppercase

letters = '%s%s' % (ascii_lowercase, ascii_uppercase)
numbers = range(0, 9)

loop_ranges = ['garageband1012',
               'garageband1012',
               'garageband1016',
               'garageband1020',
               'mainstage321',
               'mainstage330',
               'logicpro1031',
               'logicpro1021']

loop_ranges.sort()

garageband_versions_range = []
mainstage_versions_range = []
logicpro_versions_range = []

for loop in loop_ranges:
    # Remove the digits to get what app the loop is for
    loop_for = ''.join(map(lambda c: '' if c in numbers else c, loop))
    # Remove the digits to get what version the loop is for
    version = ''.join(map(lambda c: '' if c in letters else c, loop))
    if 'garageband' in loop_for and version not in garageband_versions_range:
        garageband_versions_range.append(version)

    if 'mainstage' in loop_for and version not in mainstage_versions_range:
        mainstage_versions_range.append(version)

    if 'logicpro' in loop_for and version not in logicpro_versions_range:
        logicpro_versions_range.append(version)


for ver in garageband_versions_range:
    # ver_index = garageband_versions_range.index(ver)
    next_index = garageband_versions_range.index(ver) + 1
    try:
        if ver.startswith('10'):
            start_range = int(ver[-2:])
        else:
            start_range = int(ver[-1:])

        end_range = int(garageband_versions_range[next_index][-2:]) - 1
        print 'garageband_ver MATCHES 10(%s-%s)' % (start_range, end_range)
    except IndexError:
        pass


for ver in mainstage_versions_range:
    # ver_index = garageband_versions_range.index(ver)
    next_index = mainstage_versions_range.index(ver) + 1
    try:
        if ver.startswith('10'):
            start_range = int(ver[-2:])
        else:
            start_range = int(ver[-1:])

        end_range = int(mainstage_versions_range[next_index][-2:]) - 1
        print 'mainstage_ver 3(%s-%s)' % (start_range, end_range)
    except IndexError:
        pass


for ver in logicpro_versions_range:
    # ver_index = garageband_versions_range.index(ver)
    next_index = logicpro_versions_range.index(ver) + 1
    try:
        if ver.startswith('10'):
            start_range = int(ver[-2:])
        else:
            start_range = int(ver[-1:])

        end_range = int(logicpro_versions_range[next_index][-2:]) - 1
        print 'logicpro_ver 10(%s-%s)' % (start_range, end_range)
    except IndexError:
        pass
