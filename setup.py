"""
This python script will generate hisock eggs and wheels for upload to PyPI.
Just call `python setup.py sdist bdist_wheel` to generate.

====================================
Copyright SSS_Says_Snek, 2021-present
====================================
"""
import os
import sys
import datetime
import shutil
import pathlib
import re
import subprocess
from distutils.core import Command
from setuptools import setup

ROOT = pathlib.Path(__file__).parent  # pathlib.Path object of root (/hisock/)
DIST = ROOT / "dist"

README = (ROOT / "README.md").read_text()  # Reads README
NAME = "hisock"

CONSTANT_TXT = (ROOT / "hisock/constants.py").read_text()

VERSION = re.search('__version__ = "[^\n"]+"', CONSTANT_TXT).group()
VERSION = VERSION.lstrip('__version__ = "').rstrip('"')
ESCAPED_VERSION = re.escape(VERSION)

custom_cmds = {}


class ANSIColors:
    PINK = "\033[95m"
    PURPLE = "\033[35m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    DARK_GREEN = "\033[32m"
    YELLOW = "\033[93m"
    DARK_YELLOW = "\033[33m"
    RED = "\033[91m"
    DARK_RED = "\033[31m"
    END = "\033[0m"

    FONTCHANGE_BOLD = "\033[1m"
    FONTCHANGE_UNDERLINE = "\033[4m"


def color_text(txt, color=None, font_changes=None):
    """I copied this from... my own code -.-"""
    return f"""{f'{getattr(ANSIColors, color.upper().replace(" ", "_"))}' if color is not None else ''}{f'{getattr(ANSIColors, f"FONTCHANGE_{font_changes.upper()}")}' if font_changes is not None else ''}{txt}{f'{ANSIColors.END * sum([bool(i) for i in [color, font_changes]])}'}"""


def add_command(name):
    def internal(custom_cmd):
        custom_cmds[name] = custom_cmd

    return internal


def clear_directory(directory: pathlib.Path):
    if not directory.exists():
        print(color_text(f'[INFO] directory "{directory}" does not exist', "green"))
        return

    for path in directory.iterdir():
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


#########################
#   CUSTOM BUILD CMDS   #
#########################


@add_command("test")
class TestCmd(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        print(
            color_text(
                f"\n[COMMAND] Running hisock tests..."
                f"\n          Using Python: {sys.executable}\n",
                "green",
            )
        )

        try:
            return subprocess.run([sys.executable, "-m", "pytest"])
        except subprocess.CalledProcessError:
            print(color_text("Did you install pytest on this python version?", "red"))


@add_command("clean")
class CleanCmd(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        print(color_text("\n[COMMAND] Cleaning dist and build directories...", "green"))

        build_dir = ROOT / "build"

        clear_directory(build_dir)
        clear_directory(DIST)


@add_command("format")
class FormatCmd(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        print(
            color_text(
                f"\n[COMMAND] Recursively formatting root directory..."
                f"\n          Using Python: {sys.executable}\n",
                "green",
            )
        )
        try:
            return subprocess.run([sys.executable, "-m", "black", ROOT])
        except subprocess.CalledProcessError:
            print(color_text("Did you install black on this python version?", "red"))


num_nonbuild_cmds = sum([i in list(custom_cmds) for i in sys.argv[1:]])
no_build = num_nonbuild_cmds == len(sys.argv[1:])

#########################
#      START BUILD      #
#########################

if num_nonbuild_cmds == 0:
    print(color_text(f"Building hisock version {VERSION}...\n", "green"))
elif num_nonbuild_cmds != len(sys.argv[1:]):
    print(
        color_text(
            f"Building hisock version {VERSION}, then running non-build commands...\n",
            "green",
        )
    )
else:
    print(color_text("Running non-build commands...\n", "green"))

    setup(cmdclass=custom_cmds)
    sys.exit()

#########################
#   EXAMPLE SUBMODULES  #
#########################

raw_ex_subdirs = [
    content.relative_to(ROOT) for content in (ROOT / "examples").iterdir()
]
stringified_ex_subdirs = list(
    map(str, list(filter(pathlib.Path.is_dir, raw_ex_subdirs)))
)
ex_subdirs = [
    subdir.replace("\\", ".").replace("/", ".") for subdir in stringified_ex_subdirs
]
ex_subdirs = [i for i in ex_subdirs if i != "examples.__pycache__"]

print_ex_subdirs = "- " + "\n- ".join(ex_subdirs)
print(
    color_text(
        "[INFO] Collected the following examples modules:\n" f"{print_ex_subdirs}\n",
        "green",
    )
)

#########################
#      REQUIREMENTS     #
#########################

requirements = [
    line.strip() for line in (ROOT / "requirements.txt").read_text().splitlines()
]
requirements_dev = [
    line.strip()
    for line in (ROOT / "requirements_contrib.txt").read_text().splitlines()
]
print_requirements = "- " + "\n- ".join(requirements)
print_requirements_dev = "- " + "\n- ".join(requirements_dev)

print(
    color_text(
        f"[INFO] Requirements necessary:\n{print_requirements}\n",
        "green",
    )
)

print(
    color_text(f"[INFO] Developer requirements:\n{print_requirements_dev}\n", "green")
)

#########################
#  REMOVE OLD VERSIONS  #
#########################

yes_to_all = False

try:
    dist_subdir_items = list(DIST.iterdir())
except FileNotFoundError:
    dist_subdir_items = []
    print(color_text("[INFO] dist doesn't exist!\n", "green"))

if DIST.exists():
    if not dist_subdir_items:
        print(color_text("[INFO] Nothing in dist!", "green"))
    else:
        print(
            color_text(
                f"[INFO] Found {len(dist_subdir_items)} items in dist, removing...",
                "green",
            )
        )
        for old_build_file in DIST.iterdir():
            if not yes_to_all and VERSION in str(old_build_file):
                build_file_stats = old_build_file.stat()
                file_create_time = datetime.datetime.fromtimestamp(
                    build_file_stats.st_ctime
                )
                file_create_time_days = (
                    datetime.datetime.now() - file_create_time
                ).days

                indentation = "          "

                print(
                    color_text(
                        f"\n[WARNING] Found file {old_build_file.name} with same version!"
                        f"\n{indentation}"
                        "If you already pushed this file to PyPI, do NOT push the files being "
                        f"generated right now.\n\n{indentation}File Info:\n{indentation}"
                        f"  - Creation time: {file_create_time:%a %b %d %Y, %I:%M:%S %p} "
                        f"({file_create_time_days} days ago)\n{indentation}"
                        f"  - Size: {build_file_stats.st_size} bytes",
                        "yellow",
                    )
                )

                try:
                    continue_building = input(
                        color_text(
                            "Do you want to continue? ([Y]es, [N]o, [A]ll - yes to all) ",
                            "red",
                        )
                    ).lower()
                except EOFError:  # Pip install - DO NOT REMOVE THIS
                    break

                if continue_building == "n":
                    sys.exit()
                elif continue_building == "a":
                    yes_to_all = True

            print(
                color_text(
                    f"[INFO] Removing build file {old_build_file.name}...", "green"
                )
            )
            old_build_file.unlink()
    print()

#########################
#         SETUP         #
#########################

setup(
    cmdclass=custom_cmds,
    name=NAME,
    version=VERSION,
    description="A higher-level extension of the socket module, with simpler and more efficient usages",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/SSS-Says-Snek/hisock",
    author="SSS-Says-Snek",
    author_email="bmcomis2018@gmail.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    install_requires=requirements,
    packages=[
        "hisock",
        "examples",
    ]
    + ex_subdirs,
    python_requires=">=3.7",
)

print(color_text(f"\nSuccessfully built {NAME} {VERSION}!", "green"))

if DIST.exists() and not any(DIST.iterdir()):
    print(color_text("- No build files generated!", "green"))
