"""Unit tests for telemetry message handling. No network connections."""

import importlib.util
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def bridge(monkeypatch):
    """Load the bridge with fake settings, without calling main()."""
    monkeypatch.setenv("LOCAL_BROKER_HOST", "localhost")
    monkeypatch.setenv("LOCAL_BROKER_PORT", "1883")
    monkeypatch.setenv("DRONE_SN", "TEST_DRONE")
    monkeypatch.setenv("LOCAL_PUBLISH_TOPIC", "test/telemetry")

    path = (Path(__file__).resolve().parents[1] / "services/telemetry-bridge/telemetry_bridge.py")
    spec = importlib.util.spec_from_file_location("bridge_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


@pytest.fixture
def client(bridge):
    """Fake MQTT client that records calls instead of sending messages."""
    fake = Mock()
    fake.publish.return_value.rc = bridge.mqtt.MQTT_ERR_SUCCESS
    return fake


def send_message(bridge, client, envelope):
    """Convert a Python value into an incoming JSON message."""
    message = SimpleNamespace(
        payload=json.dumps(envelope).encode("utf-8")
    )
    bridge.on_message(client, None, message)


def test_successful_connection_subscribes(bridge, client):
    bridge.on_connect(client, None, {}, 0)

    client.subscribe.assert_called_once_with(
        "thing/product/TEST_DRONE/osd", qos=0
    )


def test_failed_connection_does_not_subscribe(bridge, client):
    bridge.on_connect(client, None, {}, 5)

    client.subscribe.assert_not_called()


def test_valid_message_is_forwarded(bridge, client):
    data = {
        "latitude": -33.86,
        "longitude": 151.21,
        "height": 50,
        "elevation": 80,
        "horizontal_speed": 5,
        "vertical_speed": -1,
        "attitude_head": 90,
        "attitude_pitch": 2,
        "attitude_roll": -3,
        "mode_code": 1,
        "position_state": 4,
    }

    send_message(bridge, client, {
        "timestamp": 123456789,
        "data": data,
    })

    client.publish.assert_called_once()
    args, kwargs = client.publish.call_args

    assert args[0] == "test/telemetry"
    assert kwargs == {"qos": 0, "retain": False}
    assert json.loads(args[1]) == {
        "timestamp": 123456789,
        "drone_sn": "TEST_DRONE",
        **data,
    }


@pytest.mark.parametrize("payload", [
    b"not valid json",
    b'{"data":',
    b"",
    b"\xff",
])
def test_invalid_payload_is_ignored(bridge, client, payload):
    bridge.on_message(client, None, SimpleNamespace(payload=payload))

    client.publish.assert_not_called()


@pytest.mark.parametrize("data", [
    {},
    {"latitude": 10},
    {"longitude": 20},
    {"latitude": None, "longitude": 20},
    {"latitude": 10, "longitude": None},
    {"latitude": 0, "longitude": 0},
])
def test_missing_coordinates_or_no_fix_are_ignored(bridge, client, data):
    send_message(bridge, client, {"data": data})

    client.publish.assert_not_called()


@pytest.mark.parametrize("latitude,longitude", [
    (0, 20),       # Equator: one zero coordinate is valid.
    (10, 0),       # Prime meridian.
    (90, 180),     # Upper geographic boundaries.
    (-90, -180),   # Lower geographic boundaries.
])
def test_valid_coordinate_boundaries(bridge, client, latitude, longitude):
    send_message(bridge, client, {
        "data": {"latitude": latitude, "longitude": longitude}
    })

    client.publish.assert_called_once()
    output = json.loads(client.publish.call_args.args[1])
    assert output["latitude"] == latitude
    assert output["longitude"] == longitude


def test_missing_optional_fields_become_null(bridge, client):
    send_message(bridge, client, {
        "data": {"latitude": 10, "longitude": 20}
    })

    client.publish.assert_called_once()
    output = json.loads(client.publish.call_args.args[1])

    optional_fields = [
        "timestamp", "height", "elevation",
        "horizontal_speed", "vertical_speed",
        "attitude_head", "attitude_pitch", "attitude_roll",
        "mode_code", "position_state",
    ]
    for field in optional_fields:
        assert field in output
        assert output[field] is None


def test_publish_failure_is_logged(bridge, client, caplog):
    client.publish.return_value.rc = bridge.mqtt.MQTT_ERR_NO_CONN

    with caplog.at_level(logging.WARNING):
        send_message(bridge, client, {
            "data": {"latitude": 10, "longitude": 20}
        })

    assert "Publish failed" in caplog.text


# These tests describe desired rejection of malformed messages.
# The current bridge lacks these checks, so failures reveal real bugs.

@pytest.mark.parametrize("envelope", [
    [],
    None,
    {"data": None},
    {"data": []},
])
def test_invalid_message_structure_is_ignored(bridge, client, envelope):
    send_message(bridge, client, envelope)

    client.publish.assert_not_called()


@pytest.mark.parametrize("latitude,longitude", [
    ("invalid", 20),
    (10, "invalid"),
    (True, 20),
    (91, 20),
    (-91, 20),
    (10, 181),
    (10, -181),
])
def test_invalid_coordinates_are_rejected(bridge, client, latitude, longitude):
    send_message(bridge, client, {
        "data": {"latitude": latitude, "longitude": longitude}
    })

    client.publish.assert_not_called()