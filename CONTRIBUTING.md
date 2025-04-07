To get started contributing to this project, you'll first need to set up your development environment.

```
git clone https://github.com/ChainAccelOrg/audit-repo-cloner.git
cd audit-repo-cloner
python3 -m venv venv
source venv/bin/activate
```

We set up a virtual environment so that packages you install get installed to an isolated location (the `venv` folder we just created). If you want to exit this virtual environment, you can run `deactivate`.

Then, install the development dependencies.

```
pip install -r requirements.txt
```

### Optional

You can also install the package in editable mode.

```
pip install -e .
```

The `pip install -e .` command installs our package in "editable" mode. This means that any changes you make to the code will be reflected in the package you import in your own code.

This would be if you want to run make changes and test them out on your own code in another project.

# Pre-commit

This project uses pre-commit to ensure code quality. After installing the requirements, you can set up pre-commit with:

```bash
pre-commit install
```

This will install the git hooks that run the linters and formatters before each commit.

To run pre-commit on all files (recommended for initial setup):

```bash
pre-commit run --all-files
```

Note: By default, `pre-commit run` without `--all-files` only checks staged files. If you see "no files to check", either:
1. Stage your files with `git add .` before running pre-commit, or
2. Use `pre-commit run --all-files` to check all files regardless of staging status

# Tests

## Unit Tests

```bash
pytest
```

## Integration Tests

TODO

## All tests

TODO

# Upload to PyPI (For most contributors)

Once the package is ready, do the following:

1. Update the `__version__` in `__version__.py`
2. Cut a release in the GitHub UI with the same version as what's in `__version__.py`

The github actions should then automatically push it to PyPI.

# Uploading to PyPI (Manual)

_For maintainers only. You can view the [docs](https://packaging.python.org/en/latest/tutorials/packaging-projects/#generating-distribution-archives) to learn more._

_Note: `setup.py sdist` is deprecated. Use `python3 -m build` instead._

```
python3 -m build
python3 -m twine upload dist/*
```

Right now, we have our GitHub actions setup so that every release we push we automatically upload to PyPI.
