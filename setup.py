import os
from setuptools import setup

VERSION = "2.0.0"

REQUIRES = [
    "cryptography",
    "docopt",
    "pyyaml",
    "requests",
]

TESTS_REQUIRE = [
    "nox",
    "pytest",
    "pytest-cover",
]

here = os.path.abspath(os.path.dirname(__file__))
try:
    README = open(os.path.join(here, "README.md")).read()
except IOError:
    README = CHANGES = ""

setup(
    name="droplets",
    version=VERSION,
    description="Library for building Ansible dynamic inventories for Digital Ocean.",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Chris Rossi",
    author_email="chris@christophermrossi.com",
    url="http://github.com/chrisrossi/droplets",
    license="BSD-derived (http://www.repoze.org/LICENSE.txt)",
    classifiers=[
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "License :: Repoze Public License",
    ],
    install_requires=REQUIRES,
    extras_require={
        "testing": TESTS_REQUIRE,
    },
    entry_points={
        "console_scripts": [
            "secrets = droplets.secrets:secrets_cli",
        ]
    },
)
