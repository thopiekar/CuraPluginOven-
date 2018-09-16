# Copyright (c) 2018 Thomas Karl Pietrowski

import argparse

# File and OS handling
import json
import os
import shutil
import sys
from urllib.parse import urlparse

# Building the package
import compileall
import py_compile

# packaging the plugin
import zipfile

# File extensions
system_files = [".",
                "Thumbs.db"]

python_sources = [".py"]
python_bytecompiled = [".pyc",
                       ".pyo",
                       ]
qml_bytecompiled = [".qmlc",
                    ]
python_files = python_sources + python_bytecompiled

excluded_extentions = python_bytecompiled + qml_bytecompiled

essential_package_fields = (("package_id",),
                            ("package_type",),
                            ("display_name",),
                            ("description",),
                            ("package_version",),
                            ("sdk_version",),
                            ("website",),
                            ("author",),
                            ("author", "author_id"),
                            ("author", "display_name"),
                            ("author", "email"),
                            ("author", "website"),
                            ("tags",),
                            )

essential_plugin_fields = ("name",
                           "id",
                           "i18n-catalog",
                           "author",
                           "email",
                           "version",
                           "description",
                           )

class CuraCreatorCommon():
    "Common methods across all creators"
    def loadInfoFromJsonFile(self, source_path, filename):
        json_file = open(os.path.join(source_path,
                                      filename,
                                      )
                        )
        result = json.load(json_file)
        json_file.close()
        return result

    def cleanUpBuildDirectory(self, build_path):
        if os.path.isdir(build_path):
            if len(os.listdir(build_path)):
                print("- Warning: The given build path is neither a new location nor empty. Cleaning it up!")
                shutil.rmtree(build_path)

    def prepareBuildDirectory(self, build_path):
        self.cleanUpBuildDirectory(build_path)

        os.makedirs(build_path,
                    exist_ok = True)

        print("i Build directory prepared!")

    def checkForIgnorableFiles(self, relative_filename):
        checked_entries = []
        for entry in relative_filename.split(os.sep):
            args.exclude
            if entry.startswith("."): # dot files and directories
                return True
            this_path = os.path.join(args.source, *checked_entries, entry)
            if this_path.startswith(os.path.split(__file__)[0]):
                return True
            if this_path.startswith(args.build):
                return True
            if entry in ("test","tests") and os.path.isdir(this_path): # test directories
                return True
            if os.path.isfile(this_path):
                for extension in excluded_extentions:
                    if entry.endswith(extension):
                        return True
            checked_entries.append(entry)
        return False

    def compileAllPySources(self, variant, optimize = -1):
        # zip_handle is zipfile handle
        for walked in os.walk(args.source):
            root = walked[0]
            filenames = walked[2]
            for filename in filenames:
                fullname = os.path.join(root, filename)
                relative_filename = os.path.relpath(fullname, args.source)
                if self.checkForIgnorableFiles(relative_filename):
                    continue
                _, extension = os.path.splitext(filename)
                if extension in python_sources:
                    destdir = os.path.join(args.build,
                                           relative_filename)
                    destdir = os.path.split(destdir)[0]
                    os.makedirs(destdir, exist_ok = True)
                    if variant in ("binary+source", "source", "binary"):
                        filename_copied = "{}/{}".format(destdir, filename)
                        shutil.copyfile(fullname,
                                        filename_copied
                                        )
                        print("* Copying: {}".format(relative_filename))
                        if variant in ("binary+source", "binary"):
                            compileall.compile_file(filename_copied,
                                                ddir = relative_filename,
                                                quiet = 2,
                                                optimize = optimize,
                                                )
                            print("* Compiling: {}".format(relative_filename))
                        if variant is "binary":
                            if relative_filename != "__init__.py":
                                print("* Removing: {}".format(relative_filename))
                                os.remove(filename_copied)
                    else:
                        print("E Invalid variant!")
        print("i Python files compiled and optionally copied source(s)!")

    def copyOtherFiles(self):
        # zip_handle is zipfile handle
        for walked in os.walk(args.source):
            root = walked[0]
            filenames = walked[2]
            for filename in filenames:
                if filename.startswith("."): # dot files
                    continue
                if filename in system_files: # system files
                    continue
                if os.path.splitext(filename)[1] in python_files: # python files
                    continue
                fullname = os.path.join(root, filename)
                relative_filename = os.path.relpath(fullname, args.source)
                if self.checkForIgnorableFiles(relative_filename):
                    continue
                print("* Copying: {}".format(relative_filename))

                destdir = os.path.split(os.path.join(args.build,
                                                     relative_filename)
                                                     )[0]
                os.makedirs(destdir, exist_ok = True)
                shutil.copyfile(fullname,
                                os.path.join(destdir, filename)
                                )
        print("i Copied other files!")

    def requiresCura(self, path):
        return self.getFlavour(path) is "cura"

    def isUrlAddress(self, address):
        try:
            urlparse(address)
            return True
        except:
            return False

    def getSource(self, location):
        if os.path.isdir(location):
            return location

        if isUrlAddress(location):
            if os.path.isdir(args.downloaddir):
                print("- Warning: The given download path is not a empty location. Cleaning it up!")
                shutil.rmtree(args.downloaddir)
            if location.endswith(".git"):
                ret = os.system("git clone {} --single-branch --depth 1 --recurse-submodules {} {}".format(args.gitargs, location, args.downloaddir))
                if not ret:
                    return args.downloaddir

        return None

