from __future__ import annotations

import pytest


def test_hermes_clawrouter_version(capsys):
    from clawrouter_hermes import cli

    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith("hermes-plugin-clawrouter ")
