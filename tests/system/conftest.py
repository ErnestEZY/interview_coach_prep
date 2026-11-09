"""Command-line options for the live-app system suite.

pytest calls ``pytest_addoption`` on plugins and conftest modules only. The hook
used to sit in ``test_system.py``, where it was never invoked, so the
``--system-base-url`` flag advertised in that file's docstring was rejected by
pytest as an unrecognized argument. Declaring it here makes both documented
run commands work.
"""


def pytest_addoption(parser):
    parser.addoption(
        "--system-base-url",
        default=None,
        help="Base URL of the running ICP server for system tests",
    )