class CuraPackageCreator(CuraCreatorCommon):
    "Creates package files based on package info (package.json)"

    def __init__(self):
        self._source_base = None

    def generateDistribution(self, args):
        # Source validation check
        if not self.checkValidPlugin(args.source):
            print("E The provided source is not valid!")
            sys.exit(1)

        self.generatePluginMetadata(override = False)
        if not self.verifyPluginMetadata(args):
            print("E The plugins metadata is not valid!")
            sys.exit(1)

    def generatePluginMetadata(self, override = False):
        if os.path.isfile(os.path.join(self._source_base, "plugin.json")) and not override:
            print("w Metadata of the plugin already exists. Skipping automated creation!")
            return

    def verifyPluginMetadata(self, args):
        plugin_meta = self.loadInfoFromJsonFile(self._source_base, "plugin.json")
        package_meta = self.loadInfoFromJsonFile(args.source, "package.json")

        # Equality of IDs
        if not plugin_meta["id"] == package_meta["package_id"]:
            return False
        # Equality of the names
        if not plugin_meta["name"] == package_meta["display_name"]:
            return False
        return True

    def checkValidPlugin(self, path):
        # A plugin must be a folder
        if not os.path.isdir(path):
            return False
        print("* Verify: Found project base")

        # .. and a plugin must contain an plugin.json!
        result = False
        for license_file in ("LICENSE",
                             "LICENSE.txt",):
            if os.path.isfile(os.path.join(path, license_file)):
                result = True
                break
        if not result:
            print("! ERROR: Licence file not found!")
            return False
        print("* Verify: Licence file found")

        # Checking whether package metadata is parsable
        metadata = self.loadInfoFromJsonFile(args.source, "package.json")
        print("* Verify: Passed syntax verification of plugin definition")

        # Checking whether all keywords are present
        for keywords in essential_package_fields:
            test_object = metadata
            for keyword in keywords:
                if keyword not in test_object.keys():
                    print("! ERROR: Missing keyword in metadata: {}".format(repr(".".join(keywords))))
                    return False
                else:
                    test_object = test_object[keyword]
            print("* Verify: Found keyword in metadata: {}".format(repr(".".join(keywords))))

        # Trying to find source base
        if not metadata["package_type"] == "plugin":
            print("Unexpected package format: %s".format(repr(metadata["package_type"])))
        expected_source_bases = (os.path.join(args.source, metadata["package_type"], metadata["package_id"]), # As placed in the final package
                                 os.path.join(args.source, metadata["package_id"]), # as done at CuraDrive
                                 os.path.join(args.source, ), # in case the package.json is in the same directory as the sources
                                 )
        result = False
        for expected_source_base in expected_source_bases:
            print("* Testing path: {}".format(repr(expected_source_base)))
            # Checking for some general requirements here:
            # A source base must contain an __init__.py
            if not os.path.isfile(os.path.join(expected_source_base, "__init__.py")):
                continue
            print("* Verify: Found __init__ file")

            print("i Found source base")
            self._source_base = expected_source_base
            result = True
            break

        if not result:
            print("e Source base not found!")
            return False

        # All checks done
        print("i Verification passed!")
        return True


