import os
import sys

from setuptools import setup

CURRENT_PYTHON = sys.version_info[:2]
REQUIRED_PYTHON = (3, 7)

if CURRENT_PYTHON < REQUIRED_PYTHON:
    sys.stderr.write(
        """
==========================
Unsupported Python version
==========================
This version of audit-repo-cloner requires at least Python {}.{}, but
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
with open(os.path.join(here, "audit_repo_cloner", "__version__.py"), "r") as f:
    exec(f.read(), about)

setup(
    name=about["__title__"],
    version=about["__version__"],
    author=about["__author__"],
    license=about["__license__"],
    install_requires=["certifi", "cffi", "charset-normalizer", "click", "cryptography", "Deprecated", "exceptiongroup", "gql", "idna", "packaging", "pyasn1", "pycparser", "PyGithub", "PyJWT", "PyNaCl", "python-dotenv", "PyYAML", "requests", "requests-toolbelt", "rsa", "tomli", "urllib3", "wrapt"],
    packages=[about["__title__"]],
    python_requires=">=3.7, <4",
    url="https://github.com/Cyfrin/audit-repo-cloner",
    long_description=readme,
    long_description_content_type="text/markdown",
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    entry_points={
        "console_scripts": [
            "audit_repo_cloner = audit_repo_cloner:create_audit_repo",
        ],
    },
)
