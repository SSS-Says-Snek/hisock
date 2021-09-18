import pathlib
from setuptools import setup

ROOT = pathlib.Path(__file__).parent

README = (ROOT / "README.md").read_text()

setup(
    name="hisock",
    version="0.0.1.post7",
    description="A higher-level extension of the socket module, with simpler and more efficient usages",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/SSS-Says-Snek/hisock",
    author="SSS-Says-Snek",
    author_email="bmcomi2018@gmail.com",
    license="MIT",
    install_requires=[
        "pytest>=6.2.5",
        "cryptography>=3.4.8"
    ],
    packages=[
        'hisock'
    ]
)