class CuraPluginCreatorLegacy(CuraCreatorCommon):
    "Creates plugin files based on package info (package.json)"

class CuraPluginCreator(CuraCreatorCommon):
    "Creates plugin files based on plugin info (plugin.json)"

    def generateDistribution(self, args):
        # Source validation check
        if not self.checkValidPlugin(args.source):
            print("E The provided source is not valid!")
            sys.exit(1)

        # Reading the JSON file and checking which flavour of package needs to be built
        plugin_json = self.loadInfoFromJsonFile(args.source, "plugin.json")
        self.requiresCura(args.source)

        # Preparing build..
        self.prepareBuildDirectory(args.build)
        # Build all files.. Compile and copy them..
        self.compileAllPySources(args.variant, optimize = args.optimize)
        self.copyOtherFiles()
        # Building the package
        self.buildPackage(plugin_json, compression=args.compression)
        # Testing package
        self.testPackage(plugin_json)
        # Clean up build directory
        self.cleanUpBuildDirectory(args.build)

    def checkValidPlugin(self, path):
        # A plugin must be a folder
        if not os.path.isdir(path):
            return False
        print("* Verify: Found sources")

        # A plugin must contain an __init__.py
        if not os.path.isfile(os.path.join(path, "__init__.py")):
            print("E Verify: Found no __init__ file")
            return False
        print("* Verify: Found __init__ file")

        # .. and a plugin must contain an plugin.json!
        if not os.path.isfile(os.path.join(path, "plugin.json")):
            return False
        print("* Verify: Found plugin definition")
        plugin_json = self.loadInfoFromJsonFile(args.source, "plugin.json")
        print("* Verify: Passed syntax verification of plugin definition")

        # .. and a plugin must contain an plugin.json!
        result = False
        for license_file in ("LICENSE",
                             "LICENSE.txt",):
            if os.path.isfile(os.path.join(path, license_file)):
                result = True
                break
        if not result:
            print("! ERROR: Licence file not found!")
            return False
        print("* Verify: Licence file found")

        # The JSON also should contain a license definition!
        for keyword in essential_json_fields:
            if keyword not in plugin_json.keys():
                print("! ERROR: Missing keyword in plugin definition: {}".format(keyword))
                return False
            else:
                print("* Verify: Found keyword in \"{}\" definition.".format(keyword))

        print("i Verification passed!")

        return True

    def getFlavour(self, path):
        imports_cura = False
        imports_uranium = False
        for walked in os.walk(path):
            root = walked[0]
            filenames = walked[2]
            for filename in filenames:
                filename = os.path.join(root, filename)
                extension = os.path.splitext(filename)[1]
                if extension in python_sources:
                    source_file = open(filename)
                    for line in source_file.readlines():
                        if "import" in line and "cura." in line:
                            imports_cura = True
                        elif "import" in line and "UM." in line:
                            imports_uranium = True

        if imports_cura:
            return "cura"
        elif imports_uranium:
            return "uranium"
        else:
            raise ValueError("This is impossible! You need to import Uranium at least!")

    def buildPackage(self, metadata, compression = zipfile.ZIP_DEFLATED):
        plugin_name = metadata["id"]
        plugin_extension = ["umplugin", "curaplugin"][self.requiresCura(args.source)]
        plugin_file = "{}-{}.{}".format(plugin_name,
                                        metadata["version"],
                                        plugin_extension)
        plugin_file = os.path.join(args.destination, plugin_file)
        if os.path.isfile(plugin_file):
            os.remove(plugin_file)

        zip_object = zipfile.ZipFile(plugin_file, "w",
                                     compression = compression)
        # Cura convention: Plugin inside the zip needs to be in a directory with the same name of the plugin itself.
        # Originally taken from Uranium:
        ## Ensure that the root folder is created correctly. We need to tell zip to not compress the folder!
        subdirectory = zipfile.ZipInfo(plugin_name + "/")
        zip_object.writestr(subdirectory, "", compress_type = zipfile.ZIP_STORED) #Writing an empty string creates the directory.

        for walked in os.walk(args.build):
            root = walked[0]
            files = walked[2]
            for file in files:
                filename = os.path.relpath(os.path.join(root, file), args.build)
                print("* Packaging: {}".format(filename))
                zip_object.write(os.path.join(args.build, filename),
                                 os.path.join(plugin_name, filename)
                                 )
        print("i Package built: {}".format(plugin_file))

    def testPackage(self, metadata):
        plugin_name = metadata["id"]
        plugin_extension = ["umplugin", "curaplugin"][self.requiresCura(args.source)]
        plugin_file = "{}-{}.{}".format(plugin_name,
                                        metadata["version"],
                                        plugin_extension)

        # Checking for the Cura convention!
        with zipfile.ZipFile(plugin_file, "r") as zip_ref:
            plugin_id = None
            for file in zip_ref.infolist():
                if file.filename.endswith("/"):
                    plugin_id = file.filename.strip("/")
                    break

            if plugin_id is None:
                print("E Built package is invalid!")
                return False
        print("i Built package is valid!")
        return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--creator", "--cr", "-C",
                        dest="creator",
                        type = str,
                        default = "package",
                        choices = ["package",
                                   "plugin_legacy",
                                   "plugin",
                                   ],
                        help = "Choose which creator to take to build your file")
    parser.add_argument("--source", "--src", "-s",
                        dest="source",
                        type = str,
                        default = "source",
                        help = "Location of the source folder")
    parser.add_argument("--exclude", "--excl", "-e",
                        dest="exclude",
                        type = str,
                        default = None,
                        help = "Exclude files or directories separated via os.pathsep")
    parser.add_argument("--downloaddir", "--dldir", "-dd",
                        dest="downloaddir",
                        type = str,
                        default = "download",
                        help = "Location of the download folder")
    parser.add_argument("--build", "--bld", "-b",
                        dest="build",
                        type = str,
                        default = "build",
                        help = "Location of the build folder")
    parser.add_argument("--destination", "--dest", "-d",
                        dest="destination",
                        type = str,
                        default = os.curdir,
                        help = "Location, where to place the resulting package")
    parser.add_argument("--variant", "--var", "-v",
                        dest="variant",
                        type = str,
                        default = "source",
                        choices = ["binary+source",
                                   "binary",
                                   "source",
                                   ],
                        help = "Variant of build")
    parser.add_argument("--compression", "--comp", "-c",
                        dest="compression",
                        type = str,
                        default = "zlib",
                        choices = ["none",
                                   "zlib",
                                   "bzip2",
                                   "lzma",
                                   ],
                        help = "Package compression")
    parser.add_argument("--optimize", "--opt", "-o",
                        dest="optimize",
                        type = int,
                        default = 0,
                        choices = range(3),
                        help = "Location of the build folder")
    parser.add_argument("--gitargs", "-ga",
                        dest="gitargs",
                        type = str,
                        default = "",
                        help = "git arguments")
    args = parser.parse_args()

    if args.creator == "package":
        creator = CuraPackageCreator
    elif args.creator == "plugin":
        creator = CuraPluginCreator
    else:
        print("Unknown distribution!")
        sys.exit(0)
    creator = creator()

    # Getting the real paths
    args.source = creator.getSource(args.source)
    args.source = os.path.realpath(args.source)
    args.build = os.path.realpath(args.build)

    # Preparing the compression option
    if args.compression is "none":
        args.compression = zipfile.ZIP_STORED
    elif args.compression is "zlib":
        args.compression = zipfile.ZIP_DEFLATED
    elif args.compression is "bzip2":
        args.compression = zipfile.ZIP_BZIP2
    elif args.compression is "lzma":
        args.compression = zipfile.ZIP_LZMA
    else:
        print("Unknown compression format!")
        sys.exit(1)

    creator.generateDistribution(args)
