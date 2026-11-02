import sys
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from zabbix_mcp.sentry_init import init_sentry


@pytest.fixture
def fake_sentry(monkeypatch):
    """A stand-in sentry_sdk, so the test records init() without sending anything."""
    sdk = MagicMock()
    monkeypatch.setenv("SENTRY_DSN", "https://key@example.invalid/1")
    for name in (
        "SENTRY_SEND_DEFAULT_PII",
        "SENTRY_TRACES_SAMPLE_RATE",
        "SENTRY_ENVIRONMENT",
        "SENTRY_RELEASE",
        "SENTRY_PROFILE_SESSION_SAMPLE_RATE",
        "SENTRY_PROFILE_LIFECYCLE",
        "SENTRY_ENABLE_LOGS",
    ):
        monkeypatch.delenv(name, raising=False)
    with patch.dict(
        sys.modules,
        {
            "sentry_sdk": sdk,
            "sentry_sdk.integrations": MagicMock(),
            "sentry_sdk.integrations.mcp": MagicMock(),
        },
    ):
        yield sdk.init


def test_sentry_sends_no_pii_unless_asked(fake_sentry):
    """Setting only SENTRY_DSN shipped tool arguments and results to a third
    party without anyone opting in."""
    assert init_sentry() is True
    assert fake_sentry.call_args.kwargs["send_default_pii"] is False


def test_sentry_pii_can_still_be_opted_into(fake_sentry, monkeypatch):
    monkeypatch.setenv("SENTRY_SEND_DEFAULT_PII", "true")
    assert init_sentry() is True
    assert fake_sentry.call_args.kwargs["send_default_pii"] is True


@pytest.mark.parametrize("value", [None, "", "   "])
def test_unset_or_blank_dsn_leaves_sentry_off(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("SENTRY_DSN", raising=False)
    else:
        monkeypatch.setenv("SENTRY_DSN", value)
    assert init_sentry() is False


def test_missing_sentry_sdk_warns_and_stays_off(monkeypatch, caplog):
    monkeypatch.setenv("SENTRY_DSN", "https://key@example.invalid/1")
    # A None entry makes the import raise ImportError.
    with patch.dict(sys.modules, {"sentry_sdk": None}):
        assert init_sentry() is False
    assert "Sentry SDK not installed" in caplog.text


def test_settings_are_read_from_the_environment(fake_sentry, monkeypatch):
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.25")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", " staging ")
    monkeypatch.setenv("SENTRY_PROFILE_SESSION_SAMPLE_RATE", "0")
    monkeypatch.setenv("SENTRY_PROFILE_LIFECYCLE", "manual")
    monkeypatch.setenv("SENTRY_ENABLE_LOGS", "false")

    assert init_sentry() is True

    kwargs = fake_sentry.call_args.kwargs
    assert kwargs["dsn"] == "https://key@example.invalid/1"
    assert kwargs["traces_sample_rate"] == 0.25
    assert kwargs["environment"] == "staging"
    assert kwargs["profile_session_sample_rate"] == 0.0
    assert kwargs["profile_lifecycle"] == "manual"
    assert kwargs["enable_logs"] is False


@pytest.mark.parametrize("value", [None, "trace", "all", "continuation"])
def test_unknown_profile_lifecycle_means_trace(fake_sentry, monkeypatch, value):
    """sentry_sdk only accepts 'manual' and 'trace'."""
    if value is None:
        monkeypatch.delenv("SENTRY_PROFILE_LIFECYCLE", raising=False)
    else:
        monkeypatch.setenv("SENTRY_PROFILE_LIFECYCLE", value)
    init_sentry()
    assert fake_sentry.call_args.kwargs["profile_lifecycle"] == "trace"


def test_explicit_release_is_used(fake_sentry, monkeypatch):
    monkeypatch.setenv("SENTRY_RELEASE", "1.2.3")
    init_sentry()
    assert fake_sentry.call_args.kwargs["release"] == "1.2.3"


def test_release_defaults_to_the_installed_package_version(fake_sentry, monkeypatch):
    import importlib.metadata

    monkeypatch.delenv("SENTRY_RELEASE", raising=False)
    init_sentry()
    assert fake_sentry.call_args.kwargs["release"] == importlib.metadata.version(
        "zabbix-mcp"
    )


def test_release_is_none_when_the_package_is_not_installed(fake_sentry, monkeypatch):
    import importlib.metadata

    def missing(_name):
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.delenv("SENTRY_RELEASE", raising=False)
    monkeypatch.setattr(importlib.metadata, "version", missing)
    init_sentry()
    assert fake_sentry.call_args.kwargs["release"] is None


def test_init_failure_is_logged_not_raised(fake_sentry, caplog):
    fake_sentry.side_effect = RuntimeError("bad dsn")
    assert init_sentry() is False
    assert "Failed to initialize Sentry: bad dsn" in caplog.text


def test_bad_sample_rate_is_logged_not_raised(fake_sentry, monkeypatch, caplog):
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "half")
    assert init_sentry() is False
    assert "SENTRY_TRACES_SAMPLE_RATE must be a number" in caplog.text
    fake_sentry.assert_not_called()
