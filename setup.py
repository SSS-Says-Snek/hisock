import pathlib
import re
from setuptools import setup

ROOT = pathlib.Path(__file__).parent  # pathlib.Path object of root (/hisock/)

README = (ROOT / "README.md").read_text()  # Reads README
NAME = "hisock"

CONSTANT_TXT = (ROOT / "hisock/constants.py").read_text()

VERSION = re.search('__version__ = "[^\n"]+"', CONSTANT_TXT).group()
VERSION = VERSION.lstrip('__version__ = "').rstrip('"')
ESCAPED_VERSION = re.escape(VERSION)


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


#########################
#      START BUILD      #
#########################

print(color_text(f"Building version {VERSION}...\n", "green"))

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
    subdir.replace("\\", ".").replace("/", ".") for subdir in stringified_ex_subdirs \
]
ex_subdirs = [i for i in ex_subdirs if i != "examples.__pycache__"]

print_ex_subdirs = "- " + "\n- ".join(ex_subdirs)
print(
    color_text(
        "[INFO] Collected the following examples modules:\n"
        f"{print_ex_subdirs}\n",
        "green",
    )
)

#########################
#      REQUIREMENTS     #
#########################

requirements = [line.strip() for line in (ROOT / "requirements.txt").read_text().splitlines()]
print_requirements = "- " + "\n- ".join(requirements)

print(
    color_text(
        "[INFO] Requirements necessary:\n"
        f"{print_requirements}\n",
        "green",
    )
)

#########################
#  REMOVE OLD VERSIONS  #
#########################

dist_subdir = (ROOT / "dist")
try:
    dist_subdir_items = list(dist_subdir.iterdir())
except FileNotFoundError:
    dist_subdir_items = []
    print(color_text("[INFO] dist doesn't exist!\n", "green"))

if dist_subdir.exists():
    if not dist_subdir_items:
        print(color_text("[INFO] Nothing in dist!", "green"))
    else:
        print(color_text(f"[INFO] Found {len(dist_subdir_items)} items, removing...", "green"))
        for old_build_files in dist_subdir.iterdir():
            if (
                    re.match(f"{NAME}-{ESCAPED_VERSION}\.tar\.gz", old_build_files.name)
                    or re.match(f"{NAME}-{ESCAPED_VERSION}-py3-none-any\.whl", old_build_files.name)
            ):
                print(
                    color_text(
                        f"[WARNING] Found file {old_build_files.name} with same version!\n"
                        "          "
                        "If you already pushed this file to PyPI, do NOT push the files being "
                        "generated right now.",
                        "yellow"
                    )
                )
            else:
                print(
                    color_text(
                        f"[INFO] Removing build file {old_build_files.name}...",
                        "green"
                    )
                )
            old_build_files.unlink()
    print()

#########################
#         SETUP         #
#########################

setup(
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
    ],
    install_requires=requirements,
    packages=[
                 "hisock",
                 "examples",
             ]
             + ex_subdirs,
    python_requires=">=3.7",
)

print(
    color_text(
        f"\nSuccessfully built {NAME} {VERSION}!",
        "green"
    )
)
