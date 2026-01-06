import pytest

from zabbix_mcp.utils import parse_bool


@pytest.mark.parametrize(
    "val,default,expected",
    [
        (None, True, True),
        (None, False, False),
        ("1", False, True),
        ("true", False, True),
        ("yes", False, True),
        ("on", False, True),
        ("TrUe", False, True),
        ("YES", False, True),
        ("ON", False, True),
        ("1 ", False, True),
        ("0", True, False),
        ("false", True, False),
        ("no", True, False),
        ("off", True, False),
        ("", True, False),
        ("random", True, False),
        ("  ", True, False),
        ("False", True, False),
    ],
)
def test_parse_bool(val, default, expected):
    assert parse_bool(val, default) is expected
