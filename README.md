# appleLoops.py

## Requirements
macOS with the system standard `python` and an active Internet connection.

## GarageBand, Logic Pro X, and MainStage 3 First Run
All three apps will attempt to download a mandatory set of packages containing loops and various other items. This mandatory set is a small subset of _all_ the available content for each of those apps.

Typically, the content is the same within minor releases, for example, the content released with GarageBand 10.1.2 remained the same through until GarageBand 10.1.5 was released. Occasionally Apple may modify a specific package or specific packages for security fixes. This behaviour is identical for all three apps.

All three apps do have a number of packages that are shared in common, both in the essential package sets, and optional package sets.

## What does ``appleLoops.py`` do?
`.appleLoops.py` is a utility to _download_ the mandatory and optional packages that are normally downloaded/offered for download in the first run of any of the GarageBand, Logic Pro X, or MainStage 3 apps.

There is some basic file duplication checking done during run time that will check if loops have already been downloaded, and if so, copies or skips the file. Where possible, file downloads are resumed (incomplete files are over-written).

The tool can also create a dmg from the downloaded content.

Unfortunately there is no means to do a digest comparison on each package, as Apple does not (currently) include an MD5 or SHA digest for each package.

_Note_ this tool is not intended to mirror the source servers at Apple.

### Package download location
Packages will be saved into the `/tmp/appleLoops` folder by default, unless the `-d, --destination <folder>` flag and argument is provided.

The content is stored in a folder within the specified or default download location based on the plist file it was processed from.

For example:
```
/tmp/appleLoops/garageband1016
............................../mandatory
......................................../MAContent10_AssetPack_0539_DrummerTambourine.pkg
......................................../...
......................................../MAContent10_AssetPack_0312_UB_UltrabeatKitsGBLogic.pkg
```
The same structure as the above example is used for the optional packages.
```
/tmp/appleLoops/garageband1016
............................../optional
......................................./MAContent10_AssetPack_0170_AlchemyGuitarsElectricTrad.pkg
......................................./...
......................................./MAContent10_AssetPack_0069_AlchemySoundscapesMicroForest.pkg
```

## Usage
* `git clone https://github.com/carlashley/appleLoops`
* `./appleLoops.py --help` for usage

### Quick usage examples
* `./appleLoops.py --help` show all options
* `./appleLoops.py -f garageband1016.plist -d ~/Desktop/loops` downloads all mandatory and optional packages for GarageBand using the `garageband1016.plist` as a reference, and stores the loops in the `~/Desktop/loops` folder.
* `./appleLoops.py -f garageband1016.plist -d ~/Desktop/loops --build-dmg ~/Desktop/loops.dmg` as above, except it will also create a DMG file of all the downloaded loops in the path specified. Handy if you want to use this in JSS/JAMF.

Some arguments are 'stackable'; for example, downloading GarageBand and Logic Pro X content in one command can be achieved using:
```./appleLoops.py -f garageband1016.plist logicpro1030.plist -d ~/Desktop/loops```

### Recommended Best practice for downloading:
Recommended best practice is to be version specific with the tool by using the `-f` or `--file` argument along with the plist file (as shown in the quick usage examples above), however, the tool will, for the most part, figure out the correct folder structure to store the content in.

# Copyright
```
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

Elements of `FoundationPlist.py` from `munki` are used in this tool from https://github.com/munki/munki.
