from setuptools import setup
import os
import sys

CURRENT_PYTHON = sys.version_info[:2]
REQUIRED_PYTHON = (3, 7)

if CURRENT_PYTHON < REQUIRED_PYTHON:
    sys.stderr.write(
        """
==========================
Unsupported Python versionw
==========================
This version of Requests requires at least Python {}.{}, but
you're trying to install it on Python {}.{}. To resolve this,
consider upgrading to a supported Python version.
""".format(
            *(REQUIRED_PYTHON + CURRENT_PYTHON)
        )
    )
    sys.exit(1)


here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.md"), "r") as f:
    readme = f.read()

about = {}
with open(os.path.join(here, "audit_repo_clone_test", "__version__.py"), "r") as f:
    exec(f.read(), about)

setup(
    name=about["__title__"],
    version=about["__version__"],
    author=about["__author__"],
    license=about["__license__"],
    install_requires=[
        "certifi",
        "cffi",
        "charset-normalizer",
        "click",
        "cryptography",
        "Deprecated",
        "exceptiongroup",
        "idna",
        "iniconfig",
        "numpy",
        "packaging",
        "pandocfilters",
        "pluggy",
        "pyasn1",
        "pycparser",
        "PyGithub",
        "PyJWT",
        "PyNaCl",
        "pytest",
        "python-dotenv",
        "PyYAML",
        "requests",
        "rsa",
        "tomli",
        "urllib3",
        "wrapt"
    ],
    packages=[about["__title__"]],
    python_requires=">=3.7, <4",
    url="https://github.com/bensacc/audit-repo-cloner.git",
    long_description=readme,
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    entry_points={
        "console_scripts": [
            "audit_repo_clone_test = audit_repo_clone_test:create_audit_repo",
        ],
    },
)
