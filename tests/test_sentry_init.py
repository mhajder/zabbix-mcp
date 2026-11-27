import logging
import sys
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from zabbix_mcp.sentry_init import _data_collection
from zabbix_mcp.sentry_init import init_sentry


@pytest.fixture
def fake_sentry(monkeypatch):
    """A stand-in sentry_sdk, so the test records init() without sending anything."""
    sdk = MagicMock()
    logging_integration = MagicMock()
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
            "sentry_sdk.integrations.logging": logging_integration,
            "sentry_sdk.integrations.mcp": MagicMock(),
        },
    ):
        sdk.init.logging_integration = logging_integration.LoggingIntegration
        yield sdk.init


def test_sentry_sends_no_pii_unless_asked(fake_sentry):
    """Setting only SENTRY_DSN shipped tool arguments and results to a third
    party without anyone opting in."""
    assert init_sentry() is True
    collection = fake_sentry.call_args.kwargs["data_collection"]
    assert collection["mcp"] == {"inputs": False, "outputs": False}
    assert collection["gen_ai"] == {"inputs": False, "outputs": False}
    assert collection["user_info"] is False
    # Over the HTTP transports, incoming bodies are MCP calls with tool
    # arguments.
    assert collection["http_bodies"] == []
    # A tool's arguments are locals of the frame that raised.
    assert collection["stack_frame_variables"] is False
    assert collection["cookies"] == {"mode": "off"}
    assert "send_default_pii" not in fake_sentry.call_args.kwargs


def test_sentry_pii_can_still_be_opted_into(fake_sentry, monkeypatch):
    """Opting in keeps the SDK defaults, except that secret-looking frame
    locals are still filtered."""
    monkeypatch.setenv("SENTRY_SEND_DEFAULT_PII", "true")
    assert init_sentry() is True
    assert fake_sentry.call_args.kwargs["data_collection"] == {
        "stack_frame_variables": {"mode": "denylist", "terms": []}
    }


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
    # With PII on, logs would default to on, so this proves the explicit
    # setting wins.
    monkeypatch.setenv("SENTRY_SEND_DEFAULT_PII", "true")
    monkeypatch.setenv("SENTRY_ENABLE_LOGS", "false")

    assert init_sentry() is True

    kwargs = fake_sentry.call_args.kwargs
    assert kwargs["dsn"] == "https://key@example.invalid/1"
    assert kwargs["traces_sample_rate"] == 0.25
    assert kwargs["environment"] == "staging"
    assert kwargs["profile_session_sample_rate"] == 0.0
    assert kwargs["profile_lifecycle"] == "manual"
    assert "enable_logs" not in kwargs
    fake_sentry.logging_integration.assert_called_once_with(
        level=None, event_level=logging.ERROR
    )


def test_logging_integration_is_enabled_by_default(fake_sentry):
    """sentry-sdk 3.x stopped enabling it on its own; without it logged errors
    never reach Sentry."""
    assert init_sentry() is True
    fake_sentry.logging_integration.assert_called_once()
    assert fake_sentry.logging_integration.call_args.kwargs["event_level"] == (
        logging.ERROR
    )
    assert (
        fake_sentry.logging_integration.return_value
        in fake_sentry.call_args.kwargs["integrations"]
    )


@pytest.mark.parametrize(
    ("pii", "logs", "expected_level"),
    [
        # Log lines can name hosts and items, so they follow the PII choice...
        (None, None, None),
        ("true", None, logging.INFO),
        # ...unless SENTRY_ENABLE_LOGS says otherwise.
        (None, "true", logging.INFO),
        ("true", "false", None),
    ],
)
def test_sentry_logs_follow_the_pii_setting_by_default(
    fake_sentry, monkeypatch, pii, logs, expected_level
):
    if pii is not None:
        monkeypatch.setenv("SENTRY_SEND_DEFAULT_PII", pii)
    if logs is not None:
        monkeypatch.setenv("SENTRY_ENABLE_LOGS", logs)
    assert init_sentry() is True
    fake_sentry.logging_integration.assert_called_once_with(
        level=expected_level, event_level=logging.ERROR
    )


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


def test_profiling_is_off_by_default(fake_sentry):
    assert init_sentry() is True
    assert fake_sentry.call_args.kwargs["profile_session_sample_rate"] == 0.0


@pytest.mark.parametrize(
    "name", ["SENTRY_TRACES_SAMPLE_RATE", "SENTRY_PROFILE_SESSION_SAMPLE_RATE"]
)
@pytest.mark.parametrize("value", ["50", "-0.1", "1.01"])
def test_out_of_range_sample_rate_is_logged_not_raised(
    fake_sentry, monkeypatch, caplog, name, value
):
    """A rate of 50 meant as a percentage must not reach the SDK."""
    monkeypatch.setenv(name, value)
    assert init_sentry() is False
    fake_sentry.assert_not_called()
    assert f"{name} must be between 0.0 and 1.0" in caplog.text


@pytest.mark.parametrize("value", ["0", "1", "1.0"])
def test_sample_rate_bounds_are_accepted(fake_sentry, monkeypatch, value):
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", value)
    assert init_sentry() is True
    assert fake_sentry.call_args.kwargs["traces_sample_rate"] == float(value)


@pytest.mark.parametrize("send_default_pii", [False, True])
def test_data_collection_is_accepted_by_the_real_sdk(send_default_pii):
    """The other tests stub sentry_sdk, so a key or mode the SDK rejects would
    only surface at startup, leaving Sentry silently off."""
    sentry_sdk = pytest.importorskip("sentry_sdk")
    # No integrations: they patch libraries process-wide even without a DSN.
    client = sentry_sdk.Client(
        data_collection=_data_collection(send_default_pii),
        default_integrations=False,
        auto_enabling_integrations=False,
    )
    try:
        resolved = client.options["data_collection"]
    finally:
        client.close()
    assert resolved["mcp"]["inputs"] is send_default_pii
    if send_default_pii:
        assert resolved["stack_frame_variables"]["mode"] == "denylist"
    else:
        assert resolved["stack_frame_variables"] is False


def _capture_frame_vars(send_default_pii):
    """Raise inside a real client and return the raising frame's variables."""
    sentry_sdk = pytest.importorskip("sentry_sdk")
    events = []
    client = sentry_sdk.Client(
        dsn="https://key@example.invalid/1",
        data_collection=_data_collection(send_default_pii),
        default_integrations=False,
        auto_enabling_integrations=False,
        before_send=lambda event, _hint: events.append(event),
    )

    # The arguments are the frame locals under test.
    def create_host(host, zabbix_password):  # noqa: ARG001
        raise RuntimeError("boom")

    try:
        with sentry_sdk.isolation_scope() as scope:
            scope.set_client(client)
            try:
                create_host("web01", "hunter2")
            except RuntimeError:
                sentry_sdk.capture_exception()
    finally:
        client.close()
    return events[0]["exception"]["values"][0]["stacktrace"]["frames"][-1].get("vars")


def test_frame_variables_are_not_sent_without_pii():
    assert _capture_frame_vars(send_default_pii=False) is None


def test_secret_frame_variables_are_filtered_with_pii():
    """sentry-sdk 3.x sends frame locals unfiltered by default."""
    frame_vars = _capture_frame_vars(send_default_pii=True)
    assert frame_vars["host"] == "'web01'"
    assert "hunter2" not in str(frame_vars)
