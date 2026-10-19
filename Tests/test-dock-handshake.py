"""Dock-handshake unit tests. No network or config-method calls."""

import importlib.util
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def dock(monkeypatch):
    """Load the real module with test settings and block config."""
    settings = {
        "LOCAL_BROKER_HOST": "localhost",
        "LOCAL_BROKER_PORT": "1883",
        "DJI_APP_ID": "",
        "DJI_APP_KEY": "",
        "DJI_APP_LICENSE": "",
        "ORG_ID": "test-org",
        "ORG_NAME": "Test Organisation",
        "WORKSPACE_ID": "test-workspace",
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)

    # Locate the source inside services without assuming its subfolder.
    root = Path(__file__).resolve().parents[1]
    matches = list((root / "services").rglob("dock_handshake.py"))
    assert len(matches) == 1, (
        "Expected exactly one dock_handshake.py inside services."
    )

    spec = importlib.util.spec_from_file_location(
        "dock_under_test", matches[0]
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Prevent accidental execution of the real config handler.
    blocker = Mock(
        side_effect=lambda *args, **kwargs: pytest.fail(
            "The config handler must never be called."
        )
    )
    monkeypatch.setattr(module, "handle_config", blocker)
    monkeypatch.setitem(module.HANDLERS, "config", blocker)

    yield module

    blocker.assert_not_called()


@pytest.fixture
def client():
    """Record MQTT calls without connecting to a broker."""
    return Mock()


def send_request(dock, client, method, data):
    """Send a fake request through the real message-routing function."""
    request = {
        "tid": "test-tid",
        "bid": "test-bid",
        "method": method,
        "data": data,
    }
    message = SimpleNamespace(
        topic="thing/product/TEST_DOCK/requests",
        payload=json.dumps(request).encode("utf-8"),
    )
    dock.on_message(client, None, message)


def read_reply(client):
    """Check the reply destination and decode its JSON."""
    client.publish.assert_called_once()
    args, kwargs = client.publish.call_args

    assert args[0] == "thing/product/TEST_DOCK/requests_reply"
    assert kwargs == {"qos": 0}
    return json.loads(args[1])


def test_connection_subscribes(dock, client):
    dock.on_connect(client, None, {}, 0)

    client.subscribe.assert_called_once_with(
        "thing/product/+/requests", qos=0
    )


def test_failed_connection_does_not_subscribe(dock, client):
    dock.on_connect(client, None, {}, 5)

    client.subscribe.assert_not_called()


@pytest.mark.parametrize("devices", [
    [],
    [{"sn": "TEST_DRONE"}],
    [{"sn": "TEST_DRONE"}, {"sn": "TEST_DOCK"}],
    [{}],
])
def test_bind_status_reply(dock, client, monkeypatch, devices):
    """Check device entries, request IDs, and timestamp."""
    monkeypatch.setattr(dock.time, "time", lambda: 1000.0)

    send_request(
        dock, client, "airport_bind_status", {"devices": devices}
    )
    reply = read_reply(client)

    assert reply["tid"] == "test-tid"
    assert reply["bid"] == "test-bid"
    assert reply["method"] == "airport_bind_status"
    assert reply["timestamp"] == 1000000
    assert reply["data"]["result"] == 0

    expected = [
        {
            "sn": device.get("sn", "unknown"),
            "is_device_bind_organization": True,
            "organization_id": "test-org",
            "organization_name": "Test Organisation",
            "device_callsign": device.get("sn", "unknown"),
        }
        for device in devices
    ]
    assert reply["data"]["output"]["bind_status"] == expected


def test_organization_get_reply(dock, client):
    send_request(
        dock, client, "airport_organization_get",
        {"device_binding_code": "FAKE_TEST_CODE"},
    )
    reply = read_reply(client)

    assert reply["method"] == "airport_organization_get"
    assert reply["data"] == {
        "result": 0,
        "output": {"organization_name": "Test Organisation"},
    }


@pytest.mark.parametrize("devices", [[], [{"sn": "TEST_DRONE"}]])
def test_organization_bind_reply(dock, client, devices):
    send_request(
        dock, client, "airport_organization_bind",
        {"bind_devices": devices},
    )
    reply = read_reply(client)

    assert reply["method"] == "airport_organization_bind"
    assert reply["data"] == {
        "result": 0,
        "output": {"err_infos": []},
    }


@pytest.mark.parametrize("payload", [
    b"not JSON",
    b'{"method":',
    b"",
    b"\xff",
])
def test_invalid_payload_is_ignored(dock, client, payload):
    message = SimpleNamespace(
        topic="thing/product/TEST_DOCK/requests",
        payload=payload,
    )
    dock.on_message(client, None, message)

    client.publish.assert_not_called()


@pytest.mark.parametrize("method", ["unknown_method", ""])
def test_unknown_method_is_ignored(dock, client, method):
    send_request(dock, client, method, {})

    client.publish.assert_not_called()


def test_short_topic_is_ignored(dock, client):
    message = SimpleNamespace(
        topic="invalid",
        payload=b'{"method":"airport_bind_status"}',
    )
    dock.on_message(client, None, message)

    client.publish.assert_not_called()


def test_handler_error_is_logged(dock, client, monkeypatch, caplog):
    """A failed non-config handler should be caught and logged."""
    broken_handler = Mock(side_effect=ValueError("Test handler failure"))
    monkeypatch.setitem(
        dock.HANDLERS, "airport_bind_status", broken_handler
    )

    with caplog.at_level(logging.ERROR):
        send_request(dock, client, "airport_bind_status", {})

    broken_handler.assert_called_once()
    client.publish.assert_not_called()
    assert "Test handler failure" in caplog.text