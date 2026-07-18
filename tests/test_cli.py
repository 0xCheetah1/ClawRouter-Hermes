from __future__ import annotations

import tomllib
from importlib import metadata
from pathlib import Path

import pytest

from clawrouter_hermes import _VERSION, cli

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_hermes_clawrouter_version(capsys):
    try:
        expected = metadata.version(cli._DIST_NAME)
    except metadata.PackageNotFoundError:
        expected = _VERSION

    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"hermes-plugin-clawrouter {expected}"


def test_dist_name_matches_pyproject():
    """Guard the name ``cli.main`` hands to ``metadata.version``.

    A typo there is invisible to the test above: it raises
    ``PackageNotFoundError``, falls through to the ``_VERSION`` fallback, and
    prints a correct-looking string for the wrong reason. Comparing against
    ``pyproject.toml`` catches it regardless of what is installed.
    """
    if not _PYPROJECT.is_file():
        pytest.skip("running outside a source checkout")

    project = tomllib.loads(_PYPROJECT.read_text())["project"]
    assert cli._DIST_NAME == project["name"]
    assert _VERSION == project["version"], (
        "clawrouter_hermes._VERSION has drifted from pyproject.toml"
    )
