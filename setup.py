import pathlib
import os
import re
from setuptools import setup

ROOT = pathlib.Path(__file__).parent  # pathlib.Path object of root (/hisock/)

README = (ROOT / "README.md").read_text()  # Reads README
NAME = "hisock"

CONSTANT_TXT = (ROOT / "hisock/constants.py").read_text()

VERSION = re.search("__version__ = \"[^\n\"]+\"", CONSTANT_TXT).group()
VERSION = VERSION.lstrip("__version__ = \"").rstrip("\"")


class ANSIColors:
    PINK = '\033[95m'
    PURPLE = '\033[35m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    DARK_GREEN = '\033[32m'
    YELLOW = '\033[93m'
    DARK_YELLOW = '\033[33m'
    RED = '\033[91m'
    DARK_RED = '\033[31m'
    END = '\033[0m'

    FONTCHANGE_BOLD = '\033[1m'
    FONTCHANGE_UNDERLINE = '\033[4m'


def color_text(txt, color=None, font_changes=None):
    """I copied this from... my own code -.-"""
    return f"""{f'{getattr(ANSIColors, color.upper().replace(" ", "_"))}' if color is not None else ''}{f'{getattr(ANSIColors, f"FONTCHANGE_{font_changes.upper()}")}' if font_changes is not None else ''}{txt}{f'{ANSIColors.END * sum([bool(i) for i in [color, font_changes]])}'}"""


print(color_text(f"Building version {VERSION}...", "green"))

raw_ex_subdirs = [
    content.relative_to(ROOT) for content in (ROOT / "examples").iterdir()
]
stringified_ex_subdirs = list(
    map(
        str, list(filter(pathlib.Path.is_dir, raw_ex_subdirs))
    )
)
ex_subdirs = [
    subdir.replace('\\', '.').replace('/', '.') for subdir in stringified_ex_subdirs
]

print_ex_subdirs = "- " + "\n- ".join(ex_subdirs)
print(
    color_text("[INFO] Collected the following examples modules:\n"
               f"{print_ex_subdirs}", "green")
)

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
        "Programming Language :: Python :: 3.9"
    ],
    install_requires=[
        "pytest>=6.2.5",
        "pycryptodome>=3.11"
    ],
    packages=[
        'hisock',
        'examples',
    ] + ex_subdirs,
    python_requires=">=3.7"
)

if os.path.exists("dist"):
    for i in os.listdir("dist"):
        if not (
                re.match(f"{NAME}-{VERSION}\.tar\.gz", i) or
                re.match(f"{NAME}-{VERSION}-py3-none-any\.whl", i)
        ):
            print(color_text(f"Removing old version {i}...", "red"))
            os.remove(os.path.join("dist", i))
