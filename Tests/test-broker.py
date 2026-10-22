"""Broker integration test. Requires a running, reachable MQTT broker."""

import os
import threading
import uuid

import paho.mqtt.client as mqtt


def test_broker_delivers_message():
    """Check connection, subscription, and delivery between two clients."""
    host = os.getenv("TEST_BROKER_HOST", "localhost")
    port = int(os.getenv("TEST_BROKER_PORT", "1883"))

    # A unique topic prevents interference with other tests.
    topic = f"tests/fpv/{uuid.uuid4().hex}"
    payload = "broker connectivity test"

    subscribed = threading.Event()
    received = threading.Event()
    messages = []
    subscription_errors = []

    subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    publisher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_subscribe(client, userdata, mid, reason_codes, properties):
        if any(code.is_failure for code in reason_codes):
            subscription_errors.append("Broker rejected the subscription.")
        subscribed.set()

    def on_message(client, userdata, message):
        messages.append((message.topic, message.payload))
        received.set()

    subscriber.on_subscribe = on_subscribe
    subscriber.on_message = on_message

    try:
        # Start the receiving client first.
        subscriber.connect(host, port, keepalive=30)
        subscriber.loop_start()

        result, _ = subscriber.subscribe(topic, qos=0)
        assert result == mqtt.MQTT_ERR_SUCCESS, (
            "Could not send the subscription request."
        )
        assert subscribed.wait(10), (
            "No subscription acknowledgement within 10 seconds."
        )
        assert not subscription_errors, subscription_errors[0]

        # Send a non-retained message from a separate client.
        publisher.connect(host, port, keepalive=30)
        publisher.loop_start()

        result = publisher.publish(
            topic, payload, qos=0, retain=False
        )
        assert result.rc == mqtt.MQTT_ERR_SUCCESS, (
            "Could not send the test message."
        )

        assert received.wait(10), (
            "Subscriber did not receive the message within 10 seconds."
        )
        assert messages[0] == (topic, payload.encode("utf-8"))

    finally:
        # Always release both clients, even if the test fails.
        publisher.disconnect()
        subscriber.disconnect()
        publisher.loop_stop()
        subscriber.loop_stop()