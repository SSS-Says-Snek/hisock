import pathlib
import os
import re
from setuptools import setup

ROOT = pathlib.Path(__file__).parent  # pathlib.Path object of root (/hisock/)

README = (ROOT / "README.md").read_text()  # Reads README
VERSION = "0.2"
NAME = "hisock"

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
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9"
    ],
    install_requires=[
        "pytest>=6.2.5",
        "cryptography>=3.4.8"
    ],
    packages=[
        'hisock',
        'examples',
    ],
    python_requires=">=3.6"
)

for i in os.listdir("dist"):
    if not (
            re.match(f"{NAME}-{VERSION}\.tar\.gz", i) or
            re.match(f"{NAME}-{VERSION}-py3-none-any\.whl", i)
    ):
        print(f"Removing old version {i}...")
        os.remove(os.path.join("dist", i))
