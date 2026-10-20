"""Unit tests for the stage-1 flight-command receiver.

All MQTT connections are mocked. No commands reach a broker or drone.
"""

import importlib.util
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def bridge(monkeypatch):
    """Load the module with test settings without running main()."""
    monkeypatch.setenv("MQTT_HOST", "localhost")
    monkeypatch.setenv("MQTT_PORT", "1883")

    # Change this path if your source file is somewhere else.
    path = (
        Path(__file__).resolve().parents[1]
        / "services/flight-command-bridge/bridge.py"
    )

    spec = importlib.util.spec_from_file_location("flight_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client():
    """Fake client that records calls without using the network."""
    return Mock()


def test_successful_connection_subscribes(bridge, client):
    reason = SimpleNamespace(is_failure=False)

    bridge.on_connect(client, None, None, reason, None)

    client.subscribe.assert_called_once_with("dock/dock1/flight", qos=0)


def test_failed_connection_does_not_subscribe(bridge, client, caplog):
    reason = SimpleNamespace(is_failure=True)

    with caplog.at_level(logging.ERROR, logger="flight-command-bridge"):
        bridge.on_connect(client, None, None, reason, None)

    client.subscribe.assert_not_called()
    assert "MQTT connect failed" in caplog.text


def test_reconnection_subscribes_again(bridge, client):
    reason = SimpleNamespace(is_failure=False)

    bridge.on_connect(client, None, None, reason, None)
    bridge.on_connect(client, None, None, reason, None)

    assert client.subscribe.call_count == 2
    client.subscribe.assert_called_with("dock/dock1/flight", qos=0)


def test_disconnect_is_logged(bridge, client, caplog):
    with caplog.at_level(logging.WARNING, logger="flight-command-bridge"):
        bridge.on_disconnect(client, None, None, "test disconnect", None)

    assert "MQTT disconnected" in caplog.text


@pytest.mark.parametrize("payload, expected", [
    (b'{"command":"takeoff"}', '{"command":"takeoff"}'),
    (b"not JSON", "not JSON"),
    (b"", ""),
    (b"\xff", "\ufffd"),
    ("سلام".encode("utf-8"), "سلام"),
])
def test_received_payload_is_logged(bridge, client, caplog, payload, expected):
    """Stage 1 logs all payloads, including malformed commands."""
    message = SimpleNamespace(payload=payload)

    with caplog.at_level(logging.INFO, logger="flight-command-bridge"):
        bridge.on_message(client, None, message)

    assert any(
        record.name == "flight-command-bridge"
        and record.getMessage() == f"RECEIVED {expected}"
        for record in caplog.records
    )

    # This stage must not forward commands.
    client.publish.assert_not_called()


def test_main_configures_client(bridge, client, monkeypatch):
    """Check startup settings without connecting to anything."""
    factory = Mock(return_value=client)
    monkeypatch.setattr(bridge.mqtt, "Client", factory)

    bridge.main()

    factory.assert_called_once_with(
        bridge.mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"flight-command-bridge-{bridge.os.getpid()}",
    )
    assert client.on_connect is bridge.on_connect
    assert client.on_disconnect is bridge.on_disconnect
    assert client.on_message is bridge.on_message

    client.reconnect_delay_set.assert_called_once_with(
        min_delay=1, max_delay=10
    )
    client.connect.assert_called_once_with(
        "localhost", 1883, keepalive=30
    )
    client.loop_forever.assert_called_once_with(
        retry_first_connection=True
    )


def test_main_retries_when_broker_is_unavailable(bridge, client, monkeypatch):
    """Fail twice, then connect; replace sleeping with a mock."""
    client.connect.side_effect = [
        OSError("Broker unavailable"),
        OSError("Broker unavailable"),
        None,
    ]

    monkeypatch.setattr(bridge.mqtt, "Client", Mock(return_value=client))
    sleep = Mock()
    monkeypatch.setattr(bridge.time, "sleep", sleep)

    bridge.main()

    assert client.connect.call_count == 3
    assert sleep.call_count == 2
    sleep.assert_called_with(3)
    client.loop_forever.assert_called_once_with(
        retry_first_connection=True
    )