"""Wires the recipes up to the mock API from the python-sdk repo.

The mock lives in python-sdk/tests because that repo is the reference
implementation of the API contract — one definition of what the server does,
used by the SDK suites and by these recipe tests, so the two can never drift
from each other.

Point at it with --sdk-path (default: ../python-sdk, the side-by-side layout):

    pytest
    pytest --sdk-path /elsewhere/python-sdk
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

DEFAULT_SDK = Path(__file__).resolve().parents[2] / "python-sdk"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--sdk-path",
        default=str(DEFAULT_SDK),
        help="path to the python-sdk checkout that provides tests/mock_api.py",
    )


def pytest_configure(config: pytest.Config) -> None:
    sdk = Path(config.getoption("--sdk-path")).resolve()
    mock = sdk / "tests" / "mock_api.py"
    src = sdk / "src"
    if not mock.exists():
        pytest.exit(
            f"cannot find {mock}.\n"
            "These tests run the recipes against the API mock from the python-sdk "
            "repo. Clone it beside this one, or pass --sdk-path.",
            returncode=4,
        )
    # For this process (to import MockAPI) and for the recipe subprocesses
    # (so `import speechrevolutions` resolves to the local SDK, not a release).
    sys.path.insert(0, str(sdk / "tests"))
    sys.path.insert(0, str(src))
    os.environ["SR_SDK_SRC"] = str(src)


@pytest.fixture
def api():
    from mock_api import MockAPI

    with MockAPI(progress_steps=2) as a:
        yield a
